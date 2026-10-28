# Conveyor Belt

Project băng chuyền phân loại tắc sống, tắc chín và tắc hư bằng Raspberry Pi 5
và STM32F103C8T6. Pi xử lý camera; STM32 phụ trách giao tiếp UART và điều khiển
phần cứng. Hệ thống hướng tới xử lý bằng sự kiện

## Cấu trúc

- `STM32Firmware/Core/`: mã C cho UART, servo và hàng đợi sản phẩm đang phát triển.
- `STM32Firmware/Drivers/`: STM32 HAL và CMSIS, giữ kèm giấy phép của nhà cung cấp.
- `STM32Firmware/STM32Firmware.ioc`: cấu hình phần cứng STM32CubeMX.
- `STM32Firmware/cmake/`: toolchain và cấu hình build.
- `RaspberryPi/DataCollector/`: công cụ thu thập ảnh, kiểm tra chất lượng và tài liệu.
- `RaspberryPi/ModelTest/`: thử mô hình nhận diện với camera trên Pi.
- `AGENTS.md`: hướng dẫn làm việc trong repository.

## Build firmware

Cần CMake 3.22 trở lên, Ninja và ARM GNU Toolchain (`arm-none-eabi-gcc`)
trong `PATH`. Từ thư mục `STM32Firmware`:

```sh
cmake --preset Debug
cmake --build --preset Debug
```

Firmware được tạo tại `build-local/Debug/STM32Firmware.elf`.
Nạp bằng STM32CubeProgrammer và ST-Link qua SWD; xác minh Flash sau khi nạp.
Cấu hình VS Code và đường dẫn công cụ của từng máy không được commit.

## Raspberry Pi

Đọc README trong từng công cụ để tạo môi trường Python và cài đúng
`requirements.txt`. Một số phụ thuộc camera cần Raspberry Pi OS.
Chức năng thu ảnh và thử model hiện tách riêng; tích hợp UART, cảm biến và servo
đang được phát triển.

Pi kết nối UART qua USB CP2102; firmware dùng USART1 ở 115200 baud, 8N1.



