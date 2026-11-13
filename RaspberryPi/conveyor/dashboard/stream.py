"""Một worker encode JPEG mới nhất, chỉ làm việc khi có người xem."""

from io import BytesIO
from pathlib import Path
import threading
import time

from .broadcast import Broadcast

LABELS = {"green": "Tắc sống", "riped": "Tắc chín", "damaged": "Tắc hư"}
COLORS = {"green": "#39d98a", "riped": "#ffcb47", "damaged": "#ff6978"}


class JpegEncoder:
    def __init__(self, width, quality, font_path):
        self.width = width
        self.quality = quality
        self.font_path = font_path
        self._font = None

    def __call__(self, frame, detections, crossing, color_order):
        from PIL import Image, ImageDraw, ImageFont

        if self._font is None:
            if not Path(self.font_path).is_file():
                raise OSError(f"Vietnamese font not found: {self.font_path}")
            self._font = ImageFont.truetype(self.font_path, 15)
        rgb = frame[..., ::-1] if color_order == "BGR" else frame
        image = Image.fromarray(rgb)
        original_width, original_height = image.size
        scale = min(1, self.width / original_width)
        if scale < 1:
            image = image.resize((round(original_width * scale), round(original_height * scale)))
        draw = ImageDraw.Draw(image)
        axis, position = crossing
        if axis == "x":
            coordinate = round(position * image.width)
            line = (coordinate, 0, coordinate, image.height)
        else:
            coordinate = round(position * image.height)
            line = (0, coordinate, image.width, coordinate)
        draw.line(line, fill="#59c8ff", width=2)
        for detection in detections:
            box = tuple(round(value * scale) for value in detection.xyxy)
            color = COLORS[detection.label]
            draw.rectangle(box, outline=color, width=2)
            text = f"{LABELS[detection.label]} {detection.confidence:.0%}"
            x, y = max(0, box[0]), max(0, box[1] - 23)
            bounds = draw.textbbox((x, y), text, font=self._font)
            draw.rectangle(bounds, fill="#101b2b")
            draw.text((x, y), text, font=self._font, fill=color)
        output = BytesIO()
        image.save(output, format="JPEG", quality=self.quality)
        return output.getvalue()


class CameraStream:
    def __init__(self, settings, on_change, encoder=None):
        self.frames = Broadcast()
        self._changed = on_change
        self._encode = encoder or JpegEncoder(settings["width"], settings["quality"], settings["font"])
        self._interval = 1 / settings["fps"]
        self._condition = threading.Condition()
        self._viewers = 0
        self._pending = None
        self._jpeg = None
        self._version = 0
        self._last_encoded = 0.0
        self._active = False
        self._stalled = False
        self._closed = False
        self._message = "Camera chưa hoạt động"
        self._thread = threading.Thread(target=self._run, name="camera-jpeg", daemon=True)
        self._thread.start()

    def status(self):
        with self._condition:
            return {"active": self._active and not self._stalled,
                    "message": "Camera chưa có frame mới" if self._stalled else self._message}

    def set_active(self, active, message):
        with self._condition:
            self._active = active
            self._stalled = False
            self._message = message
            if not active:
                self._pending = None
                self._jpeg = None
            self._condition.notify_all()
        self.frames.notify()
        self._changed()

    def mark_stalled(self):
        with self._condition:
            self._stalled = True
            self._jpeg = None
        self.frames.notify()
        self._changed()

    def add_viewer(self):
        with self._condition:
            if not self._active or self._closed:
                return False
            self._viewers += 1
            self._condition.notify_all()
            return True

    def remove_viewer(self):
        with self._condition:
            self._viewers -= 1
            if self._viewers == 0:
                self._pending = None
                self._jpeg = None
            self._condition.notify_all()

    def submit(self, frame, detections, crossing, color_order):
        recovered = False
        with self._condition:
            if self._stalled:
                self._stalled = False
                recovered = True
        if recovered:
            self._changed()
        with self._condition:
            if not self._active or not self._viewers or self._closed:
                return
            # Camera.read trả buffer độc lập; chỉ worker này dùng bản sao để vẽ.
            self._pending = (frame.copy(), tuple(detections), crossing, color_order)
            self._condition.notify()

    def latest(self):
        with self._condition:
            return self._version, self._jpeg, self._active and not self._stalled

    def _run(self):
        while True:
            with self._condition:
                self._condition.wait_for(lambda: self._closed or self._pending is not None)
                if self._closed:
                    return
                delay = self._last_encoded + self._interval - time.monotonic()
                if delay > 0:
                    self._condition.wait(timeout=delay)
                    continue
                item = self._pending
                self._pending = None
            try:
                jpeg = self._encode(*item)
            except Exception as exc:
                self.set_active(False, f"Lỗi stream: {exc}")
                continue
            with self._condition:
                self._last_encoded = time.monotonic()
                if not self._active or not self._viewers or self._closed:
                    continue
                self._jpeg = jpeg
                self._version += 1
                self._condition.notify_all()
            self.frames.notify()

    def close(self):
        self.set_active(False, "Camera đã dừng")
        with self._condition:
            self._closed = True
            self._condition.notify_all()
        self.frames.close()
        self._thread.join(timeout=5)
