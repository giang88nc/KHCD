# KHCD — Quản lý cầm vàng Kim Hạnh

Ứng dụng Python/Flask dùng trực tiếp MySQL `khj_cd` trên `127.0.0.1:3308`, tài khoản CSDL `khj_admin`. Web chạy tại **https://tiemvangkimhanh2:8200** trong LAN hoặc **https://localhost:8200** trên máy chủ. Địa chỉ HTTP cũ tự chuyển sang HTTPS cùng cổng.

## Thư mục chính duy nhất — chốt ngày 14/09/2026

**Dự án CẦM ĐỒ Python đặt tại `D:\PYTHON\KHCD`. Mọi phát triển, khởi động, cấu hình và sao lưu tệp dự án đều thực hiện tại đây.** Không tạo hoặc vận hành thêm bản dự án tại `Documents\ChatGPT`. Bản trước khi chuyển chỉ giữ làm bản sao lưu tại `backups\source-before-relocation-20260914`, không dùng để chạy ứng dụng.

- Mã nguồn: `khcd`; Python riêng: `.venv`; cấu hình: `.env`; bản sao lưu SQL: `backups`.
- Bật ứng dụng bằng `D:\PYTHON\KHCD\TURN_ON_KHCD.vbs` hoặc `scripts\start.ps1`; tắt bằng `scripts\stop.ps1`.
- Tác vụ Windows `KHCD Web Host` chạy `D:\PYTHON\KHCD\scripts\host.ps1`, giữ cơ chế tự phục hồi hiện có. Caddy HTTPS 8200, Waitress nội bộ 8201; dịch vụ khách KHBL nội bộ 18202 dùng khóa cầu nối tại `instance\customer-bridge.key` của dự án này.
- Chứng chỉ và khóa HTTPS giữ nguyên trong `instance\caddy-data`; log Caddy cũng nằm trong `instance` tại ổ D.
- **Kho ảnh phiếu: `D:\PYTHON\KHCD\media\pawn`**, cấu hình `LEGACY_PAWN_IMAGE_ROOT`. Giải nén ảnh backup trực tiếp vào đây, giữ tên tệp, tránh lồng `pawn\pawn`. Đã chép 74 tệp đang có từ kho PHP cũ để bảo toàn ảnh; backup đầy đủ của người dùng cần bổ sung vào kho mới này. Ảnh BLOB tiếp tục nằm trong MySQL như trước. Không xóa kho PHP dùng chung với hệ thống cũ.
- MySQL trên MrGiang và MSSQL trên KK giữ nguyên vị trí/dữ liệu. Di chuyển thư mục dự án không chuyển hoặc nhân bản các CSDL đang hoạt động.

Đã đối chiếu SHA-256 toàn bộ 496 tệp dự án cần giữ và 74 tệp ảnh, tạo lại môi trường Python ở ổ D, cập nhật tác vụ Windows và đường dẫn lưu chứng chỉ/log Caddy. 115 kiểm thử đạt trong CSDL thử riêng tại môi trường mới; xác minh HTTPS localhost/tên LAN, đăng nhập còn hiệu lực, khách KK đọc được và tác vụ tự khởi động lại backend thành công. Bản SQL/chứng chỉ/khóa cầu nối giữ nguyên, không thử ghi giao dịch thật khi chuyển thư mục.

## Đường dẫn chuẩn Cầm đồ — 14/09/2026

| Mục | Đường dẫn |
|---|---|
| Tổng quan | `/` hoặc `/camdo` (menu dùng `/camdo`) |
| Cầm đồ · Lập phiếu | `/camdo/lap-phieu` |
| Phiếu cầm đồ | `/camdo/phieu-cam-do` |
| Biên nhận SQL mới | `/camdo/bien-nhan` |
| Chi tiết phiếu | `/camdo/phieu-cam-do/<id>` |
| Khách hàng | `/camdo/khach-hang` |
| Thống kê | `/camdo/thong-ke` |

Áp dụng trên mọi hostname HTTPS của port 8200, gồm localhost và tiemvangkimhanh2 trong LAN. Các trang con, API tìm khách và popup khách cũng thuộc `/camdo`. Đăng nhập, đăng xuất, health và static giữ đường dẫn hạ tầng hiện có.

`khcd/urls.py` giữ tương thích link cũ: GET/HEAD chuyển tiếp 308 sang URL chuẩn, giữ nguyên bộ lọc/query; POST của form cũ gọi cùng endpoint với cùng kiểm tra session/CSRF và khóa nghiệp vụ, không chuyển thành GET hay tự gửi lần thứ hai. `/cam-do` và `/phieu-cam-do/moi` cũ đều dẫn đến `/camdo/lap-phieu`. Không đổi dữ liệu hay thuật toán khi chuẩn hóa URL.

## Quyết định kiến trúc đã chốt — chuẩn phát triển tiếp theo

**Nguồn: quyết định của chủ hệ thống ngày 14/09/2026.** Các lần phát triển tiếp theo cần đọc phần này trước khi thay đổi đăng nhập, khách hàng, nhân viên hoặc kết nối CSDL. Phân biệt quyết định đích với chức năng đã triển khai ở các phần vận hành bên dưới; không coi kế hoạch là tính năng đang có.

| Thành phần | Vai trò đã chốt |
|---|---|
| KHBL — cổng 8100 | Webapp BÁN LẺ, vận hành và triển khai độc lập |
| KHCD — cổng 8200 | Webapp CẦM ĐỒ, vận hành và triển khai độc lập |
| KH HR / KHJ — cổng 8000 | Webapp nhân sự, công và lương, vận hành và triển khai độc lập |
| MSSQL chính trên máy KK | Nguồn PMV: khách, nhân viên giao dịch, bán lẻ, doanh thu, hoa hồng… |
| MySQL 8 trên MrGiang | Các CSDL nghiệp vụ riêng `khj_bl`, `khj_cd`, `khj_hr`, kết hợp với MSSQL thành một hệ thống |
| MSSQL `I_CUSTOMER` | Bảng KHÁCH HÀNG chính, đầy đủ nhất; đích sử dụng khách hàng chung lâu dài |
| MSSQL `T_EMPLOYEE` | Danh mục nhân viên ghi nhận giao dịch bán hàng và cầm đồ |
| `khj_hr.employees` | Hồ sơ nhân viên tính công/lương, có liên kết và đồng bộ với `T_EMPLOYEE`; giữ mã PMV và MCC |
| `khj_bl.auth_user` | Nguồn tài khoản đăng nhập chung cho quản trị và giao dịch của cả ba app |
| HR `/portal-user/` | Kênh nhân viên đăng nhập bằng FaceID, gắn đúng hồ sơ nhân viên và quyền portal |

- Giữ ba webapp với port riêng. Không gộp thành một chương trình hoặc một CSDL nghiệp vụ duy nhất.
- Hoàn thiện cổng truy cập thống nhất **sau khi** các luồng dữ liệu và đăng nhập ổn định; cổng chung không thay thế sự độc lập của ba app.
- Tài khoản chung vẫn có quyền theo từng ứng dụng. Cookie/phiên phải tránh xung đột trên cùng hostname và khác port. Đồng bộ mật khẩu không đồng nghĩa đã có đăng nhập một lần (SSO).
- Khi tích hợp HR, đối chiếu tài khoản hiện tại trong bảng `users`, vai trò/quyền và liên kết `employees.user_id`; không chép đè ID hoặc đổi khóa ngoại bằng cách suy đoán username. Không thay quyết định nguồn tài khoản sang một CSDL khác.
- FaceID của portal không tự cấp quyền quản trị, bán hàng hoặc xử lý tiền cầm đồ.
- Nhân viên giao dịch đối soát bằng `T_EMPLOYEE.EmpID`; công/lương dùng `employees.id`, nối qua `employee_pmv`, MCC qua `employee_no`. Không đồng nhất các loại ID hoặc ghép lâu dài bằng họ tên. Giữ riêng người thao tác và nhân viên được ghi nhận doanh số/hoa hồng.
- Phân định nguồn được sửa từng trường, có nhật ký và chống xử lý trùng khi đồng bộ. Doanh số/hoa hồng đưa vào HR phải giữ mã chứng từ nguồn; tiền gốc cầm đồ không được cộng thành doanh thu bán lẻ.

## Khách hàng — nguồn KK đã áp dụng ngày 14/09/2026

**Chốt mới nhất của chủ hệ thống:** khách CĐ đã đồng bộ lên KK; danh sách khách, hồ sơ trên phiếu và UPSERT khách đều dùng MSSQL `I_CUSTOMER`. Quyết định này thay thế giới hạn chỉ đọc/không ghi MSSQL của giai đoạn trước. Lưu lịch sử đề xuất tại `docs/customer-readonly-stage.md`; không dùng tài liệu lịch sử để bật lại nguồn CĐ.

- `/camdo/khach-hang` hiện là danh sách KK duy nhất; bỏ hai tab nguồn cũ khỏi luồng hoạt động. Tìm theo tên, ba số điện thoại, mã khách hoặc CCCD. Khách có mã `CustID` dạng chuỗi; không đổi sang ID số CĐ.
- `/camdo/khach-hang/kk/<CustID>` xem/sửa hồ sơ; `/camdo/khach-hang/moi` thêm khách; popup tại `/camdo/lap-phieu` thêm và chọn đúng CustID, giữ phiếu nháp. Hoàn tất lưu khách không tự lập phiếu hoặc ghi nhận thu/chi.
- UPSERT đi qua **service chuẩn KHBL** `apps/pos/customer.py`, `customer_phones.py`, `PmvClient` và gateway. Không chép SQL/proc ghi riêng, không gộp/xóa khách. Tạo để PMV cấp mã; sửa đúng CustID, mã mất thì báo lỗi, không chuyển sang INSERT. Giữ kiểm tra ba SĐT, CCCD, quyền danh mục khách, SAVE_LOCK và khóa MySQL dùng chung.
- **Popup dùng chung KHBL (14/09/2026):** bấm **Thêm khách** hoặc tên khách trong `/camdo/khach-hang` mở popup ngay trên trang. Dùng trực tiếp `templates/pos/_khach_form.html`, CSS/JS và thuật toán của KHBL qua bridge, không giữ bản sao form hay thuật toán riêng. Bố cục 7 dòng: họ tên/giới tính/ngày sinh; CCCD/ngày cấp/nơi cấp; ba SĐT; địa chỉ 2 cột/email; ghi chú 3 cột; mã/loại khách; ảnh. Có QR, upload/chụp ảnh, cắt CCCD và ảnh đã lưu. Không có nút dạy QR trong popup. Form cũ ở URL trực tiếp và bàn lập phiếu vẫn hoạt động; thay đổi lần này áp dụng danh sách khách.
- Popup nằm trong iframe cùng origin `/camdo/khach-hang/popup/frame`, giữ giao diện KHBL và cô lập CSS khỏi nền đỏ Cầm đồ. Đăng nhập/quyền vẫn theo KHCD + kiểm lại quyền KHBL ở bridge; không chia sẻ cookie 8100. Chỉ iframe và phản hồi popup dùng chính sách CSP tương thích các script/handler inline của KHBL; trang chính vẫn giữ CSP nghiêm ngặt. Chỉ cho cùng origin nhúng iframe này.
- Upload tối đa 48 MiB mỗi request, từng ảnh qua giới hạn 15 MB/25 triệu pixel và bộ nén chuẩn KHBL. Bridge bọc dữ liệu multipart bằng base64 trong JSON ký HMAC (trần 88 MiB), chỉ nhận danh sách endpoint/tệp tài nguyên khách được cho phép. Ảnh ghi vào kho PMV và kho local KHBL hiện có, không có kho CCCD mới ở KHCD.
- Sau complete mới đóng popup/làm mới danh sách và thông báo. Lỗi giữ nguyên dữ liệu nhập; partial giữ CustID và cấp token sửa mới; kết quả chưa rõ có liên kết kiểm tra biên nhận, không tự gửi lại. Fingerprint lưu gồm ảnh khi có upload; token cũ không ảnh vẫn tương thích.
- Trường bỏ gửi được đọc giữ lại từ KK; trường gửi rỗng là yêu cầu xóa giá trị. Kiểm dấu vết hồ sơ trước sửa để báo khi dữ liệu đã đổi. Đây là kiểm tra ở ứng dụng, không phải khóa mọi chương trình PMV desktop.
- Tài khoản và quyền được kiểm lại ở dịch vụ: cùng ID `khj_bl.auth_user`, phải active và có quyền XEM/SỬA của danh mục `KHACH_HANG`; không tự cấp quyền hoặc chia sẻ cookie giữa app.

### Dịch vụ khách riêng, cùng code KHBL

Dịch vụ chạy bằng `D:/PYTHON/KHBL/venv/Scripts/python.exe -X utf8 D:/PYTHON/KHBL/manage.py run_customer_bridge --key-file <đường_dẫn_khóa>` tại **127.0.0.1:18202**, không mở LAN. Nằm trong repo KHBL, tái sử dụng service/gateway nhưng chạy riêng tiến trình web BÁN LẺ 8100. Dừng/khởi động lại KHBL web không làm dừng dịch vụ khách này. Dịch vụ vẫn phụ thuộc MySQL `khj_bl` và MSSQL KK.

KHCD gọi API giới hạn thao tác qua HMAC (thời gian, nonce, nội dung, bằng chứng phiên tài khoản); không gửi password hash hoặc khóa cho trình duyệt. Đích **KK cố định** ở tiến trình, không theo công tắc sandbox của KHBL và không cho request chọn đích. `--target sandbox` chỉ dùng trong môi trường thử riêng. Mọi truy cập MSSQL của luồng mới qua gateway chuẩn; cấu hình `PMV_MSSQL_*` cũ tại KHCD không còn phục vụ luồng khách đang hoạt động.

`CUSTOMER_MASTER=kk`, `CUSTOMER_BRIDGE_KEY_FILE=instance/customer-bridge.key`. Khóa tạo riêng trên máy chủ, bị loại khỏi Git. Script bật/tắt KHCD quản lý đúng tiến trình bridge theo đường dẫn key; Windows host kiểm tra và khởi chạy lại khi tiến trình dừng. `/health` trả `customer_service`. Không tự chuyển sang khách CĐ khi KK hoặc dịch vụ gặp lỗi.

### Biên nhận lưu và phục hồi

`khj_bl.customer_bridge_receipt` (migration pos 0027) giữ token, tài khoản, đích, fingerprint, CustID, trạng thái và kết quả. Biên nhận tách riêng với `customer_sync_receipt` của import CĐ. Lưu CustID ngay khi proc tạo trả mã; chỉ `complete=True` mới hiển thị thành công. Gửi lại cùng token/nội dung trả kết quả đã hoàn tất; token khác nội dung bị từ chối. Kết quả chưa rõ sau timeout/restart không được tự INSERT tiếp.

Màn hình lỗi giữ biểu mẫu và mã yêu cầu. Dùng `/camdo/khach-hang/ket-qua/<token>` để đọc lại biên nhận của chính tài khoản đang đăng nhập. Khi đã biết CustID, mở đúng hồ sơ đó để kiểm tra/hoàn tất; khi chưa biết thì đối soát biên nhận/PMV trước, không tạo khách mới để thay thế. Không khẳng định giao dịch nguyên tử giữa MSSQL và MySQL.

### Liên kết phiếu và bảo toàn dữ liệu cũ

- Bảng mới `khj_cd.khcd_pawn_customer`: `pawn_id → pmv_cust_id`, nguồn đối chiếu và thời điểm. Phiếu mới lưu CustID đã chọn cùng transaction tạo phiếu; không tạo khách hoặc ID giả trong `khj_cd.customer`.
- Phiếu cũ: lấy biên nhận sync hoàn tất trước; nếu không có, đối chiếu chính xác SĐT theo quy tắc ba cột chuẩn và khóa SĐT chủ hệ thống đã chọn. Chỉ ghép khi đúng một khách, không mâu thuẫn CCCD. Lưu dấu vết riêng `sync_receipt`, `phone_identity`, `unique_phone`; không coi ghép SĐT là chứng cứ xác thực danh tính.
- Đã thêm **18.474 liên kết / 18.832 phiếu**: 7.522 theo biên nhận sync, 2.634 trùng SĐT + tên/CCCD, 8.318 theo SĐT duy nhất. Còn **358 phiếu** (29 phiếu đang cầm): 305 thiếu/nhiều đối ứng PMV, 30 xung đột CCCD, 23 thiếu/nhiều khách nguồn CĐ. Xem `/camdo/phieu-cam-do?status=unlinked`. Không tự chọn ID đầu tiên cho các trường hợp này.
- Sau khi có liên kết, tên/SĐT/CCCD/địa chỉ trên giao diện phiếu được đọc KK bằng CustID; đổi SĐT khách không chuyển phiếu sang người khác. `pawn.phone` giữ nguyên làm dấu vết gốc, không ghi đè hàng loạt. Chưa có liên kết hoặc KK lỗi thì ghi rõ tình trạng, không lấy tên khách CĐ giả làm dữ liệu KK.
- Giữ nguyên bảng khách CĐ, bảng phiếu, số dư và nhật ký. Nguồn CĐ ngưng thêm/sửa qua KHCD; đường dẫn số cũ chỉ chuyển sang KK nếu xác định được một CustID. Không xóa bảng nguồn hoặc lịch sử.
- Script `scripts/link_customer_master.py` mặc định chỉ xem thống kê; `--apply` thêm liên kết chưa có, không đổi liên kết đã lưu. Trước thêm lưu bản chụp liên kết trong `backups/`; thống kê không chứa PII ở `output/customer-master-cutover.json`. Không chạy lại để tự xử lý mâu thuẫn danh tính.

Trước đưa UPSERT vào vận hành đã chạy backup PMV COPY_ONLY và VERIFY: `D:/KHJ_PMV_BACKUP/PMV_BANLE_KH2_20260914_1636.bak` (448 MB) trên KK. Không tạo/sửa khách thử hoặc hợp đồng thật để nghiệm thu; kiểm ghi thực hiện trên sandbox.

## Chạy ứng dụng

Máy hiện tại đã có môi trường `.venv` và cấu hình `.env`. Nhấp đúp `TURN_ON_KHCD.vbs` để chạy ẩn, hoặc:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

Tắt riêng ứng dụng này:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop.ps1
```

Đăng nhập web bằng **tài khoản và mật khẩu hiện tại của KHBL** (`admin`, `kimhanh2`, `ketoan` ở lần đồng bộ ngày 13/09/2026). `khj_admin` chỉ còn là tài khoản kết nối MySQL; mật khẩu web riêng trong phiên bản đầu đã ngừng sử dụng. Cấu hình, mật khẩu, bản sao lưu và dữ liệu riêng đều bị loại khỏi Git.

Waitress chỉ lắng nghe `127.0.0.1:8201`; Caddy phục vụ HTTPS cổng 8200 và chuyển tiếp vào Waitress. Script khởi động/tắt quản lý riêng hai tiến trình KHCD. Máy hiện tại dùng tác vụ Windows **KHCD Web Host** để giữ ứng dụng độc lập với phiên công cụ/terminal khởi chạy. Tác vụ chạy ẩn bằng tài khoản Windows hiện tại với quyền thường; kiểm tra HTTPS mỗi 15 giây và khởi chạy lại tiến trình bị dừng. Nhật ký phục hồi ở `instance/host.log`. `stop.ps1` dừng cả tác vụ lẫn ứng dụng để không tự bật lại sau thao tác tắt chủ động. Cookie đăng nhập bắt buộc Secure; phiên 8 giờ, CSRF cho mọi thao tác POST, giới hạn thử mật khẩu, tự động escape HTML và chặn nhúng từ website khác; riêng popup khách được nhúng cùng origin. Không bật debug. Chưa cấu hình tự chạy khi khởi động Windows; tác vụ chỉ chạy khi gọi script bật ứng dụng, cần phiên Windows đã đăng nhập.

Cài lại tác vụ trên máy chủ nếu cần: `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-windows-host.ps1` (Windows yêu cầu quyền quản trị khi đăng ký). Sau đó dùng script bật/tắt bình thường. Tham số `start.ps1 -Direct` dành cho tác vụ nội bộ hoặc xử lý sự cố.

## Giao diện và HTTPS trong LAN

- Topbar năm menu và footer đồng bộ phong cách BÁN LẺ; logo, bộ biểu tượng và font dùng chung từ KHBL. Mục **CẦM ĐỒ** dùng icon `pawn.png` do người dùng cung cấp. Nền đỏ ruby, điểm nhấn vàng, hiệu ứng chuyển động nhẹ và bố cục đáp ứng màn hình nhỏ. Nút **BÁN LẺ** mở địa chỉ `RETAIL_URL` trong `.env`.
- Caddy tại `ops/caddy/` dùng cùng CA nội bộ đã dùng cho BÁN LẺ. Cấu hình hỗ trợ `tiemvangkimhanh2`, `localhost`, `127.0.0.1`, `192.168.1.6`, `192.168.1.9` và tên máy `mrgiang`. CA/key riêng được giữ trong `instance/caddy-data/`, loại khỏi Git; không đưa khóa riêng sang máy khách.
- Máy chủ đã ánh xạ `tiemvangkimhanh2` tới `192.168.1.6`. Quy tắc Windows Firewall `KHCD-HTTPS-8200-LAN` chỉ cho phép TCP 8200 từ `LocalSubnet`; cổng 8201 vẫn chỉ truy cập được trên máy chủ.
- Máy LAN đã cấu hình tên và tin cậy CA của BÁN LẺ có thể mở thẳng **https://tiemvangkimhanh2:8200**. Máy mới: sao chép thư mục `LAN_HTTPS_KIT`, chạy `CAI_HTTPS_PC_LAN.bat` và chấp nhận yêu cầu quản trị Windows để thêm tên máy/chứng chỉ công khai. Xem `LAN_HTTPS_KIT/README.md`. Đã kiểm tra HTTPS qua địa chỉ LAN từ máy chủ; chưa thử trên một máy khách riêng.
- Nếu cần cấu hình lại máy chủ, chạy `powershell -NoProfile -ExecutionPolicy Bypass -File .\LAN_HTTPS_KIT\configure-lan.ps1 -Server`. Script lưu bản sao hosts và kết quả trong thư mục kit. Khi IP máy chủ đổi, cập nhật `$ServerIp` trong script và cấu hình tên trên các máy khách.

## Đăng nhập và đồng bộ tài khoản KHBL

- Nguồn duy nhất: `khj_bl.auth_user`. Đích: `khj_cd.auth_user`, cùng MySQL cổng 3308. Cấu hình tên CSDL nguồn bằng `AUTH_SOURCE_DB`.
- Sao chép ID, username, password hash Django, họ tên, email, cờ `is_active`/`is_staff`/`is_superuser`, ngày tham gia và `passcode`. Không giải mã, không đặt lại mật khẩu, không sửa dữ liệu tài khoản nguồn. Passcode chỉ đồng bộ dữ liệu, **không dùng thay mật khẩu để đăng nhập**.
- Lần đồng bộ đầy đủ đã thực hiện cho 3 tài khoản. Muốn đồng bộ lại toàn bộ:

```powershell
.\.venv\Scripts\python.exe scripts\sync_auth_users.py
```

- Script lưu bản chụp bảng đích trong `backups/auth_user_before_sync_*.json` trước khi chạy. Bản chụp chứa hash nhạy cảm và bị loại khỏi Git. Khi tài khoản bị xóa ở nguồn, tài khoản đích được khóa, không xóa mất thông tin lịch sử. Nếu ID/username xung đột, dừng và rollback thay vì gộp nhầm tài khoản.
- Mỗi lần đăng nhập, đồng bộ tài khoản đang nhập từ KHBL rồi kiểm tra mật khẩu bằng thư viện Django 5.2.17. Tài khoản mới ở KHBL tự được thêm vào KHCD khi đăng nhập lần đầu. Hiện hỗ trợ PBKDF2-SHA256, PBKDF2-SHA1 và scrypt; dữ liệu hiện tại đều dùng PBKDF2-SHA256.
- Mỗi yêu cầu đã đăng nhập đều kiểm tra lại tài khoản nguồn: đổi mật khẩu, khóa hoặc xóa tài khoản sẽ vô hiệu phiên ở yêu cầu tiếp theo. Tài khoản được mở khóa có thể đăng nhập lại. Nếu CSDL nguồn không truy cập được, không tiếp tục phục vụ dữ liệu hay xử lý tiền bằng trạng thái tài khoản cũ.
- Phiên lưu ID và chữ ký HMAC, không lưu password hash trong cookie. Cookie riêng `khcd_session` tránh trùng với ứng dụng khác. Phiên đăng nhập của cơ chế cũ không còn hợp lệ.
- `last_login` ở KHCD ghi thời điểm đăng nhập CẦM ĐỒ theo UTC, không ghi ngược về KHBL và không bị đồng bộ lại đè lên.
- Tất cả tài khoản `is_active=1` được dùng bốn trang nghiệp vụ hiện có. Cờ quản trị được giữ và hiển thị; **chưa ánh xạ các bảng nhóm/quyền riêng của Django sang phân quyền từng thao tác trong KHCD**. Nhật ký nghiệp vụ ghi đúng username người thực hiện.

## Chức năng bản đầu

- **Tổng quan:** dư nợ hiện tại; tiền thu, tiền chi, lãi đã thu trong ngày/tháng/khoảng chọn; biểu đồ 14 ngày; phiếu quá hạn, sắp đến hạn và giao dịch gần đây. Dư nợ tổng hợp tất cả hồ sơ cũ còn mở, kể cả các hồ sơ cần đối soát loại tài sản.
- **Cầm đồ** (`/camdo/lap-phieu`): bàn lập biên nhận theo bố cục PHP `gold/quan-ly-bien-nhan`, gồm phiếu mới trong ngày, biểu mẫu tiếp nhận và bản xem trước. Tìm khách bằng tên/SĐT/CCCD; thêm và chọn khách ngay trên trang; tính trọng lượng thực từng món, ngày hẹn, lãi dự kiến bằng số nguyên có tỷ lệ để tránh sai số làm tròn. Tìm/thêm khách không làm mất nội dung phiếu. Lỗi nghiệp vụ khi lưu trả lại biểu mẫu với nội dung đã nhập; CSRF và khóa chống gửi trùng tiếp tục áp dụng. Sau khi lưu, mở chi tiết để in biên nhận. Đường dẫn cũ `/phieu-cam-do/moi` chuyển tiếp sang `/camdo/lap-phieu`. Số liệu "Tiền cầm đã lập" phản ánh phiếu lập trong ngày, không phải dòng tiền ròng sau hủy/chuộc.
- **Phiếu cầm đồ:** tìm kiếm, phân trang, lọc trạng thái; lập phiếu với tối đa hai tài sản; xem/in biên nhận; sửa mô tả, vị trí két, ghi chú; tính tiền chuộc; gia hạn; hủy phiếu tạo bằng Python trong ngày nếu chưa có xử lý và đã thu hồi tiền giao khách.
- **Thống kê:** toàn bộ `pawn_log` cũ và mới theo ngày/khoảng chọn, lọc nghiệp vụ; nhật ký thay đổi bản Python có người xử lý và lý do. Thu/chi = tiền mặt (`total`) + chuyển khoản (`mbank`). Giao dịch tạo mới bằng Python hiện ghi nhận tiền mặt; chưa có phân tách phương thức thanh toán trên biểu mẫu mới.
- **Khách hàng:** nguồn KK duy nhất, tìm bằng ba SĐT/tên/CCCD, thêm/sửa đúng CustID qua service chuẩn KHBL; kiểm trùng, quyền và biên nhận lưu. Khách CĐ cũ ngưng ghi, vẫn giữ để truy vết.

## Quy tắc tính lãi

1. Cơ sở tính là **tiền cầm giao khách**, không phải giá trị định giá tài sản.
2. `lãi = tiền gốc × lãi suất phần trăm mỗi ngày × số ngày / 100`.
3. Hệ thống PHP cũ lưu `percent` theo **%/30 ngày**. Python đọc `percent / 30` để hiển thị %/ngày; phiếu mới lưu `daily_rate × 30`. Không đổi ý nghĩa cột cũ. Ví dụ `percent=3` là `0,1%/ngày`.
4. Tính chênh lệch ngày lịch tại Việt Nam, tối thiểu 1 ngày cho kỳ đầu, không cộng thêm ngày đầu và ngày cuối. Tham số `MIN_INTEREST_DAYS=1` nằm trong `.env`.
5. Gia hạn thu lãi đến hôm nay, giữ nguyên gốc/lãi suất, đặt lại ngày bắt đầu kỳ lãi và hẹn mới. Hạn mới phải sau hạn hiện tại, sau hôm nay, tối đa 365 ngày.
6. Không thu gia hạn hai lần trong cùng ngày. Nếu đã gia hạn rồi chuộc ngay cùng ngày, chỉ thu tiền gốc, không thu lại lãi.
7. Dùng `Decimal`, tính toàn kỳ rồi `ROUND_HALF_UP` đến đồng, không làm tròn lãi từng ngày. Không lãi kép, không tự thêm phí/phạt quá hạn. Mức lãi do người dùng nhập theo thỏa thuận; ứng dụng không tự đặt mức lãi mặc định và không xác nhận tính pháp lý của mức lãi.
8. Giao dịch thu/chi mới ghi nhận trong ngày hiện tại; chưa hỗ trợ nhập lùi ngày, cầm thêm, trả bớt, thanh lý hoặc xử lý phiếu báo mất trong bản này. Lịch sử các nghiệp vụ đó từ PHP vẫn được tra cứu.
9. Tiền gốc/lãi suất không sửa tùy ý sau khi lập phiếu. Mô tả, két, ghi chú sửa được và có nhật ký. Sửa sai tài chính cần quy trình đối soát hoặc hủy phiếu mới đủ điều kiện rồi lập lại.

## CSDL và tương thích dữ liệu cũ

Ứng dụng dùng các bảng `customer`, `pawn`, `pawn_log`, `gold_price`, `pawn_status`. Không nhập bản sao dữ liệu vào bảng nghiệp vụ mới. Liên kết điện thoại PHP được giữ làm dấu vết lịch sử. Luồng hiện hành dùng `khcd_pawn_customer.pmv_cust_id` để đọc khách KK; `khcd_pawn_meta.customer_id` còn giữ cho phiếu Python của giai đoạn trước.

Các bảng bổ sung:

- `khcd_event`: nhật ký, số tiền gốc/lãi, thời gian, người thao tác, dữ liệu trước/sau, khóa chống gửi trùng.
- `khcd_pawn_meta`: mã khách hàng gắn với phiếu tạo bằng Python.
- `khcd_customer_meta`: trạng thái lưu trữ.

Nâng cấp chuyển `customer`, `pawn`, `pawn_log` từ MyISAM sang InnoDB, chuyển tiền sang DECIMAL nguyên đồng, trọng lượng sang DECIMAL 4 chữ số thập phân, lãi suất tháng sang DECIMAL 8 chữ số thập phân và thêm chỉ mục tra cứu. Không đổi tên hay xóa cột cũ. Kiểm tra trước khi đổi kiểu tiền: nếu có số tiền lẻ dưới đồng, script dừng để đối soát thay vì âm thầm làm tròn.

Mã loại vàng cũ dùng `scut` (ví dụ `61`, `99`, `bk`, `sjc`), không dùng ID. Các giá trị lịch sử `18k`, `24k`, `99.99` được hiển thị rõ là dữ liệu cũ, không tự biến vàng 18K thành vàng 610. Danh mục `Khác` không được chọn trên phiếu mới. Một số phiếu cũ thiếu hồ sơ khách/loại vàng hoặc có tài sản ngoài phạm vi; giữ nguyên để rà soát.

Ghi tiền, cập nhật trạng thái và thêm lịch sử chạy trong một transaction. Khóa hàng `FOR UPDATE`, kiểm tra dấu vết phiên bản và khóa giao dịch duy nhất chặn thu trùng. Giao diện chỉ hiển thị thành công sau commit. Nếu mất kết nối đúng lúc commit, cần tra cứu lịch sử trước khi thử lại.

**Không dùng song song PHP để ghi cùng CSDL khi chuyển đổi hoặc trong vận hành bản Python.** PHP cũ không có các kiểm tra giao dịch/khóa chống gửi trùng của bản này. Trước mỗi lần nâng cấp, dừng ghi từ PHP và ứng dụng khác vào `khj_cd`.

## Sao lưu và nâng cấp lại

```powershell
.\.venv\Scripts\python.exe scripts\migrate.py
```

Script sao lưu SQL trước khi đổi cấu trúc, kiểm tra mã thoát và kích thước bản dump, kiểm tra số hồ sơ sau nâng cấp. Chạy lặp được. Một số tài khoản `khj_admin` không có quyền `RELOAD`; khi đó dùng cấu hình tài khoản sao lưu có quyền phù hợp:

```powershell
.\.venv\Scripts\python.exe scripts\migrate.py --backup-env DUONG_DAN_CAU_HINH_SAO_LUU
```

Tài khoản sao lưu chỉ dùng cho `mysqldump`; nâng cấp vẫn thực hiện bằng tài khoản trong `.env`. Script kiểm tra hai cấu hình trỏ cùng host, cổng và CSDL. Bản sao lưu nằm trong `backups/`, chứa dữ liệu thật và cần giữ riêng. Không tự khôi phục đè lên dữ liệu đang vận hành. Khôi phục vào một CSDL khác để kiểm tra trước rồi thực hiện chuyển đổi có kiểm soát.

## Cài ở máy khác

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\setup.py
```

Điền kết nối MySQL và `AUTH_SOURCE_DB=khj_bl` trong `.env`, chuẩn bị CSDL cũ, sao lưu/nâng cấp, chạy `scripts/sync_auth_users.py`, rồi khởi động. `setup.py` không ghi đè cấu hình đã tồn tại. Đường dẫn mặc định `mysqldump` trong script dành cho máy này; dùng `--dump-exe` nếu thay đổi vị trí.

Khi chuyển máy chủ, cần cài Caddy, sửa đường dẫn storage tuyệt đối trong `ops/caddy/Caddyfile`, chuyển CA riêng bằng kênh quản trị an toàn và cấu hình lại IP/tên LAN. Không dùng bộ kit máy khách để thay thế CA của máy chủ. `.env` chạy Waitress với `APP_PORT=8201`, `COOKIE_SECURE=1`; địa chỉ người dùng vẫn là HTTPS cổng 8200.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Kiểm thử tích hợp MySQL cần `KHCD_TEST_ENV` trỏ cấu hình có quyền tạo/xóa CSDL thử, trong đó `DB_NAME=khj_cd` để lấy cấu trúc nghiệp vụ. Mỗi lượt tạo thêm CSDL nguồn tài khoản giả `<tên_CSDL_thử>_auth`, không dùng tài khoản KHBL thật để thử mật khẩu. Chỉ sao chép cấu trúc, tạo hồ sơ giả trong CSDL `khcd_test_<ngẫu nhiên>`, tự xóa CSDL thử sau khi kết thúc; không ghi hồ sơ thử vào `khj_cd`.

```powershell
$env:KHCD_TEST_ENV='DUONG_DAN_CAU_HINH_THU'
.\.venv\Scripts\python.exe -m pytest -q
```

Các kiểm thử quan trọng: đăng nhập bằng hash Django, đồng bộ lặp, tài khoản nhân viên, khóa/đổi mật khẩu/xóa ở nguồn, thu hồi phiên cũ, lỗi nguồn, xung đột ID, giới hạn thử mật khẩu; lãi cũ/tháng sang ngày, ngày nhuận, làm tròn, gia hạn rồi chuộc cùng ngày, tạo/chuộc gửi trùng, hai yêu cầu chuộc đồng thời, rollback khi ghi audit lỗi, hủy hoàn lại dòng tiền, CSRF, đăng nhập, escaping và chế độ chỉ đọc.

Giai đoạn chỉ đọc trước chuyển nguồn, ngày 14/09/2026: **51 kiểm thử đạt**, gồm chuẩn hóa định danh chỉ để so sánh, nhiều ứng viên, xung đột CCCD, hai tab/so sánh không sửa hồ sơ, chặn POST và truy cập chưa đăng nhập, XSS escaping, lỗi PMV không biến thành khách thiếu, và chặn kết nối PMV thật khi TESTING. Giao diện được kiểm tra bằng hồ sơ giả trong CSDL thử riêng; không tạo hồ sơ thử trong nguồn vận hành.

### Kiểm chuyển nguồn KK / UPSERT ngày 14/09/2026

- 55 kiểm thử KHCD đạt; 51 kiểm thử KHBL/service đạt (gồm 8 ca bridge), dùng CSDL thử riêng.
- Đã kiểm INSERT thật trên sandbox, replay cùng token trả cùng CustID, UPDATE theo mã và giữ trường không gửi; service trả complete sau đọc kiểm. Không ghi thử khách KK.
- Dọn khách sandbox: proc DELETE vendor gọi OLE đang bị tắt; dùng nhánh dọn đúng ID qua allowlist sandbox như smoke chuẩn. Đã xác nhận xóa đúng khách thử và hai biên nhận; không bật OLE.
- Hai smoke chuẩn phone/sync được chạy lúc đầu có giao nhau: kiểm ba SĐT/CCCD và dữ liệu sync đạt, nhưng ca tranh khóa bị timeout an toàn và phép so tổng dòng bị nhiễu bởi smoke kia. Không ghi nhận hai lệnh đó là PASS toàn bộ; dữ liệu thử đã dọn. Khi chạy lại các smoke có kiểm tổng dòng phải chạy tuần tự.
- Đã kiểm UI danh sách/hồ sơ/popup ba SĐT, lỗi lưu giữ phiếu nháp và màn hình 390px; kiểm GET trên nguồn thật cho danh sách, hồ sơ, lập phiếu, danh sách/chi tiết phiếu, tổng quan và danh sách chưa nối. HTTPS localhost/LAN và customer_service đều OK.

## Các bước phát triển tiếp

### Chốt SQL tối giản và chuyển từng phiếu — 14/09/2026

Chỉ thêm **4 bảng**: `cd_loans`, `cd_loan_items`, `cd_loan_logs`, `cd_payments`; tái sử dụng `pawn_status` cho nghiệp vụ, nhật ký và ảnh có sẵn. `cd_loans` giữ cả `phone` cũ và `cust_id` tham chiếu KK. Trạng thái phiếu tách khỏi nghiệp vụ gần nhất; báo mất biên nhận là cờ riêng. Các nguyên tắc tính lãi theo đoạn, tách gốc/lãi/thu/chi, tài khoản khách/tiệm, nhân viên/user và bảo toàn lịch sử tiếp tục theo đề xuất đã duyệt.

Trang Phiếu cầm đồ có popup **CHUYỂN ĐỔI** cho quản trị viên: đối soát từng phiếu, lỗi chi tiết, xác nhận, chuyển nguyên tử và đọc kiểm; chặn trùng, sai lệch và thay đổi sau xem trước. Bản chuyển ở trạng thái **STAGED, chờ tiếp quản**; hệ thống vẫn ghi nghiệp vụ vào `pawn`, không cộng trùng số liệu mới vào báo cáo. Chưa chuyển phiếu thật tự động. Xem [thiết kế, cách chuyển và giới hạn](docs/CHUYEN_DOI_SQL.md).

**Bổ sung chuyển hàng loạt:** nút CHUYỂN ĐỔI đầu trang mở danh sách tất cả phiếu đang cầm (status 1/2/3/4/7), tải hết danh sách và hiển thị 50 phiếu/trang. Bấm đối soát tất cả phiếu chưa chuyển → xem lỗi/lưu ý → chọn các phiếu đạt → tick xác nhận → chuyển N phiếu. Mỗi phiếu có transaction và kết quả riêng; phiếu lỗi hoặc đã chuyển không được chọn. Có dừng sau phiếu hiện tại; giữ popup mở khi chạy. Mất kết nối chưa xác định kết quả thì dừng, tải lại/đối soát trước khi tiếp tục. Phiếu hoàn tất được giữ, gửi lại không tạo trùng. Nút ở từng dòng vẫn hỗ trợ chuyển đơn. Không thêm bảng SQL, không tự sửa nguồn hay tiếp quản nghiệp vụ.

**Sau đồng bộ/import SQL cũ:** cần giữ engine InnoDB và các cột tiền/trọng lượng DECIMAL của KHCD. Import kèm CREATE TABLE từ PHP có thể đưa `pawn`, `pawn_log` về MyISAM và số thực, làm mất khả năng rollback. Không bỏ chặn giao dịch; sao lưu rồi chạy `.venv\Scripts\python.exe scripts\migrate.py` từ `D:\PYTHON\KHCD`. Script sao lưu bằng READ lock các bảng trong chính CSDL, không cần mở thêm quyền RELOAD toàn máy chủ. Bước đối soát nay báo rõ bảng nào thiếu hoặc dùng sai engine trước khi cho phép chọn chuyển.

Đã xử lý lần tái nhập ngày 14/09/2026: khôi phục InnoDB/DECIMAL và index; backup `backups\khj_cd_20260914_225951.sql`. Giữ 18.858 phiếu, 51.173 dòng lịch sử, 7.547 khách cũ, 981 phiếu đang cầm và 1 bản đã chuyển. Checksum 11 bảng trước/sau khớp khi chuẩn hóa theo kiểu số đích; không chuyển phiếu thật để thử. Sau sửa cấu trúc phải tải lại danh sách và đối soát lại để lấy review_hash mới.

### BIÊN NHẬN và tái sử dụng ảnh — 14/09/2026

**Ngoại lệ chuyển đổi đã duyệt (14/09/2026):** popup chuyển đơn/hàng loạt có ô **Cho phép lỗi đã duyệt**, mặc định tắt. Bật lên chỉ hạ ba nhóm lỗi `CUSTOMER` (CustID KK), `CASHFLOW` (tiền thu/chi, gồm trường hợp Log #47063), `ITEM_COUNT` (không phân tách được món) thành cảnh báo có ghi nhận. Mọi phiếu chọn trong chế độ này phải có ít nhất một giao dịch `pawn_log.date2` trong 6 tháng lịch gần nhất theo giờ Việt Nam, gồm ngày đầu kỳ, loại ngày tương lai. Không dùng ngày hẹn hoặc ngày trên `pawn` thay lịch sử; không dùng 180 ngày thay 6 tháng. Tắt tùy chọn giữ quy trình đối soát nghiêm ngặt cũ.

- Bật/tắt tùy chọn xóa kết quả và lựa chọn cũ, phải đối soát lại. Máy chủ kiểm lại nguồn, điều kiện ngày và chế độ trước mỗi lần ghi; không thể dùng kết quả đối soát của chế độ khác.
- Giữ SĐT, liên kết CustID đã có và toàn bộ nguồn thô; thiếu CustID thì để rỗng, không tìm/ghép khách theo SĐT, không UPSERT KK. Giữ nguyên tiền thu/chi sai lệch; không sửa gốc, lãi hoặc tự cân tiền. Không tạo món vàng giả cho tài sản KHÁC; mô tả cũ còn trong `legacy_json` và hiện trong BIÊN NHẬN khi chưa có dòng món.
- Lưu quy tắc, ngày bắt đầu kỳ/ngày kiểm tra, ID/thời điểm giao dịch đủ điều kiện và từng lỗi đã chấp nhận trong `cd_loans.terms_json.conversion_exceptions`, kèm nhật ký `khcd_event`. Người xác nhận/thời điểm dùng các cột chuyển đổi sẵn có. Không thêm bảng/cột SQL.
- BIÊN NHẬN hiển thị ngoại lệ đã nhận. Đối soát về sau chỉ giữ cảnh báo cho lỗi đúng bản đã chấp nhận khi checksum nguồn/đích còn khớp; nguồn thay đổi phải báo lỗi lại. Điều kiện 6 tháng được lưu tại lúc chuyển, không làm bản chuyển cũ tự mất hiệu lực sau này.
- Thiếu lịch sử/mở đầu, sai dư gốc, thiếu SĐT, sai trọng lượng, lỗi ngày/số, mất kết nối KK và lỗi khác vẫn chặn. Chấp nhận chuyển dữ liệu không xác nhận sai lệch đã được sửa; bản chuyển tiếp tục STAGED.

Kiểm chứng bản ngoại lệ: **141 kiểm thử đạt** trên CSDL thử riêng, gồm biên 6 tháng lịch/ngày nhuận/ngày tương lai, kiểm lại lúc POST, đổi chế độ, các lỗi vẫn chặn, bảo toàn dữ liệu và audit, chống trùng, đối soát về sau và phát hiện sai lệch mới. Popup thử đã chuyển 3 phiếu giả (một phiếu có đủ 3 ngoại lệ), khóa phiếu quá cũ; giao diện đơn/hàng loạt kiểm ở 390 px. HTTPS localhost/LAN 8200 và kết nối khách KK hoạt động. CSDL thử đã dọn; không xác nhận chuyển phiếu vận hành trong lượt kiểm thử này.

- Menu **BIÊN NHẬN**: `/camdo/bien-nhan`, chỉ liệt kê `cd_loans`; tìm mã, tên khách tại lúc chuyển, SĐT cũ hoặc CustID; lọc trạng thái. Chi tiết `/camdo/bien-nhan/<id>` hiển thị món, lịch sử nghiệp vụ, dòng tiền và hồ sơ ảnh từ bản chuyển.
- Đối soát chỉ đọc: kiểm checksum đích, nguồn hiện tại, liên kết khách KK, các trường phiếu, từng món/log/dòng tiền, thiếu ảnh hoặc ảnh MySQL bị thay đổi. Báo riêng lỗi và cảnh báo; không tự sửa, chuyển thêm phiếu hoặc ghi KK. Tài khoản nhân viên được tra cứu, quyền chuyển đổi vẫn dành cho quản trị.
- **Ảnh cũ tái sử dụng được nếu còn tệp gốc.** Giữ `documents_json` tham chiếu tên ảnh PHP và ảnh trong `khcd_pawn_photo`; webapp phục vụ ảnh qua route có đăng nhập, không nhân bản BLOB hoặc đưa CCCD vào static công khai. Biến `.env` `LEGACY_PAWN_IMAGE_ROOT` hiện trỏ đến `D:/PYTHON/KHCD/media/pawn`. Thiếu tệp hiện cảnh báo rõ, không suy luận đã có đủ ảnh chỉ từ tên tệp.
- Kiểm tra thực tế thấy một biên nhận đã được chuyển trước lượt triển khai mục này; hai tên ảnh của bản chuyển chưa có trong thư mục PHP mặc định đã kiểm tra. Cần xác định kho ảnh gốc đầy đủ để cấu hình đường dẫn. Không kết luận ảnh đã mất, không tự thay ảnh hoặc sửa tham chiếu.
- Về sau: sao lưu/mirror nguyên kho ảnh sang thư mục hồ sơ riêng của KHCD, kiểm số lượng và checksum rồi đổi cấu hình thư mục. Giữ nguyên tên tệp và route xem ảnh nên không cần sửa hàng loạt phiếu; bổ sung checksum tệp cũ sau khi xác nhận đúng nguồn. Không xóa kho cũ trước khi đối soát và sao lưu hoàn tất. Dữ liệu BLOB hiện có vẫn dùng trực tiếp; chỉ di chuyển riêng khi có nhu cầu dung lượng.

1. Đối soát phiếu cũ thiếu thông tin, số điện thoại trùng và tài sản ngoài phạm vi; ánh xạ khách hàng bằng ID cho toàn bộ lịch sử.
2. Mở rộng chuyển khoản cho khâu thu tiền chuộc/gia hạn; cầm thêm/trả bớt theo từng kỳ lãi và phân quyền nghiệp vụ nhân viên.
3. Mã túi/két, kiểm kê vàng, mẫu in theo biểu mẫu tiệm và sao lưu định kỳ.

## Bàn lập phiếu 3 cột — 14/09/2026

- `/camdo/lap-phieu`: trái là nghiệp vụ theo `pawn_status.sort`, giữa là phiếu/khách/món vàng/thanh toán, phải là 2 ảnh vàng và ảnh QR ngân hàng khách. Khoảng cách nội dung thu gọn 3–6 px; CCCD trước/sau nằm ngay cạnh ô tìm khách, mỗi ảnh có một hàng Chọn/Chụp/Cắt/X.
- Mã biên nhận nhận nhập bàn phím, máy quét hoặc QR qua ảnh/camera. Chỉ mở đúng mã hoặc đường dẫn chi tiết nội bộ; không tìm gần đúng. Mở phiếu đã lưu sẽ khóa thông tin, dòng món và ảnh, bật các nút nghiệp vụ khi phiếu đang hoạt động. Nút Cầm mới trở về bản nháp. Popup nghiệp vụ hiện chỉ xem thông tin; xác nhận và xử lý tiền tiếp tục phát triển sau.
- Khách chọn từ KK `I_CUSTOMER` theo SĐT/CCCD/tên, liên kết bằng CustID, hiển thị rút gọn. Nút X bỏ lựa chọn; nút chữ Thêm khách và Sửa hồ sơ giữ popup KHBL qua bridge. Không còn lịch sử khách tại bàn lập phiếu. Đổi khách xóa thông tin tài khoản/QR của khách trước để tránh chi nhầm.
- Nhân viên tiếp nhận chọn từ KK `T_EMPLOYEE` đang hoạt động. Tài khoản thao tác vẫn được ghi riêng trong nhật ký.
- Tối đa 30 dòng món; nhập trọng lượng tổng/hột, máy chủ tính lại TL vàng và giá trị. Giá/chỉ và tạm tính được ẩn trên UI nhưng vẫn tính theo giá danh mục. Nội dung tự ghép `[LOẠI] mô tả TLc/g`; tiền cầm vượt tổng định giá hiển thị cảnh báo. Phiếu PHP cũ chưa lưu định giá hiển thị Chưa lưu định giá, không tự gán giá hôm nay vào lịch sử.
- Chọn 3 / 2,5 / 2 / 1,5 / 1 % mỗi tháng; mặc định 30 ngày. Lưu chính xác lãi suất tháng vào `pawn.percent`, giữ công thức gốc: gốc × % tháng × số ngày / 3000, làm tròn đồng ở cuối kỳ. Ngày hẹn = ngày lập + kỳ hạn; không nhập lùi ngày lập.
- Chi tiền mặt, chuyển khoản toàn bộ hoặc kết hợp; `pawn_log.total` là phần tiền mặt âm, `mbank` là phần chuyển khoản âm. Tổng hai khoản bằng âm tiền cầm. Đây là ghi nhận khoản đã chi, không phát lệnh chuyển tiền ngân hàng. Hủy phiếu lập nhầm trong ngày hoàn lại đúng cơ cấu chi gốc theo điều kiện hiện có.
- Phương thức chọn bằng radio. Chuyển khoản mặc định bằng tiền cầm, cho nhập lại phần tiền mặt/chuyển khoản, tổng luôn phải bằng tiền cầm và máy chủ kiểm lại. Nội dung mặc định `THANH TOÁN TIỀN VÀNG1`. VietQR dùng bộ đọc chuẩn KHBL, kiểm CRC và loại QR chuyển tới tài khoản; đọc ngân hàng/số tài khoản/tên nếu có. Không tự đoán tên chủ tài khoản khi QR thiếu tên. Ảnh QR được giữ trong hồ sơ phiếu (`anh_qr`).
- Phân luồng tài khoản nhận: Cầm mới/Cầm thêm (CHI) dùng ngân hàng khách; Trả bớt/Gia hạn/Chuộc (THU) dùng danh mục đang bật `khj_bl.gold_bank`, ưu tiên `type=pawn`. Nếu chưa có cấu hình pawn, không tự chọn tài khoản bán lẻ. Popup chỉ đọc danh mục, không chuyển tiền hoặc ghi nghiệp vụ.
- Ảnh dùng camera, chọn tệp và cắt CCCD nguyên bản KHBL. Chuẩn hóa JPEG/EXIF/giới hạn 15 MB qua service ảnh chuẩn; không tự UPSERT hồ sơ khách khi lưu ảnh phiếu. Ảnh hồ sơ KK hiện có dùng để xem/cắt; ảnh mới chọn/chụp/cắt được gắn vào phiếu khi Lưu.
- `khcd_pawn_desk` lưu đầy đủ các món, nhân viên tiếp nhận, cơ cấu chi và nội dung. Hai món đầu vẫn phản chiếu vào cột `pawn.gold1/.../gold2/...` để đọc tương thích; hệ PHP cũ không quản lý các món thứ 3 trở đi. `khcd_pawn_photo` lưu ảnh JPEG theo `(pawn_id,kind)`; chỉ tải qua route có đăng nhập, không đưa ảnh CCCD vào thư mục công khai.
- Phiếu, liên kết CustID, phần mở rộng, ảnh, dòng tiền và nhật ký lưu trong cùng một giao dịch MySQL. Lỗi chuẩn bị ảnh xảy ra trước khi ghi phiếu; lỗi ghi giữa chừng rollback toàn bộ. Gửi lại cùng request_key không tạo phiếu mới.
- Nút Xóa ở bàn lập phiếu chỉ xóa bản nháp. Phiếu đã ghi tiền dùng nghiệp vụ Hủy có kiểm tra, không xóa cứng. In được mở từ trang biên nhận sau khi lưu; bản in hiển thị đủ các món.
- Nâng cấp thêm hai bảng bằng `.venv\Scripts\python.exe scripts\migrate_desk.py`: sao lưu MySQL trước, chỉ CREATE TABLE IF NOT EXISTS, không sửa dữ liệu `I_CUSTOMER` hoặc phiếu cũ. Bản nháp giữ trong trang hiện tại, không lưu CCCD vào localStorage.

Kiểm tra bàn lập phiếu: 86 kiểm thử KHCD + 28 kiểm thử popup/service KHBL đạt trên CSDL thử riêng; sau các tinh chỉnh cuối đã chạy lại 38 ca liên quan, đều đạt. Kiểm giao diện 1280 px và 390 px: thêm món, tổng hợp nội dung, số tiền bằng chữ, lãi suất tháng, tiền mặt/chuyển khoản, tìm/chọn khách, popup khách giữ bản nháp, lỗi cắt khi chưa có ảnh, xác nhận Xóa bản nháp. Không lưu thử khách hoặc phiếu cầm vào nguồn vận hành; camera vật lý chưa chụp thử. HTTPS localhost và tên LAN kiểm tra thành công. Bản sao lưu trước mở rộng: `backups/khj_cd_desk_20260914_181950.sql`.

Kiểm tra bản thu gọn: 98 kiểm thử KHCD và 31 kiểm thử KHBL đạt. Kiểm UI máy tính và 390 px: tìm/chọn khách, cảnh báo vượt định giá, cơ cấu tiền mặt/chuyển khoản, VietQR dữ liệu giả, mở đúng phiếu cũ và khóa sửa/xóa món/ảnh, popup THU chọn đúng type=pawn và popup CHI dùng nguồn tài khoản khách. HTTPS localhost/LAN và bridge hoạt động; không ghi thử khách hoặc phiếu vào nguồn vận hành. Camera vật lý chưa chụp thử; giải mã ảnh QR và cắt CCCD được kiểm bằng ảnh giả qua bộ xử lý chuẩn.
