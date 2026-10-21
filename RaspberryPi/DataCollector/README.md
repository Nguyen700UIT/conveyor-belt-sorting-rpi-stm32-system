1# Thu ảnh CSI và kiểm tra ảnh bằng MCP

Chạy trên **PowerShell Windows local**, không chạy script chính trong terminal SSH.
Pi chỉ chụp JPEG trong RAM bằng Picamera2 rồi truyền ảnh và metadata qua SSH.
Mặc định SSH: `pi@192.168.1.175`, ảnh 1280x720, JPEG quality 95, yêu cầu 15 FPS.

## Chạy thu dữ liệu

```powershell
cd D:\UIT\ConveyorBelt\RaspberryPi\DataCollector
.\.venv\Scripts\python.exe .\capture_yolo_local.py --output .\dataset --focus once
```

Dừng rpicam-hello/chương trình đang dùng camera. Đặt quả đứng yên giữa vùng chụp,
đợi `Focus locked` rồi bật băng tải. Focus thực hiện bằng phơi sáng tự động trước,
sau đó mới áp dụng shutter/gain cố định nếu được yêu cầu.

- Space/S: lưu một ảnh gốc vào `dataset/images`, không có chữ preview.
- A: bật/tắt auto; nếu không truyền interval thì chu kỳ là 2 giây/ảnh.
- Q/Esc/Ctrl+C: thoát. Chạy một collector tại một thời điểm.
- `--interval 0.5`: tự lưu mỗi khoảng 0,5 giây, độc lập FPS preview.
- `--focus manual --lens-position 2`: chỉnh lens thủ công; khoảng 0,5 m, cần thử thực tế.
- `--shutter-us 0`: auto exposure. Khi khác 0, gain được đặt cố định.

Khi đủ ánh sáng và muốn giảm nhòe chuyển động:

```powershell
.\.venv\Scripts\python.exe .\capture_yolo_local.py --output .\dataset --fps 15 --focus once --shutter-us 1000 --gain 2 --interval 1
```

Trên Pi cần `python3-picamera2` (cài bằng apt nếu chưa có). SSH phải đăng nhập được;
thử `ssh pi@192.168.1.175` trước, xác minh host key và gõ exit về Windows.

## MCP trong Codex

Đã đăng ký stdio server `conveyor_image_quality` trong cấu hình Codex của tài khoản
bằng `codex mcp add`; `codex mcp get conveyor_image_quality --json` xác minh server được bật.
`.codex/config.toml` ở gốc project giữ cấu hình tương ứng để dùng lại cho project.
Môi trường `.venv` riêng chứa OpenCV, NumPy, MCP SDK 1.x.
Codex chỉ nạp cấu hình project khi project được tin cậy. Sau khi tải lại cửa sổ
VS Code/Codex hoặc mở phiên mới, kiểm tra danh sách MCP.

Nếu SSH hỏi mật khẩu, nhập trong terminal chạy collector. Không đưa mật khẩu vào
mã nguồn, cấu hình MCP hoặc chat. MCP không cần đăng nhập SSH vì nó đọc snapshot
do collector trên Windows cung cấp.

Trong khi script đang chạy, yêu cầu Codex:

> Dùng conveyor_image_quality kiểm tra ảnh live mới nhất; xem độ nét, độ sáng và phản sáng của quả.

Ba tool:

- `get_live_frame(roi=None)`: ảnh mới nhất, tuổi ảnh, thông số camera thực tế và chỉ số chất lượng.
- `list_recent_captures(limit=5)`: danh sách ảnh đã lưu.
- `inspect_saved_image(filename, roi=None)`: xem ảnh dataset và chỉ số.

ROI là `[x, y, width, height]` chuẩn hóa 0..1. Chọn vùng chứa quả để bề mặt băng tải
không làm sai đánh giá độ nét. Tool trả cả ảnh đầy đủ và crop ROI.

Collector thay nguyên tử `.live/latest.json` mỗi khoảng một giây; trong đó có JPEG
và metadata tương ứng cùng một frame. File chỉ giữ ảnh mới nhất, không tạo dataset
phụ; snapshot vẫn cập nhật khi chưa bật auto lưu. MCP chỉ đọc khi được gọi, không
polling nền, không mở camera hoặc điều khiển motor. Không cần API key.

`age_seconds` là tuổi từ lúc PC nhận ảnh, không đo toàn bộ độ trễ SSH; `stale=true`
khi quá 5 giây. Snapshot cũ vẫn có thể tồn tại sau khi collector dừng: luôn xem tuổi ảnh.
MCP cung cấp kiểm tra theo yêu cầu, không khiến Codex tự theo dõi liên tục sau khi kết thúc lượt chat.

Laplacian variance là chỉ số tham khảo, không có ngưỡng đạt/chưa đạt chung. Nhiễu hoặc
vân băng tải có thể làm chỉ số tăng. So cùng ROI, kích thước, ánh sáng với ảnh quả đứng
yên rõ nét và nhìn ảnh để phân biệt nhòe chuyển động/lệch nét. Giá trị độ sáng là luma
0..255; tỷ lệ tối (<20) và sáng (>245) không tự kết luận chất lượng train.

Nếu đổi output, cập nhật `COLLECTOR_IMAGES_DIR` trong cấu hình MCP để trỏ đúng `images`.
Nếu đổi `--live-dir`, cập nhật `COLLECTOR_LIVE_DIR` tương ứng.

Tài liệu cấu hình: https://developers.openai.com/codex/mcp

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Test dùng ảnh tổng hợp, không kết nối camera và không thay ảnh đang thu.
