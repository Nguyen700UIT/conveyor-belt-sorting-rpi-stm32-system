# Tổng quan project
Mình sử dụng STM32 để lái servo gạt sản phẩm xuống hộp phân loại. Hiện tại hệ thống sẽ có 3 loại sản phẩm là tắc sống, tắc chín và tắc hư. Hệ thống sử dụng 2 servo MG90S và trước mỗi servo sẽ có 1 cảm biến hồng ngoại E3F-DS30C4 để phát hiện vật đến đúng vị trí giúp servo có thể gạt đúng lúc.

STM32 sẽ sử dụng mạch cầu BTS7960 để lái motor JGB37 545 không encoder.

STM32 và Pi 5 sẽ sử dụng giao tiếp UART. Pi 5 sẽ nhận UART bằng USB thông qua module CP2102 để giao tiếp với STM32. Pi 5 sử dụng thuật toán YOLO phát hiện loại quả tắc trên bằng chuyền sau khi vật thể được băng tải đưa đến 1 vị trí trên khung hình lúc đó Pi 5 sẽ gửi tín hiệu cho STM32 để thông báo servo nào cần gạt hoặc không cần gạt (tình huống không cần gạt là tình huống trái đạt tiêu chuẩn có thể tiêu thụ).

Hạn chế sử dụng polling trong project này vì mục tiêu mình cần là tiết kiệm tài nguyên và năng lượng 1 cách tối đa hết mức có thể

Project sẽ có thống kê số lượng quả của từng loại và có web server dashboard để hiện các thống kê sản lượng trong mỗi ngày.
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

* Luôn hỏi mình có muốn tự viết phần code này không? Nếu có thì hãy hướng dẫn mình viết phần code đó sao cho mình cũng có thể hiểu đoạn code (tưởng tượng bạn như 1 người giảng viên hướng dẫn mình viết), nếu không sau khi viết phần code hãy giải thích về các đoạn code bạn thêm hoặc thay đổi 
 
