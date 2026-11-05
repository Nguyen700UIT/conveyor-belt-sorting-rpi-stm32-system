"""Lấy frame BGR và thời gian cảm biến từ camera Picamera2."""


class Camera:
    # Picamera2 RGB888 trả mảng có thứ tự byte B,G,R.
    color_order = "BGR"

    def __init__(self, width, height, fps):
        self.width = width
        self.height = height
        self.fps = fps
        self._camera = None

    def start(self):
        """Cấu hình và mở camera; chỉ import Picamera2 khi thực sự sử dụng."""
        if self._camera is not None:
            raise RuntimeError("Camera is already started")
        from picamera2 import Picamera2

        camera = Picamera2()
        try:
            camera.configure(camera.create_video_configuration(
                main={"size": (self.width, self.height), "format": "RGB888"},
                controls={
                    "FrameRate": self.fps,
                    "AfMode": 0,  # Manual: giữ nguyên vị trí lấy nét.
                    "LensPosition": 10.0,
                    "AeEnable": False,
                    "ExposureTime": 2000,  # Shutter, đơn vị microsecond (2 ms).
                    "AnalogueGain": 2.0,
                },
                buffer_count=4,
                queue=False,
            ))
            camera.start()
        except BaseException:
            # Đóng cả khi khởi động lỗi hoặc người dùng nhấn Ctrl+C.
            camera.close()
            raise
        self._camera = camera

    def read(self):
        """Chờ ảnh, trả (frame BGR độc lập với buffer, timestamp cảm biến giây)."""
        if self._camera is None:
            raise RuntimeError("Camera is not started")
        request = self._camera.capture_request()
        try:
            metadata = request.get_metadata()
            timestamp = metadata.get("SensorTimestamp")
            if type(timestamp) is not int or timestamp <= 0:
                raise ValueError("Camera metadata is missing a valid SensorTimestamp")
            frame = request.make_array("main").copy()
            return frame, timestamp / 1_000_000_000
        finally:
            request.release()

    def close(self):
        """Đóng camera và trả tài nguyên; có thể gọi nhiều lần."""
        if self._camera is not None:
            self._camera.close()
            self._camera = None
