# Thử model Roboflow với camera CSI trên Pi 5

Model: `tung-tran-s-workspace/ce224-project-1-yolo26n-t1`.
Script chạy suy luận ONNX CPU trên Pi và truyền JPEG có bounding box qua HTTP.
Mở trang xem trên máy cùng mạng; đóng trang để tạm ngưng suy luận.
Camera chỉ dành cho một chương trình tại một thời điểm; dừng collector trước khi chạy.

## Môi trường trên Pi

Thư mục triển khai: `/home/pi/conveyor_belt_project/roboflow_test`.
Picamera2 và OpenCV lấy từ Raspberry Pi OS qua `--system-site-packages`.

```bash
cd ~/conveyor_belt_project/roboflow_test
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install --no-deps --no-compile inference-models==0.39.5
.venv/bin/python -m pip install --no-compile -r requirements.txt
```

Nếu `/tmp` nằm trên RAM và không đủ chỗ tải thư viện, tạo `.tmp` trong thư mục
thử nghiệm và thêm `TMPDIR="$PWD/.tmp"` trước lệnh cài.

Đây là bộ phụ thuộc dành riêng cho YOLO26 ONNX. Cài engine với `--no-deps`
để tránh tải thêm thư viện cho các họ model khác. Khi đổi họ model cần kiểm tra
lại phụ thuộc, không dùng môi trường này như bộ Roboflow đầy đủ.

Đặt `ROBOFLOW_API_KEY=...` trong `.env` cùng thư mục script, chạy `chmod 600 .env`.
Không commit key. Lần đầu cần Internet để tải model và thư viện.

## Chạy

```bash
cd ~/conveyor_belt_project/roboflow_test
.venv/bin/python camera_boxes.py
```

Giữ quả đứng yên ở giữa khung hình trong lúc autofocus, rồi mở
`http://192.168.1.175:8080/`. `Ctrl+C` dừng chương trình và giải phóng camera.
Ngưỡng hiển thị mặc định 40%; có thể đổi bằng `--confidence 0.25`.
`green`: xanh, `riped`: chín (giữ nguyên nhãn của model), `damaged`: hư.
FPS trên ảnh đo thời gian chụp và suy luận/vẽ; chưa gồm truyền JPEG đến trình duyệt.
Đây là trang kiểm tra trong LAN, không có đăng nhập. Không chuyển tiếp cổng ra Internet.
Chưa gửi UART, điều khiển servo hoặc đếm sản lượng.

Tài liệu runtime: https://inference-models.roboflow.com/api-reference/auto-model/
