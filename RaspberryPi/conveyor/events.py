"""Dữ liệu bất biến dùng chung cho nhận diện, theo dõi và gửi lệnh phân loại."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Detection:
    """Một kết quả nhận diện trong một ảnh, chưa xác định cùng một quả qua nhiều ảnh."""

    # Tọa độ pixel trên ảnh gốc, trước khi đổi kích thước để suy luận.
    xyxy: tuple[float, float, float, float]
    class_id: int
    label: str
    confidence: float


@dataclass(frozen=True)
class TrackedDetection:
    """Kết quả nhận diện được bộ theo dõi gắn với một quả.

    track_id là ID duy nhất trong một lần chạy pipeline, khác với SEQ của UART.
    observed_at là thời gian của khung hình nguồn, tính bằng giây theo đồng hồ
    đơn điệu (monotonic).
    """

    track_id: int
    detection: Detection
    observed_at: float


@dataclass(frozen=True)
class CrossingEvent:
    """Sự kiện lần đầu xác nhận một quả vượt vạch quyết định theo chiều cho phép.

    Bộ xử lý vượt vạch phát tối đa một sự kiện cho mỗi track_id trong một lần chạy.
    label/confidence lưu quyết định tại lúc vượt vạch, không đổi theo ảnh về sau.
    crossed_at là thời gian của khung hình xác nhận, tính bằng giây theo đồng hồ
    đơn điệu; đây là thời điểm vượt vạch ước tính, không phải thời điểm gửi UART.
    """

    track_id: int
    label: str
    confidence: float
    crossed_at: float
