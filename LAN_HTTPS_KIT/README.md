# HTTPS LAN — Cầm đồ Kim Hạnh 2

Địa chỉ: **https://tiemvangkimhanh2:8200**. Máy chủ: **192.168.1.6**.

Máy đã sử dụng được `https://tiemvangkimhanh2:8100` của BÁN LẺ thường không cần cài lại: hai ứng dụng dùng cùng tên máy và CA nội bộ.

Với PC Windows mới trong LAN:

1. Chép cả thư mục này sang PC đó (không chép các khóa riêng trong `instance/`).
2. Mở `CAI_HTTPS_PC_LAN.bat`, chấp nhận hộp thoại Administrator của Windows.
3. Script kiểm tra đúng CA Kim Hạnh 2, thêm tên máy vào hosts, cài CA tin cậy và kiểm tra kết nối HTTPS. Kết quả nằm trong `install-result.txt`.
4. Mở lại trình duyệt, vào địa chỉ bên trên. Nếu Firefox dùng kho chứng chỉ riêng, nhập chứng chỉ CA công khai trong thư mục vào kho tin cậy của Firefox theo quy định quản trị máy.

Script giữ các tên máy khác trong hosts và tạo bản sao lưu trước khi thay đổi. Không tắt kiểm tra chứng chỉ, không tải CA từ nguồn không xác thực. Tên miền và IP dùng chung cho cả BÁN LẺ và CẦM ĐỒ.

Riêng **máy chủ**, chạy `configure-lan.ps1 -Server` để thêm quy tắc tường lửa TCP 8200 chỉ cho mạng con cục bộ. Cổng backend 8201 chỉ nghe loopback, không mở cho LAN. Không cần chuyển tiếp cổng router.
