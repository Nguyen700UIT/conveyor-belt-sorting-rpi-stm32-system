# Pipeline Raspberry Pi

Package `conveyor` có pipeline Picamera2 → detector → tracker → crossing → sender
→ STM32. Detector Ultralytics dùng trọng số cục bộ. Thống kê và dashboard chưa
triển khai; pipeline cần kiểm chứng trên phần cứng và hiệu chỉnh thời gian gạt.
`DataCollector/` và `ModelTest/` tiếp tục chạy riêng theo README của từng công cụ.

## Cài đặt và chạy phần hiện có

Từ thư mục `RaspberryPi` trên Pi:

```sh
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m conveyor --help
.venv/bin/python -m conveyor --ping --port /dev/ttyUSB0
.venv/bin/python -m conveyor --ping --config config.toml
.venv/bin/python -m unittest discover -s tests -v
```

PING chỉ kiểm tra đường truyền, không Start motor hoặc gạt servo. Kết quả thành
công là `STM32 PONG`; lỗi kết nối/timeout trả exit code 1. Chạy không có tham số
chỉ hiện trợ giúp. Firmware hiện điều khiển Start/Stop/Reset qua debugger.
PONG không chứng minh hệ thống đang RUNNING.

Sau khi nạp firmware có lệnh START, có thể chuyển READY → RUNNING bằng:

```sh
.venv/bin/python -m conveyor --start --config conveyor/config.toml
```

START (`CMD=5`) trả ACK khi chuyển thành công hoặc đã RUNNING; trả NOT_READY
nếu đang INIT/STOPPED/FAULT. START chuyển FSM sang RUNNING và bật motor chiều
LPWM với duty thử 30%; không tự reset lỗi hoặc xóa hàng đợi. STOP/RESET vẫn dùng debugger. Không dùng
`--ping` và `--start` cùng lúc.

## Chạy pipeline Picamera2 và STM32 thật

Trên Raspberry Pi OS, dùng môi trường có quyền truy cập Picamera2 từ hệ thống:

```sh
sudo apt install python3-picamera2 python3-venv
# Chỉ tạo venv khi chưa có; venv cần được tạo với --system-site-packages.
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements-vision.txt
.venv/bin/python -m conveyor --run --config conveyor/config.toml
```

Nạp firmware mới hỗ trợ START và motor trước khi thử. Chép trọng số vào
`models/best.pt`, kiểm tra cổng serial và các bảng camera/detector/crossing/sender
trong TOML. Có thể dùng `--port /dev/ttyUSB0` để ghi đè cổng. Các chế độ
`--run`, `--ping`, `--start` loại trừ nhau; `--run` tự gửi PING rồi START,
không cần chạy `--start` riêng.

Chương trình tải model một lần, mở camera và warmup trên ảnh thật trước START.
`vision/camera.py` quản lý Picamera2 qua `Camera.start()`, `read()` và `close()`;
`app.py` nhận `(frame, timestamp)` từ `read()` rồi truyền frame vào detector.
Picamera2 dùng RGB888 (mảng BGR), timestamp lấy từ metadata SensorTimestamp của
cùng ảnh. Camera chờ ảnh mới; sender ngủ khi queue rỗng. Không cần trình duyệt
hoặc màn hình. Terminal hiện số track, thời gian inference, CROSS và ACK/lỗi.
ACK nghĩa là STM32 đã nhận, không xác nhận gạt thành công.

Vạch quyết định dùng tâm box và cấu hình chuẩn hóa: `axis="x"`, `position=0.5`,
`direction="increasing"` là đi từ trái sang phải qua giữa ảnh. Quả cần được
nhìn thấy trước vạch. Có thể thêm bảng tùy chọn sau vào cấu hình cá nhân:

```toml
[tracker]
max_distance_px = 80.0
max_age_seconds = 0.5
```

Nếu khoảng cách giữa các frame suy luận quá lớn, cần hiệu chỉnh tracker theo
tốc độ băng tải; ID đổi có thể gây bỏ sót/đếm trùng. Thời gian firmware hiện
tính từ lúc nhận lệnh, chưa bù độ trễ camera/inference/UART; cần đo và chỉnh
trước khi đánh giá vị trí gạt.

Ctrl+C dừng pipeline và đóng camera/UART; giao dịch đang chạy được hoàn thành,
sự kiện còn chờ được in NOT SENT. Lỗi camera, hàng đợi đầy hoặc lỗi UART dừng
nhận quả mới. **Motor không tự dừng khi Pi thoát hoặc lỗi:** dùng debugger STM32
`servo_test_command=3` để Stop. Sau kết quả UART không rõ, không chạy lại để gửi
bù sản phẩm; cần dừng, dọn băng tải và khôi phục trạng thái/phiên UART trước.

`requirements.txt` chỉ chứa pyserial để kiểm tra UART. Detector dùng bộ phụ thuộc
riêng `requirements-vision.txt`; không dùng môi trường Roboflow của ModelTest.
Sao chép `config.example.toml` thành `config.toml` và truyền `--config config.toml`.
Loader kiểm tra `serial`, `camera` (width/height/fps nguyên dương) và `detector`
(model là đường dẫn `.pt`, imgsz nguyên dương, confidence hữu hạn trong khoảng mở 0..1). Các bảng còn lại
dành cho bước tiếp theo. Khi dùng `--config`, cần cả ba bảng kể cả lúc PING.
Nếu truyền thêm `--port`, cổng CLI ưu tiên hơn cổng trong file. Chỉ dùng `--port`
thì các tham số UART còn lại lấy mặc định của transport/protocol. Đường dẫn tương đối
tới file cấu hình tính từ thư mục đang chạy lệnh. Riêng đường dẫn model tương đối
tính từ thư mục chứa TOML, được loader chuyển thành tuyệt đối.
Cấu hình sai trả lỗi trước khi mở cổng; PING không cần file trọng số tồn tại.
Đường dẫn output dự kiến dùng thư mục
`runtime/`. Cấu hình cá nhân, output và SQLite không được commit.
Package vận hành không cần API key Roboflow. ModelTest cũ vẫn dùng cấu hình riêng.

## Model Ultralytics cục bộ

Chép file detection đã train vào `RaspberryPi/models/best.pt` (Git bỏ qua `.pt`).
Trong `RaspberryPi/config.toml`, đặt `model = "models/best.pt"`; nếu file cấu hình
ở `RaspberryPi/conveyor/config.toml`, đặt `model = "../models/best.pt"`.
Không dùng URL hoặc model ID để thay thế trọng số. Detector kiểm tra file tồn tại
trước khi gọi Ultralytics, không tự chọn/tải model khi thiếu file.

```toml
[detector]
model = "models/best.pt"
confidence = 0.4
imgsz = 640
```

Trên Pi, cài `ultralytics` đúng phiên bản của môi trường train trước, rồi cài
`requirements-vision.txt` bằng pip trong venv. Ghi phiên bản thực tế và khóa nó
trong môi trường triển khai sau khi thử model trên Pi. Chưa chốt phiên bản vì
repo chưa có trọng số hoặc thông tin môi trường train. NumPy/PyTorch là phụ thuộc
của Ultralytics. Picamera2 sẽ dùng từ Raspberry Pi OS khi triển khai camera.

`Detector(model_path, confidence=0.4, imgsz=640)` tải model một lần. Nó yêu cầu
task `detect` và đúng ba nhãn `green`, `riped`, `damaged`, lấy tên từ metadata,
không mặc định ID 0/1/2. File hỏng hoặc sai task/nhãn gây lỗi lúc khởi tạo.

`predict(frame, color_order="BGR")` nhận NumPy uint8 H×W×3 và trả danh sách
`Detection(xyxy, class_id, label, confidence)`. `xyxy` theo pixel ảnh gốc.
Phải truyền rõ `color_order="RGB"` hoặc `"BGR"` dựa trên dữ liệu thật; RGB được
đổi sang BGR trước predict. Không suy luận thứ tự màu chỉ từ tên format Picamera2.
Mỗi lần gọi predict dùng CPU, imgsz/confidence đã cấu hình, không lưu ảnh tự động.
Không có detection thì trả danh sách rỗng. PING không import vision/Ultralytics.

Để thử riêng trên Pi sau khi cài phụ thuộc, từ `RaspberryPi`:

```python
import cv2
from conveyor.config import load_config
from conveyor.vision.detector import Detector

config = load_config("conveyor/config.toml")
settings = config["detector"]
detector = Detector(settings["model"], settings["confidence"], settings["imgsz"])
frame = cv2.imread("test-fruit.jpg")
if frame is None:
    raise ValueError("Cannot read test-fruit.jpg")
detections = detector.predict(frame, color_order="BGR")
for detection in detections:
    print(detection)
```

Thử ảnh một quả, nhiều quả, không quả; đo thời gian tải model riêng với thời gian
predict sau warmup. Chưa xác nhận FPS hoặc độ chính xác trên phần cứng.
Chạy test sau khi cài vision để kiểm tra RGB/BGR bằng NumPy thật; thiếu NumPy,
hai test ảnh được skip nhưng các test đường dẫn/task/nhãn vẫn chạy bằng model giả.

### Thử cả thư mục ảnh trên Windows

Từ `RaspberryPi`, dùng Python trong virtual environment:

```powershell
.\.venv\Scripts\python.exe -m conveyor.vision.annotate_images --config conveyor/config.toml --source images --output runtime/predictions/my_test
```

Output phải là thư mục mới, nằm ngoài thư mục ảnh đầu vào. Chương trình dùng
detector của pipeline, lưu bản sao có box/nhãn/confidence và `report.json` chứa
từng detection, thời gian suy luận và tổng số box mỗi lớp. Ảnh gốc không bị sửa.
Số detection không phải độ chính xác: cần nhãn ground truth để đánh giá accuracy/mAP.
Với bộ trọng số hiện có, môi trường Windows được thử bằng Ultralytics `8.4.194`
và PyTorch CPU. Kết quả máy tính không đại diện tốc độ Pi.

## Cấu trúc hiện có và nơi thêm code

```text
RaspberryPi/
├── conveyor/
│   ├── __init__.py
│   ├── __main__.py           # điểm chạy python -m conveyor
│   ├── app.py                # hiện chỉ điều phối kiểm tra UART
│   ├── config.py             # kiểm tra cấu hình serial, camera, detector
│   ├── events.py             # Detection dùng chung
│   ├── vision/
│   │   ├── __init__.py
│   │   └── detector.py       # Ultralytics .pt trên CPU
│   └── communication/
│       ├── __init__.py
│       ├── serial_link.py    # UartLink: byte I/O
│       └── protocol.py       # frame, CRC, ACK, retry, SEQ
├── tests/
│   ├── test_app.py
│   ├── test_config.py
│   ├── test_detector.py
│   ├── test_protocol.py
│   └── test_serial_link.py
├── config.example.toml
├── requirements.txt
├── requirements-vision.txt
├── models/README.md
├── README.md
├── DataCollector/
└── ModelTest/
```

Không tạo file rỗng cho chức năng chưa viết. Khi đến bước tương ứng, thêm:

| Module | Trách nhiệm |
|---|---|
| `conveyor/events.py` (mở rộng) | Thêm kiểu dữ liệu track và sự kiện vượt vạch |
| `conveyor/vision/camera.py` | Ảnh và thời gian chụp monotonic |
| `conveyor/vision/tracker.py` | Duy trì ID qua các frame |
| `conveyor/vision/crossing.py` | Phát một sự kiện/ID khi vượt vạch đúng chiều |
| `conveyor/communication/sender.py` | Một luồng gửi tuần tự, chờ queue có giới hạn |
| `conveyor/statistics/store.py` | SQLite: sự kiện, thời gian thực và kết quả ACK/lỗi |

Thêm `__init__.py` vào `statistics/` khi bắt đầu viết lưu trữ.
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
CMD: PING `1`, UNRIPE `2`, RIPE `3`, SPOILED `4`, START `5`.
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
2. Thử detector với trọng số thật, rồi viết camera và mở rộng `events.py`. Inference hoạt động khi
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
