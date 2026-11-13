# Tổng quan project

Hệ thống băng tải phân loại tắc sống, tắc chín và tắc hư bằng Raspberry Pi 5 và STM32F103C8T6.

- Pi lấy ảnh từ Picamera2, dùng YOLO nhận diện, theo dõi ID và gửi loại quả khi tâm box vượt vạch đếm đúng chiều. Model dùng đúng ba nhãn `green`, `riped`, `damaged`; hỗ trợ trọng số `.pt` và thư mục NCNN `*_ncnn_model`.
- STM32 điều khiển hai servo MG90S và motor JGB37-545 không encoder qua BTS7960. Firmware dùng hàng đợi sản phẩm, deadline thời gian và FSM servo để gạt quả sống/hư; quả chín đi tiếp. Thời gian di chuyển và servo cần hiệu chỉnh theo băng tải thật.
- Pi giao tiếp USART1 của STM32 qua USB CP2102, 115200 baud, 8N1. CP2102 TX nối PA10, RX nối PA9, GND nối chung.
- SQLite lưu sự kiện vượt vạch và kết quả UART. Dashboard FastAPI trên LAN hiển thị sản lượng theo ngày, SSE và camera MJPEG có khung YOLO, nhãn, vạch đếm.

## Cấu trúc và vận hành

- `STM32Firmware/Core/` chứa firmware; cấu hình CubeMX ở `STM32Firmware/STM32Firmware.ioc`.
- `RaspberryPi/conveyor/app.py` điều phối camera, detector, tracker, crossing và sender. Logic nhận diện ở `vision/`, giao tiếp ở `communication/`, lưu dữ liệu ở `statistics/`, web và stream ở `dashboard/`.
- `RaspberryPi/config.example.toml` là cấu hình mẫu. Đường dẫn model, database và font tương đối được tính từ file TOML.
- `RaspberryPi/notebooks/ce224-yolo.ipynb` phục vụ transfer learning trên Kaggle và export NCNN. `RaspberryPi/dataset_tools/` chuẩn bị augmentation theo nhóm quả.
- `--run` tự PING, mở camera, warmup rồi gửi START. `--dashboard` chỉ xem lịch sử. `--ping` và `--start` dùng để kiểm tra UART và khởi động motor.
- Firmware hiện dừng bằng `servo_test_command = 3` trong debugger. Reset trạng thái bằng lệnh `4` khi hai servo idle và băng tải đã được dọn. Pi thoát hoặc lỗi không tự gửi STOP motor.

## Các ràng buộc kỹ thuật

- Ưu tiên tiết kiệm tài nguyên và năng lượng. Dùng blocking I/O, Event, Condition và notification; hạn chế polling, tránh busy-wait.
- Camera stream dùng lại frame và kết quả inference. Một worker giữ frame mới nhất, encode dùng chung khi có người xem.
- Số lượng chính tính theo vượt vạch. ACK biểu thị STM32 chấp nhận lệnh; xác nhận quả vào hộp cần bằng chứng riêng từ phần cứng.
- Chống ghi trùng bằng `(session_id, track_id)`. Lưu thời gian UTC, tổng hợp ngày theo `Asia/Bangkok`. Kết quả UART không rõ cần được ghi nhận để xử lý khôi phục, tránh tự gửi bù.
- Giữ các ảnh và biến thể của cùng một quả trong cùng split khi train/validation/test. Chọn cấu hình model bằng validation hoặc CV theo nhóm quả.
- Dataset, trọng số model, cấu hình cá nhân, runtime và tests được giữ cục bộ theo `.gitignore`. Theo yêu cầu hiện tại, không commit tests lên repository.
- README dùng tiếng Anh, viết ngắn gọn về mô tả hệ thống và cài đặt.

# Các quy tắc chính khi làm việc 
## 1. Suy nghĩ trước khi code
* Phát biểu giả định ra lời. Nếu yêu cầu mơ hồ — hỏi. Nếu có cách đơn giản hơn — phản đối. Khi bối rối, dừng lại, chỉ ra điều chưa rõ thay vì tự chọn một cách diễn giải rồi cứ thế chạy.
## 2. Ưu tiên sự đơn giản 
* Viết lượng code tối thiểu giải quyết được vấn đề. Không abstraction phỏng đoán. Không "tính linh hoạt" mà chẳng ai yêu cầu. Bài test: một senior engineer có gọi cái này là over-engineered không?
## 3. Thay đổi kiểu phẫu thuật (Surgical Changes):
* Chỉ động đến đúng phần task yêu cầu. Không "cải thiện" code lân cận. Không refactor cái đang chạy ổn. Mỗi dòng thay đổi phải truy ngược lại được về yêu cầu cụ thể.
## 4. Thực thi theo mục tiêu
* Biến chỉ thị mơ hồ thành mục tiêu kiểm chứng được trước khi viết dòng code nào. "Thêm validation" thành "viết test cho các input không hợp lệ, sau đó làm test pass."
# Các quy tắc phụ
* Ưu tiên trả lời bằng tiếng Việt 
* Viết code Python tường minh
* Luôn hỏi mình có muốn tự viết phần code này không? Nếu có thì hãy hướng dẫn mình viết phần code đó sao cho mình cũng có thể hiểu đoạn code (tưởng tượng bạn như 1 người giảng viên hướng dẫn mình viết và khi hướng dẫn hãy chỉ cung cấp thuật toán thay vì viết code ra), nếu không sau khi viết phần code hãy giải thích về các đoạn code bạn thêm hoặc thay đổi
 
