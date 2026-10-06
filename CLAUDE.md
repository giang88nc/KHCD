# KHCD — WEBAPP CẦM ĐỒ | KIM HẠNH 2

> File định hướng cho Claude Code. **Đang chạy TIỀN THẬT** (`CD_LIVE=1` từ 15/09/2026) — mọi thay đổi phải thận trọng, `main` luôn chạy được.
> UI + commit message bằng **tiếng Việt**. KHÔNG sửa code ngoài phạm vi được yêu cầu. **Không ghi thử khách/phiếu vào dữ liệu vận hành** — kiểm bằng CSDL thử riêng.
> Không chạy PHP cũ ghi song song vào `khj_cd`. Không hạ `CD_LIVE` về 0.

## 1. BỐI CẢNH

- Webapp **CẦM ĐỒ** của Kim Hạnh 2, một trong 3 app độc lập: KHBL (bán lẻ, 8100) · **KHCD (cầm đồ, 8200)** · KHJ (HR, 8000). Không gộp app/CSDL; cổng chung chỉ làm sau khi luồng dữ liệu + đăng nhập ổn định.
- Thay hệ PHP cũ (`gold/quan-ly-bien-nhan`). Lịch sử PHP (`pawn`, `pawn_log`) giữ nguyên để tra cứu/đối soát.
- Thư mục DUY NHẤT: `D:\PYTHON\KHCD` (bản cũ ở `Documents\ChatGPT` chỉ là backup, không chạy).

## 2. STACK & HẠ TẦNG

| Thành phần | Chi tiết |
|---|---|
| Backend | Python · **Flask** (`khcd/`), serve bằng **waitress** `run.py` @ `127.0.0.1:8201`; Python riêng `.venv` |
| HTTPS | **Caddy** (`ops/caddy/`) cổng **8200** → 8201; CA nội bộ dùng chung với KHBL, giữ ở `instance/caddy-data/` |
| CSDL | MySQL 8 @ **3308**, DB **`khj_cd`**, tài khoản chung **`khj_admin`** (không tạo user quyền hẹp). **DB lưu giờ VN từ 20/09/2026** |
| Đọc chéo | `khj_bl` (auth_user, gold_prices, gold_bank, pmv_state, zalo_messages, document_contacts) |
| PMV/KK | MSSQL KK `I_CUSTOMER`, `T_EMPLOYEE` — **chỉ qua cầu nối KHBL**, không SQL trực tiếp |
| Cầu nối khách | `D:/PYTHON/KHBL/venv/Scripts/python.exe -X utf8 D:/PYTHON/KHBL/manage.py run_customer_bridge --key-file instance\customer-bridge.key` @ **127.0.0.1:18202** — chạy bằng venv/code KHBL nhưng **THUỘC KHCD** |
| Secret | `.env` (không commit). Tên biến: `DB_HOST/PORT/NAME/USER/PASSWORD` · `SECRET_KEY` · `DB_READ_ONLY` · `APP_HOST/APP_PORT=8201` · `MIN_INTEREST_DAYS=1` · `AUTH_SOURCE_DB=khj_bl` · `COOKIE_SECURE=1` · `RETAIL_URL` · `PMV_MSSQL_*` (cũ, không còn phục vụ luồng khách) · `LEGACY_PAWN_IMAGE_ROOT` · `CD_LIVE`. Tùy chọn: `CUSTOMER_MASTER=kk`, `CUSTOMER_BRIDGE_KEY_FILE`, `ZNS_DB`, `GOLD_PRICE_DB`, `DOCUMENT_CONTACT_DB`, `KHBL_STATIC_ROOT`, `GCD_CONG_CU_IN`, `GCD_EDGE` |
| Git | `github.com/giang88nc/KHCD` (private, nhánh `main`). **`instance/` gitignored nhưng PHẢI giữ** (khóa cầu nối + CA LAN — mất là phải phát hành lại cert mọi máy); KHJ `backup_toan_bo` sao lưu hằng đêm |

## 3. LINK

- `https://tiemvangkimhanh2:8200` (LAN) · `https://localhost:8200` (máy chủ). HTTP tự chuyển HTTPS. Health: `/health`.
- Đường dẫn chuẩn `/camdo/...`: Tổng quan `/camdo` · Lập phiếu `/camdo/lap-phieu` · Phiếu cũ `/camdo/phieu-cam-do[/<id>]` (chưa nối khách: `?status=unlinked`) · Biên nhận SQL mới `/camdo/bien-nhan[/<id>]` · Khách `/camdo/khach-hang` · Thống kê `/camdo/thong-ke` · Gửi SMS `/camdo/gui-sms`.
- Link cũ: `khcd/urls.py` GET/HEAD → 308 sang URL chuẩn (giữ query); POST cũ gọi cùng endpoint (không đổi thành GET, không gửi lại).
- Đăng nhập = tài khoản/mật khẩu **KHBL** (`khj_bl.auth_user`). Cấu hình mẫu in GCD ở KHBL: `https://127.0.0.1:8100/he-thong/mau-in-gcd/`.

## 4. CẤU TRÚC

```
KHCD/
├── khcd/            # app Flask: urls, views, auth, db, live_loans, live_schema, loans, pawn_desk, transactions,
│                    #  desk_sessions, payment_split, banking_qr, gold_prices, customer_* , pmv_customers,
│                    #  loan_conversion, conversion_views, loan_images, gcd_layout/gcd_print/gcd_may_in, ma_vach,
│                    #  sms, document_contacts, overview, domain, services  (+ templates/ static/ resources/)
├── scripts/         # migrate*.py, sync_auth_users.py, link_customer_master.py, setup.py, inspect_live_cutover.py
├── ops/vanhanh/     # vanhanh.ps1 (BẢN SAO KHJ) + cauhinh_khcd.ps1 · ops/caddy/ · ops/MO_QUAY_CAM_DO.bat
├── instance/        # khóa cầu nối, caddy-data, log, gcd_layout.json (gitignored)
├── media/pawn       # ảnh phiếu PHP cũ · media/loans: ảnh phiếu mới
├── tests/ docs/ backups/ LAN_HTTPS_KIT/
└── RESET_KHCD.bat   # cửa vào vận hành DUY NHẤT
```

## 5. NGUỒN DỮ LIỆU

| Dữ liệu | Nguồn sự thật | Ghi chú |
|---|---|---|
| Phiếu/tiền (vận hành) | `khj_cd`: `cd_loans` · `cd_loan_items` · `cd_loan_logs` · `cd_payments` | `version` chống ghi đè; `request_key`, `reverses_log_id` UNIQUE |
| Phiếu cũ PHP | `pawn`, `pawn_log`, `customer`, `gold_price`, `pawn_status` | CHỈ XEM/đối soát/chuyển đổi; `khcd_event`, `khcd_pawn_meta`, `khcd_pawn_customer`, `khcd_pawn_desk`, `khcd_pawn_photo` |
| Khách hàng | KK `I_CUSTOMER` theo **`CustID` (chuỗi)** | UPSERT qua service KHBL (`apps/pos/customer.py`, `customer_phones.py`, PmvClient, gateway) qua cầu nối HMAC; biên nhận `khj_bl.customer_bridge_receipt` |
| NV giao dịch | KK `T_EMPLOYEE.EmpID` | người thao tác (auth_user) ghi riêng |
| Tài khoản | `khj_bl.auth_user` → đồng bộ sang `khj_cd.auth_user` | |
| Giá vàng | **`khj_bl.gold_prices.buy`, `is_current=1`, id mới nhất mỗi loại** | KHÔNG fallback `khj_cd.gold_price` |
| TK nhận tiền THU | `khj_bl.gold_bank` đang bật, ưu tiên `type=pawn` | chưa có pawn → không tự chọn TK bán lẻ |
| Mẫu in GCD + máy in | `khj_bl.pmv_state['gcd_layout']`, `may_in_ds` | KHCD CHỈ ĐỌC |
| SĐT theo phiếu | `khj_bl.document_contacts` (`source_type=KHCD_LOAN`) | ghi cùng transaction với `cd_loans.phone` |
| Tin nhắc Zalo | `khj_bl.zalo_messages` (`source_type='khcd_pawn'`) | gương `khj_cd.cd_sms_log` |

## 6. QUY TẮC NGHIỆP VỤ

**Tiền & lãi** (`live_loans.py`, `loans.py`, `domain.py`):
- Lãi = dư gốc × % tháng × số ngày / 3000; `Decimal`, tính cả kỳ rồi `ROUND_HALF_UP` tới đồng; không lãi kép, không tự thêm phí phạt; mức lãi do người dùng nhập (3/2,5/2/1,5/1 %/tháng), app không đặt mặc định pháp lý.
- Cột cũ `pawn.percent` = %/30 ngày (hiển thị %/ngày = percent/30). Không đổi nghĩa cột cũ.
- Ngày lịch VN, tối thiểu `MIN_INTEREST_DAYS`; nghiệp vụ thu lãi (3/4/5/6) tối thiểu **1 ngày và 5.000đ**, kể cả cùng ngày.
- Cầm thêm/Trả bớt: chốt lãi trên gốc CŨ → đổi gốc → kỳ mới. Dòng tiền ròng = −biến động gốc + lãi + thêm − giảm (Cầm thêm 2tr lãi 50k → CHI 1.950.000).
- Gia hạn: ngày giao dịch = mốc chốt lãi (≥ interest_from, ≤ 365 ngày); hẹn mới sau mốc, ≤ 365 ngày; `happened_at` = giờ thật, mốc hiệu lực trong `terms_json`.
- Thanh lý: radio gốc / gốc+lãi / giá trị thực tế (= Σ net_weight × giá KHBL hiện tại, không ×70%); dư gốc về 0, chênh lệch vào extra/discount.
- Báo mất: thu lãi tới ngày báo mất, **bắt buộc ảnh cam kết**; phiếu khóa mọi giao dịch tới khi Mở khóa bằng **PassCode** (băm, auth_user, 5 lần sai/5 phút). Mở khóa = log op 8, không thanh toán, không đổi mốc lãi.
- **XÓA phiên**: chỉ phiên CUỐI, tạo trên SQL mới, < 300 giây, khớp snapshot → khôi phục trạng thái trước, DELETE payments+log (không bút toán đảo). Xóa phiên Cầm mới duy nhất = DELETE cả phiếu. Phiên nhập từ PHP không xóa được.
- Mã phiếu: `KH2` + YYMM + STT 6 số, MAX STT cùng năm + 1 (khóa MySQL theo năm, UNIQUE sku).
- Cảnh báo CẦM TỐI ĐA = 70% tổng định giá (làm tròn lên 1.000đ), vượt vẫn cho xác nhận. Món `KHAC` định giá tay, không theo trọng lượng. Tối đa 30 món; tủ 1=18k, 2=24k, 3=đồ lớn.
- Thanh toán: `cd_payments` tách tiền mặt/CK; đây là GHI NHẬN, không phát lệnh ngân hàng. Đổi phương thức chỉ cho log mới nhất op 1/2, OUT > 0, trong 1.800s. VietQR offline qua `banking_qr.py` (thuật toán KHBL), QR lưu `bank_snapshot`, route `/camdo/phien/<log_id>/qr` cần đăng nhập.
- Ghi tiền + trạng thái + log trong MỘT transaction, `FOR UPDATE`, fingerprint, chỉ báo thành công sau commit; mất kết nối lúc commit → tra lịch sử trước khi thử lại, không tự POST lại.
- Tiền gốc cầm đồ KHÔNG cộng vào doanh thu bán lẻ.

**Khách hàng**: chỉ KK. Tạo để PMV cấp mã; sửa đúng CustID (mất mã → báo lỗi, không INSERT). Không gộp/xóa khách. Popup dùng nguyên `templates/pos/_khach_form.html` của KHBL trong iframe cùng origin (`/camdo/khach-hang/popup/frame`), không giữ bản sao form. Phiếu cũ chưa nối (358) không tự chọn ID đầu tiên. Ghép SĐT không phải bằng chứng danh tính.

**Đăng nhập** (`auth.py`): mỗi request kiểm lại tài khoản nguồn (đổi mật khẩu/khóa → mất phiên); nguồn không truy cập được → không phục vụ. Cookie **`khcd_session`** (Secure, 8h), CSRF mọi POST, giới hạn thử mật khẩu. Passcode không thay mật khẩu đăng nhập. Chưa có phân quyền từng thao tác (mọi user active dùng được; chuyển đổi chỉ quản trị).

**Gửi SMS/ZNS** (`sms.py`): `d` = hôm nay − ngày giao dịch gần nhất; mức nhắc trong `cd_sms_rules` (mặc định 15/30/45/60, ≥67 → Chờ thanh lý) + `cd_sms_settings` + `cd_sms_rules_history`; chu kỳ mới mỗi giao dịch; khóa trùng `sha256("1|khcd_pawn|{loan}|{mốc}|{mức}")`; `sau_giao_dich()` không bao giờ ném lỗi vào luồng tiền. Mẫu **635511**, 6 biến; giờ gửi 8–20h. **Mọi SQL lọc `source_type='khcd_pawn'`**. CARE360 (qua cầu nối KHJ) là bộ gửi DUY NHẤT; KHJ chỉ XEM loại này (sửa ở KHJ sẽ bị `dong_bo()` đè).

**In GCD** (giấy in sẵn A5 ngang): chỉ in CHỮ, không bao giờ in ảnh nền `GCD.jpg`; `gcd_layout.py` song sinh với KHBL `apps/pos/gcd_layout.py` (18 key cùng thứ tự/số đo — test FAIL nếu lệch); `ma_vach.py` là BẢN SAO KHBL (sửa bên KHBL rồi chép vùng, khóa sha256 theo ký tự). `gcd_layout.doc_so()` = bản sao `words()` trong `static/pawn-entry.js` — sửa cả hai. Quầy in qua `ops\MO_QUAY_CAM_DO.bat` (Edge hồ sơ riêng, không kiosk-printing, máy **HP Laser CAM DO**).

## 7. VẬN HÀNH

- **Cửa vào DUY NHẤT `RESET_KHCD.bat`** (07/10/2026). Không tham số = RESET đầy đủ có pause: kiểm điều kiện (thiếu MySQL80/.venv/caddy/CA/khóa cầu nối/venv KHBL → KHÔNG tắt gì) → tắt (giám sát trước) → kiểm tắt sạch → bật → kiểm `https://localhost:8200/health` phải `app: KHCD` + `customer_service: ok` (Caddy giữ 8200 dù backend chết — nhìn cổng là báo dối).
- Tham số: `/reset` (không pause — **Claude dùng**: `cmd /c D:\PYTHON\KHCD\RESET_KHCD.bat /reset` từ **PowerShell, KHÔNG từ Git Bash**) · `/bat` bật cái thiếu · `/tat` tắt hẳn (cả giám sát) · `/kiem` chỉ xem (quyền thường được).
- Đã XÓA: `TURN_ON_KHCD.bat/.vbs`, `TURN_OFF_KHCD.bat`, `scripts\host.ps1/start.ps1/stop.ps1/install-windows-host.ps1/kiem_khcd.ps1`, tác vụ Windows `KHCD Web Host`. Đừng tạo lại.
- Thành phần: cầu nối **18202** → waitress **8201** → Caddy **8200**; vòng giám sát khóa cổng **8219** (60s bật lại thành phần chết). Cổng bị app khác giữ → báo LỖI kèm PID, không giết. `RESET_KHBL` không đụng 18202.
- Động cơ `ops/vanhanh/vanhanh.ps1` = **bản sao byte-identical của KHJ** (sửa ở KHJ rồi chép KHBL + KHCD) + `ops/vanhanh/cauhinh_khcd.ps1`.
- Quyền thường bấm RESET không hỏi UAC: kích tác vụ `KimHanh2-VanHanh-KHCD` (S4U Admin, phiên nền session 0, không chết theo app gọi).
- Tự bật cùng Windows: KHJ `KHOI_DONG_TOAN_HE_THONG.bat` bước [G] → `RESET_KHCD /bat`; `RESET_TOAN_HE_THONG` gọi `/tat`.
- Log: `instance\vanhanh_khcd.log`, `server-*`, `caddy-*`, `bridge-*` trong `instance\`.
- **Sửa `.py` → RESET_KHCD; sửa `.html/.css/.js` → F5** (`TEMPLATES_AUTO_RELOAD`).
- Migration: `scripts/migrate.py` (InnoDB/DECIMAL; `--backup-env` nếu thiếu quyền), `migrate_desk.py`, `migrate_live.py`, `live_schema.upgrade`, `sms.ensure_schema()`. Luôn sao lưu trước; khôi phục vào DB khác trước, không đổ đè DB thật. Sau import SQL từ PHP phải chạy lại `migrate.py` (import đưa bảng về MyISAM/float).
- Đồng bộ tài khoản: `.venv\Scripts\python.exe scripts\sync_auth_users.py`.
- HTTPS máy LAN mới: `LAN_HTTPS_KIT\CAI_HTTPS_PC_LAN.bat`. Firewall `KHCD-HTTPS-8200-LAN` chỉ LocalSubnet; 8201 chỉ localhost.

## 8. BẪY ĐÃ DÍNH / KIỂM THỬ

- **Kiểm thử chỉ chạy đích danh tệp**: `.venv\Scripts\python.exe -m pytest tests/<tệp>.py -q`, không discover cả bộ tùy tiện. Test tích hợp cần `KHCD_TEST_ENV` (tạo `khcd_test_<rand>` rồi xóa); test phải trỏ `GOLD_PRICE_DB`/`DOCUMENT_CONTACT_DB`/`ZNS_DB` về DB thử. Smoke có kiểm tổng dòng phải chạy tuần tự.
- CSP `style-src 'self'` không `unsafe-inline`: `<style>`/`style=""` bị chặn câm → CSS động phải qua route `text/css` (vd `/camdo/bien-nhan/mau-in.css`). Không nới CSP.
- `gcd-print.css` fail-closed: CSS bố cục không nạp → ẩn tờ in. Không đặt `background` lên `.gcd-a5`, không dùng `print-color-adjust`; mã vạch phải là `<img>` PNG data URI.
- Đọc `khj_bl` hỏng không được làm mất tờ phiếu: bắt lỗi tại chỗ (không để lọt `errorhandler(pymysql.MySQLError)` → 503); đọc phiếu TRƯỚC, đọc bố cục CUỐI. Route `in-may-chu` luôn JSON 200.
- `gcd_may_in`: mọi subprocess qua một cửa `_chay` (test thay cửa này). `ConvertTo-Json` 1 máy in trả chuỗi, không mảng. Không dùng `gdb_layout.IN_KHO` (thiếu `A5N`). Mã vạch không rút gọn 9 số (`_ma_gdb` gây trùng).
- Template mới chạy cùng view cũ trong khoảng chưa RESET → luôn có lớp đỡ (`css_tinh_url or url_for(...)`).
- `I_CUSTOMER.Gender=False` không đáng tin (mặc định khi nhập) — chỉ tin True → Anh.
- Proc DELETE khách của vendor gọi OLE đang tắt — không bật OLE.
- Ảnh: tệp trên đĩa không dọn trong transaction; commit không rõ → giữ tệp. Ảnh CCCD chỉ qua route có đăng nhập, không vào static.
- Cookie phiên riêng `khcd_session` (tránh đụng KHJ/KHBL cùng host khác cổng).

## 9. UI

- Topbar 5 menu + footer đồng bộ KHBL (logo/icon/font dùng chung); nền **đỏ ruby**, điểm nhấn vàng; đáp ứng 390px.
- Popup xác nhận dùng `KHDialog.confirm/notify` (`ui-dialog.js/css` nạp ở `base.html`).
- Icon nghiệp vụ ở `khcd/static/img/ico` (cammoi, chuocdo, gianhan, camthem, trabot, matgiay, thanhly); CSS `desk-actions.css`.
- Tài nguyên popup khách đọc thẳng `D:/PYTHON/KHBL/static` (`KHBL_STATIC_ROOT`, allowlist), version theo mtime.
- Tiền chấm nghìn khi nhập, gửi số thô; tiếng Việt toàn bộ.

## 10. TRẠNG THÁI & VIỆC TIẾP

- Đang LIVE trên `cd_loans`; còn **9 phiếu đang cầm nguồn cũ chưa chuyển** (Tổng quan hiện riêng) — không tự tạo lịch sử để nhập.
- Chờ GĐ chốt: tiền in trên GCD `du_hien_tai` vs `goc_ban_dau`; quy tắc làm tròn toàn hệ (phần gốc lẻ phiếu cũ).
- Chưa kiểm trên thiết bị thật: quét mã vạch bằng máy quét; in phía máy chủ (Edge headless khổ A5, SumatraPDF chưa đặt ở `ops\`); camera vật lý.
- Mẫu 635511 đang DISABLE trên Zalo OA → tin chờ.
- Chưa làm: xác nhận chuyển khoản thực tế theo nội dung/mã phiếu; phân quyền nghiệp vụ theo nhân viên; mã túi/két, kiểm kê vàng; đối soát phiếu cũ thiếu thông tin/trùng SĐT; bổ sung kho ảnh PHP đầy đủ vào `media\pawn` (giữ tên tệp, không lồng `pawn\pawn`).

Tài liệu đầy đủ cho người: README.md.
