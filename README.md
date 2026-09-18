# KHCD — Quản lý cầm vàng Kim Hạnh

Ứng dụng Python/Flask dùng trực tiếp MySQL `khj_cd` trên `127.0.0.1:3308`, tài khoản CSDL `khj_admin`. Web chạy tại **https://tiemvangkimhanh2:8200** trong LAN hoặc **https://localhost:8200** trên máy chủ. Địa chỉ HTTP cũ tự chuyển sang HTTPS cùng cổng.

## Thư mục chính duy nhất — chốt ngày 14/09/2026

**Dự án CẦM ĐỒ Python đặt tại `D:\PYTHON\KHCD`. Mọi phát triển, khởi động, cấu hình và sao lưu tệp dự án đều thực hiện tại đây.** Không tạo hoặc vận hành thêm bản dự án tại `Documents\ChatGPT`. Bản trước khi chuyển chỉ giữ làm bản sao lưu tại `backups\source-before-relocation-20260914`, không dùng để chạy ứng dụng.

- Mã nguồn: `khcd`; Python riêng: `.venv`; cấu hình: `.env`; bản sao lưu SQL: `backups`.
- Vận hành bằng 3 tệp ở gốc dự án, giống nếp KHJ/KHBL (16/09/2026): **`TURN_ON_KHCD.bat`** · **`TURN_OFF_KHCD.bat`** · **`RESET_KHCD.bat`** (sửa tệp `.py` thì RESET; sửa `.html/.css/.js` chỉ cần F5). Gọi qua PowerShell: `cmd /c D:\PYTHON\KHCD\RESET_KHCD.bat`. `TURN_ON_KHCD.vbs` nay chỉ là vỏ chạy ẩn của `TURN_ON_KHCD.bat`. Logic bật/tắt vẫn nằm nguyên ở `scripts\start.ps1` / `scripts\stop.ps1` — 3 tệp `.bat` chỉ thêm: chờ dịch vụ MySQL80, kiểm tác vụ Windows có thật hay không (không có thì bật tách qua WMI để tiến trình không chết theo app gọi lệnh), và **tự đo lại sức khỏe ở CẢ cổng 8200 lẫn 8201** bằng `scripts\kiem_khcd.ps1` (tệp CHỈ ĐỌC; `-Viec chu-cong` cho biết ai đang giữ cổng). Lý do phải đo cả hai: Caddy vẫn giữ 8200 khi backend đã chết — lúc đó mọi trang trả 502 mà nhìn cổng thì tưởng vẫn tốt.
- Từ 16/09/2026 KHCD nằm trong chuỗi khởi động toàn hệ: `D:\PYTHON\KHJ\KHOI_DONG_TOAN_HE_THONG.bat` bước `[G]` gọi `TURN_ON_KHCD.bat`, `RESET_TOAN_HE_THONG.bat` bước `[2b]` gọi `TURN_OFF_KHCD.bat`, và bảng kiểm sức khỏe có thêm 3 mục cổng 8200 / 8201 / 18202. Trước đó KHCD không có đường lên nào khi khởi động lại máy (tác vụ Windows không có trigger) mà bảng kiểm vẫn báo "TOÀN HỆ THỐNG OK".
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

Máy hiện tại đã có môi trường `.venv` và cấu hình `.env`. Nhấp đúp `TURN_ON_KHCD.vbs` để chạy ẩn, hoặc gọi 3 tệp vận hành (đường dùng hằng ngày — chúng gọi lại chính `start.ps1`/`stop.ps1` bên dưới):

```powershell
cmd /c D:\PYTHON\KHCD\TURN_ON_KHCD.bat
```

Tắt riêng ứng dụng này (đặt cờ `instance\host.stop` + kết thúc tác vụ trước, rồi mới tắt tiến trình, cuối cùng đo lại 3 cổng và nói rõ **ai** còn giữ cổng):

```powershell
cmd /c D:\PYTHON\KHCD\TURN_OFF_KHCD.bat
```

Bật lại sau khi sửa tệp `.py` — kiểm đủ điều kiện **trước** khi tắt, và tắt không sạch thì **không** bật lại (tiến trình cũ còn giữ cổng 8201 sẽ khiến `start.ps1` bỏ qua, mã `.py` cũ chạy tiếp mà không ai báo lỗi):

```powershell
cmd /c D:\PYTHON\KHCD\RESET_KHCD.bat
```

Xem ai đang giữ cổng / đo sức khỏe mà không đụng gì (chỉ đọc):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\kiem_khcd.ps1 -Viec chu-cong
```

Hai script gốc vẫn dùng trực tiếp được khi cần xử lý sự cố:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start.ps1
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

Nhận QR CCCD tại ô tìm khách: chuỗi phân cách `|` có số CCCD 12 chữ số ở trường đầu và ngày cấp 8 chữ số ở trường cuối được rút về số CCCD trước khi tìm. Không dùng các chữ số trong tên/địa chỉ bị lỗi font, không tự chọn/gộp/sửa hồ sơ; phần giải mã đầy đủ tên/ảnh vẫn dùng popup chuẩn KHBL. Máy chủ kiểm lại bằng `customer_lookup.lookup_key`; chuỗi chưa đủ/sai định dạng báo lỗi, không tìm bằng toàn bộ RAW. Gõ/quét trong ô tìm khách chưa làm bản nháp thay đổi; chọn khách hoặc nhập dữ liệu phiếu vẫn bảo vệ nháp như trước.

Khắc phục tải giao diện cũ: bật `TEMPLATES_AUTO_RELOAD` khi chạy Waitress; đổi phiên bản tài nguyên cho form mới. Dùng `scripts/start.ps1 -Direct -RestartBackend` khi cập nhật Python để dừng đúng backend, chờ tiến trình cũ thoát rồi khởi động lại. Nếu tab vẫn giữ trang cũ vì đang bảo vệ bản nháp, không tự bỏ dữ liệu đang nhập; lưu/giữ hoặc xác nhận bỏ nháp theo trạng thái thực tế. Phiên đăng nhập hết hạn cần đăng nhập lại. Đã kiểm 46 ca liên quan và chuỗi QR mẫu rút đúng số CCCD.

Cập nhật tủ/ô khách 15/09/2026: chọn `safe=1` → Tủ 18k (mặc định), `2` → Tủ 24k, `3` → Tủ đồ lớn. Khi mở phiếu cũ, mã ngoài danh sách vẫn hiển thị riêng, không tự đổi thành tủ khác. Cụm nút nằm trên ô tìm khách: chưa chọn hiện `+`; đã chọn hiện `X` trước `SỬA`. Sửa truyền đúng CustID vào popup KHBL dùng chung; bỏ chọn xóa CustID của nút sửa và trả về nút thêm. Giữ cơ chế khóa phiếu đã lưu/chỉ đọc. Đã kiểm 35 ca liên quan, giao diện desktop/mobile và đường dẫn popup thêm/sửa bằng hồ sơ giả.

Popup **DANH SÁCH phiên giao dịch** (15/09/2026): bấm chữ DANH SÁCH phía trên các nút nghiệp vụ để mở, mũi tên cạnh bên vẫn thu gọn bảng. Mặc định d1=d2=hôm nay; tìm SĐT cũ hoặc tên/CCCD/SĐT hiện tại qua `search_ids` KK và CustID đã liên kết. Mỗi dòng là một `pawn_log`, không gộp các lần giao dịch của cùng phiếu. Lọc theo `date2`, thiếu thì dùng `date1` và hiện lưu ý. Phân trang 50 dòng; footer tính toàn bộ kết quả lọc: số phiên, tổng thu, tổng chi, lãi ghi nhận, tiền mặt/CK ròng và số phiên theo từng nghiệp vụ. Bảo toàn dấu và số tiền cũ, không tính lại lịch sử. Nút MỞ dùng luồng tra phiếu hiện có, tải thông tin hiện tại và khóa sửa; có xác nhận trước khi thay bản nháp. API GET `/camdo/lap-phieu/phien-giao-dich` yêu cầu đăng nhập, không ghi dữ liệu. Nguồn phiên vẫn là `pawn_log` trong giai đoạn STAGED; không cộng trùng với `cd_loan_logs`.

Cập nhật bảng nghiệp vụ 15/09/2026: dùng ảnh có sẵn tại `khcd/static/img/ico` theo ánh xạ Cầm mới → `cammoi.png`, Chuộc đồ → `chuocdo.png`, Gia hạn → `gianhan.png`, Cầm thêm → `camthem.png`, Trả bớt → `trabot.png`, Báo mất → `matgiay.png`, Thanh lý → `thanhly.png`. Thẻ đỏ vàng cho trạng thái active, icon giảm màu và dấu khóa khi disabled; có hover, focus bàn phím và hỗ trợ giảm chuyển động. Desktop xếp dọc; tablet 4 cột và mobile 3 cột, có thu gọn bảng. CSS riêng `desk-actions.css`; giữ thứ tự `pawn_status.sort`, mã nghiệp vụ, điều kiện bật/tắt và xử lý popup cũ. Đã kiểm đủ 7 ảnh, mở phiếu để bật nghiệp vụ, popup Cầm thêm và bố cục 390 px trên CSDL thử riêng.

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


### Quầy lập phiếu — CHỐT TIỀN (15/09/2026)
- `/camdo/lap-phieu`: cột giữa giữ thông tin biên nhận, khách, món hàng và ảnh hồ sơ (hai ảnh vàng + QR khách); nút IN PHIẾU đặt cuối giữa. Hai ảnh CCCD vẫn cạnh khách.
- Cột phải CHỐT TIỀN chứa số tiền/thành chữ, lãi suất, số ngày/ngày hẹn, ghi chú phiên và toàn bộ phương thức thanh toán. Xác nhận thành công giữ phiếu tại quầy ở chế độ khóa, có thể xem/in.
- XÓA với bản nháp chỉ xóa nội dung đang nhập. Với phiên Cầm mới đã lưu: chỉ cho hủy trong 300 giây từ thời điểm tạo `khcd_event`, còn trạng thái cầm mới và duy nhất một log mở đầu khớp gốc/tiền. Không áp dụng phiếu nguồn cũ không đủ nhật ký hoặc đã có nghiệp vụ tiếp theo.
- Hủy cần lý do và xác nhận thu hồi đủ tiền. Máy chủ kiểm tra lại trong transaction có khóa, chống gửi lặp, ghi đảo đúng tiền mặt/chuyển khoản, giữ biên nhận và audit. Đây là ghi nhận hoàn tiền đã thu hồi thực tế, không tự chuyển tiền qua ngân hàng.
- Ghi chú khi tạo được lưu vào cả phiếu và sự kiện create. Khi bắt đầu bản nháp kế tiếp sinh request_key mới.
- Các popup Cầm thêm/Trả bớt/Gia hạn/Chuộc/Thanh lý/Báo mất trên quầy vẫn đang chờ triển khai xử lý; không dùng nút XÓA này để đảo những nghiệp vụ đó.
- Kiểm thử: 169 tests đạt trên CSDL tách biệt; trình duyệt thử xác nhận, khóa/in, hủy và bố cục 390px. Không ghi giao dịch thử vào dữ liệu đang hoạt động.


### Tiếp quản vận hành bằng cd_loans — 15/09/2026 (thay thế mô hình STAGED ở trên)
- Từ bản này `CD_LIVE=1`: quầy lập phiếu, nghiệp vụ, tra phiếu/QR, danh sách phiên, Tổng quan, Thống kê, lịch sử theo CustID và in biên nhận sử dụng SQL mới. Không ghi `pawn`/`pawn_log` nữa. Menu PHIẾU CŨ chỉ xem, đối soát và chuyển đổi có kiểm tra.
- Bốn bảng: `cd_loans` (trạng thái, dư gốc, khách/nhân viên/điều khoản), `cd_loan_items` (mọi dòng tài sản), `cd_loan_logs` (nghiệp vụ + ảnh chụp trạng thái trước/sau + người thao tác), `cd_payments` (thu/chi riêng tiền mặt/chuyển khoản). Legacy IDs cho phép NULL ở phiếu/phiên mới. `version` chống ghi đè; request_key và reverses_log_id có UNIQUE chống ghi lặp/đảo lặp.
- Ảnh mới: `D:\PYTHON\KHCD\media\loans`, tệp tên ngẫu nhiên bất biến; documents_json lưu tên, kích thước và SHA256, truy cập qua route yêu cầu đăng nhập. Sao lưu thư mục này cùng SQL. Nếu kết quả commit không xác định, giữ tệp có thể chưa được tham chiếu để tránh mất ảnh của phiếu đã commit. Ảnh cũ tiếp tục dùng kho media/pawn hoặc BLOB cũ, không sao chép hàng loạt.
- Xác nhận phải qua tính/đối chiếu phía máy chủ; transaction khóa phiếu, kiểm tra fingerprint và tổng tiền, sau đó ghi log + payment và cập nhật dư gốc. Có lỗi ghi thì rollback. Không tự thực hiện chuyển tiền ngân hàng.
- Lãi = dư gốc × % tháng × ngày / 3000, làm tròn đồng; tối thiểu theo MIN_INTEREST_DAYS. Cầm thêm giữ lãi đã phát sinh trong interest_carry, sau đó tính trên dư gốc mới; Trả bớt thu lãi đến ngày giao dịch và tính kỳ sau trên dư gốc còn lại. Gia hạn thu lãi, không đổi gốc. Đã chốt lãi cùng ngày không tính lại ngày tối thiểu. Chuộc/Thanh lý đóng phiếu, dư gốc 0; thu thêm/giảm trừ phải khai báo và đối chiếu tổng. Báo mất giữ mốc lãi và dư gốc; tất toán phiếu mất cần xác minh giấy tờ.
- Hủy phiên cuối trong 300 giây, chỉ phiên được tạo trên SQL mới: lý do + xác nhận đã hoàn trả tiền/tài sản; thêm log đảo, đảo từng phương thức tiền, khôi phục trạng thái trước, tăng version. Không xóa log. Phiên nhập từ PHP không được hủy bằng luồng này.
- Khách đọc từ KK.I_CUSTOMER bằng CustID; lưu snapshot dự phòng khi mất kết nối. SĐT trên phiếu giữ đối soát. Nút chốt phiếu không UPSERT khách; popup khách vẫn dùng service/skill KHBL hiện hữu.
- Trước tiếp quản: 973 phiếu STAGED, dư gốc 16.327.850.000đ; checksum nguồn/đích đều khớp. Đã chuyển cờ LIVE, không đổi số tiền/lịch sử nguồn. Còn 9 phiếu đang cầm nguồn cũ chưa chuyển; Tổng quan hiển thị riêng số lượng và dư gốc chưa nằm trong vận hành mới. Không tạo lịch sử hay tự sửa sai để nhập các phiếu này.
- Migration: `scripts/migrate_live.py` sao lưu toàn bộ CSDL, xác minh bản STAGED rồi thêm cột/index và đánh dấu LIVE. Backup trước tiếp quản: `backups/khj_cd_conversion_20260915_111111.sql`. Không hạ CD_LIVE về 0 để tiếp tục ghi SQL cũ sau khi SQL mới đã có giao dịch; phục hồi sự cố phải đối soát log và ảnh trước.

- Xác minh bản nâng cấp: 183 kiểm thử toàn hệ thống đạt; sau bổ sung kiểm tra ảnh/QR/hồ sơ, 46 kiểm thử liên quan đạt và 15 kiểm thử sổ mới đạt (bao gồm giao dịch trên phiếu chuyển đổi, nguồn pawn giữ nguyên). Thử trình duyệt trên CSDL riêng: tạo → gia hạn → hủy gia hạn thành công. Không lập/thu/chi thử vào dữ liệu thật.

- Chống gửi lại qua thời điểm chuyển hệ: nếu request_key đã ghi create trong khcd_event cũ, trả lại biên nhận đã chuyển hoặc báo phải chuyển phiếu nguồn; tuyệt đối không tạo phiếu/chi tiền mới cho cùng yêu cầu. Bộ kiểm thử sổ mới cuối cùng: 16 tests đạt.

### Cột BIÊN NHẬN tại quầy (15/09/2026)
- Tiêu đề BIÊN NHẬN và mã phiếu căn giữa. Phiếu chưa lưu hiển thị PHIẾU MỚI.
- Phiên giao dịch hiện tại hiển thị nghiệp vụ/thời gian phiên mới nhất, dư gốc, lãi suất kỳ tiếp theo và ngày hẹn đã chốt. Ẩn ô số ngày; giữ giá trị mặc định cho luồng lập mới.
- Lãi ước tính đến ngày hẹn tính ở máy chủ từ interest_from trên dư gốc hiện tại + interest_carry, theo quy tắc tối thiểu hiện hành. Phiếu đóng ẩn dự tính lãi.
- Thanh toán/thu-chi và ghi chú hiển thị phiên gần nhất; ghi chú trống của phiếu đã lưu được ẩn. Bản nháp vẫn có ô nhập ghi chú. Không ghi lại tiền hoặc thay đổi điều khoản khi chỉ xem.
- 18 kiểm thử sổ mới đạt, gồm dự tính sau Trả bớt, Cầm thêm giữ lãi, ghi chú phiên và phiếu đóng; đã kiểm tra hiển thị bằng trình duyệt với dữ liệu riêng.

- Tinh gọn BIÊN NHẬN: bỏ nhãn THÀNH CHỮ, căn giữa số tiền bằng chữ; lãi suất + chọn ngày 15/30/45/60 (mặc định 30) + ngày hẹn cùng hàng. Bản nháp tính ngày hẹn từ ngày lập hôm nay; phiếu đã chốt giữ ngày hẹn và khóa chọn kỳ hạn. Ghi chú chỉ hiện khi cầm mới. Dòng lãi ước tính bỏ các chú thích phụ.


### Tài sản và QR theo phiên — 15/09/2026
- Thông tin món hàng gộp hai cột: `.desk-items` nhập/tổng hợp món, `.desk-imgs` chứa hai ảnh vàng. Không có QR trong nhóm ảnh sản phẩm; chụp/chọn/cắt CCCD tiếp tục qua adapter KHBL.
- QR mới gắn với dòng chuyển khoản của phiên trong `cd_payments.bank_snapshot` (`qr_image` Base64, `qr_mime`). Đây là mã hóa biểu diễn, không phải mã hóa bảo mật. Route `/camdo/phien/<log_id>/qr` yêu cầu đăng nhập; không nhúng chuỗi Base64 vào trang lịch sử.
- Cầm mới: chọn/chụp/quét QR trong góc phần chuyển khoản; xác nhận lưu QR với log mở đầu. Các nghiệp vụ tiếp theo: chọn ảnh QR riêng trong popup khi có tiền chuyển khoản. Phiên không có QR không tự lấy lại ảnh phiên trước. Thanh toán tiền mặt không gửi/lưu QR.
- Hiển thị bàn làm việc dùng QR của phiên cuối; lịch sử thanh toán cho xem đúng QR từng phiên. Hủy giữ ảnh ở phiên gốc, dòng đảo chỉ ghi tham chiếu phiên gốc, không sao chép QR thành mã thanh toán mới.
- QR cũ trong hồ sơ ảnh vẫn giữ để đối soát; chỉ dùng làm ảnh mở đầu khi đang xem chính phiên mở đầu, không gán sang phiên tiếp theo. Ảnh vàng mới tiếp tục ở media/loans với checksum; không đưa QR mới vào documents_json.
- 20 kiểm thử sổ mới đạt: QR riêng qua hai phiên, giữ QR cũ, hủy không tái sử dụng QR, chặn truy cập chưa đăng nhập và chặn lưu QR khi không chuyển khoản. Đã kiểm tra bố cục bằng trình duyệt trên CSDL riêng.
- Tinh gọn món hàng: nhập món và THÊM cùng hàng, chỉ hiện thông báo lỗi; bỏ đơn vị nhỏ dưới từng món. Nội dung và tổng định giá cùng hàng. Hai ảnh vàng nằm ngang, rộng khoảng 200px/ô; màn hình hẹp chuyển nhóm ảnh xuống dưới để giữ độ rộng nhập liệu.
- Bấm ảnh vàng/CCCD/QR mở trình xem chung, chuyển bằng nút hoặc phím trái/phải; Escape đóng. Xem ảnh vẫn hoạt động trên phiếu đã khóa. Thay đổi giao diện không đổi cách lưu ảnh và QR theo phiên. Kiểm tra cú pháp JavaScript và 32 kiểm thử customer popup/pawn desk đạt.

### Định giá và lượt in — 15/09/2026
- Mức cảnh báo bằng 70% tổng giá hiện tại đã nhập/lấy khi thêm món (giảm 30%); ví dụ 10.000.000 đ → 7.000.000 đ. Vượt mức vẫn được xác nhận. Đơn giá và giá trị món trong SQL giữ nguyên cơ sở giá; không giảm lần hai khi mở lại phiếu. Phiếu cũ chưa lưu giá vẫn báo chưa lưu định giá.
- KHAC: tài sản không tính theo trọng lượng; chuẩn hóa các trọng lượng về 0, nhập giá hiện tại cho cả món. Mô tả và giới hạn giá vẫn được kiểm tra ở server.
- cd_loans.count_print đếm yêu cầu in qua nút IN trên trang in, không đếm chỉ mở trang. Không thể xác nhận máy in ra giấy hay người dùng hủy hộp thoại. Không truy hồi lượt in lịch sử chưa ghi nhận; mặc định 0. Trường đếm độc lập với fingerprint giao dịch và hash đối soát chuyển đổi. Schema bổ sung trong live_schema.upgrade.
- Thanh điều hướng biên nhận: CẦM MỚI + mã/QR + DANH SÁCH cùng hàng; tiếp tục dùng luồng tra phiếu và xác nhận bỏ bản nháp hiện có. Các nút điều hướng vẫn dùng được khi phiếu khóa.
- Cột trái đổi thành GIAO DỊCH, bỏ Cầm mới và chú thích số thao tác. Lịch sử phiếu chỉ bật khi đã mở phiếu, dùng loan_id chính xác và toàn bộ thời gian; phân trang/tổng hợp từ cd_loan_logs và cd_payments, hiển thị ghi chú và tham chiếu phiên đảo. DANH SÁCH vẫn dùng bộ lọc chung theo ngày.

### MẪU IN GIẤY CẦM ĐỒ (GCD) — A5 NẰM NGANG, GIẤY IN SẴN — 15/09/2026
- Giấy biên nhận cầm đồ là **giấy đã in sẵn khổ A5 nằm ngang 210×148 mm**. Bản in thật **chỉ in CHỮ** vào ô trống; **tuyệt đối không in ảnh nền**. Ảnh `khcd/static/img/GCD.jpg` (2470×1724) chỉ dùng cho chế độ xem trước trên màn hình.
- **Cấu hình tập trung ở KHBL** (`https://127.0.0.1:8100/he-thong/mau-in-gcd/`) — nơi GHI DUY NHẤT, lưu một dòng JSON ở `khj_bl.pmv_state['gcd_layout']`, cùng bảng key-value với `gdb_layout` và `deposit_print_layout`. **KHCD chỉ ĐỌC**, không bao giờ UPDATE/INSERT vào `khj_bl`. Không cần DDL, không migration.
- **Ba đường in ở KHCD** (đường cũ `/camdo/bien-nhan/<lid>/in` GIỮ NGUYÊN làm lưới an toàn; từ trang đó có nút sang giấy in sẵn):

  | Đường | Việc |
  |---|---|
  | `GET /camdo/bien-nhan/<lid>/giay` | IN THẬT. Template độc lập `loan_print_gcd.html`, không extend `base.html`. Có nút IN đếm lượt (`cd_loans.count_print`) như trang cũ. |
  | `… /giay?nen=1` | XEM TRƯỚC CÓ NỀN để kiểm khớp ô. Không có nút in. |
  | `… /giay?thuoc=1` | IN THƯỚC 100 mm + 4 dấu thập, **in trên GIẤY TRẮNG** để bắt máy in đang bật "Fit to page". |
  | `GET /camdo/bien-nhan/mau-in.css` | CSS bố cục, `Content-Type: text/css`. |

- **Vì sao CSS phải qua route riêng**: `khcd/__init__.py` đặt `style-src 'self'` **không có** `'unsafe-inline'` ⇒ thẻ `<style>` và `style="..."` bị chặn câm. Route trả `text/css` được `'self'` cho qua, **không phải nới CSP**.
- **Chốt chặn hỏng-câm (fail-closed)**: nếu CSS bố cục không nạp được (phiên hết hạn trả HTML đăng nhập, sai MIME — trình duyệt bỏ stylesheet mà không báo gì) thì `static/gcd-print.css` **ẩn tờ giấy và hiện dòng cảnh báo khi in** ⇒ ra tờ trắng, mất 1 tờ giấy, **không phun 17 khối chồng lên góc trái tờ in sẵn**. CSS bố cục lật công tắc lại bằng `!important` (`gcd_print.BAT_TO_GIAY`). `static/gcd-print.js` kiểm thêm `getComputedStyle` rồi mới cho bấm in, và **không bao giờ tự gọi `window.print()`**.
- **Ảnh nền không có đường nào lọt vào bản in**: nền là phần tử riêng `.gcd-nen` mang class `no-print`, chỉ được render khi `?nen=1`; `@media print{.no-print{display:none!important}}`. Không bao giờ đặt `background` lên `.gcd-a5` (rule đó có độ đặc hiệu cao hơn rule chống in) và **không dùng `print-color-adjust`**.
- **Đọc hụt `khj_bl` không được làm mất tờ phiếu**: `gcd_layout.load()` đi SQL → bản chép `instance/gcd_layout.json` → MẶC ĐỊNH biên dịch cứng. Mọi lỗi bắt **tại chỗ** (`try/except Exception`), không để lọt lên `errorhandler(pymysql.MySQLError)` vốn biến mọi lỗi MySQL thành trang 503. Cấu hình nhớ tạm 120 giây trong tiến trình; bản chép chỉ ghi khi nội dung đổi, ghi `.tmp` rồi `os.replace` (nguyên tử). **Trang `/camdo/lap-phieu` không gọi một dòng nào của module này** — KHBL sập thì quầy vẫn lập phiếu và vẫn in được.
- **Thứ tự truy vấn bắt buộc**: đọc phiếu + khách + món TRƯỚC (`live_loans.receipt_context`), đọc bố cục CUỐI CÙNG. `db.one()` dùng chung connection của request; đọc chéo `khj_bl` mà chết connection thì mọi truy vấn sau cũng chết. (Ghi chú: rủi ro thật là **mất kết nối / timeout**, không phải "khj_bl bận/khoá" — `SELECT` không khoá của InnoDB không bị writer chặn.)
- **Khổ giấy cố ý khác `gdb_layout`**: mặc định `_in.kho = "A5N"` → `@page{size:210mm 148mm;margin:0}`, **không phải `auto`**. Khổ tờ giấy là **tham số `_in.kho_w` × `_in.kho_h` (mm)**, không phải hằng số: `GCD.jpg` có tỷ lệ 1,4327 còn A5 ngang là 1,4189 — **phải đo tờ in sẵn bằng thước** rồi nhập, tờ xén tay 205×145 là chuyện thường. GĐB là tờ dọc nên `auto` an toàn; GCD là tờ **ngang rộng 210 mm**, nếu driver đang để A5 dọc thì `auto` cho khung 148 mm và tờ giấy tràn ra ngoài, bị cắt hoặc vỡ hai trang. Driver để khổ lớn hơn (A4) thì Chromium canh giữa → lệch, hấp thụ bằng `dx/dy` như GĐB. ⚠ **Không dùng lại `gdb_layout.IN_KHO`**: dict đó không có `"A5N"`, `.get()` trả `"auto"` và mất khổ ngang mà không báo lỗi.
- **Không viết hàm gộp món thứ hai**: dòng "Món hàng" dùng lại `pawn_desk.summary()` — chuỗi đó đã ghi xuống `khcd_pawn_desk.content` và đang hiện ở màn chốt phiếu, chữ trên biên nhận giao khách phải đúng chuỗi nhân viên đã xác nhận.
- **"Bằng chữ"** dùng `gcd_layout.doc_so()` — **bản sao thuật toán** của `words()` trong `static/pawn-entry.js` dòng 21. Sửa một bên phải sửa cả hai; `tests/test_gcd_print.py` giữ bảng ~40 giá trị đối chiếu (bẫy *mốt · lăm · lẻ · mười · mươi*; JS dùng `BigInt` nên `n/=1000n` là chia nguyên → Python phải `//`).
- **Chống tràn, không cắt cụt**: server tự chọn bậc co chữ `gcd-co-1/2/3` (100 / 88 / 76%) cho `mon_hang`, `khach_diachi`, `so_tien_chu`. Hết bậc thì cho xuống dòng và **trang xem trước hiện dải đỏ** để soi mắt trước khi in — cắt cụt tên khách hay danh sách món trên chứng từ pháp lý là lỗi nặng. `overflow:hidden` chỉ đặt ở **cấp tờ giấy** khi in, để chữ tràn không đẻ ra trang 2 (ăn thêm một tờ in sẵn).
- **Song sinh với KHBL** — cái dùng chung là **JSON trong `pmv_state`**, không phải chuỗi CSS. `apps/pos/gcd_layout.py` bên KHBL và `khcd/gcd_layout.py` phải khớp: **17 key cùng thứ tự · cùng số đo mặc định · cùng `GIOI_HAN`/`IN_KHO`/`IN_GIOI_HAN`/`CT_TIEN`/`NEN_GIOI_HAN` · cùng `_so()` = `"%g"`**. `tests/test_gcd_print.py::test_khop_mac_dinh_voi_khbl` đọc thẳng mã nguồn KHBL và **FAIL nếu lệch** (tự bỏ qua nếu không có tệp đó) — cùng tiền lệ `anh_cccd.py` ↔ `smoke_cccd`. **KHÔNG so chuỗi CSS giữa hai bên**: mỗi bên có markup riêng nên selector khác nhau (`[data-gcd="<key>"]` ở KHCD, `.gcd-a5__<tên>` ở KHBL), mỗi bên tự sinh CSS cho markup của mình. Điểm KHCD bắt buộc phải tự sinh: `.gcd-a5{position:relative!important;…}` — KHCD không có `khbl.css` khai sẵn, thiếu nó là 17 khối `absolute` neo vào viewport và bố cục vỡ toàn bộ.
- **Số đo mặc định là ĐIỂM KHỞI ĐẦU để kéo, không phải số cuối cùng** — nhưng đã kiểm lại trên chính `GCD.jpg`: chúng đo theo lối **"ĐÁY Ô nằm trên đường chấm"**, khớp đúng cách canh chữ của `gcd-print.css` (`flex column` + `justify-content:flex-end`) — đáy ô của 6 dòng thân phải rơi vào 32,4 / 36,4 / 40,3 / 44,3 / 48,2 / 52,8% đúng vị trí các đường kẻ chấm. ⚠ **Đổi `h` thì phải đổi `top` theo**, nếu không chữ rời khỏi dòng kẻ. Toạ độ NGANG khớp gần như tuyệt đối.
- **Tỷ lệ ảnh nền lệch tờ giấy ~1%**: `GCD.jpg` là 2470×1724 (tỷ lệ 1,4327) còn A5 ngang là 1,4189 — lệch ~2 mm bề ngang. Hoặc bản scan méo, hoặc **tờ in sẵn không đúng A5 chuẩn** (nhà in địa phương xén tay). **Phải đo tờ giấy thật bằng thước** trước khi chốt toạ độ; `_nen` (x/y/w/h %) chỉ để kéo ảnh cho khớp lúc xem trước và **không bao giờ lọt vào CSS in**.
- **Cảnh báo sát mép**: `gcd_layout.khoi_sat_mep()` soi mép trên/dưới/trái theo biên cứng 6 mm và trang xem trước nói ra. Mặc định còn **một khối lọt biên**: `Số phiếu — cuống trên` (đỉnh 1,0% ≈ 1,5 mm từ mép trên). `Cửa hàng có giữ các giấy tờ` (đáy 97,1% ≈ 4,3 mm) đã **TẮT SẴN** vì lý do này — laser/inkjet phổ thông có biên cứng 4,2–6,4 mm và `@page{margin:0}` **không mở được** vùng đó. Phải in thử giấy trắng đúng máy in rồi mới chốt toạ độ, hoặc tắt khối và đưa CCCD sang cuống trái.
- **Máy in**: `_in.may_in` là **id trỏ sang sổ `may_in_ds`** (khoá riêng trong cùng `pmv_state`, dùng chung cho GĐB · CỌC · GCD), **không bao giờ chứa tên máy in thật** — tên máy in Windows có dấu ngoặc và khoảng trắng, không lọt qua `[A-Za-z0-9_-]{0,40}`. `_in.ban_in` kẹp 1–4. Cách dùng id đó xem mục ngay dưới.
- **Tiền in trên giấy**: `_ct.tien` mặc định `du_hien_tai` (`principal_balance`) — **đúng con số trang in cũ đang in**, hai đường in không được hiện hai số khác nhau cho cùng một phiếu. Chuyển sang `goc_ban_dau` (`original_principal`, đúng chữ in sẵn "Số tiền cầm") ở trang cấu hình KHBL; khi đó nếu phiếu đã trả bớt thì trang giấy in sẵn **hiện dải cảnh báo ghi cả hai số**. ⚠ **Đây là điểm CHỜ GĐ CHỐT** — chọn `goc_ban_dau` thì phải dán nhãn "bản nội bộ" cho trang in cũ, đừng để nhân viên đưa nhầm cho khách.
- **Ngày tháng**: tờ in sẵn có sẵn chữ "năm ……" riêng nên hai ô ngày chỉ in **dd/mm**, ô năm in **yyyy** — xác nhận lại ở lần in thử giấy trắng đầu tiên.
- **Bài kiểm**: `tests/test_gcd_print.py`. Chạy **chỉ đích danh tệp**, không chạy cả bộ, không discover:
  `.venv\Scripts\python.exe -m pytest tests/test_gcd_print.py -q`
  52 bài thuần hàm chạy không cần CSDL; 13 bài web/CSDL tự bỏ qua khi chưa đặt `KHCD_TEST_ENV` (conftest tạo CSDL nháp rồi xoá). Bài kiểm soi **HTML đã render** (so tập `data-gcd` với `BLOCKS`) chứ không chỉ so chuỗi CSS — quên một `data-gcd` trong template thì chuỗi CSS vẫn khớp, test vẫn đạt, mà khối đó **không bao giờ được định vị** trên bản in.

### MÃ VẠCH SỐ BIÊN NHẬN TRÊN GIẤY CẦM ĐỒ — 16/09/2026
GĐ yêu cầu: *"thêm mã Barcode trên SỐ biên nhận"*. Khối thứ **18** của mẫu in GCD, key **`ma_phieu_vach`** ("Mã vạch Số biên nhận"), đứng ngay **TRÊN** ô `ma_phieu` (ô "SỐ:"). Kéo/căn ở trang cấu hình KHBL như 17 khối kia; KHCD chỉ ĐỌC và in ra giấy.

- **Thuật toán là BẢN SAO, không viết mới** — `khcd/ma_vach.py`, chép nguyên văn từ `D:\PYTHON\KHBL\apps\pos\ma_vach.py` (hằng `CODE39` · `so_ma_vach()` · `png_code39()`). Đây chính là thuật toán đang in mã vạch **Giấy đảm bảo** và **đã quét được ngoài thực tế**; một Code 39 tự chế sai tỷ lệ vạch rộng/hẹp vẫn "nhìn như mã vạch" mà máy quét không đọc nổi, và lỗi đó chỉ lộ ra khi khách đã cầm tờ giấy về nhà.
  - Vùng sao chép nằm giữa hai dòng mốc `BẮT ĐẦU/HẾT VÙNG SAO CHÉP`; lớp riêng của KHCD nằm **ngoài** vùng đó. **Sửa thuật toán = sửa bên KHBL trước rồi chép lại nguyên vùng**, không sửa tại KHCD.
  - Khoá lại bằng **sha256** (`ma_vach.van_tay()`), đúng nếp `apps/common/anh_cccd.py` ↔ `smoke_cccd` của KHJ. ⚠ KHBL lưu **LF**, KHCD lưu **CRLF** ⇒ bài kiểm đọc cả hai ở **chế độ văn bản** rồi mới băm: cái buộc phải giống nhau là **ký tự**, không phải byte thô.
- **Ảnh PNG data URI, KHÔNG phải div/CSS**: trình duyệt co vạch lẻ thành pixel mờ khi in, vạch hẹp 0,17 mm rơi vào nửa pixel là xám nhoè và máy quét chịu. Ảnh 1-bit thì mỗi vạch là số nguyên pixel, in ra **đen đậm**. ⚠ Và **không được vẽ bằng `background`**: bản in GCD cố ý không có `print-color-adjust` nên mọi thứ vẽ bằng background **biến mất trên giấy** — thẻ `<img>` là nội dung thật, luôn in ra. Data URI chứ không phải tệp rời vì đường in phía máy chủ nạp trang qua `file:///` trong thư mục tạm.
- **Nội dung mã = phần CHỮ SỐ của mã phiếu, KHÔNG rút gọn** (`KH22609000123` → `22609000123`). Tiền tố chữ là hằng nên bỏ đi vẫn tra ngược được đúng một phiếu. ⚠ **Cố ý KHÔNG dùng `_ma_gdb()`** (hàm rút 9 số của Giấy đảm bảo): `KH22609000123` và `KH22609001123` đều rút thành `226090123` ⇒ **hai phiếu khác nhau cùng một mã vạch**, quét nhầm là trả nhầm hàng. Bài kiểm `test_khong_rut_gon_9_so` giữ nguyên ví dụ này.
- **Bề rộng vạch hẹp là con số quyết định quét được hay không**, và nó **đổi theo độ dài mã phiếu** (README ghi rõ "giữ nguyên mã lịch sử" — phiếu cũ có thể dài hơn 11 số). Mã 11 số chiếm **227 mô-đun** (207 mô-đun vạch + 2×10 quiet-zone dựng sẵn **trong ảnh**); khối rộng 18,8% trên tờ 210 mm ⇒ vạch hẹp **≈ 0,174 mm = 7 mil**. Vì vậy trang xem trước **đo theo từng phiếu** (`ma_vach.vach_hep_mm`, có nhân `_in.ty_le`) và báo **hai mức, cố ý không gộp**:

  | Vạch hẹp | Trang in | Vì sao |
  |---|---|---|
  | ≥ 0,19 mm | im lặng | mức thoải mái của máy quét cầm tay |
  | 0,15 – 0,19 mm | dải **XÁM** một dòng | vẫn thường đọc được nhưng **phải quét thử tờ in đầu tiên** — đây là trạng thái của bố cục mặc định hôm nay |
  | < 0,15 mm | dải **ĐỎ** | máy quét quầy chịu thua; ai đó vừa bóp nhầm khối hoặc thu nhỏ tỷ lệ in |

  Kêu đỏ trên đường chạy hằng ngày thì vài hôm là **không ai đọc dải cảnh báo nào nữa**, kể cả dải báo lệch tiền — đó là lý do tách hai mức chứ không phải một.
- ⚠ **BỀ RỘNG 18,8% LÀ TRẦN CỨNG CỦA TỜ GIẤY IN SẴN**, không phải lựa chọn thẩm mỹ: cả nửa phải tờ giấy không có dải trống nào quá ~40 mm. Khối đặt ở dải bên phải chữ đỏ "KIM HẠNH II" (hết ở 77,1%), dưới dòng "DNTN KINH DOANH VÀNG & CẦM ĐỒ", trên dòng địa chỉ. **Quét không ra thì ĐỪNG cắt bớt chữ số**: nới ô Rộng % lấn sang trái, hoặc kéo khối xuống dải y 23–30,5% (bên phải tiêu đề "BIÊN NHẬN CẦM ĐỒ"), hoặc đặt tờ in sẵn có chừa chỗ cho mã vạch.
- **Không làm khối "số đọc được" riêng** như Giấy đảm bảo: bên GĐB mã vạch mang mã **rút gọn** khác với mã in trên giấy nên bắt buộc in kèm số; ở đây khối `ma_phieu` ngay bên dưới **đã in nguyên mã** rồi, thêm một dòng số nữa là in trùng trên tờ giấy vốn đã chật.
- **Hai bên khớp nhau — ba điểm bị khoá bằng bài kiểm**: (1) khối `ma_phieu_vach` phải **cùng key, cùng thứ tự, cùng số đo** với `apps/pos/gcd_layout.py`; (2) chuỗi **`CSS_ANH`** (`object-fit:fill` + `image-rendering:pixelated`) phải giống **từng ký tự** — nó quyết định hình dáng ảnh trên giấy, và phải do `css()` **sinh ra** chứ không nằm trong `static/gcd-print.css` (tệp static là của riêng từng dự án, để ở đó là đúng kiểu lệch đã làm **chữ lệch 9 mm** lượt trước); (3) markup là thẻ `<img data-gcd=…>` **không bọc `<div>`**, y như `templates/pos/_gcd_a5.html` bên KHBL. Riêng `.gcd-a5 .gcd-anh{z-index:1}` trong `static/gcd-print.css` là **lo riêng của KHCD** (cho mã vạch nổi trên ảnh nền lúc xem trước), không phải hình dáng ảnh — đừng gộp hai thứ.
- **Không đường nào được làm mất tờ phiếu**: khối TẮT thì không vẽ ảnh; mã không có chữ số nào → trả `''` để template bỏ khối (**không** in mã vạch của số 0 lên chứng từ); lỗi dựng ảnh (thiếu Pillow, hết bộ nhớ) cũng nuốt tại chỗ — **mất mã vạch còn hơn mất tờ phiếu**, cùng nguyên tắc với `gcd_layout`.
- **Bài kiểm**: `tests/test_gcd_ma_vach.py`. Chạy **chỉ đích danh tệp**, không chạy cả bộ, không discover:
  `.venv\Scripts\python.exe -m pytest tests/test_gcd_ma_vach.py -q`
  **36 bài chạy không cần CSDL**, 10 bài web tự bỏ qua khi chưa đặt `KHCD_TEST_ENV`. Tệp có **bộ GIẢI MÃ Code 39 riêng** đọc ngược ảnh PNG ra chuỗi số: so mã nguồn thôi thì chưa đủ — chép đúng chữ mà Pillow đổi hành vi thì mã vẫn câm. Nhóm bài dựng trang bằng Jinja trần với dữ liệu giả (không đụng CSDL, không đụng máy in) và **quét lại ảnh lấy từ HTML đã render**, vì view hoàn toàn có thể vẽ mã vạch của một phiếu khác mà bài kiểm so chuỗi vẫn xanh.
- ⚠ **CHƯA QUÉT THỬ BẰNG MÁY QUÉT THẬT** — đây là việc duy nhất còn treo của mục này, phải làm ở tờ in đầu tiên. Cũng chưa in thử ra máy in (theo yêu cầu). `len(G.BLOCKS)` đổi 17 → 18 nên `tests/test_gcd_print.py` đã cập nhật con số đó.

### IN THEO MÁY IN ĐÃ LƯU + ĐƯỜNG RƠI VỀ TRÌNH DUYỆT — 15/09/2026
GĐ chốt: *"tìm → chọn → lưu máy in vào cấu hình để sử dụng → nếu không gọi được máy in đó → thì trình duyệt tự điều hướng chọn máy in"*. **Tìm · chọn · lưu** làm ở trang cấu hình KHBL (người ghi duy nhất); **dùng** là `khcd/gcd_may_in.py` (KHCD chỉ ĐỌC, không bao giờ ghi sang `khj_bl`).

- **Quyết định đi đường nào xảy ra LÚC DỰNG TRANG, không phải lúc bấm.** `gcd_may_in.kiem_tra()` chạy ngay trong `giay()`, nên trang biết trước mình đi đường nào: đủ điều kiện → nút `id="gcd-nut-in"` (gcd-print.js gọi máy chủ); thiếu → nút `id="tracked-print-button"` **y hệt cũ**, receipt-print.js đếm lượt rồi `window.print()` ngay. ⚠ **Không được đổi thành "thử máy chủ rồi mới rơi về"** — như vậy người dùng phải chờ vài giây dựng PDF mới thấy hộp thoại. **Hôm nay máy chủ không có máy in vật lý và không có công cụ đẩy bản in ⇒ đường rơi về là ĐƯỜNG CHẠY THẬT HẰNG NGÀY**, nó phải mượt đúng như trước, không đợi, không nháy trang.
- **Bậc thang điều kiện — rẻ trước, tốn sau**, hụt bậc nào là dừng ngay và trả một câu ngắn: ① cấu hình đã chọn máy in chưa → ② sổ `may_in_ds` có bản ghi đó và có tên thiết bị Windows chưa → ③ máy chủ có `msedge.exe` không → ④ có công cụ đẩy PDF ra máy in không → ⑤ tên đó **còn** trong `Get-Printer` không. Hôm nay **bậc ① đã hụt** (chưa ai lưu `gcd_layout`) ⇒ trang in **không gọi PowerShell một lần nào**. Danh sách máy in nhớ tạm 120 giây trong tiến trình.
- **Tìm máy in = PowerShell `Get-Printer` → JSON**, không cài gì (không pywin32, không thư viện mới, không tải tệp nhị phân nào). ⚠ Máy chủ hiện **chỉ có máy in ẢO** — Microsoft Print to PDF, XPS Document Writer, OneNote, và mấy cổng `TS00x` của phiên Remote Desktop. **Đó là bình thường, không phải lỗi**; cắm máy in mạng vào máy chủ là nó tự hiện ra. Bẫy: `ConvertTo-Json` với **đúng một** máy in trả **chuỗi trần**, không phải mảng — `liet_ke()` nhận cả hai, và "không có máy in nào" là **danh sách rỗng + không lỗi** (hỏi được, câu trả lời là không có). Khớp tên bỏ qua hoa-thường và khoảng trắng thừa rồi trả **đúng chữ Windows đang gọi** để truyền cho công cụ in.
- **Dựng bản in: CHỈ Microsoft Edge chạy ẩn `--print-to-pdf`, từ CHÍNH `loan_print_gcd.html`** (`gcd_print._dung_trang(pdf=True)`), cùng CSS do `gcd_layout.css()` sinh. Giữ **một bản vẽ duy nhất**: dựng PDF bằng thư viện vẽ khác sẽ thành **bản vẽ thứ ba**, lệch với cả bản xem trước lẫn bản in trình duyệt, và không ai biết bản nào đúng cho tới khi hỏng một tờ giấy in sẵn. ⚠ **Luôn `nen=False`** — bản gửi máy in chỉ có CHỮ, thư mục tạm cũng không hề có `GCD.jpg` để mà in ra.
- **Edge nạp trang qua `file:///` trong thư mục tạm, KHÔNG qua HTTPS.** Mọi endpoint KHCD đều đòi đăng nhập ⇒ Edge chạy ẩn sẽ nhận trang đăng nhập; cấp cho nó một "vé" bỏ qua đăng nhập là **mở một lỗ xác thực mới trên hệ chạy tiền thật**, không đáng chỉ để in một tờ giấy. Đi `file://` còn tránh luôn chứng chỉ tự ký của LAN. Trang + `mau-in.css` + `gcd-print.css` nằm **cạnh nhau** trong thư mục tạm nên chỉ tham chiếu tương đối.
- **Tệp tạm và tiến trình**: mỗi lượt một thư mục `khcd_gcd_*`, **xoá trong `finally`** dù hụt ở bước nào — tờ phiếu có tên và địa chỉ khách, không được nằm lại trên ổ đĩa; trước mỗi lượt còn quét dọn thư mục cũ quá 1 giờ (mất điện giữa chừng thì lần in sau dọn hộ). Quá giờ chờ thì **giết cả cây bằng `taskkill /T /F`** — Edge đẻ tiến trình con, giết mỗi tiến trình cha là để lại rác ngốn RAM trên máy chủ chạy 24/7. Giờ chờ: Get-Printer 8s · dựng PDF 15s · đẩy bản in 20s; JS phía trang tự ngắt ở **30s** rồi rơi về hộp thoại in.
- **Bật đường in phía máy chủ khi có máy in thật**: chép `SumatraPDF.exe` (bản portable) vào `D:\PYTHON\KHCD\ops\` rồi RESET KHCD — **không phải sửa một dòng mã nào**. Để chỗ khác thì đặt `GCD_CONG_CU_IN=<đường dẫn>` trong `.env` (`GCD_EDGE` tương tự cho Edge). Hỗ trợ `SumatraPDF` (`-print-to … -silent -exit-when-done`, nhiều bản bằng `-print-settings Nx`) và `PDFtoPrinter` (lặp lệnh vì không hỗ trợ số bản). ⚠ **Cố ý KHÔNG hỗ trợ Acrobat/Foxit**: chúng mở cửa sổ rồi nằm lại; trên máy chủ chạy ẩn 24/7 thì mỗi lượt in đẻ một tiến trình GUI treo.
- **Rơi về KHÔNG PHẢI LỖI**: dải **XÁM** một dòng ("Chưa chọn máy in trong cấu hình (Bán lẻ → Mẫu in GCD). Bấm IN sẽ mở **hộp thoại in của trình duyệt** để chọn máy in — vẫn in bình thường"), **không phải dải đỏ**, không chặn ai. Gửi được thì dải **XANH** "Đã gửi tới ‹tên máy in›". Route `POST /camdo/bien-nhan/<lid>/in-may-chu` **luôn trả JSON 200**, `{ok:false, ly_do:…}` chứ không bao giờ trả lỗi HTTP — lỗi HTTP ở đây sẽ thành trang 500 đúng lúc quầy đang cần tờ phiếu.
- **Sổ máy in đọc thoáng**: `ten_thiet_bi()` nhận `thiet_bi · ten_windows · windows · may · may_windows · device · printer` rồi mới rơi về `ten`. Sổ do KHBL ghi, hai dự án có thể đặt tên trường khác nhau — thà đọc thoáng còn hơn im lặng in hụt; `ten` xếp cuối vì nó có thể chỉ là nhãn cho người ("Máy quầy 1").
- **`css_tinh_url` có lớp đỡ `or url_for(static…)`**: `TEMPLATES_AUTO_RELOAD=True` nạp template mới NGAY còn `.py` phải RESET mới đổi ⇒ luôn có một khoảng **template mới chạy cùng view cũ**. Thiếu lớp đỡ đó thì trong khoảng ấy thẻ `<link>` rỗng, `gcd-print.css` không nạp, chốt chặn fail-closed chặn in và quầy tưởng hệ hỏng. Lớp này đỡ cho mọi lần sửa template về sau.
- **Bài kiểm**: `tests/test_gcd_may_in.py` — **35 bài, không cần CSDL, không chạm máy in thật**. Mọi lời gọi tiến trình ngoài (PowerShell · Edge · công cụ in) đi qua **một cửa duy nhất** `gcd_may_in._chay` và bài kiểm thay cửa đó bằng hàm giả; **đừng gọi `subprocess` ở chỗ khác trong module này**, nếu không bài kiểm sẽ in thật. Chạy **chỉ đích danh tệp**:
  `.venv\Scripts\python.exe -m pytest tests/test_gcd_may_in.py -q`
- **CHƯA KIỂM ĐƯỢC TRÊN THIẾT BỊ THẬT** (máy chủ không có máy in, không có công cụ đẩy bản in): còn hai điểm phải xác nhận ở lần in thật đầu tiên — (a) Edge `--headless=new --print-to-pdf` có tôn trọng `@page{size:210mm 148mm}` không (bản headless cũ thì không, ra khổ Letter); (b) `-print-to` của SumatraPDF có giữ đúng khổ không hay tự "fit to page". Cách bắt: in chế độ `?thuoc=1` trên **giấy trắng** rồi đo bằng thước, đúng như đường in trình duyệt.

### Mã phiếu mới KH2 — 15/09/2026
- Áp dụng skill tao-ma-phieu-cam-do: KH2 + YYMM + STT sáu số, MAX STT trên mọi tháng cùng năm + 1. Đổi tháng tiếp tục dãy; năm mới bắt đầu 000001. Chỉ xét mã KH2 hợp lệ; giữ nguyên mã lịch sử.
- Dùng khóa MySQL theo CSDL/năm, giữ tới khi transaction INSERT commit/rollback; cùng request_key vẫn trả phiếu đã tạo. Giữ UNIQUE(sku), báo hết dãy khi vượt 999999. Không tạo thêm bảng hoặc thay mã nguồn cũ.
- Bỏ desk-title và desk-recent khỏi trang lập phiếu.
- Sửa lỗi sau lưu: lockForm(true) có thể chạy trước khi loaded được nạp; nút lịch sử/in chỉ bật khi có loaded. Giữ savedSku để lỗi hiển thị không bật lại xác nhận phiếu đã lưu. Phản hồi lưu không đọc được được đối chiếu bằng request_key qua API chỉ đọc, giới hạn đúng actor tạo phiếu; không tự POST lại giao dịch.
- Sau THÊM, loại vàng và đơn giá được đặt trống; tooltip từng dòng hiển thị TL vàng × đơn giá = giá trị hiện tại (KHÁC hiển thị giá cả món).
- Tủ đồ mặc định --Chọn-- (rỗng); server chỉ nhận 1/2/3 khi tạo mới. Phiếu cũ vẫn hiển thị tủ đã lưu.
- Nhãn CẦM TỐI ĐA thay TỔNG ĐỊNH GIÁ; tooltip giữ tổng giá trị định giá, mức 70% làm tròn lên bội 1.000đ. Quy tắc làm tròn toàn bộ giao dịch đang chờ chốt cách đối soát phần gốc lẻ ở phiếu cũ; chưa sửa các dòng tiền đã lưu.

### Popup nghiệp vụ / Gia hạn — 15/09/2026
- Dùng chung popup hai cột: thông tin phiếu + số tiền phiên; kỳ tiếp/ghi chú + thanh toán. Gia hạn có ngày giao dịch tính lãi, kỳ 15/30/45/60 ngày, ngày hẹn sửa trực tiếp và lãi suất kỳ tiếp. Giao diện tự gọi tính lại, khóa Xác nhận trong khi kết quả cũ hết hiệu lực; server vẫn tính lại trước commit.
- Ngày giao dịch trong popup Gia hạn là ngày chốt lãi hiệu lực; không trước interest_from và không quá 365 ngày từ hôm nay. Ngày hẹn phải sau ngày này, tối đa 365 ngày. Có thể thu trước hoặc chọn ngày quá khứ trong kỳ chưa chốt.
- cd_loan_logs.happened_at giữ thời gian xác nhận thực tế; mốc hiệu lực lưu trong terms_json. interest_from mới bằng ngày chọn. Kỳ đã trả trước chưa đến mốc không cho tính ngược lãi bằng ngày hôm nay; giao diện dùng mốc đã chốt cho gia hạn tiếp.
- Lãi thu dùng monthly_rate cũ; cd_loans.monthly_rate cập nhật kỳ tiếp, cd_loan_logs.monthly_rate giữ mức áp dụng kỳ vừa thu. Trước đổi rate lưu bản trước để hủy khôi phục đủ mốc/rate. Không sửa lịch sử nguồn. Quy tắc làm tròn toàn hệ thống từ yêu cầu trước vẫn chờ chốt riêng, không gộp vào thay đổi này.
- Popup dùng lãi suất kỳ hiện tại có thể chọn lại; hiển thị một chữ số thập phân. Server tính tối thiểu 1 ngày và 5.000đ cho nghiệp vụ thu lãi 3/4/5/6, kể cả phiên cùng ngày; Cầm thêm giữ lãi chuyển tiếp, Báo mất không tự thu lãi. Rate áp dụng ghi ở log, không đổi rate kỳ tiếp ngoài lựa chọn Gia hạn.
- Ngày hẹn và số ngày gia hạn đồng bộ hai chiều (ngày tùy chọn sinh lựa chọn số ngày tương ứng). Cầm thêm/Trả bớt có dòng số tiền và gốc mới; ngày Chuộc đồ hiện nhưng khóa. Các ô tiền trong bàn lập phiếu/popup format dấu chấm khi nhập, giữ số thô khi gửi API.
- Thanh toán tách khỏi popup nghiệp vụ: XÁC NHẬN mở bước xác nhận thanh toán riêng, CHỐT THANH TOÁN mới ghi phiên; không tự mặc định ghi tiền mặt khi người dùng chưa xác nhận bước này.

### Chốt lại Cầm thêm / Trả bớt — 15/09/2026
- Thay thế quy tắc Cầm thêm giữ lãi chuyển tiếp: cả 2/3 chốt lãi trên gốc CŨ (tối thiểu 1 ngày, 5.000đ), tính thêm/giảm, rồi cập nhật gốc MỚI và mốc kỳ mới. Lãi tồn chuyển tiếp từ phiên cũ nếu có được cộng chốt một lần, sau đó interest_carry=0.
- Dòng tiền ròng = -biến động gốc + lãi + thêm - giảm. Cầm thêm 2.000.000đ, lãi 50.000đ → CHI 1.950.000đ. Trả bớt 2.000.000đ, cùng lãi → THU 2.050.000đ. Nếu Cầm thêm có net dương, thực tế THU phần chênh; tài khoản tiệm/khách đổi theo hướng tiền thực tế.
- Cầm thêm, Trả bớt và Gia hạn đều có kỳ tiếp: ngày tính lãi, ngày hẹn, lãi suất mới. Log giữ lãi/rate trên gốc cũ; kỳ sau tính gốc/rate mới. Hủy khôi phục gốc, mốc lãi, rate và đảo đúng tiền ròng. Giữ nguyên phiên đã chốt theo quy tắc cũ.

### Thanh toán CHI sau nghiệp vụ — 15/09/2026
- Popup nghiệp vụ xác nhận trực tiếp, payload dùng tiền mặt (bank_amount=0); không mở bước xác nhận thanh toán riêng. Bàn chính mặc định tiền mặt khi lập mới, đổi CK sau khi đã lưu.
- Phương thức thanh toán trên bàn chính chỉ mở cho log mới nhất do hệ thống mới ghi, operation 1/2, dòng tiền OUT >0, trong 1.800 giây kể từ happened_at thực tế. THU dùng luồng khác sau này. Hiển thị số THU/CHI dương của phiên, không dùng dư gốc làm số tiền chi.
- Quét QR khách qua bộ đọc KHBL; tạo VietQR offline từ mã NH/BIN, số TK, tên, số tiền CK và nội dung chứa mã phiếu. banking_qr.py tái sử dụng thuật toán KHBL, giữ nguyên số tiền phiên (không tự làm tròn QR). QR chỉ được chuẩn bị, không có xác nhận ngân hàng đã chuyển tiền.
- LƯU QR đổi cơ cấu CASH/BANK trong cd_payments cùng log, tổng chi không đổi. Lưu QR PNG/Base64 và dữ liệu banking tại bank_snapshot, transfer_status=PREPARED. Trước/sau đổi thanh toán cùng người/thời gian/request_key lưu ở cd_loan_logs.terms_json.payment_changes; không tạo thêm nghiệp vụ/gốc/lãi. Khóa loan, kiểm tra phiên + thời hạn + payment_version trong transaction, idempotency khi phản hồi thất lạc. Hủy phiên đảo đúng phương thức hiện tại.
- Skill xác nhận chuyển khoản thực tế vào/ra theo nội dung/mã phiếu chưa triển khai, làm ở giai đoạn sau.

### Ảnh cam kết Báo mất — 16/09/2026
- Popup Báo mất có ô ảnh lớn, Chụp/Chọn/Bỏ ảnh và ghi chú; hướng dẫn: Viết cam kết tài sản và báo mất giấy; chụp hình CCCD + giấy cam kết.
- Ảnh gắn RIÊNG từng cd_loan_logs operation_id=7; terms_json.lost_photo lưu tên file/hash/kích thước. File JPEG chuẩn hóa trong media/loans, tên ngẫu nhiên. Không gộp vào ảnh tài sản hay ghi đè hồ sơ CCCD khách.
- Giới hạn 15MB/25MP, giữ tối đa cạnh 2400px, loại EXIF khi chuẩn hóa. Route /camdo/phien/<log_id>/cam-ket yêu cầu đăng nhập, xác minh đường dẫn và checksum. Xem lại qua nhật ký popup và chi tiết biên nhận.
- Hủy phiên vẫn giữ ảnh ở phiên Báo mất gốc. File không đọc được làm rollback phiên; kiểm thử lưu, đọc lại, hủy giữ ảnh và rollback ảnh lỗi đạt.

### Báo mất có thu lãi và khóa PassCode — 16/09/2026
- Thay thế quy tắc Báo mất không thu: thu lãi từ mốc lãi đã chốt tới ngày báo mất, tối thiểu 1 ngày / 5.000đ; giữ nguyên gốc, cập nhật mốc lãi sau thu.
- Mô tả tài sản, xuất trình CCCD/VNeID, đối chiếu và ký cam kết là thủ tục trên giấy. Popup chỉ giữ ảnh cam kết + ghi chú; không thêm các ô nhập hoặc kiểm tra bắt buộc cho thủ tục giấy. Ảnh lưu riêng phiên Báo mất. Dữ liệu hồ sơ đã lưu trước đó được giữ nguyên.
- receipt_lost mà chưa có lost_unlocked được khóa tất cả giao dịch/hủy phiên ở server; chỉ xem/in/lịch sử. Áp dụng cả phiếu báo mất cũ chưa mở khóa. Không đổi tiền hoặc dữ liệu lịch sử nguồn.
- Mở khóa bằng PassCode băm của tài khoản đăng nhập từ auth_user dùng chung, không dùng mật khẩu đăng nhập thay PassCode, không tạo mã mới. Có lý do, giới hạn 5 lần sai/5 phút theo tài khoản trên phiếu; không lưu PassCode gốc. Ghi nghiệp vụ 8 Mở khóa báo mất, không thu/chi; giữ receipt_lost và hồ sơ để truy vết. Nếu hủy chính phiên mở khóa sẽ trở về trạng thái bị khóa.
- 39 kiểm thử sổ mới đạt, gồm tính lãi Báo mất, chặn giao dịch/hủy, PassCode sai/đúng, mở khóa idempotent và đối soát sau mở.

- Điều chỉnh theo xác nhận 16/09/2026: đã gỡ các trường thủ tục giấy và yêu cầu tương ứng ở server; kiểm thử báo mất không có các trường này và luồng lãi/khóa/mở khóa đều đạt.

### Xem giấy báo mất tại bàn lập phiếu — 16/09/2026
- Dưới Lịch sử phiếu có nút Giấy báo mất, chỉ hiện khi biên nhận có phiên Báo mất. Popup chia tab theo phiên, mới nhất trước; hiển thị ảnh cam kết và ghi chú đã lưu, thông báo rõ khi thiếu ảnh/nội dung. Không tự đọc hoặc tạo nội dung từ ảnh. Giữ đường ảnh có xác thực và dữ liệu riêng từng phiên.

### Điều chỉnh Báo mất / Mở khóa — 16/09/2026
- Thay thế quy tắc chặn hủy khi báo mất: phiên Báo mất mới nhất được XÓA trong 5 phút như các phiên khác; ghi bút toán đảo, hoàn đúng tiền đã thu và khôi phục trạng thái/mốc lãi trước phiên. Ảnh và lịch sử vẫn giữ để đối soát. Hết 5 phút không cho hủy.
- Mở khóa là thông báo kiểm soát, vẫn ghi log operation_id=8 để truy vết nhưng không tạo thanh toán, không đổi interest_from/lãi suất/ngày hẹn hoặc nghiệp vụ tài chính gần nhất. Không tính vào số phiên giao dịch và danh sách giao dịch chung; vẫn xuất hiện trong nhật ký riêng của phiếu. Không cho XÓA thông báo mở khóa như phiên tài chính.
- Ví dụ Báo mất ngày 01/09 đã thu lãi tới 01/09, mở khóa 16/09: nghiệp vụ tiếp theo ngày 16/09 tính 15 ngày từ 01/09; không tính từ giờ mở khóa. Bàn thanh toán hiển thị phiên tài chính gần nhất, bỏ qua thông báo mở khóa.

### XÓA trực tiếp phiên trong 5 phút — 16/09/2026
- Thay thế cơ chế ghi bút toán đảo: mọi nghiệp vụ mới, kể cả Báo mất và thông báo Mở khóa, được xóa khi là phiên cuối cùng, chưa đủ 300 giây, còn khớp snapshot. Không xóa phiên nhập từ nguồn cũ hay dòng hủy cũ.
- Transaction khóa biên nhận, kiểm tra fingerprint/thời hạn, phục hồi gốc, mốc lãi, lãi suất, ngày hẹn, trạng thái trước phiên; DELETE cd_payments của phiên rồi DELETE cd_loan_logs. Không ghi log hủy thay thế. Phải hoàn trả tiền/tài sản thực tế trước xác nhận.
- Xóa Cầm mới giữ biên nhận trạng thái CANCELLED, gốc 0, giữ mã tránh cấp trùng; không còn log/thanh toán của phiên. Xóa Mở khóa khôi phục khóa. Tệp ảnh trên đĩa không tự dọn trong transaction; liên kết ảnh/QR của log đã xóa không còn truy cập được. Không xóa hàng loạt lịch sử hiện có.

### Popup dùng chung và xóa toàn bộ CẦM MỚI — 16/09/2026
- KHDialog.confirm({title, danger}) dùng hai nút Có/Không, không ô nhập hay checkbox; KHDialog.notify({title, message}) dùng cho thông báo. Thành phần ui-dialog.js/css được nạp từ base.html, hỗ trợ Escape, focus, hàng đợi popup, nội dung textContent.
- Xóa phiên gửi confirmed=yes; vẫn kiểm tra CSRF, phiên mới nhất, fingerprint và hạn 5 phút tại server.
- Thay thế quy tắc giữ biên nhận CANCELLED: xóa phiên Cầm mới duy nhất của phiếu mới sẽ DELETE cd_payments, cd_loan_logs, cd_loan_items, cd_loans trong cùng transaction. Không giữ bản ghi SQL của phiếu, không ghi lịch sử hủy; giao diện về phiếu trống. Không áp dụng xóa toàn bộ cho phiếu nguồn cũ.
- Xóa các nghiệp vụ tiếp theo vẫn khôi phục phiếu trước phiên. Khách hàng KK dùng chung không bị xóa. Tệp ảnh trên đĩa không dọn trong transaction SQL.

### Báo mất bắt buộc ảnh và tải mẫu Word — 16/09/2026
- Popup dùng hướng dẫn: Viết cam kết báo mất giấy + hình CCCD. XÁC NHẬN chỉ bật khi đã tính phiên và có ảnh chụp/chọn; server bắt buộc ảnh hợp lệ, giữ giới hạn ảnh hiện hành. Thiếu ảnh không ghi phiên. Không thêm trường thủ tục giấy.
- Nút tải Giấy cam kết nằm bên phải dòng Chụp/Chọn. File khcd/resources/giay-cam-ket-bao-mat-kim-hanh-2.docx là bản sao nguyên vẹn file người dùng cung cấp. Route /camdo/mau/giay-cam-ket-bao-mat yêu cầu đăng nhập, trả attachment Word.

### Màu cột biên nhận và lọc phiên — 16/09/2026
- Toàn bộ desk-checkout đổi màu nền/viền/header/footer theo watermark của trạng thái thực tế.
- Popup danh sách có Trạng thái (nghiệp vụ phiên) trước Khách hàng, gửi kind tới API sẵn có. Phiếu đã chuộc/thanh lý vẫn xuất hiện theo ngày giao dịch, không lọc riêng phiếu ACTIVE. Ngày mặc định tự cập nhật khi qua ngày mới nếu người dùng chưa chọn khoảng khác; Hôm nay đặt lại tất cả bộ lọc.
- Kiểm tra trực tiếp 16/09: SQL mới và API hôm nay đều có Chuộc đồ lúc 14:33:05. Không phát hiện API loại bỏ phiên này. Danh sách chỉ đọc SQL mới, không trộn lịch sử pawn_log chưa chuyển đổi.

### Thanh lý: chọn giá trị thu — 16/09/2026
- Popup Thông tin phiên có radio: tiền gốc (mặc định), gốc + lãi, giá trị thực tế. Tổng thu bằng đúng lựa chọn; ẩn ô thêm/bớt nhập tay riêng nghiệp vụ Thanh lý.
- Giá trị thực tế = tổng net_weight × giá hiện tại gold_price.value theo gold_code và cùng đơn vị, không lấy đơn giá lịch sử trên phiếu, không nhân 70%. Thiếu món/giá/trọng lượng, món KHAC hoặc khác đơn vị sẽ chặn riêng lựa chọn thực tế. Giá được tính lại khi xác nhận; tổng thay đổi thì yêu cầu tính lại.
- Thanh lý đưa dư gốc về 0. Chọn gốc hoặc thực tế không thu lãi riêng; chọn gốc+lãi dùng quy tắc lãi hiện hành. Chênh lệch giá trị thực tế với gốc lưu extra_amount/discount_amount để giữ đối soát dòng tiền. terms_json.liquidation của log lưu lựa chọn, giá, trọng lượng từng món và tổng. Không đổi phiên Thanh lý cũ.

### Nguồn giá vàng duy nhất KHBL — 16/09/2026
- Ghi đè quy tắc giá ở các mục trước: mọi định giá mới và thanh lý đọc trực tiếp khj_bl.gold_prices.buy, is_current=1, chọn id mới nhất mỗi gold_type như KHBL. Không fallback sang khj_cd.gold_price.value. Bảng cũ chỉ còn phục vụ nhãn/đơn vị hồ sơ nguồn cũ.
- Mapping 61→610, 99→9999, 98→980, sjc→SJC (đồng/chỉ); bk→BK, vt→VT (đồng/gram). KHAC không phải vàng, giữ định giá nhập tay. Thiếu giá hiện tại thì không cho chốt món vàng hay thanh lý thực tế.
- Form cập nhật giá khi chọn loại vàng, quay lại cửa sổ và mỗi 60 giây khi đang nhập. API /camdo/gia-vang no-store. Server đọc lại giá, chặn giá gửi lên cũ/sửa tay; báo cập nhật trước khi xác nhận. Hồ sơ đã chốt giữ đơn giá lịch sử; thanh lý thực tế đọc giá KHBL hiện tại.
- Kiểm thử dùng GOLD_PRICE_DB trỏ CSDL khj_cd_test_* riêng; không ghi vào gold_prices thật của KHBL.

### Tối ưu tải bàn lập phiếu — 16/09/2026
- Tài nguyên popup CSS/JS/font đọc trực tiếp từ D:/PYTHON/KHBL/static (config KHBL_STATIC_ROOT), danh sách cho phép giống KHBL và kiểm tra đường dẫn. Giữ auth, CSP; nếu không có file cục bộ thì dùng bridge cũ. Không sao chép bộ logic khách hàng.
- URL CSS/JS có phiên bản mtime_ns; cache private 1 ngày khi phiên bản khớp. Tài nguyên không version (font qua CSS) revalidate bằng ETag/Last-Modified, trả 304. HTML/API/ảnh khách tiếp tục no-store, lỗi và chuyển đăng nhập không cache.
- Mở phiếu trống không gọi danh sách khách; vẫn lấy khách được chọn và tìm kiếm theo API khi nhập. Bỏ truy vấn recent và safes không được template sử dụng. Giữ thống kê ngày, nhân viên, giá vàng trực tiếp.
- Đo Chrome + log Caddy: trước main 843ms, popup assets 48 request/697660 bytes, hoàn tất sau 5.97s. Lượt đầu sau sửa main 98.9ms, 24 asset request (12 trả 304),174415 bytes, hoàn tất sau 1.46s. Đây là thời gian HTTP, không phải chỉ số FPS. 55 kiểm thử đạt; kiểm tra lại 4 iframe và không thấy lỗi JS.

## In thẳng giấy cầm đồ tại quầy — 17/09/2026

- Nút **▤ IN PHIẾU** ở `/camdo/lap-phieu` in theo cách của Bán lẻ: tải mảnh `GET /camdo/bien-nhan/<id>/giay-manh` (cắt từ đúng `_dung_trang()` của trang giấy cầm đồ, một bản vẽ duy nhất) vào ô ẩn `#khcd-in`, `desk-print.css` ẩn giao diện quầy khi in, rồi `window.print()` từ chính cửa sổ quầy; `afterprint` dọn. Khổ trang do `mau-in.css` (cấu hình KHBL `/he-thong/mau-in-gcd/`, khổ **A4T** = không ép khổ/hướng, lề 0, tờ A5 ngang ghim góc trên-trái = nửa trên tờ A4 đứng; chọn A4 đứng trong hộp thoại in, Edge nhớ cho lần sau). Phiếu đã chuộc/thanh lý/báo mất trả 423, quầy báo lý do, không in.
- **Máy in**: trang web không chọn được máy in. `--kiosk-printing` in ra máy in **mặc định Windows** và là cờ của cả tiến trình Edge, nên Cầm đồ chạy trong **Edge riêng, không có cờ đó**: `ops\MO_QUAY_CAM_DO.bat` (chép ra Desktop PC KK) mở `--user-data-dir=%LOCALAPPDATA%\KHCD_Edge --app=…/camdo/lap-phieu`. Bấm IN PHIẾU → hộp thoại in hiện ra, Edge nhớ máy in dùng lần trước của hồ sơ này: lần đầu chọn **HP Laser CAM DO** (khổ A4, tỷ lệ 100%, lề Mặc định/None, tắt Fit to page), từ lần sau chỉ **Enter**. Bán lẻ vẫn chạy Edge kiosk cũ, in thẳng LBP6230dn. Hai hồ sơ Edge tách biệt nên không dùng chung máy in.
- Đường in phía máy chủ (`in-may-chu`, cần SumatraPDF) vẫn giữ nhưng không dùng ở quầy: hai máy in đều là máy in "(redirected)" của phiên Remote Desktop từ PC KK, chỉ tồn tại trên máy chủ khi phiên đang mở.

## Gửi SMS (ZNS) — 18/09/2026

- Mục **GỬI SMS** (`/camdo/gui-sms`, icon `sendsms.png`, sau BIÊN NHẬN): kiểm soát phiếu → lên lịch nhắc khách. `d` = hôm nay − ngày **giao dịch gần nhất** (không tính mở khóa báo mất). **Lịch nhắc GĐ chốt**: lần 1 = 15 ngày · lần 2 = 30 · lần 3 = 45 (notes báo "thanh lý trong 15 ngày tới") · **lần 4 (cuối) = 60** (notes "THANH LÝ trong 7 ngày tới") · `d ≥ 67` = hết hạn nhắc → nhóm **Chờ thanh lý**. KHÔNG có tin "thanh lý" riêng gửi khách. Tham số ở `sms.MUC` / `sms.HAN_CHOT`.
- **Chu kỳ nhắc**: mỗi giao dịch mới mở chu kỳ mới (mốc = id dòng `cd_loan_logs` gần nhất), nhắc lại từ lần 1; khóa chống trùng = `sha256("1|khcd_pawn|{loan}|{mốc}|{mức}")`. **Đã nhắc mức nào thì ẩn** khỏi "Cần nhắc" tới khi `d` chạm mức kế (mức tới hạn > mức đã xử lý; tin hủy/lỗi không tính). Nhảy cóc chỉ đề xuất MỘT tin ở mức hiện tại. Một SĐT nhiều phiếu: xếp hàng bình thường, không giới hạn thêm.
- **Tắt nhắc từng biên nhận** (nút 🔕 trên dòng): *Tắt hẳn* hoặc *Hoãn đến ngày*, bắt buộc lý do; đặt xong tự hủy tin đang chờ; chip "Không nhắc" để bật lại.
- **Tự hủy tin chờ khi có giao dịch mới / phiếu đóng**: `sms.sau_giao_dich()` móc ở `live.commit` và `views.desk_cancel` (không bao giờ ném lỗi ra luồng tiền) + lưới an toàn `ra_tin_cho()` mỗi lần mở trang.
- **Hai bảng riêng trong khj_cd** (tự tạo bằng `sms.ensure_schema()`; KHÔNG ghi vào `cd_loans`/`cd_loan_logs` vì đó là sổ tiền có vân tay + đối soát): `cd_sms_control` (1 dòng/phiếu: tắt/hoãn/lý do/ai đặt) · `cd_sms_log` (1 dòng/tin: phiếu, mốc chu kỳ, mức, d, bản chụp 6 biến, `zalo_message_id` + `tracking_id` + `dedupe_key`, giờ hẹn, trạng thái đọc lần cuối, ai tạo/sửa). Cột phải của trang đọc `cd_sms_log`; `dong_bo()` kéo trạng thái từ `khj_bl.zalo_messages` mỗi lần mở trang. **Đối soát hai chiều**: tin có log mà mất bên sổ KHBL → `missing` (tab Lỗi); dòng `khcd_pawn` bên sổ KHBL không có log → băng cảnh báo. Popup XEM biên nhận có khối "Nhắc khách (ZNS)".
- Sổ gửi là **`khj_bl.zalo_messages`** (KHBL/CARE360 gửi theo `scheduled_at`), mẫu ZNS **635511** với 6 biến `pawn_code · customer_name · anh_chi · promise_date · days · notes`. Dòng Cầm đồ: `source_type='khcd_pawn'`, `channel=phone`, `status=queued`, băm SĐT `care360-zbs|84…`, `recipient_ciphertext='khcd_no_cipher'`, `send_rule_id=NULL`, `created_by`=id tài khoản. **Mọi câu SQL đều lọc `source_type='khcd_pawn'`**. Giờ gửi 8:00–20:00. `ZNS_DB` (.env, mặc định `khj_bl`); sổ hỏng → trang vẫn 200 kèm cảnh báo.
- Mẫu 635511 hiện **DISABLE** trên Zalo OA và bộ gửi KHBL chưa chạy thật ⇒ tin nằm chờ tới khi KHBL bật; KHBL tự quản chi phí. Bộ kiểm `tests/test_sms.py` (6 bài, CSDL nháp chép DDL 2 bảng zalo từ khj_bl).
- **Quy tắc nhắc trong SQL — `cd_sms_rules` (18/09/2026 tối)**: 4 mức cố định theo `level_no` 1–4 (chỉ bật/tắt, không xóa): số ngày, tên mức, câu `notes` (≤200 ký tự, không link, biến con `{lan}` `{days}` `{ngay_thanh_ly}` `{so_ngay_con_lai}`); `cd_sms_settings`: hạn chót chờ thanh lý, khung giờ gửi, giờ mặc định, xưng hô mặc định; `cd_sms_rules_history` lưu mọi lần sửa (ai, lúc nào, cũ → mới). Ràng buộc: ngày tăng dần theo lần, hạn chót > lần cuối, giờ mặc định nằm trong khung. Sửa ở nút **⚙ Quy tắc nhắc** trên trang — chỉ tài khoản quản trị lưu được, mọi tài khoản xem được. Không có ngày hiệu lực: tin đã lên lịch giữ bản chụp biến trong `cd_sms_log`, quy tắc mới áp dụng từ lượt lên lịch kế. Giá trị gieo lần đầu = `sms.MUC` / `sms.CAI_DAT_MAC_DINH`.
- **Biến tin**: `days` = d = hôm nay − ngày giao dịch gần nhất (GĐ chốt: đó là "số ngày quá hạn"), `promise_date` = CHÍNH ngày giao dịch gần nhất để câu "quá hạn kể từ ngày X – số ngày: d" khớp nhau. **`anh_chi`**: tên KK có tiền tố "Anh …"/"Chị …" thì **tiền tố thắng** (đo 18/09: 81/90 khách tên "Anh …" mang Gender=Nữ — False trên KK phần lớn là mặc định lúc nhập); không có tiền tố thì theo `I_CUSTOMER.Gender` (True → Anh · False → Chị); chưa có gì → xưng hô mặc định. KHÔNG đoán theo chữ lót/tên gọi — cầu nối KHBL `customer_bridge.FIELDS` đã thêm `Gender`, KHCD `customer_master.adapt()` trả `gender`, `hydrate()` trả `customer_gender`; dòng chưa có giới tính hiện dấu ⚥? để quầy bổ sung ở hồ sơ khách; vẫn sửa tay được từng tin ở cột phải. **`customer_name` tự bỏ tiền tố "Anh/Chị" ở đầu** (`ten_khong_tien_to`: "Chị Quỳnh" → "Quỳnh").
