# Lịch sử giai đoạn tra cứu khách — đã được thay thế

Tài liệu này chỉ lưu bối cảnh trước khi chủ hệ thống xác nhận đã đồng bộ khách sang KK và yêu cầu chuyển nguồn/UPSERT. Quyết định vận hành hiện hành nằm trong README.md.

## Khách hàng — giới hạn hiện tại và lộ trình đề xuất

**Trạng thái ngày 14/09/2026: ĐÃ triển khai hai tab và bảng so sánh chỉ đọc. CHƯA đồng bộ khách, CHƯA xác nhận/lưu liên kết ID, CHƯA đổi nguồn khách và CHƯA ghi dữ liệu MSSQL.** Nút `Sync` và `+ Thêm vào MSSQL` vẫn là đề xuất, chưa bật. Không tự chạy di trú từ kế hoạch này.

### Những điều phải giữ nguyên trong giai đoạn hiện tại

- `I_CUSTOMER` giữ nguyên cấu trúc và dữ liệu: không cập nhật, ghi đè, thêm cột, thêm/xóa khách theo đề xuất này. Các ý tưởng `Sync` và `+` bên dưới là chức năng tương lai, không phải thao tác được thực hiện ngay.
- Giữ toàn bộ khách hàng `khj_cd.customer` vì đang phục vụ nghiệp vụ. SĐT là khóa liên kết nghiệp vụ hiện tại giữa khách và phiếu; không tự sửa/chuẩn hóa số đang lưu, gộp hoặc xóa khách làm đứt liên kết. Khóa kỹ thuật `customer.id` vẫn phải giữ.
- Tiếp tục sử dụng luồng hiện tại cho tới khi có kế hoạch chuyển đổi được chốt và kiểm tra. Không ngưng bảng khách CĐ khi còn phiếu đang tham chiếu theo SĐT.
- Đích cuối cùng: KHCD sử dụng khách từ `I_CUSTOMER`; ngưng dùng `khj_cd.customer` làm nguồn khách hoạt động sau đối soát và chuyển đổi thành công. "Ngưng sử dụng" không có nghĩa xóa bảng hoặc xóa lịch sử; giữ bản lưu chỉ đọc và bảng đối chiếu để truy vết.

### Giao diện `/khach-hang`: hai tab đã triển khai

| Tab | Dữ liệu và thao tác hiện có |
|---|---|
| **Khách PMV** | Đọc `I_CUSTOMER`, tìm theo SĐT/tên/CCCD/mã khách/CustID, phân trang, hiển thị ứng viên đối chiếu CĐ; chỉ đọc, chưa xác nhận liên kết |
| **Khách CĐ** | Đọc `khj_cd.customer`, giữ các thao tác đang vận hành, thêm trạng thái đối chiếu PMV và lối mở bảng so sánh |

Mỗi khách có bảng so sánh theo từng trường: **Trường thông tin · Giá trị CĐ · Giá trị PMV · Kết quả so sánh · Hướng xử lý đề xuất**. Nhóm so sánh gồm tên, SĐT, CCCD, địa chỉ; hiển thị riêng `customer.id` CĐ và `I_CUSTOMER.CustID`. Ghi chú riêng của nghiệp vụ CĐ được giữ riêng. Không mặc định hai trường cùng tên có cùng ý nghĩa.

Các trạng thái cần phân biệt: chưa đối chiếu, có ứng viên trùng SĐT, đã xác nhận liên kết, khác thông tin, nhiều ứng viên, xung đột CCCD, chưa tìm thấy trong PMV, lỗi kết nối. Mất kết nối hoặc truy vấn lỗi **không** được hiển thị thành "PMV chưa có".

Hiện có nút **So sánh** mở `/khach-hang/doi-chieu`, xem dữ liệu gốc hai bên và số phiếu liên quan theo SĐT gốc. Một ứng viên chỉ được chọn để hiển thị, không đồng nghĩa đã xác nhận cùng người; nhiều ứng viên phải chọn từng hồ sơ để xem. Có thêm trạng thái trùng CCCD nhưng khác SĐT và thiếu định danh hợp lệ. Trạng thái **đã xác nhận liên kết** dành cho giai đoạn sau, chưa có trong bản này. Tab CĐ vẫn là mặc định và giữ CRUD đang vận hành.

Kết nối nguồn chính KK được cấu hình riêng qua `PMV_MSSQL_*` trong `.env` (xem `.env.example`), không phụ thuộc tiến trình KHBL hay tự chuyển sang CSDL sandbox. Cần `pyodbc==5.3.0` và ODBC driver tương thích máy chủ; máy hiện tại dùng SQL Server Native Client 10.0. Bộ đọc `khcd/pmv_customers.py` chỉ có câu lệnh SELECT, luôn rollback/đóng kết nối, không gọi thủ tục ghi. Đây là giới hạn của mã ứng dụng, không khẳng định tài khoản SQL hiện có chỉ có quyền đọc; tài khoản chuyên biệt chỉ có SELECT là cải tiến vận hành tiếp theo.

Nguồn KK hiện là SQL Server 2005: đối chiếu lấy các khóa CustID/SĐT/CCCD vào bộ nhớ, chuẩn hóa để tìm ứng viên rồi đọc hồ sơ theo CustID; không sửa chuẩn hóa vào CSDL, không lưu bản sao khách hoặc cache kết quả cũ. Có timeout và giới hạn số ứng viên; khi lỗi hoặc vượt giới hạn, báo chưa đối chiếu được. Mất nguồn PMV vẫn tra cứu/CRUD khách CĐ được, không kết luận khách thiếu ở PMV. Môi trường `TESTING` chặn kết nối MSSQL thật.

Khảo sát chỉ đọc ngày 14/09/2026: PMV **56.877** khách, CĐ **7.547** khách. Phân loại CĐ: 2.956 có một ứng viên trùng SĐT; 4.379 chưa tìm thấy đối ứng; 160 thiếu định danh hợp lệ; 26 có nhiều ứng viên; 8 xung đột CCCD; 18 trùng CCCD nhưng khác SĐT. Đây là số hồ sơ/ứng viên tại thời điểm khảo sát, **không phải số người đã liên kết**. Chỉ lưu số tổng hợp trong `output/customer-reconciliation-summary.json`, không xuất thông tin cá nhân.

### Đề xuất nút `Sync` khi có ứng viên trùng SĐT

1. Chuẩn hóa SĐT để **so sánh** (khoảng trắng, dấu phân cách, `+84`/`0` khi hợp lệ), vẫn giữ nguyên dữ liệu gốc. Trùng SĐT chỉ tạo ứng viên; nhân viên xác nhận bằng tên/CCCD và hồ sơ trước khi gắn liên kết.
2. Nếu một SĐT có nhiều khách, hoặc CCCD hai bên mâu thuẫn, chuyển sang đối soát thủ công. Không tự lấy khách đầu tiên, ID nhỏ nhất hoặc tự gộp người chỉ vì trùng số.
3. Sau xác nhận, ưu tiên **liên kết ID** và dùng dữ liệu PMV cho phần thông tin khách chung. Đề xuất tách hai lựa chọn rõ: **Chỉ liên kết** và **Nhận thông tin từ PMV**.
4. Nếu triển khai `Sync` dữ liệu trong giai đoạn chuyển tiếp, hướng đề xuất là **PMV → CĐ**, chọn từng trường hoặc tất cả trường được phép. Không có đồng bộ hai chiều ghi đè `I_CUSTOMER` mặc định.
5. "Tất cả" chỉ bao gồm các trường hồ sơ đã được duyệt ánh xạ. Không gồm ID, SĐT đang liên kết phiếu, ghi chú riêng, tiền, lãi suất, trạng thái phiếu hoặc lịch sử giao dịch. Trường nguồn rỗng không tự xóa giá trị đang có; thao tác xóa giá trị phải được chỉ rõ trong bản xem trước.
6. Hiển thị thay đổi trước/sau và hướng đồng bộ trước khi ghi; kiểm tra bản ghi chưa bị sửa ở phiên khác. Lưu người thực hiện, thời gian, nguồn/đích, trường thay đổi và mã xử lý chống lặp. Chức năng này chưa được thực hiện chỉ từ việc ghi nhận đề xuất.

### Đề xuất nút `+` khi khách CĐ chưa có trong PMV

Ý tưởng của chủ hệ thống: có nút **`+ Thêm vào MSSQL`**. Lưu ý ranh giới: đây là thao tác tạo mới trong `I_CUSTOMER`, khác với yêu cầu hiện tại "không thay đổi và cập nhật gì thêm". Vì vậy **chỉ lưu thiết kế**, chưa triển khai hoặc bật ghi. Cần chốt riêng việc cho phép **INSERT khách còn thiếu**, kể cả khi vẫn cấm UPDATE khách PMV đã có.

Khi được chốt triển khai: kiểm tra lại trên nguồn PMV đang truy cập được bằng SĐT và CCCD ngay trước khi tạo; xử lý hồ sơ thiếu định danh/nhiều ứng viên; dùng luồng tạo khách PMV đã được kiểm chứng và để PMV cấp `CustID`, không tự tạo ID bằng `MAX+1` hoặc dùng ID CĐ. Sau khi tạo phải đọc kiểm lại, lưu `CustID` trả về và gắn với khách CĐ gốc.

Nếu MSSQL đã tạo khách nhưng ghi liên kết vào MySQL thất bại, lưu/truy vết yêu cầu và tiếp tục đối soát để gắn lại cùng `CustID`; không bấm thử lại thành một khách mới khác. Không giả định ghi MSSQL và MySQL nằm trong cùng một giao dịch tự rollback.

### Liên kết bền vững, ảnh CCCD và chuyển nguồn

- Đề xuất một bảng ánh xạ riêng lưu tối thiểu: ID khách CĐ, `pmv_cust_id` nguyên định dạng nguồn, SĐT gốc dùng đối chiếu, trạng thái xác nhận, người/thời điểm xác nhận. Chưa tạo bảng này. Không đổi ID khách cũ thành `CustID` hoặc đổi hàng loạt `pawn.phone`.
- Khi đã liên kết, truy cập PMV bằng `CustID`; SĐT phục vụ tìm kiếm. Phân biệt trường hợp một người có nhiều hồ sơ CĐ với hai người dùng chung số; lưu dấu vết đối soát thay vì xóa hồ sơ nguồn.
- Trước khi chuyển nguồn, phiếu đang hoạt động phải có liên kết khách ổn định theo ID và thông tin khách tại thời điểm lập được bảo toàn. Bản chụp hồ sơ cũ chỉ dựa trên dữ liệu thực sự có; không coi thông tin hiện tại là bằng chứng chắc chắn của quá khứ.
- Ảnh CCCD tận dụng kho riêng KHBL và cơ chế đọc ảnh PMV hiện có, tham chiếu bằng `CustID`/mã tài liệu. Đề xuất truy cập có xác thực/phân quyền và giữ phiên bản; không sao chép thành nhiều kho độc lập hoặc công khai đường dẫn máy chủ. Chưa đồng bộ, di chuyển hay đổi tên ảnh.

Lộ trình dự kiến:

1. **Đã khảo sát chỉ đọc:** thống kê trùng/thiếu/xung đột; màn hình so sánh xem số phiếu liên quan từng hồ sơ. Chưa lưu danh sách hoặc ánh xạ khách lâu dài.
2. **Đã triển khai:** hai tab và bảng so sánh chỉ đọc; chưa bật ghi/sync.
3. Chốt quy tắc ánh xạ, hướng `Sync`, danh sách trường được phép và ngoại lệ tạo khách MSSQL; sau đó mới xây thao tác ghi có kiểm soát.
4. Xác nhận liên kết, xử lý khách thiếu và bảo toàn mọi tham chiếu của phiếu đang hoạt động; thử trên dữ liệu thử/bản sao trước.
5. Đối soát số khách, phiếu, liên kết, số dư và lịch sử; xử lý toàn bộ trường hợp chặn chuyển đổi, có bản sao lưu và phương án quay lại.
6. Chốt thời điểm chuyển KHCD sang nguồn `I_CUSTOMER`, ngưng tạo/sửa khách ở nguồn CĐ cũ; giữ bảng cũ và ánh xạ để tra cứu. Không âm thầm quay lại tạo khách ở bảng cũ khi MSSQL gặp lỗi.

