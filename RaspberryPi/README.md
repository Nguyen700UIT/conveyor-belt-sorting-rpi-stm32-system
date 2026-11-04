# Pipeline Raspberry Pi

Package `conveyor` dành cho chương trình vận hành. Hiện đã có transport UART,
protocol và lệnh PING. Camera, tracking, sender và thống kê là các bước bạn sẽ
tự viết tiếp; chưa có chương trình phân loại toàn pipeline hoặc dashboard.
`DataCollector/` và `ModelTest/` tiếp tục chạy riêng theo README của từng công cụ.

## Cài đặt và chạy phần hiện có

Từ thư mục `RaspberryPi` trên Pi:

```sh
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m conveyor --help
.venv/bin/python -m conveyor --ping --port /dev/ttyUSB0
.venv/bin/python -m unittest discover -s tests -v
```

PING chỉ kiểm tra đường truyền, không Start motor hoặc gạt servo. Kết quả thành
công là `STM32 PONG`; lỗi kết nối/timeout trả exit code 1. Chạy không có tham số
chỉ hiện trợ giúp. Firmware hiện điều khiển Start/Stop/Reset qua debugger.
PONG không chứng minh hệ thống đang RUNNING.

`requirements.txt` hiện chỉ chứa pyserial. Chưa cài thêm bộ inference vào package;
khi bắt đầu viết detector, dùng hướng dẫn ONNX/Picamera2 trong `ModelTest/README.md`.
`config.example.toml` mô tả cấu hình dự kiến, CLI hiện nhận cổng qua `--port`.
Sau này sao chép thành `config.toml` khi viết loader. Đường dẫn output dùng thư mục
`runtime/`. Cấu hình cá nhân, output và SQLite không được commit.
`ROBOFLOW_API_KEY` lấy từ biến môi trường, không đặt trong TOML.

## Cấu trúc hiện có và nơi thêm code

```text
RaspberryPi/
├── conveyor/
│   ├── __init__.py
│   ├── __main__.py           # điểm chạy python -m conveyor
│   ├── app.py                # hiện chỉ điều phối kiểm tra UART
│   └── communication/
│       ├── __init__.py
│       ├── serial_link.py    # UartLink: byte I/O
│       └── protocol.py       # frame, CRC, ACK, retry, SEQ
├── tests/
│   ├── test_app.py
│   ├── test_protocol.py
│   └── test_serial_link.py
├── config.example.toml
├── requirements.txt
├── README.md
├── DataCollector/
└── ModelTest/
```

Không tạo file rỗng cho chức năng chưa viết. Khi đến bước tương ứng, thêm:

| Module | Trách nhiệm |
|---|---|
| `conveyor/config.py` | Đọc/kiểm tra TOML, thông báo cấu hình sai trước khi mở thiết bị |
| `conveyor/events.py` | Kiểu dữ liệu detection, track và sự kiện vượt vạch |
| `conveyor/vision/camera.py` | Ảnh và thời gian chụp monotonic |
| `conveyor/vision/detector.py` | Tải model một lần, trả box/nhãn/confidence |
| `conveyor/vision/tracker.py` | Duy trì ID qua các frame |
| `conveyor/vision/crossing.py` | Phát một sự kiện/ID khi vượt vạch đúng chiều |
| `conveyor/communication/sender.py` | Một luồng gửi tuần tự, chờ queue có giới hạn |
| `conveyor/statistics/store.py` | SQLite: sự kiện, thời gian thực và kết quả ACK/lỗi |

Thêm `__init__.py` vào `vision/` và `statistics/` khi tạo các package đó.
`app.py` sẽ nối camera → detector → tracker → crossing → queue → sender → STM32;
thống kê được gọi từ tầng điều phối, không ghép vào transport/protocol.

## UART hiện có

Code cũ đã chuyển vị trí:

- `UartLink/uart_link.py` → `conveyor/communication/serial_link.py`.
- `UartLink/protocol.py` → `conveyor/communication/protocol.py`.
- `UartLink/requirements.txt` → `RaspberryPi/requirements.txt`.

Import mới là `conveyor.communication.serial_link.UartLink` và
`conveyor.communication.protocol.UartProtocol`. Không còn thư mục `UartLink/`.

`UartLink` mở CP2102 ở 115200 baud, 8N1 theo mặc định. `open/close` quản lý cổng;
`send` ghi byte; `receive` đọc có timeout. Context manager đóng cổng khi thoát.
Transport không giải mã giao thức.

| Chiều | Frame 4 byte |
|---|---|
| Pi → STM32 | `0xA5, SEQ, CMD, CRC8` |
| STM32 → Pi | `0x5A, SEQ, STATUS, CRC8` |

CRC-8/ATM: poly `0x07`, init `0`, không reflect, xorout `0`; tính trên ba byte đầu.
CMD: PING `1`, UNRIPE `2`, RIPE `3`, SPOILED `4`.
STATUS: PONG `0`, ACK `1`, FULL `2`, NOT_READY `3`, BAD_CMD `4`.

`exchange(command)` giữ tối đa một giao dịch đang chờ. Retry cùng SEQ/CMD;
SEQ tăng modulo 256 sau ACK/PONG. ACK chỉ xác nhận STM32 chấp nhận sản phẩm,
không xác nhận gạt thành công. FULL/NOT_READY có thể retry trong số lượt cấu hình.
Khi hết lượt với FULL/NOT_READY, ứng dụng nhận status cuối và phải xử lý nó,
không coi sản phẩm là đã nhận. BAD_CMD phải báo lỗi cấu hình.

Nếu timeout hoặc lỗi transport khiến kết quả không rõ, protocol chặn giao dịch mới
bằng `UncertainTransaction`. Không tạo đối tượng protocol mới để gửi lại sản phẩm:
có thể thêm trùng. Chống trùng trên STM32 chỉ nhớ request gần nhất trong RAM và
không tồn tại qua reset; cần quy trình khôi phục riêng trước khi vận hành tự động.

## Lộ trình tự viết

1. Chạy kiểm tra UART và PING. Dùng fake transport trong test, không cần cắm Pi.
2. Viết `config.py`, `events.py`, rồi camera/detector. Inference hoạt động khi
   pipeline chạy, không phụ thuộc người mở trang xem như script ModelTest.
3. Viết tracker và crossing. Ánh xạ nhãn model `green` → UNRIPE,
   `riped` → RIPE, `damaged` → SPOILED. Nhãn lạ phải báo lỗi trước khi gửi lệnh.
   Test nhiều frame cùng quả, qua vạch đúng/ngược chiều và hai quả liên tiếp.
4. Viết sender với queue giới hạn và một worker chờ blocking, không busy-wait.
   FULL/NOT_READY hết retry, queue đầy hoặc kết quả không rõ phải báo lỗi về app
   và ngừng nhận sản phẩm mới. Không gửi bù quả đã qua vị trí gạt.
5. Viết SQLite store và test với database tạm. Lưu riêng sự kiện vượt vạch,
   STM32 đã nhận và lỗi; không gọi ACK là sản lượng đã gạt. Dùng thời gian UTC
   cho lưu trữ, tổng hợp ngày theo Asia/Bangkok; monotonic chỉ tính khoảng thời gian.
6. Nối app, kiểm thử motor dừng, đo độ trễ camera/UART rồi hiệu chỉnh thời gian gạt.
   Thêm test sender/store khi bắt đầu viết chúng.

Camera bị lỗi, queue đầy hoặc lỗi UART không tự dừng motor STM32: giao thức
hiện chưa có lệnh Stop/heartbeat. Đây là phần phải bổ sung trước vận hành tự động.
Preview và dashboard để bước sau; không đặt logic phân loại trong HTTP handler.
