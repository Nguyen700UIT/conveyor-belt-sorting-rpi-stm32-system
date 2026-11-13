"""Chia theo quả rồi tạo ảnh train để gán bounding box sau."""

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import random
import re
import shutil

from PIL import Image, ImageEnhance, ImageOps, ImageDraw


CLASSES = {"green": "green", "ripe": "riped", "damaged": "damaged"}
EXTENSIONS = {".jpg", ".jpeg", ".png"}
MANIFEST_FIELDS = (
    "split", "class", "group", "source", "output", "augmented",
    "brightness", "contrast", "source_sha256",
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def discover(source):
    """Tên fruitN (frame) là định danh quả; fruiti11 được hiểu là fruit11."""
    groups = defaultdict(list)
    seen_hashes = {}
    for folder, label in (*CLASSES.items(), ("background", "background")):
        directory = source / folder
        if not directory.is_dir():
            raise ValueError(f"Missing source directory: {directory}")
        images = sorted(path for path in directory.iterdir()
                        if path.is_file() and path.suffix.lower() in EXTENSIONS)
        if not images:
            raise ValueError(f"No images in {directory}")
        for path in images:
            if label == "background":
                group = "background-session-unknown"
            else:
                match = re.fullmatch(r"fruiti?(\d+)(?:\s*\((\d+)\))?", path.stem, re.IGNORECASE)
                if match is None:
                    raise ValueError(f"Cannot identify physical fruit from filename: {path.name}")
                group = f"fruit{int(match.group(1))}"
            digest = sha256(path)
            if digest in seen_hashes:
                raise ValueError(f"Exact duplicate: {path} and {seen_hashes[digest]}; review before splitting")
            seen_hashes[digest] = path
            with Image.open(path) as image:
                image.verify()
            groups[label, group].append((path, digest))
    return groups


def choose_splits(groups, seed):
    assignments = {}
    rng = random.Random(seed)
    for label in CLASSES.values():
        keys = sorted(key for key in groups if key[0] == label)
        if len(keys) < 3:
            raise ValueError(f"Need at least 3 independent fruits for {label}")
        rng.shuffle(keys)
        train_count = max(1, int(len(keys) * .7))
        val_count = max(1, round(len(keys) * .15))
        if train_count + val_count >= len(keys):
            train_count = len(keys) - val_count - 1
        for index, key in enumerate(keys):
            if index < train_count:
                split = "train"
            elif index < train_count + val_count:
                split = "val"
            else:
                split = "test"
            assignments[key] = split
    # Không chia ngẫu nhiên một chuỗi nền thành ba tập tương quan với nhau.
    assignments["background", "background-session-unknown"] = "train"
    return assignments


def augment_image(source, output, brightness, contrast):
    """Chỉ đổi sáng/tương phản nhẹ, giữ nguyên hình học và không chủ động đổi hue."""
    with Image.open(source) as image:
        transformed = ImageOps.exif_transpose(image).convert("RGB")
        transformed = ImageEnhance.Brightness(transformed).enhance(brightness)
        transformed = ImageEnhance.Contrast(transformed).enhance(contrast)
        transformed.save(output, format="JPEG", quality=95)


def create_preview(output, rows):
    examples = []
    for label in ("green", "riped"):
        augmented = next((row for row in rows if row["class"] == label and row["augmented"]), None)
        if augmented is None:
            continue
        original = next(row for row in rows if row["source"] == augmented["source"] and not row["augmented"])
        examples.extend((original, augmented))
    if not examples:
        return
    canvas = Image.new("RGB", (720, 240 * (len(examples) // 2)), "#16202b")
    draw = ImageDraw.Draw(canvas)
    for index, row in enumerate(examples):
        x, y = (index % 2) * 360, (index // 2) * 240
        with Image.open(output / row["output"]) as image:
            thumbnail = ImageOps.contain(ImageOps.exif_transpose(image).convert("RGB"), (360, 202))
            canvas.paste(thumbnail, (x, y + 32))
        caption = f"{row['class']} / {'augmented' if row['augmented'] else 'original'}"
        if row["augmented"]:
            caption += f" B={row['brightness']:.2f} C={row['contrast']:.2f}"
        draw.text((x + 8, y + 8), caption, fill="white")
    canvas.save(output / "preview.jpg", quality=95)


def prepare(source, output, seed=42):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_dir():
        raise ValueError("Source must be an existing directory")
    if output == source or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError("Output must be separate from the original dataset")
    if output.exists():
        raise FileExistsError(f"Output already exists; choose a new directory: {output}")
    groups = discover(source)
    assignments = choose_splits(groups, seed)
    train_counts = Counter()
    for key, images in groups.items():
        if assignments[key] == "train" and key[0] != "background":
            train_counts[key[0]] += len(images)
    target = max(train_counts.values())
    rows = []
    training = defaultdict(list)
    output.mkdir(parents=True, exist_ok=False)
    for (label, group), images in sorted(groups.items()):
        split = assignments[label, group]
        directory = output / split / label
        directory.mkdir(parents=True, exist_ok=True)
        for index, (path, digest) in enumerate(images, 1):
            destination = directory / f"{label}__{group}__{index:03d}{path.suffix.lower()}"
            shutil.copy2(path, destination)
            row = {"split": split, "class": label, "group": group,
                   "source": path.relative_to(source).as_posix(),
                   "output": destination.relative_to(output).as_posix(),
                   "augmented": False, "brightness": 1.0, "contrast": 1.0,
                   "source_sha256": digest}
            rows.append(row)
            if split == "train" and label != "background":
                training[label].append(row)
    rng = random.Random(seed)
    for label in sorted(training):
        originals = list(training[label])
        rng.shuffle(originals)
        source_uses = Counter()
        for index in range(target - len(originals)):
            # Lần lượt qua mọi ảnh trước khi lặp, tránh dồn vào một ảnh duy nhất.
            original = originals[index % len(originals)]
            source_uses[original["source"]] += 1
            source_output = Path(original["output"])
            name = f"{source_output.stem}__aug{source_uses[original['source']]:03d}.jpg"
            destination = source_output.with_name(name)
            brightness = round(rng.uniform(.9, 1.1), 6)
            contrast = round(rng.uniform(.9, 1.1), 6)
            # Tránh bản gần như không đổi cả hai tham số.
            if abs(brightness - 1) + abs(contrast - 1) < .04:
                brightness = .94 if brightness < 1 else 1.06
            augment_image(source / original["source"], output / destination, brightness, contrast)
            rows.append({**original, "output": destination.as_posix(), "augmented": True,
                         "brightness": brightness, "contrast": contrast})
    with (output / "manifest.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    counts = {}
    for split in ("train", "val", "test"):
        counts[split] = {}
        for label in (*CLASSES.values(), "background"):
            selected = [row for row in rows if row["split"] == split and row["class"] == label]
            counts[split][label] = {
                "originals": sum(not row["augmented"] for row in selected),
                "augmented": sum(row["augmented"] for row in selected),
                "total": len(selected),
                "groups": sorted({row["group"] for row in selected}),
            }
    report = {"seed": seed, "target_train_images_per_fruit_class": target,
              "requires_bounding_box_annotation": True,
              "group_assumption": "Each fruitN denotes one physical fruit within its class; fruiti11 is fruit11",
              "background_policy": "All background images kept in train: independent sessions are unknown",
              "transforms": {"brightness": [.9, 1.1], "contrast": [.9, 1.1],
                             "hue_shift": False, "geometric_transforms": False},
              "counts": counts}
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "README.txt").write_text(
        "Images are NOT a ready-to-train YOLO detection dataset.\n"
        "Annotate bounding boxes before training. Names: green, riped, damaged.\n"
        "Background is a negative image, not a fourth object class.\n"
        "Import train, val and test separately; preserve these splits on export.\n"
        "Do not randomly re-split or place variants of one fruit in different splits.\n"
        "Do not import manifest.csv, report.json or preview.jpg as training images.\n"
        "Only train has augmented images; val/test are byte-for-byte original copies.\n"
        "Background-only false positives need an independent background evaluation set.\n",
        encoding="utf-8",
    )
    create_preview(output, rows)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    report = prepare(args.source, args.output, args.seed)
    for split, classes in report["counts"].items():
        print(split, {label: values["total"] for label, values in classes.items()})
    print(f"Output: {args.output.resolve()}; annotate bounding boxes before training.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
