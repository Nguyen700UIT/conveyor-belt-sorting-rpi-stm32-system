"""Phát sự kiện khi tâm quả vượt vạch quyết định đúng chiều."""

import math

from ..events import CrossingEvent, TrackedDetection


class CrossingDetector:
    """Mỗi ID phát tối đa một sự kiện trong vòng đời instance.

    Dùng cùng một instance với một Tracker trong suốt lần chạy pipeline.
    Lưu trạng thái các ID đến hết lần chạy để không phát lại khi quả quay về.
    Không phân biệt được cùng một quả nếu tracker cấp nhầm ID mới.
    """

    def __init__(self, axis="x", position=0.5, direction="increasing"):
        if axis not in ("x", "y"):
            raise ValueError("axis must be x or y")
        if type(position) not in (int, float):
            raise ValueError("position must be a number")
        if not math.isfinite(position) or not 0 < position < 1:
            raise ValueError("position must be finite and between 0 and 1")
        if direction not in ("increasing", "decreasing"):
            raise ValueError("direction must be increasing or decreasing")

        self.axis = axis
        self.position = position #Decision line
        self.direction = direction
        # Giá trị None đánh dấu ID đã phát sự kiện; số là vị trí lần trước.
        self._positions: dict[int, float | None] = {}
        self._last_observed_at = None

    def update(
        self,
        observations: list[TrackedDetection],
        *,
        frame_width: int,
        frame_height: int,
    ) -> list[CrossingEvent]:
        """Nhận các quan sát từ một ảnh, trả sự kiện theo thứ tự đầu vào.

        Kích thước phải là ảnh gốc chứa bounding box. Thời gian lấy từ ảnh xác
        nhận vượt vạch, không nội suy thời điểm giữa hai ảnh. Ảnh rỗng trả [].
        """
        for name, value in (
            ("frame_width", frame_width),
            ("frame_height", frame_height),
        ):
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")

        # Kiểm tra cả khung hình trước khi thay đổi trạng thái.
        seen_ids = set()
        positions = []
        frame_time = None
        for observation in observations:
            track_id = observation.track_id
            if type(track_id) is not int or track_id <= 0:
                raise ValueError("track_id must be a positive integer")
            if track_id in seen_ids:
                raise ValueError("Duplicate track_id in one frame")
            seen_ids.add(track_id)

            timestamp = observation.observed_at
            if type(timestamp) not in (int, float) or not math.isfinite(timestamp):
                raise ValueError("observed_at must be a finite number")
            if frame_time is None:
                frame_time = timestamp
            elif timestamp != frame_time:
                raise ValueError("Observations must belong to the same frame")
            if self._last_observed_at is not None:
                if timestamp <= self._last_observed_at:
                    raise ValueError("Frame timestamps must strictly increase")

            detection = observation.detection
            if detection.label not in ("green", "riped", "damaged"):
                raise ValueError("Unknown product label")
            if not math.isfinite(detection.confidence) or not 0 <= detection.confidence <= 1:
                raise ValueError("confidence must be finite and between 0 and 1")
            x1, y1, x2, y2 = detection.xyxy
            if not all(math.isfinite(value) for value in (x1, y1, x2, y2)):
                raise ValueError("Bounding box coordinates must be finite")
            if x2 <= x1 or y2 <= y1:
                raise ValueError("Bounding box must have positive width and height")
            if self.axis == "x":
                position = (x1 / 2 + x2 / 2) / frame_width
            else:
                position = (y1 / 2 + y2 / 2) / frame_height
            positions.append(position)

        events = []
        for observation, position in zip(observations, positions):
            track_id = observation.track_id
            if track_id not in self._positions:
                self._positions[track_id] = position
                continue

            previous = self._positions[track_id]
            if previous is None:
                continue
            if self.direction == "increasing":
                crossed = (previous < self.position) and (self.position <= position)
            else:
                crossed = (previous > self.position) and (self.position >= position)

            if crossed:
                event = CrossingEvent(
                    track_id=track_id,
                    label=observation.detection.label,
                    confidence=observation.detection.confidence,
                    crossed_at=observation.observed_at,
                )
                events.append(event)
                self._positions[track_id] = None
            else:
                self._positions[track_id] = position

        if frame_time is not None:
            self._last_observed_at = frame_time
        return events
