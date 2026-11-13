"""Theo dõi quả bằng khoảng cách giữa tâm bounding box của các khung hình."""

import math

from ..events import Detection, TrackedDetection


class Tracker:
    """Ghép một-một theo khoảng cách gần nhất, không phụ thuộc nhãn quả.

    Phù hợp khi các quả cách nhau và ít che khuất. Hai quả sát nhau hoặc mất
    nhận diện lâu có thể bị đổi ID; cần kiểm chứng trước khi dùng để gửi UART.
    Mỗi instance được dùng bởi một luồng trong một lần chạy pipeline.
    """

    def __init__(self, max_distance_px=80.0, max_age_seconds=0.5):
        # Giá trị mặc định chỉ để thử, cần hiệu chỉnh theo camera và tốc độ băng tải.
        for name, value in (
            ("max_distance_px", max_distance_px),
            ("max_age_seconds", max_age_seconds),
        ):
            if type(value) not in (int, float):
                raise ValueError(f"{name} must be a number")
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")

        self.max_distance_px = max_distance_px
        self.max_age_seconds = max_age_seconds
        self._tracks: dict[int, TrackedDetection] = {}
        self._next_id = 1
        self._last_observed_at = None

    @staticmethod
    def _center(detection: Detection) -> tuple[float, float]:
        x1, y1, x2, y2 = detection.xyxy
        for coordinate in (x1, y1, x2, y2):
            if not math.isfinite(coordinate):
                raise ValueError("Bounding box coordinates must be finite")
        if x2 <= x1 or y2 <= y1:
            raise ValueError("Bounding box must have positive width and height")
        return (x1 / 2 + x2 / 2, y1 / 2 + y2 / 2)

    def update(
        self, detections: list[Detection], observed_at: float
    ) -> list[TrackedDetection]:
        """Nhận một khung hình, trả các quả quan sát được theo thứ tự đầu vào.

        observed_at là thời gian chụp bằng monotonic, tăng qua mỗi khung hình.
        Gọi cả khi detections rỗng để loại ID hết hạn. ID chưa hết hạn được giữ
        nội bộ nhưng không được trả như một quan sát mới khi mất nhận diện.
        """
        if type(observed_at) not in (int, float):
            raise ValueError("observed_at must be a number")
        if not math.isfinite(observed_at):
            raise ValueError("observed_at must be finite")
        if self._last_observed_at is not None:
            if observed_at <= self._last_observed_at:
                raise ValueError("Frame timestamps must strictly increase")

        # Kiểm tra toàn bộ box trước khi thay đổi trạng thái tracker.
        centers = []
        for detection in detections:
            centers.append(self._center(detection))

        active_tracks = {}
        for track_id, track in self._tracks.items():
            age = observed_at - track.observed_at
            if age <= self.max_age_seconds:
                active_tracks[track_id] = track

        # Xét mọi cặp còn trong ngưỡng, ưu tiên khoảng cách nhỏ nhất toàn cục.
        candidates = []
        for track_id, track in active_tracks.items():
            old_x, old_y = self._center(track.detection)
            for index, (new_x, new_y) in enumerate(centers):
                distance = math.hypot(new_x - old_x, new_y - old_y)
                if distance <= self.max_distance_px:
                    candidates.append((distance, track_id, index))
        candidates.sort()

        matched_tracks = set()
        assignments = {}
        for distance, track_id, index in candidates:
            if track_id in matched_tracks or index in assignments:
                continue
            matched_tracks.add(track_id)
            assignments[index] = track_id

        observations = []
        for index, detection in enumerate(detections):
            if index in assignments:
                track_id = assignments[index]
            else:
                # Không tái sử dụng ID hết hạn trong cùng lần chạy.
                track_id = self._next_id
                self._next_id += 1
            observation = TrackedDetection(
                track_id=track_id,
                detection=detection,
                observed_at=observed_at,
            )
            active_tracks[track_id] = observation
            observations.append(observation)

        self._tracks = active_tracks
        self._last_observed_at = observed_at
        return observations
