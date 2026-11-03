# Giao tiếp byte UART trên Raspberry Pi

Thư mục này chứa lớp giao tiếp serial mức byte cho Raspberry Pi, dùng với bộ chuyển USB-UART như CP2102. Lớp này mở cổng serial, gửi và nhận byte thô. Nó **không** phân tích frame, diễn giải ACK/NACK, đặt timeout giao dịch hay tự gửi lại lệnh; các việc đó thuộc tầng giao thức phía trên.

## Cài đặt

Từ thư mục này, cài phụ thuộc:

```sh
python3 -m pip install -r requirements.txt
```

## Cấu hình serial

Mặc định, `UartLink` dùng 115200 baud, 8 bit dữ liệu, không parity, 1 stop bit (8N1). Khi tạo đối tượng, chương trình gọi cần truyền tên cổng, ví dụ `/dev/ttyUSB0` trên Raspberry Pi. Có thể truyền thêm baud rate và timeout đọc/ghi nếu cần.

## Các thao tác hiện có

- `open()`: mở cổng serial.
- `send(data)`: chuyển dữ liệu đầu vào thành byte và gửi; trả về số byte mà thư viện serial đã ghi.
- `receive(max_length)`: đọc tối đa số byte yêu cầu; kết quả có thể ngắn hơn do timeout đọc. Hàm không đợi đủ một frame.
- `close()`: đóng cổng.
- Có thể dùng `UartLink` với `with` để tự mở khi vào khối và đóng khi thoát.

Ứng dụng gọi lớp này cần tự ghép các byte thành frame, kiểm tra frame, chờ ACK/NACK và quyết định retry theo giao thức đã thống nhất với STM32.
