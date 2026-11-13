# Chuẩn bị ảnh augmentation trước khi gán nhãn

Công cụ dành cho bộ `dataset/ce224 dataset` hiện tại: thư mục `green`, `ripe`,
`damaged`, `background`; tên ảnh `fruitN (frame).jpg`. Giả định mọi frame của
`fruitN` thuộc một quả thật trong lớp đó; tên `fruiti11` được chuẩn hóa thành
`fruit11`. Nếu giả định này sai, phải sửa định danh nhóm trước khi chia tập.

Chạy từ gốc repo, dùng môi trường Python đã cài Pillow:

```powershell
RaspberryPi/.venv/Scripts/python.exe RaspberryPi/dataset_tools/augment.py --source "dataset/ce224 dataset" --output "dataset/ce224_augmented" --seed 42
```

- Chia theo quả khoảng 70/15/15, làm tròn để tập nào cũng có quả từng lớp.
  Với 8 quả chín, chia 5 train, 1 val, 2 test. Tập đánh giá rất nhỏ, cần đọc
  kết quả theo từng quả; nhiều frame không tương đương nhiều quả độc lập.
- Sao chép ảnh gốc, không sửa hoặc xóa nguồn. Đầu ra phải là thư mục mới.
- Chỉ tăng số ảnh train của lớp thiếu đến bằng lớp train lớn nhất. Mọi ảnh gốc
  đều được giữ; lượt augmentation phân bố qua các ảnh nguồn của từng lớp.
- Brightness và contrast trong 0.9–1.1. Không chủ động đổi hue/saturation,
  không grayscale, xoay, crop, dịch chuyển hoặc thêm blur che mất vết hư.
  Biến đổi sáng vẫn có thể gây clipping nhẹ; xem preview trước khi gán nhãn.
- Không augmentation val/test. Bản sao ảnh gốc giữ nguyên byte và có SHA-256
  trong manifest để kiểm chứng.
- Ảnh nền chưa có nhóm phiên chụp độc lập nên chỉ đưa vào train; không giả vờ
  đã có một tập test ảnh nền độc lập. Điều này hạn chế đánh giá false positive.

Đầu ra: `train/<class>`, `val/<class>`, `test/<class>`, `manifest.csv`,
`report.json`, `preview.jpg` và hướng dẫn. Nhãn `ripe` đổi thành `riped` để
khớp pipeline hiện tại. Manifest lưu nguồn, nhóm quả, tập, phép biến đổi và
hash nguồn; seed cố định giúp tái lập phép chia/augmentation cùng phiên bản Pillow.

**Chưa thể train YOLO detection trực tiếp:** chưa có bounding box. Import riêng
từng tập vào công cụ gán nhãn, giữ split khi export. Chỉ dùng ba lớp đối tượng
`green`, `riped`, `damaged`; `background` là ảnh âm tính, không phải lớp thứ tư.
Không đưa preview hoặc file báo cáo vào bộ train; không chia ngẫu nhiên lại sau
augmentation. Nếu công cụ gán nhãn chỉ chia ngẫu nhiên khi export, dùng manifest
để khôi phục train/val/test trước khi train.

Augmentation tăng số lần nhìn thấy biến thể; không tạo thêm quả thật và không
bảo đảm model tốt hơn. So sánh bản gốc/bản tăng cường trên cùng val/test. Khi
train sau này, tránh bật thêm augmentation màu mạnh chồng lên các biến thể này.
