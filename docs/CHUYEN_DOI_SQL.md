# Mô hình Cầm đồ tối giản và chuyển từng phiếu

Chốt theo yêu cầu ngày 14/09/2026: bám SQL cũ, chỉ thêm **4 bảng**.

| Bảng mới | Thay cho / nội dung |
|---|---|
| `cd_loans` | `pawn`: giữ `legacy_pawn_id`, mã phiếu, **phone cũ + cust_id KK**, trạng thái độc lập, nghiệp vụ gần nhất, gốc đầu/dư gốc, ngày, lãi suất, tủ, thông tin nguồn và dấu vết chuyển |
| `cd_loan_items` | Các món `gold1/2` hoặc toàn bộ danh sách món bổ sung; mỗi món một dòng; định giá cũ không có thì NULL |
| `cd_loan_logs` | `pawn_log`: giữ ID gốc, loại nghiệp vụ, ngày, gốc trước/biến động/sau, lãi, khoản cộng/giảm, dữ liệu gốc đầy đủ |
| `cd_payments` | Tách `total`/`mbank` thành các dòng CASH/BANK và IN/OUT; giữ thông tin ngân hàng nguồn, đánh dấu tiền lịch sử đã ghi nhận chứ không tự xác nhận giao dịch ngân hàng |

Tái sử dụng `pawn_status` làm danh mục **nghiệp vụ**, `khcd_event` làm nhật ký thao tác, ảnh hiện có qua `legacy_pawn_id`. Không tạo riêng bảng trạng thái, bảng nhân viên, bảng khách, bảng ngân hàng, bảng audit hoặc bảng ảnh thứ hai. Ảnh không sao chép BLOB lần nữa: giữ tham chiếu kèm SHA256; đường dẫn ảnh PHP giữ nguyên trong JSON nguồn. Không xóa các nguồn ảnh cũ.

Trạng thái chuyển từ nguồn: 1/2/3/4/7 → ACTIVE, 5 → REDEEMED, 6 → LIQUIDATED, 0 → CANCELLED. Mã 7 đồng thời bật `receipt_lost`, không tự reset lãi. `last_operation_id` giữ mã nghiệp vụ cũ. Quá hạn tính từ ngày hẹn và trạng thái, không tạo trạng thái đóng khoản vay. Khi triển khai luồng mới sẽ thêm DRAFT/LIQUIDATING theo mô hình đã duyệt.

## Chính sách tiếp tục áp dụng khi phát triển nghiệp vụ

- Khách hiện tại lấy `KK.I_CUSTOMER.CustID`; SĐT trên phiếu giữ nguyên để đối soát. Chuyển đổi chỉ đọc KK, không UPSERT hay đổi liên kết khách.
- Nhân viên giao dịch là `T_EMPLOYEE.EmpID`; người thao tác là `khj_bl.auth_user.id`; không coi ID user PHP là EmpID. HR tiếp tục liên kết danh mục đã chốt.
- Điều kiện lãi được phiên bản hóa trong `terms_json` của phiếu/log; các đoạn tính, miễn giảm, căn cứ phê duyệt có thể bổ sung vào JSON của đúng log trước khi cần tách bảng chuyên dụng. Không làm tròn lại hoặc tính lại lịch sử khi chuyển. Hiện đánh dấu `LEGACY_RECORDED` vì không đủ bằng chứng xác định thuật toán của mọi dòng cũ.
- `sotien` + loại nghiệp vụ quyết định thay đổi gốc; `tienthem/tienbot` là cộng thêm/giảm trừ thanh toán, không mặc định tăng/giảm gốc.
- Tiền CHI nhận bởi khách; tiền THU nhận bởi tiệm (`gold_bank`, mặc định type=pawn). Cầm thêm có thể đồng thời thu lãi và chi gốc; bù trừ phải biểu diễn rõ khi làm luồng xử lý mới.
- Thanh lý giữ dữ liệu lịch sử nhưng không giả định đó là giá bán/thu hồi đã xác minh. Giao trả vàng, mất biên nhận và đóng nợ là các sự kiện cần kiểm soát riêng.
- Một hệ ghi chính cho mỗi phiếu. Phiếu đã ghi tiền không xóa cứng; sửa bằng quy trình điều chỉnh/đảo có dấu vết.

## Giai đoạn hiện tại: STAGED

**Chỉ chuyển dữ liệu và đối soát, chưa chuyển luồng vận hành sang cd_loans.** Các màn hình lập/gia hạn/chuộc hiện vẫn dùng `pawn`; bản chuyển không được cộng thêm vào thống kê tiền hoặc dư nợ. Popup nói rõ điều này trước khi xác nhận.

Một bản chuyển có `source_hash` và `target_hash`. Khi nguồn phát sinh giao dịch hoặc dữ liệu đích thay đổi, lần đối soát tiếp theo báo lỗi chênh lệch; không tự ghi đè bản đã chuyển. Trước tiếp quản chính thức phải đối soát lại, bổ sung luồng nghiệp vụ cho bảng mới và ngừng ghi PHP/nguồn cũ. Chưa có nút tiếp quản hoặc ghi tiền vào bảng mới trong đợt này.

## Popup chuyển đổi

Trang `/camdo/phieu-cam-do` có nút CHUYỂN ĐỔI đầu trang và nút trên từng dòng; chỉ quản trị viên truy cập được chức năng này.

1. Nhập đúng mã hoặc chọn phiếu ở danh sách.
2. Xem khách, trạng thái, số món/log/dòng tiền, dư gốc, tiền mặt/chuyển khoản/lãi; bảng đối chiếu ưu tiên lỗi và lưu ý.
3. Lỗi chặn gồm thiếu CustID hợp lệ ở KK, mất kết nối KK, thiếu lịch sử, lỗi số/ngày, thứ tự không đúng, nghiệp vụ không biết, sai trọng lượng, các nguồn món không khớp, gốc hoặc tiền thu/chi không cân, mã trùng, mốc lãi khác nhau.
4. Lưu ý gồm SĐT khác khách KK hiện tại, thiếu định giá/đơn vị cũ, chưa xác định nhân viên, thanh lý chưa đối soát giá bán. Xem và xác nhận trước khi chuyển.
5. POST đọc lại nguồn và kiểm hash đối soát; khóa phiếu/log trong giao dịch, tạo cả bốn nhóm dữ liệu, đọc kiểm đích, ghi audit, rồi commit. Bất kỳ lỗi nào rollback toàn bộ.
6. Gửi trùng hoặc hai người chuyển cùng phiếu chỉ tạo một bản; nguồn thay đổi sau xem trước phải đối soát lại. Chuyển hàng loạt dùng cùng cơ chế kiểm tra và giao dịch riêng cho từng phiếu, không tự sửa dữ liệu sai.

Giới hạn hiện tại: phiếu không có đủ lịch sử không được tự dựng số dư mở đầu. Cần quy trình đối soát/chốt số dư riêng trước khi chuyển các phiếu đó. Thông tin ngân hàng lịch sử giữ nguyên giá trị thô, không tự suy diễn tài khoản nhận.

### Ngoại lệ đã duyệt, có điều kiện 6 tháng — 14/09/2026

Trong popup đơn hoặc hàng loạt, tick **Cho phép lỗi đã duyệt** rồi đối soát lại. Chỉ `CUSTOMER`, `CASHFLOW`, `ITEM_COUNT` được hạ từ lỗi thành cảnh báo, giữ chi tiết nguồn/kỳ vọng. Áp dụng cho nhóm lỗi tiền thu/chi, bao gồm Log #47063. Chế độ này yêu cầu mọi phiếu chọn có giao dịch thực trong `pawn_log.date2` từ ngày cùng kỳ 6 tháng trước đến thời điểm hiện tại (giờ Việt Nam); tháng thiếu ngày thì lấy ngày cuối tháng, gồm toàn bộ ngày đầu kỳ, không nhận ngày tương lai. Ví dụ kiểm ngày 14/09/2026 thì kỳ bắt đầu 14/03/2026. Không có lịch sử không thể hưởng ngoại lệ.

Đổi tùy chọn phải đối soát lại. GET/POST truyền `allow_exceptions=yes`; review_hash ràng buộc chế độ, bằng chứng giao dịch và ngày kiểm tra. POST kiểm lại toàn bộ trong transaction. Chế độ mặc định vẫn chặn ba lỗi trên; phiếu hợp lệ hoàn toàn vẫn chuyển theo quy trình cũ.

Không sửa tiền thu/chi, không tự ghép hoặc tạo khách, không tạo món vàng giả. Toàn bộ thông tin tài sản gốc vẫn trong `legacy_json`; BIÊN NHẬN hiển thị mô tả cũ nếu chưa có dòng món. Quy tắc + kỳ kiểm tra + giao dịch đủ điều kiện + danh sách lỗi chấp nhận được lưu trong `cd_loans.terms_json.conversion_exceptions` và audit hiện có; checksum đích bao gồm metadata này. BIÊN NHẬN hiển thị người xác nhận và các ngoại lệ, đồng thời vẫn báo sai lệch mới. Không cần migrate schema. Các lỗi khác, đặc biệt thiếu lịch sử/mở đầu, sai gốc, thiếu SĐT hoặc KK mất kết nối, tiếp tục chặn.

## Cài đặt và kiểm thử

DDL nằm trong `khcd/loan_conversion.py`; chạy `.venv\Scripts\python.exe scripts\migrate_conversion.py` để sao lưu rồi CREATE TABLE IF NOT EXISTS. Không ALTER/DROP bảng nguồn.

Đã tạo bốn bảng InnoDB trên `khj_cd`, sao lưu `backups/khj_cd_conversion_20260914_203932.sql`. Chưa chuyển phiếu thật. 109 kiểm thử toàn bộ đạt, gồm 11 kiểm thử chuyển đổi: chống trùng/đồng thời, rollback, thay đổi nguồn/đích, nhiều món/ảnh, lỗi KK, quyền và CSRF. Kiểm UI nguồn thật chỉ GET đối soát phiếu hợp lệ và thiếu CustID; không bấm chuyển dữ liệu thật.

## Bổ sung BIÊN NHẬN — 14/09/2026

### Chuyển hàng loạt phiếu ĐANG CẦM — bổ sung cùng ngày

Nút **CHUYỂN ĐỔI** ở đầu trang Phiếu cầm đồ mở popup toàn bộ phiếu `pawn.status IN (1,2,3,4,7)`, không phụ thuộc bộ lọc/từ khóa hoặc trang hiện tại của danh sách phía sau. Tải theo cursor 200 dòng mỗi yêu cầu và chốt ID lớn nhất lúc mở; popup phân trang 50 dòng, có tìm mã/SĐT/CustID và lọc kết quả. Phiếu thêm mới sau thời điểm tải sẽ xuất hiện khi tải lại. Trạng thái nguồn được kiểm tra lại trước khi ghi.

1. Bấm **Đối soát tất cả phiếu chưa chuyển**. Chạy lần lượt từng phiếu, đọc KK bằng CustID, kiểm dữ liệu gốc và lịch sử như luồng đơn. Phiếu đã có `cd_loans` được bỏ qua mặc định; vẫn có nút đối soát chi tiết để phát hiện sai lệch.
2. Phiếu đạt được chọn sẵn; có thể bỏ chọn từng phiếu hoặc chọn/bỏ toàn bộ phiếu đủ điều kiện trên mọi trang. Phiếu lỗi/đã chuyển bị khóa chọn. Xem chi tiết các lưu ý, tick xác nhận rồi bấm **Xác nhận chuyển N phiếu**. Thay đổi lựa chọn sẽ bỏ tick xác nhận cũ.
3. Hàng đợi trình duyệt gửi từng phiếu theo thứ tự, mỗi POST có CSRF và review_hash, kiểm quyền quản trị, trạng thái ACTIVE, kiểm lại nguồn, rồi dùng transaction/khóa/chống trùng/readback/audit hiện có. Không tạo bảng công việc mới. Lỗi xác định ở một phiếu cho phép tiếp tục phiếu kế; phiếu trước đã thành công được giữ lại.
4. Nút **Dừng sau phiếu hiện tại** ngừng hàng đợi ở ranh giới giữa hai phiếu. Giữ popup mở trong lúc chạy. Đóng tab/mất mạng không có worker chạy ngầm; yêu cầu đang gửi có thể đã commit, nên phải tải lại/đối soát để biết kết quả. Khi phản hồi chưa xác định, hàng đợi dừng và khóa xác nhận tiếp cho đến khi đã đối soát lại phiếu đó hoặc tải lại danh sách. Gửi lại một phiếu đã chuyển không tạo bản trùng.
5. Kết quả riêng từng phiếu và tổng số thành công/lỗi/chưa xử lý hiển thị ngay. Dữ liệu vận hành vẫn là `pawn`; batch tạo bản STAGED, không tự tiếp quản hoặc sửa khách/ảnh. Nút chuyển ở từng dòng danh sách cũ vẫn giữ popup chuyển riêng một phiếu.

Kiểm thử mới: danh sách hơn 200 dòng không trùng/bỏ sót qua cursor, đủ nhóm trạng thái đang cầm, loại phiếu đóng, lỗi từng phiếu không rollback các phiếu trước, retry không trùng, quyền/CSRF/xác nhận/chỉ đọc. Thử popup trên CSDL giả đã chuyển 2 phiếu đạt, loại phiếu thiếu CustID và phiếu đã có bản; tải lại nhận diện đúng 3 phiếu đã chuyển. Không chuyển hàng loạt dữ liệu thật khi kiểm thử.

Menu `/camdo/bien-nhan` đọc bốn bảng mới, có tìm kiếm và lọc trạng thái; chi tiết cung cấp kiểm tra toàn vẹn, đối chiếu từng trường phiếu, từng món, log và dòng tiền. Mặc định chỉ hiện lỗi/cảnh báo; bỏ chọn để xem toàn bộ kết quả. Các thao tác này chỉ đọc. Không ghi đè bản chuyển khi nguồn thay đổi; chưa tiếp quản nghiệp vụ từ `pawn`.

Ảnh dùng `documents_json`: tên tệp PHP được đọc từ `LEGACY_PAWN_IMAGE_ROOT`; ảnh BLOB dùng lại `khcd_pawn_photo` và kiểm checksum. Route ảnh yêu cầu đăng nhập, không cache, chặn đường dẫn ra ngoài kho. Tệp PHP được kiểm định dạng và khả năng đọc; chưa có checksum lịch sử nên không thể xác nhận nội dung còn nguyên từ ngày lập. Kho ảnh phải được sao lưu cùng CSDL. Khi có kho ảnh đầy đủ, giữ tên tệp và đổi cấu hình thư mục là cách triển khai đơn giản nhất; chưa sao chép hoặc xóa ảnh trong lượt này.

Kiểm tra triển khai: **115 kiểm thử đạt** trên CSDL thử riêng; 6 ca mới kiểm nguồn/đích sai lệch, thiếu dòng, nguồn bị mất, ảnh tệp/BLOB, chặn đường dẫn ngoài kho, đăng nhập và quyền tra cứu. Kiểm UI ở 1280 px và 390 px, bộ lọc 6 lỗi/cảnh báo so với 46 hạng mục đầy đủ, không tràn ngang trang. Một biên nhận đã có trong SQL mới trước lượt này; hai tệp ảnh tham chiếu chưa thấy trong kho mặc định, hiện báo lỗi rõ. Không tạo giao dịch hoặc chuyển phiếu thật để kiểm thử.

Kiểm chứng bản hàng loạt: 120 kiểm thử đạt. Popup production tải đủ 989 phiếu đang cầm qua 5 lượt cursor, chia 20 trang và nhận diện 1 bản đã chuyển; chỉ kiểm tra tải/phân trang, không xác nhận chuyển phiếu thật. Đã bổ sung pytest.ini để bộ kiểm thử chỉ thu thập thư mục tests của dự án chính, không thu thập bản sao lưu cũ trong backups.
