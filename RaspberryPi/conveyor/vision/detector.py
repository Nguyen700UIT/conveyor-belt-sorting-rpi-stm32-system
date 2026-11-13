"""Ultralytics object detection using local PyTorch or NCNN weights."""

import math
from pathlib import Path

from ..events import Detection


class Detector:
    def __init__(self, model_path, confidence=0.4, imgsz=640):
        path = Path(model_path).resolve()
        is_ncnn = path.name.endswith("_ncnn_model")
        if not is_ncnn and path.suffix.lower() != ".pt":
            raise ValueError("Detector requires a local .pt file or *_ncnn_model directory")
        if is_ncnn:
            if not path.is_dir():
                raise FileNotFoundError(f"NCNN model directory not found: {path}")
            params = list(path.glob("*.param"))
            if len(params) != 1:
                raise ValueError("NCNN directory must contain exactly one .param file")
            for required in (params[0].with_suffix(".bin"), path / "metadata.yaml"):
                if not required.is_file():
                    raise FileNotFoundError(f"NCNN model file not found: {required}")
        elif not path.is_file():
            raise FileNotFoundError(f"Model weights not found: {path}")
        if type(confidence) not in (int, float):
            raise ValueError("confidence must be a number")
        if not 0 < confidence < 1 or not math.isfinite(confidence):
            raise ValueError("confidence must be finite and between 0 and 1")
        if type(imgsz) is not int or imgsz <= 0:
            raise ValueError("imgsz must be a positive integer")
        if is_ncnn:
            import yaml

            with (path / "metadata.yaml").open(encoding="utf-8") as file:
                metadata = yaml.safe_load(file)
            if not isinstance(metadata, dict) or metadata.get("task") != "detect":
                raise ValueError("NCNN metadata must describe an object detection model")
            if metadata.get("imgsz") != [imgsz, imgsz]:
                raise ValueError("detector.imgsz must match the square NCNN export size")

        # Imported only when a detector is explicitly created, never for PING.
        from ultralytics import YOLO

        try:
            if is_ncnn:
                model = YOLO(str(path), task="detect")
            else:
                model = YOLO(str(path))
            # Accessing names also initializes the exported-model backend.
            names = model.names
        except Exception as exc:
            raise ValueError(f"Cannot load model weights: {path}: {exc}") from exc
        if model.task != "detect":
            raise ValueError("Model must be trained for object detection")
        if not isinstance(names, dict):
            raise ValueError("Model class names must be a class-ID mapping")
        if len(names) != 3 or set(names.values()) != {"green", "riped", "damaged"}:
            raise ValueError("Model must have exactly green, riped and damaged classes")

        self.model = model
        self.names = dict(names)
        self.confidence = confidence
        self.imgsz = imgsz
        self.is_ncnn = is_ncnn

    def predict(self, frame, *, color_order):
        """Return detections; caller must identify the actual BGR/RGB channel order."""
        import numpy as np

        if not isinstance(frame, np.ndarray):
            raise ValueError("frame must be a NumPy array")
        if frame.dtype != np.uint8:
            raise ValueError("frame must have uint8 pixels")
        if frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("frame must have shape (height, width, 3)")
        if frame.shape[0] == 0 or frame.shape[1] == 0:
            raise ValueError("frame must not be empty")
        if color_order == "RGB":
            bgr_frame = np.ascontiguousarray(frame[:, :, ::-1])
        elif color_order == "BGR":
            bgr_frame = np.ascontiguousarray(frame)
        else:
            raise ValueError("color_order must be BGR or RGB")

        options = {"rect": False} if self.is_ncnn else {}
        results = self.model.predict(
            source=bgr_frame,
            device="cpu",
            conf=self.confidence,
            imgsz=self.imgsz,
            verbose=False,
            save=False,
            **options,
        )
        detections = []
        for box in results[0].boxes:
            coordinates = box.xyxy[0].tolist()
            class_id = int(box.cls.item())
            detection = Detection(
                xyxy=tuple(coordinates),
                class_id=class_id,
                label=self.names[class_id],
                confidence=float(box.conf.item()),
            )
            detections.append(detection)
        return detections
