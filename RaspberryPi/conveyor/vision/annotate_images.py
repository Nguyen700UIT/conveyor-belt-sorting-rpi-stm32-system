"""Run the local detector on an image directory and save annotated copies."""

import argparse
import json
from pathlib import Path
import time

from ..config import load_config
from .detector import Detector


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="TOML configuration file")
    parser.add_argument("--source", required=True, help="Input image directory")
    parser.add_argument("--output", required=True, help="New output directory")
    args = parser.parse_args(argv)

    source = Path(args.source).resolve()
    output = Path(args.output).resolve()
    if not source.is_dir():
        parser.error("--source must be an existing image directory")
    if output == source or output.is_relative_to(source):
        parser.error("--output must be outside the input directory")
    if output.exists():
        parser.error("--output must be a new directory to avoid overwriting results")

    paths = []
    for path in sorted(source.rglob("*")):
        if path.is_file() and path.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
            paths.append(path)
    if not paths:
        parser.error("No supported images in --source")

    config = load_config(args.config)
    settings = config["detector"]
    import cv2

    detector = Detector(settings["model"], settings["confidence"], settings["imgsz"])
    output.mkdir(parents=True)
    colors = {"green": (0, 200, 0), "riped": (0, 180, 255), "damaged": (0, 0, 255)}
    counts = {"green": 0, "riped": 0, "damaged": 0}
    records = []
    total_seconds = 0.0
    for number, path in enumerate(paths, start=1):
        frame = cv2.imread(str(path))
        if frame is None:
            raise ValueError(f"Cannot read image: {path}")
        started = time.perf_counter()
        detections = detector.predict(frame, color_order="BGR")
        elapsed = time.perf_counter() - started
        total_seconds += elapsed
        items = []
        for detection in detections:
            x1, y1, x2, y2 = detection.xyxy
            color = colors[detection.label]
            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
            label = f"{detection.label} {detection.confidence:.2f}"
            cv2.putText(frame, label, (int(x1), max(20, int(y1) - 7)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            counts[detection.label] += 1
            items.append({
                "xyxy": list(detection.xyxy), "class_id": detection.class_id,
                "label": detection.label, "confidence": detection.confidence,
            })
        destination = output / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(destination), frame):
            raise OSError(f"Cannot save image: {destination}")
        records.append({"image": str(path.relative_to(source)),
                        "inference_seconds": elapsed, "detections": items})
        print(f"[{number}/{len(paths)}] {path.name}: {len(items)} detections", flush=True)

    report = {
        "model": settings["model"], "confidence": settings["confidence"],
        "imgsz": settings["imgsz"], "device": "cpu", "images": len(paths),
        "detections_per_class": counts, "inference_seconds": total_seconds,
        "results": records,
    }
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved {len(paths)} annotated images and report.json to {output}")
    print(f"Detections: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
