"""Một luồng gửi sự kiện phân loại qua UART, chờ hàng đợi bằng Condition."""

from collections import deque
import threading

from ..events import CrossingEvent
from .protocol import Command, Status


class SenderError(Exception):
    """Sender đã dừng nhận sản phẩm mới hoặc STM32 không chấp nhận lệnh."""


class Sender:
    """Dùng độc quyền một UartProtocol trong một lần chạy pipeline.

    on_result(event, response, error) chạy trong luồng gửi, phải ngắn và an toàn
    luồng. ACK chỉ nghĩa là STM32 đã nhận, không xác nhận gạt thành công.
    Khi lỗi, tầng điều phối chờ failure hoặc bắt lỗi submit để dừng nhận quả.
    Sender không có lệnh dừng motor và không tự khởi động lại sau lỗi.
    """

    def __init__(self, protocol, on_result, queue_capacity=16):
        if type(queue_capacity) is not int or queue_capacity <= 0:
            raise ValueError("queue_capacity must be a positive integer")
        if not callable(on_result):
            raise ValueError("on_result must be callable")

        self._protocol = protocol
        self._on_result = on_result #Callback
        self._queue_capacity = queue_capacity
        self._queue: deque[CrossingEvent] = deque()
        self._condition = threading.Condition()
        self._thread = None
        self._stopping = False
        self._error = None
        # Có thể chờ bằng failure.wait(); không cần vòng polling kiểm tra lỗi.
        self.failure = threading.Event()

    @property
    def error(self):
        """Lỗi đầu tiên làm sender dừng nhận; None nếu chưa có lỗi."""
        with self._condition:
            return self._error

    @property
    def pending_events(self) -> tuple[CrossingEvent, ...]:
        """Bản chụp sự kiện chưa gửi, không gồm giao dịch đang thực hiện."""
        with self._condition:
            return tuple(self._queue)

    def start(self):
        """Khởi động đúng một lần; không mở hoặc đóng cổng serial ở đây."""
        with self._condition:
            if self._thread is not None or self._stopping:
                raise SenderError("Sender cannot be started again")
            self._thread = threading.Thread(target=self._run, name="uart-sender")
            self._thread.start()

    def submit(self, event: CrossingEvent):
        """Đưa sự kiện vào hàng đợi ngay, không chờ UART.

        Giới hạn chỉ tính các sự kiện đang chờ, ngoài một giao dịch đang gửi.
        Nếu đầy, sự kiện mới không được nhận; caller phải giữ và ghi nhận lỗi.
        """
        if not isinstance(event, CrossingEvent):
            raise ValueError("event must be a CrossingEvent")
        if event.label not in ("green", "riped", "damaged"):
            raise ValueError("Unknown product label")

        with self._condition:
            if self._error is not None:
                raise SenderError("Sender failed; new events are blocked") from self._error
            if self._thread is None or self._stopping:
                raise SenderError("Sender is not accepting events")
            if len(self._queue) >= self._queue_capacity:
                error = SenderError("Sender queue is full; stop accepting products")
                self._set_error(error)
                raise error
            self._queue.append(event)
            self._condition.notify() #Wake up sender thread

    def stop(self):
        """Chờ giao dịch hiện tại và callback xong, giữ nguyên sự kiện chưa gửi.

        Tầng điều phối phải gọi trước khi đóng UART. Không gửi nốt hàng đợi vì
        các lệnh gạt có thể đã trễ. Không hủy ngang một giao dịch UART đang chạy.
        """
        with self._condition:
            self._stopping = True
            self._condition.notify_all()
            thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join()

    def _set_error(self, error):
        # Caller đang giữ _condition; giữ lỗi đầu tiên làm nguyên nhân chính.
        if self._error is None:
            self._error = error
        self.failure.set()
        self._condition.notify_all()

    def _run(self):
        commands = {
            "green": Command.UNRIPE,
            "riped": Command.RIPE,
            "damaged": Command.SPOILED,
        }
        while True:
            with self._condition:
                self._condition.wait_for(
                    lambda: self._queue or self._stopping or self._error is not None
                )
                if self._stopping or self._error is not None:
                    return
                # Lấy khỏi hàng đợi đánh dấu giao dịch này bắt đầu xử lý.
                event = self._queue.popleft()

            response = None
            error = None
            try:
                # Protocol tự retry cùng frame/SEQ; sender chỉ gọi một lần.
                response = self._protocol.exchange(commands[event.label])
                if response.status != Status.ACK:
                    error = SenderError(f"STM32 did not accept product: {response.status.name}")
            except Exception as exc:
                # Bao gồm timeout/lỗi truyền: kết quả có thể không xác định.
                error = exc

            if error is not None:
                with self._condition:
                    self._set_error(error)
            try:
                self._on_result(event, response, error)
            except Exception as exc:
                # Lỗi ghi nhận kết quả cũng phải báo lên tầng điều phối.
                with self._condition:
                    self._set_error(exc)
