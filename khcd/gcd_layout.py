"""
gcd_layout — BỐ CỤC IN GIẤY CẦM ĐỒ (GCD), khổ A5 NẰM NGANG 210×148 mm.

TỜ GIẤY ĐÃ IN SẴN: bản in thật chỉ in CHỮ vào đúng ô trống trên tờ giấy của nhà in.
KHÔNG BAO GIỜ in ảnh nền — ảnh static/img/GCD.jpg chỉ dùng cho chế độ XEM TRƯỚC trên màn hình.

NGUỒN CẤU HÌNH — MỘT CHIỀU, KHCD CHỈ ĐỌC:
    KHBL /he-thong/mau-in-gcd/  --ghi-->  khj_bl.pmv_state['gcd_layout']   (NGƯỜI GHI DUY NHẤT)
                                              |
                          (SELECT chéo DB)    v
    KHCD /camdo/bien-nhan/<lid>/giay  <--  gcd_layout.load()
                                              +--> nhớ tạm trong tiến trình (NHO_GIAY)
                                              +--> bản chép instance/gcd_layout.json (dự phòng)

BA ĐƯỜNG HỤT, KHÔNG ĐƯỜNG NÀO ĐƯỢC NỔ (mất kết nối · thiếu quyền · không có dòng · JSON hỏng):
    SQL → bản chép tệp → MẶC ĐỊNH biên dịch cứng dưới đây. Mọi lỗi bắt TẠI CHỖ, không để lọt lên
    errorhandler(pymysql.MySQLError) của khcd/__init__.py (nó biến mọi lỗi MySQL thành trang 503 —
    nuốt ở tầng đó là MẤT TỜ PHIẾU).

THỨ TỰ TRUY VẤN BẮT BUỘC: đọc phiếu + món + khách TRƯỚC, đọc bố cục CUỐI CÙNG. db.one() dùng chung
connection của request; nếu đọc chéo khj_bl làm chết connection thì mọi truy vấn SAU đó cũng chết.

SONG SINH VỚI KHBL: apps/pos/gcd_layout.py bên KHBL phải có CÙNG BLOCKS (cùng key, cùng thứ tự) và
css() phải sinh CHUỖI GIỐNG NHAU TỪNG KÝ TỰ với cùng một JSON đầu vào — đó là lý do _so() dùng "%g".
Sửa một bên thì chép sang bên kia. Xem README.md mục "MẪU IN GIẤY CẦM ĐỒ".
"""
import json
import os
import re
import time

from flask import current_app

from . import db

KEY = "gcd_layout"
# Bước nhảy hai nửa cuống, ĐO BẰNG MÁY trên static/img/GCD.jpg (tâm mực hai chữ "SỐ:" ở 3,25% và
# 50,06% chiều cao). Phải khớp hằng cùng tên bên apps/pos/gcd_layout.py của KHBL.
BUOC_CUONG_PCT = 46.81
NHO_GIAY = 120                           # nhớ tạm bố cục trong tiến trình (giây)
TEP_NHO = "gcd_layout.json"                 # bản chép dự phòng trong instance/

# ── 18 KHỐI — đo trực tiếp trên ảnh static/img/GCD.jpg (2470×1724) ────────────────────────────
# sel dùng ATTRIBUTE SELECTOR [data-gcd="key"] nên markup và CSS không thể trôi khỏi nhau:
# template lặp đúng BLOCKS này, mỗi khối một phần tử mang data-gcd cùng key.
# an: 1 = ẩn khối (css sinh display:none) — khối không phải tiệm nào cũng dùng.
# ⚠ SỐ ĐO PHẢI GIỮ Y HỆT apps/pos/gcd_layout.py BÊN KHBL. Trang cấu hình KHBL là nơi GĐ nhìn và kéo;
# nếu hai bên khác mặc định thì TRƯỚC LẦN LƯU ĐẦU TIÊN, cái GĐ thấy khác cái KHCD in ra.
# Các số này đo theo lối "ĐÁY Ô nằm trên đường chấm" — khớp đúng cách canh chữ của gcd-print.css
# (flex column, justify-content:flex-end). Đổi h thì phải đổi top theo, nếu không chữ rời khỏi dòng kẻ.
BLOCKS = [
    # A. CUỐNG TRÁI (tiệm giữ, gắn kèm món hàng) — 0 → ~29,5% bề ngang
    {"key": "so_cuong_1",     "ten": "Số phiếu — cuống trên",      "left": 5.6,  "top": 1.0,  "w": 22,   "h": 3.2,  "fs": 8,    "an": 0},
    {"key": "so_cuong_2",     "ten": "Số phiếu — cuống dưới",      "left": 5.6,  "top": 46.2, "w": 22,   "h": 3.2,  "fs": 8,    "an": 0},
    {"key": "cuong_chi_tiet", "ten": "Chi tiết cuống (tuỳ chọn)",  "left": 2.5,  "top": 8,    "w": 25,   "h": 37,   "fs": 6.5,  "an": 1},
    # HAI BẢNG CUỐNG (GĐ chốt 16/09/2026) — hai BẢN GIỐNG HỆT nhau: xé đôi cuống thì mỗi nửa vẫn
    # mang đủ thông tin, một bản gắn theo món hàng, một bản lưu sổ. Khối này chứa BẢNG chứ không
    # chứa chữ: gcd_print._bang() dựng dict, template đổ ra qua _gcd_cuong.html.
    # Tờ in sẵn có ĐÚNG HAI chữ "SỐ:" trên cuống — đó là hai nửa xé. Hai bảng cách nhau ĐÚNG BẰNG
    # khoảng cách hai chữ đó: BUOC_CUONG_PCT = 46,81% (ĐO BẰNG MÁY trên GCD.jpg 16/09/2026 — tâm mực
    # ở 3,25% và 50,06%). KHÔNG phải 45,2% như cặp so_cuong_1/so_cuong_2 đang dùng: cặp đó lệch 2,2mm
    # so với chữ in sẵn, chưa sửa vì là bố cục ĐANG CHẠY THẬT và Giám đốc đã lưu bản riêng.
    # Bản trên bắt đầu 13,5%, tức NGAY DƯỚI khối chữ in sẵn "DNTN… / KIM HẠNH II" (đáy đo được 12,06%).
    # ⚠ KHÔNG VIỀN (GĐ chốt): CSS_CUONG không vẽ một đường kẻ nào.
    # Số đo phải khớp TỪNG THUỘC TÍNH với KHBL — cái đi qua pmv_state là nguyên cụm JSON của khối.
    {"key": "cuong_bang_1",   "ten": "Bảng cuống — bản trên",      "left": 3.0,  "top": 13.5, "w": 26.0, "h": 33.0, "fs": 7,    "an": 0},
    {"key": "cuong_bang_2",   "ten": "Bảng cuống — bản dưới",      "left": 3.0,  "top": 60.3, "w": 26.0, "h": 33.0, "fs": 7,    "an": 0},
    # B. THÂN PHẢI — biên nhận giao khách
    # MÃ VẠCH Code 39 của SỐ BIÊN NHẬN (GĐ yêu cầu 16/09/2026). Khối này chứa ẢNH chứ không chứa
    # chữ: gcd_print._khoi() gắn thêm data URI PNG do khcd/ma_vach.py vẽ, template đổ ra thẻ <img>.
    # 'fs' giữ nguyên 8 dù ảnh không dùng cỡ chữ — số đo phải khớp TỪNG THUỘC TÍNH với KHBL, vì cái
    # đi qua pmv_state là nguyên cụm JSON của khối.
    # Vị trí do KHBL ĐO BẰNG MÁY trên GCD.jpg (không ước lượng bằng mắt — lần ước lượng đầu đã sai
    # 5% và đè mất chữ "II" của KIM HẠNH II): dải y 5,0–12,4% nằm DƯỚI dòng in sẵn "DNTN KINH DOANH
    # VÀNG & CẦM ĐỒ" và TRÊN dòng địa chỉ; chữ đỏ "KIM HẠNH II" hết ở 77,1%, từ đó sang phải sạch
    # mực. Đây là khoảng trống rộng nhất NẰM TRÊN ô "SỐ:". Mép phải 96,2% chừa 8,0 mm, ngoài vùng
    # chết cơ khí 4–6 mm của máy in (cùng lý do đã bắt khối giay_to phải TẮT SẴN).
    # ⚠ RỘNG 18,8% (= 39,5 mm) LÀ TRẦN CỨNG CỦA TỜ GIẤY NÀY, KHÔNG PHẢI LỰA CHỌN THẨM MỸ: cả nửa
    # phải tờ giấy không có dải trống nào quá ~40 mm. Mã 11 chữ số chiếm 227 mô-đun hẹp (207 mô-đun
    # vạch + 2×10 quiet-zone dựng sẵn TRONG ẢNH) ⇒ vạch hẹp ≈ 0,174 mm = 7 mil. Máy quét CCD/laser
    # cầm tay ở cự ly quầy đọc được cỡ này NHƯNG ĐÂY LÀ ĐIỀU DUY NHẤT PHẢI QUÉT THỬ THẬT trên tờ in
    # đầu tiên — vì vậy trang xem trước luôn hiện một dòng XÁM nhắc việc đó (gcd_print._vach_hep).
    # Quét không ra thì ĐỪNG bóp mã cho vừa chỗ khác: nới Rộng % lấn sang trái, hoặc kéo xuống dải
    # y 23–30,5% (bên phải tiêu đề "BIÊN NHẬN CẦM ĐỒ"), hoặc đặt tờ in sẵn có chừa chỗ cho mã vạch.
    # TUYỆT ĐỐI KHÔNG cắt bớt chữ số cho mã ngắn lại — xem ma_vach.so_ma_vach(). Mã phiếu LỊCH SỬ
    # dài hơn 11 số cũng làm vạch mỏng thêm ⇒ đo theo TỪNG PHIẾU chứ không đo một lần.
    # KHÔNG làm khối "số đọc được" riêng như Giấy đảm bảo: bên đó mã vạch mang mã RÚT GỌN 9 số khác
    # với mã in trên giấy nên phải in kèm số; ở đây khối ma_phieu ngay bên dưới đã in nguyên mã rồi.
    {"key": "ma_phieu_vach",  "ten": "Mã vạch Số biên nhận",       "left": 77.4, "top": 5.6,  "w": 18.8, "h": 6.0,  "fs": 8,    "an": 0},
    {"key": "ma_phieu",       "ten": "Số biên nhận",               "left": 83.8, "top": 18.4, "w": 14.2, "h": 3.2,  "fs": 8,    "an": 0},
    {"key": "khach_ten",      "ten": "Nhận của Ông/Bà",            "left": 45.0, "top": 29.0, "w": 52.9, "h": 3.4,  "fs": 9,    "an": 0},
    {"key": "khach_diachi",   "ten": "Địa chỉ",                    "left": 37.0, "top": 33.0, "w": 60.9, "h": 3.4,  "fs": 9,    "an": 0},
    {"key": "mon_hang",       "ten": "Món hàng",                   "left": 39.3, "top": 36.9, "w": 58.6, "h": 3.4,  "fs": 8.5,  "an": 0},
    {"key": "so_tien_so",     "ten": "Số tiền cầm (số)",           "left": 40.5, "top": 40.7, "w": 57.4, "h": 3.6,  "fs": 10,   "an": 0},
    {"key": "so_tien_chu",    "ten": "Bằng chữ",                   "left": 38.8, "top": 44.8, "w": 59.1, "h": 3.4,  "fs": 8.5,  "an": 0},
    {"key": "ky_han",         "ten": "Thời gian cầm (ngày)",       "left": 42.9, "top": 49.6, "w": 4.7,  "h": 3.2,  "fs": 9,    "an": 0},
    {"key": "ngay_lap",       "ten": "Kể từ ngày",                 "left": 59.0, "top": 49.6, "w": 9.6,  "h": 3.2,  "fs": 9,    "an": 0},
    {"key": "ngay_hen",       "ten": "Đến hết ngày",               "left": 78.0, "top": 49.6, "w": 10.1, "h": 3.2,  "fs": 9,    "an": 0},
    {"key": "nam",            "ten": "Năm",                        "left": 91.6, "top": 49.6, "w": 6.3,  "h": 3.2,  "fs": 9,    "an": 0},
    {"key": "nhan_vien",      "ten": "Lập phiếu (tên NV)",         "left": 76.0, "top": 59.5, "w": 21.0, "h": 3.2,  "fs": 8,    "an": 0},
    {"key": "khach_ky",       "ten": "Tên khách dưới chữ ký",      "left": 33.0, "top": 59.5, "w": 18.0, "h": 3.2,  "fs": 8,    "an": 1},
    {"key": "trang_thai",     "ten": "Dấu trạng thái / BÁO MẤT",   "left": 34.0, "top": 62.5, "w": 60.0, "h": 4.0,  "fs": 10,   "an": 1},
    # TẮT SẴN: đáy 97,1% ≈ cách mép dưới 4,3 mm — nằm trong biên cứng 4,2–6,4 mm của laser/inkjet.
    {"key": "giay_to",        "ten": "Mã truy vết (ô Giấy tờ)","left": 55.5, "top": 94.1, "w": 31.8, "h": 3.0,  "fs": 8,    "an": 1},
]
BLOCK_MAP = {b["key"]: b for b in BLOCKS}

# Khối chứa ẢNH thay vì chữ — gcd_print gắn data URI, template đổ ra thẻ <img class="gcd-anh">.
# Khai thành hằng để không chỗ nào phải gõ lại chuỗi "ma_phieu_vach".
KHOI_MA_VACH = "ma_phieu_vach"
KHOI_ANH = (KHOI_MA_VACH,)
# Khối chứa BẢNG (cuống tiệm giữ) — gcd_print gắn dict, template đổ ra qua _gcd_cuong.html.
KHOI_BANG = ("cuong_bang_1", "cuong_bang_2")

# ⚠ CHUỖI NÀY PHẢI GIỐNG TỪNG KÝ TỰ apps/pos/gcd_layout.py::CSS_ANH BÊN KHBL.
# Đây là hình dáng ẢNH mã vạch — thứ quyết định bản xem trước bên KHBL và tờ in ra bên KHCD có
# giống nhau không. Rule phải do css() SINH RA chứ không nằm trong static/gcd-print.css: tệp static
# là của riêng từng dự án, để ở đó là đúng kiểu lệch hai bên đã làm chữ lệch 9 mm hôm trước.
# object-fit:fill = kéo ảnh phủ trọn hộp; tỷ lệ BỀ NGANG giữa các vạch vẫn đều nhau (co giãn đồng
# nhất theo trục ngang) nên máy quét vẫn đọc đúng. image-rendering:pixelated để trình duyệt đừng
# làm mờ mép vạch lúc phóng ảnh ra khổ in — vạch mờ là máy quét câm.
# tests/test_gcd_ma_vach.py đối chiếu từng ký tự với mã nguồn KHBL và FAIL nếu lệch.
CSS_ANH = (".gcd-anh{display:block!important;padding:0!important;background:#fff;"
           "object-fit:fill;image-rendering:pixelated}")

# ⚠ CHUỖI NÀY PHẢI GIỐNG TỪNG KÝ TỰ apps/pos/gcd_layout.py::CSS_CUONG BÊN KHBL.
# Hình dáng HAI BẢNG CUỐNG tiệm giữ — cùng lý do với CSS_ANH: rule phải do css() SINH RA để bản
# xem trước bên KHBL và tờ in ra bên này không thể lệch nhau.
# KHÔNG CÓ VIỀN: Giám đốc chốt border=none ngày 16/09/2026; mọi đường kẻ vắng mặt là CÓ CHỦ ĐÍCH.
# Nhãn dọc co theo `em` chứ không theo biến CSS — css() bên này không sinh --gcd-fs như bên KHBL.
# tests/test_gcd_ma_vach.py đối chiếu từng ký tự với mã nguồn KHBL và FAIL nếu lệch.
CSS_CUONG = (
    ".gcd-a5 .gcd-cuong{z-index:1}"
    ".gcd-cuong{display:flex!important;flex-direction:row;align-items:stretch;gap:1.2mm;"
    "border:none!important;padding:0!important;overflow:hidden;line-height:1.15}"
    ".gcd-cuong__doc{flex:0 0 auto;writing-mode:vertical-rl;transform:rotate(180deg);"
    "white-space:nowrap;text-align:center;font-size:1.3em}"
    ".gcd-cuong__than{flex:1 1 auto;min-width:0;display:flex;flex-direction:column;gap:.9mm}"
    ".gcd-cuong__dau{display:flex;flex-direction:row;align-items:flex-start;gap:1.2mm}"
    ".gcd-cuong__qr{flex:0 0 32%;aspect-ratio:1/1;height:auto;display:block;background:#fff}"
    ".gcd-cuong__ds{flex:1 1 auto;min-width:0;display:flex;flex-direction:column;gap:1.5mm; overflow-wrap:anywhere;word-break:break-word;margin-top: 10px;}"
    ".gcd-cuong__noi{flex:1 1 auto;min-height:0;overflow-wrap:anywhere;word-break:break-word}"
    ".gcd-cuong__tien{display:flex;flex-direction:row;gap:1.2mm;justify-content:center}"
    ".gcd-cuong__tien span{flex:0 0 auto}"
    ".gcd-cuong b{font-weight:700; font-size: 16px;}"
)

# Khối chữ tự do → server tự chọn bậc co chữ (không dùng JS: CSP chặn, và co bằng JS lúc in là không kịp).
CO_CHU = ("mon_hang", "khach_diachi", "so_tien_chu")
CO_TY_LE = {2: 0.88, 3: 0.76}

GIOI_HAN = {"left": (0, 100), "top": (0, 100), "w": (1, 100), "h": (0.5, 100), "fs": (3, 30)}

# ── THIẾT LẬP IN ──────────────────────────────────────────────────────────────────────────────
# ⚠ KHỔ GIẤY CỐ Ý KHÁC gdb_layout: GĐB là tờ DỌC 148×210 nên "auto" an toàn (lọt trong mọi khổ dọc).
# GCD là tờ NGANG rộng 210 mm — nếu driver đang để A5 DỌC (148 mm) thì "auto" cho khung 148×210,
# tờ 210 mm TRÀN RA NGOÀI, bị cắt hoặc vỡ thành 2 trang. Vì vậy mặc định là kích thước TƯỜNG MINH
# "210mm 148mm" (rõ nghĩa hơn từ khoá "A5 landscape"). Driver để khổ lớn hơn (A4) thì Chromium canh
# giữa tờ 210×148 trên khổ đó → lệch, hấp thụ bằng dx/dy đúng như GĐB đã làm.
# ⚠ TUYỆT ĐỐI KHÔNG dùng lại IN_KHO của gdb_layout: dict đó không có "A5N", .get() trả "auto" và
# MẤT KHỔ NGANG MÀ KHÔNG BÁO LỖI. Module này khai IN_KHO riêng và css_in() riêng.
# ⚠ ẢNH GCD.jpg (2470×1724, tỷ lệ 1,4327) LỆCH ~1% so với A5 ngang (1,4189) ≈ 2 mm bề ngang: hoặc
# bản scan méo, hoặc TỜ IN SẴN KHÔNG ĐÚNG A5 CHUẨN (nhà in xén tay). Vì vậy khổ tờ giấy là THAM SỐ
# kho_w × kho_h (mm) lưu trong JSON, KHÔNG phải hằng số — đo tờ thật bằng thước rồi nhập vào.
IN_KEY = "_in"
PAPER_W_MM, PAPER_H_MM = 210, 148          # A5 NẰM NGANG (mặc định, đổi được bằng kho_w/kho_h)
IN_MAC_DINH = {"kho": "A5N", "canh": "giua", "dx": 0, "dy": 0, "ty_le": 100,
               "kho_w": PAPER_W_MM, "kho_h": PAPER_H_MM, "may_in": "", "ban_in": 1}
KHO_TO = "TỜ"            # giá trị canh: sinh size từ kho_w × kho_h
IN_KHO = {"A5N": KHO_TO, "auto": "auto", "A4N": "A4 landscape",
          "A5D": "A5 portrait", "A4D": "A4 portrait", "Letter": "letter landscape",
          # A4T (GĐ chốt 17/09/2026): máy in để A4 ĐỨNG, tờ GCD A5 ngang là ĐÚNG NỬA TRÊN của tờ A4
          # (210 mm = trọn bề ngang) → sát mép trên-trái, KHÔNG lề, KHÔNG canh giữa; dx/dy vẫn tinh chỉnh được.
          "A4T": "auto"}   # auto: KHÔNG ép khổ/hướng — chọn A4 đứng trong hộp thoại in, Edge nhớ cho lần sau (GĐ chốt 17/09)
IN_CANH = ("giua", "trai")
IN_GIOI_HAN = {"dx": (-80, 80), "dy": (-80, 80), "ty_le": (50, 150),
               "kho_w": (80, 420), "kho_h": (60, 420)}
BAN_IN_TOI_DA = 4
MAY_IN_DAI = 40          # may_in là ID trỏ sang sổ máy in (khoá may_in_ds), không bao giờ là tên máy in thật

# Nội dung: tiền in trên phiếu lấy theo dư hiện tại hay gốc ban đầu; có gộp món về 1 dòng không.
# ⚠ Mặc định "du_hien_tai" = ĐÚNG con số trang in cũ (loan_print.html) đang in — hai đường in không
# được hiện hai số khác nhau cho cùng một phiếu. Đổi ở trang cấu hình KHBL nếu GĐ chốt khác.
CT_KEY = "_ct"
CT_MAC_DINH = {"tien": "du_hien_tai", "mon_gop": 1}
CT_TIEN = ("du_hien_tai", "goc_ban_dau")

# Hiệu chỉnh ẢNH NỀN XEM TRƯỚC. CHỈ dùng trên màn hình. css() KHÔNG BAO GIỜ sinh ra nó.
NEN_KEY = "_nen"
NEN_MAC_DINH = {"x": 0, "y": 0, "w": 100, "h": 100}
NEN_GIOI_HAN = {"x": (-30, 30), "y": (-30, 30), "w": (50, 200), "h": (50, 200)}


def mac_dinh():
    """Bố cục biên dịch cứng — dùng khi chưa ai lưu, hoặc khi không đọc được khj_bl."""
    out = {b["key"]: {k: b[k] for k in ("left", "top", "w", "h", "fs", "an") if b[k] is not None} for b in BLOCKS}
    out[IN_KEY] = dict(IN_MAC_DINH)
    out[CT_KEY] = dict(CT_MAC_DINH)
    out[NEN_KEY] = dict(NEN_MAC_DINH)
    return out


def _ep(v, lo, hi):
    """Kẹp một số vào khoảng cho phép; NaN/Infinity/chữ → None (bỏ qua, giữ mặc định)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):
        return None
    return max(lo, min(hi, round(f, 2)))


def _nhan_in(dst, vals):
    if vals.get("kho") in IN_KHO:
        dst["kho"] = vals["kho"]
    if vals.get("canh") in IN_CANH:
        dst["canh"] = vals["canh"]
    for p, (lo, hi) in IN_GIOI_HAN.items():
        if p in vals:
            f = _ep(vals[p], lo, hi)
            if f is not None:
                dst[p] = f
    if "may_in" in vals and isinstance(vals["may_in"], str) and re.fullmatch(r"[A-Za-z0-9_\-]{0,%d}" % MAY_IN_DAI, vals["may_in"]):
        dst["may_in"] = vals["may_in"]
    if "ban_in" in vals:
        f = _ep(vals["ban_in"], 1, BAN_IN_TOI_DA)
        if f is not None:
            dst["ban_in"] = int(f)


def _nhan_ct(dst, vals):
    if vals.get("tien") in CT_TIEN:
        dst["tien"] = vals["tien"]
    if "mon_gop" in vals:
        dst["mon_gop"] = 1 if vals["mon_gop"] in (1, "1", True, "true") else 0


def _gop(out, data):
    """Đè bản lưu lên mặc định — chỉ nhận key/thuộc tính hợp lệ, số đã kẹp giới hạn.

    Dùng chung cho mọi đường vào: khoá lạ, số vượt ngưỡng, NaN/Infinity đều bị loại ở đây.
    """
    for key, vals in (data or {}).items():
        if key not in out or not isinstance(vals, dict):
            continue
        if key == IN_KEY:
            _nhan_in(out[key], vals)
            continue
        if key == CT_KEY:
            _nhan_ct(out[key], vals)
            continue
        if key == NEN_KEY:
            for p, (lo, hi) in NEN_GIOI_HAN.items():
                if p in vals:
                    f = _ep(vals[p], lo, hi)
                    if f is not None:
                        out[key][p] = f
            continue
        for p, v in vals.items():
            if p == "an" and p in out[key]:
                if v in (0, 1, "0", "1", True, False):      # nhánh riêng: chỉ nhận đúng 0/1
                    out[key]["an"] = 1 if v in (1, "1", True) else 0
                continue
            if p in out[key] and p in GIOI_HAN:
                f = _ep(v, *GIOI_HAN[p])
                if f is not None:
                    out[key][p] = f
    return out


# ── ĐỌC BỐ CỤC: SQL → bản chép tệp → mặc định ────────────────────────────────────────────────
_nho = {"luc": 0.0, "bo_cuc": None, "nguon": "", "chuoi": ""}


def _bang_cau_hinh():
    """`khj_bl`.`pmv_state` — cùng nếp auth.source_table(): chặn tên CSDL lạ, luôn backtick."""
    nguon = current_app.config["AUTH_SOURCE_DB"]
    if not re.fullmatch(r"[A-Za-z0-9_]+", nguon) or nguon == current_app.config["DB_NAME"]:
        raise RuntimeError("AUTH_SOURCE_DB phải là tên CSDL hợp lệ và khác CSDL cầm đồ.")
    return "`%s`.`pmv_state`" % nguon


def _duong_nho():
    return os.path.join(current_app.instance_path, TEP_NHO)


def _ghi_nho_tep(chuoi):
    """Chỉ ghi khi nội dung ĐỔI; ghi ra .tmp rồi os.replace (nguyên tử) — Waitress đa luồng không
    để lại tệp JSON cụt cho lần đọc hụt sau."""
    try:
        duong = _duong_nho()
        if os.path.exists(duong):
            with open(duong, "r", encoding="utf-8") as f:
                if f.read() == chuoi:
                    return
        os.makedirs(current_app.instance_path, exist_ok=True)
        tam = duong + ".tmp"
        with open(tam, "w", encoding="utf-8") as f:
            f.write(chuoi)
        os.replace(tam, duong)
    except OSError:
        pass                                   # bản chép chỉ là lưới an toàn; hỏng cũng không chặn in


def _doc_nho_tep():
    try:
        with open(_duong_nho(), "r", encoding="utf-8") as f:
            return json.loads(f.read())
    except (OSError, ValueError):
        return None


def doc_bo_cuc(bo_qua_nho=False):
    """Trả (bố cục, nguồn) — nguồn ∈ {'sql','nho','tep','mac_dinh'}.

    Cấu hình đổi không thường xuyên nên nhớ tạm NHO_GIAY giây trong tiến trình: một lượt in không
    phải bắn truy vấn chéo CSDL. Mọi lỗi bắt tại chỗ.
    """
    if not bo_qua_nho and _nho["bo_cuc"] is not None and time.time() - _nho["luc"] < NHO_GIAY:
        return json.loads(_nho["chuoi"]), "nho"
    out = mac_dinh()
    row = None
    try:
        # `key` là từ khoá MySQL → bắt buộc backtick.
        row = db.one("SELECT `value` FROM " + _bang_cau_hinh() + " WHERE `key`=%s", (KEY,))
    except Exception as loi:                   # mất kết nối · thiếu quyền · KHBL đang bảo trì
        # Ghi rõ loại lỗi: lần sau còn truy được là mất kết nối, hết quyền hay bảng đang bận.
        current_app.logger.warning("Không đọc được bố cục in %s từ %s (%s: %s); dùng bản chép/mặc định.",
                                   KEY, current_app.config.get("AUTH_SOURCE_DB"), type(loi).__name__, loi)
        row = None
        luu = _doc_nho_tep()
        if luu is not None:
            return _gop(out, luu), "tep"
        return out, "mac_dinh"
    if not row or not row.get("value"):
        _ghi_nho_tep("{}")
        _nho.update(luc=time.time(), bo_cuc=True, nguon="sql", chuoi=json.dumps(out, ensure_ascii=False))
        return out, "sql"
    try:
        data = json.loads(row["value"])
    except ValueError:
        current_app.logger.warning("Bố cục in %s hỏng JSON; dùng bản chép/mặc định.", KEY)
        luu = _doc_nho_tep()
        return (_gop(out, luu), "tep") if luu is not None else (out, "mac_dinh")
    _gop(out, data)
    _ghi_nho_tep(json.dumps(data, ensure_ascii=False))
    _nho.update(luc=time.time(), bo_cuc=True, nguon="sql", chuoi=json.dumps(out, ensure_ascii=False))
    return out, "sql"


def load():
    """Bố cục hiện hành = MẶC ĐỊNH ⊕ bản lưu (API song sinh với KHBL gcd_layout.load())."""
    return doc_bo_cuc()[0]


def quen_nho():
    """Xoá bộ nhớ tạm (bài kiểm và nút 'đọc lại cấu hình' dùng)."""
    _nho.update(luc=0.0, bo_cuc=None, nguon="", chuoi="")
    _nho_may.update(luc=0.0, so=None)


# ── SỔ MÁY IN (khoá riêng may_in_ds, dùng chung cho cả GĐB · CỌC · GCD) ──────────────────────
# Bố cục là của TỜ GIẤY (mỗi mẫu in một bản); sổ máy in là của THIẾT BỊ (cả nhà dùng chung) ⇒ hai
# khoá tách rời: đổi IP/máy in chỉ sửa MỘT dòng trong sổ, _in.may_in chỉ trỏ tới bằng id.
# ⚠ KHCD KHÔNG điều khiển được thiết bị: trang web không có API nào chọn máy in. Đây chỉ là NHÃN
# cho người vận hành biết phải đứng ở máy nào bấm in (Edge --kiosk-printing in ra máy in mặc định
# của CHÍNH máy đang mở trình duyệt).
MAY_IN_KEY = "may_in_ds"
_nho_may = {"luc": 0.0, "so": None}


def doc_may_in(ma):
    """Tra một bản ghi máy in theo id. Đọc hụt → None (chỉ mất phần nhãn, không chặn in)."""
    if not ma:
        return None
    if _nho_may["so"] is None or time.time() - _nho_may["luc"] >= NHO_GIAY:
        so = {}
        try:
            row = db.one("SELECT `value` FROM " + _bang_cau_hinh() + " WHERE `key`=%s", (MAY_IN_KEY,))
            data = json.loads(row["value"]) if row and row.get("value") else {}
            for ban in (data.get("ban") or []):
                if isinstance(ban, dict) and isinstance(ban.get("id"), str):
                    so[ban["id"]] = ban
        except Exception:
            so = {}
        _nho_may.update(luc=time.time(), so=so)
    return (_nho_may["so"] or {}).get(ma)


# ── MÁY IN THẬT do Giám đốc TÌM → CHỌN → LƯU ở trang cấu hình KHBL ───────────────────────────
# ⚠ KHÁC HẲN sổ may_in_ds ở trên. may_in_ds là bản khai TAY các đường in dự kiến (nhãn cho người
# đọc). Còn khoá này do nút "Tìm máy in" bên KHBL ghi, mang TÊN MÁY IN WINDOWS THẬT đọc được từ
# máy chủ — đây mới là cái dùng để in. Trước 15/09/2026 KHCD chỉ đọc may_in_ds nên máy in Giám đốc
# chọn KHÔNG BAO GIỜ tới được đây; đó là lỗi hợp đồng, đã vá.
MAY_IN_THAT_KEY = "gcd_may_in"
_nho_may_that = {"luc": 0.0, "goi": None}


def doc_may_in_that():
    """Trả dict cấu hình máy in thật, hoặc {} nếu chưa chọn / đọc hụt.

    Nuốt MỌI lỗi: khoá chưa có, khj_bl bận, JSON hỏng đều trả {} ⇒ lớp gọi coi như chưa chọn
    máy in và rơi về hộp thoại in của trình duyệt. TUYỆT ĐỐI không ném ra ngoài.
    """
    if _nho_may_that["goi"] is None or time.time() - _nho_may_that["luc"] >= NHO_GIAY:
        goi = {}
        try:
            row = db.one("SELECT `value` FROM " + _bang_cau_hinh() + " WHERE `key`=%s",
                         (MAY_IN_THAT_KEY,))
            data = json.loads(row["value"]) if row and row.get("value") else {}
            if isinstance(data, dict):
                goi = data
        except Exception:
            goi = {}
        _nho_may_that.update(luc=time.time(), goi=goi)
    return _nho_may_that["goi"] or {}


# ── SINH CSS ─────────────────────────────────────────────────────────────────────────────────
def _so(v):
    """3.0 → '3', 20.4 → '20.4' — khớp cách JS in số bên trang chỉnh mẫu, để CSS hai bên giống
    nhau TỪNG KÝ TỰ (bài kiểm đối chiếu KHBL ↔ KHCD dựa vào đúng điểm này)."""
    return "%g" % float(v)


def _sel(key):
    return '[data-gcd="%s"]' % key


def kho_giay(layout=None):
    """(rộng, cao) tờ giấy tính bằng mm — tham số, không phải hằng (ảnh nền lệch tỷ lệ ~1%)."""
    inn = {**IN_MAC_DINH, **((layout or {}).get(IN_KEY) or {})}
    return float(inn["kho_w"]), float(inn["kho_h"])


def css_in(inn=None):
    """@media print: khổ trang gửi máy in + cách đặt tờ GCD trên trang đó + CHỐNG IN NỀN.

    Phải đứng SAU mọi rule in khác (cùng !important → khai sau thắng) nên là nguồn DUY NHẤT quyết
    định @page + margin. KHÔNG khai @page ở bất kỳ chỗ nào khác.
    ⚠ Lớp chống in nền nằm ngay đây: `background:none` trên tờ giấy + `display:none` cho .gcd-nen và
    mọi .no-print. Ảnh nền là vật tư của MÀN HÌNH, không bao giờ được chạm tới tờ giấy in sẵn."""
    inn = {**IN_MAC_DINH, **(inn or {})}
    size = IN_KHO.get(inn["kho"], "auto")
    if size == KHO_TO:
        size = "%smm %smm" % (_so(inn["kho_w"]), _so(inn["kho_h"]))
    giua = inn["canh"] != "trai" and inn["kho"] != "A4T"   # A4T: luôn sát mép trái, không canh giữa
    rule = ["left:%smm!important" % _so(inn["dx"]), "top:%smm!important" % _so(inn["dy"]),
            "margin:0 auto!important" if giua else "margin:0!important",
            "background:none!important", "box-shadow:none!important", "overflow:hidden!important",
            # Bản thân .gcd-a5 có max-width:100% cho vừa màn hình. Rule đó nằm NGOÀI
            # @media print nên vẫn còn hiệu lực lúc in: chọn khổ giấy máy in KHÁC tờ A5
            # là cả phiếu CO NHỎ LẠI mà không báo gì — chữ lệch hết khỏi ô giấy in sẵn.
            "max-width:none!important"]
    ty_le = float(inn["ty_le"])
    if ty_le != 100:
        rule.append("transform:scale(%s)!important;transform-origin:top %s!important"
                    % (_so(ty_le / 100), "center" if giua else "left"))
    return ("@media print{@page{size:%s;margin:0}.gcd-a5{%s}.gcd-nen,.no-print{display:none!important}}"
            % (size, ";".join(rule)))


def css(layout=None):
    """CSS đặt vị trí + cỡ chữ từng khối. Tờ giấy trên màn = 210 mm thật → NHÌN SAO IN VẬY.

    ⚠ position:relative BẮT BUỘC nằm ở đây: KHCD không có khbl.css khai sẵn; thiếu nó thì 18 khối
    position:absolute neo vào viewport và bố cục vỡ toàn bộ (vỡ giống hệt nhau ở cả bản in lẫn bản
    xem trước nên rất dễ tưởng là sai toạ độ).
    ⚠ KHÔNG sinh background ẢNH, KHÔNG sinh print-color-adjust — bản in thật chỉ có CHỮ và MÃ VẠCH
    (mã vạch là thẻ <img> nội dung thật, in ra bình thường; CSS_ANH chỉ tả hình dáng thẻ đó).
    """
    layout = layout or load()
    w, h = kho_giay(layout)
    out = [".gcd-a5{position:relative!important;width:%smm!important;max-width:100%%;height:auto;aspect-ratio:%s/%s}"
           % (_so(w), _so(w), _so(h)), CSS_ANH, CSS_CUONG]
    for b in BLOCKS:
        v = layout[b["key"]]
        sel = _sel(b["key"])
        rule = ["position:absolute!important", "left:%s%%!important" % _so(v["left"]),
                "top:%s%%!important" % _so(v["top"]), "width:%s%%!important" % _so(v["w"])]
        if "h" in v:
            rule.append("height:%s%%!important" % _so(v["h"]))
        if "fs" in v:
            rule.append("font-size:%spt!important" % _so(v["fs"]))
        out.append(sel + "{" + ";".join(rule) + "}")
        if "fs" in v and b["key"] in CO_CHU:
            for bac, ty in sorted(CO_TY_LE.items()):
                out.append("%s.gcd-co-%d{font-size:calc(%spt*%s)!important}"
                           % (sel, bac, _so(v["fs"]), _so(ty)))
        if v.get("an"):
            out.append(sel + "{display:none!important}")
    out.append(css_in(layout.get(IN_KEY)))
    return "\n".join(out)


def css_nen(layout=None):
    """Hiệu chỉnh ảnh nền — CHỈ chế độ xem trước trên màn hình, TÁCH HẲN khỏi css().

    Không bao giờ được gọi trong đường in thật. Phần tử .gcd-nen vốn đã mang class no-print và
    static/gcd-print.css đặt @media print{.no-print{display:none!important}}.
    """
    layout = layout or load()
    n = {**NEN_MAC_DINH, **(layout.get(NEN_KEY) or {})}
    return ".gcd-nen{left:%s%%;top:%s%%;width:%s%%;height:%s%%}" % (_so(n["x"]), _so(n["y"]), _so(n["w"]), _so(n["h"]))


# ── ĐỌC SỐ TIỀN BẰNG CHỮ ─────────────────────────────────────────────────────────────────────
TEN_SO = ("không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín")
DON_VI = ("", "nghìn", "triệu", "tỷ")
TIEN_TOI_DA = 999999999999


def _nhom(n, du):
    a = []
    tram, chuc, dv = n // 100, n % 100 // 10, n % 10
    if tram or du:
        a += [TEN_SO[tram], "trăm"]
    if chuc > 1:
        a += [TEN_SO[chuc], "mươi"]
    elif chuc == 1:
        a.append("mười")
    elif dv and (tram or du):
        a.append("lẻ")
    if dv:
        a.append("mốt" if (dv == 1 and chuc > 1) else "lăm" if (dv == 5 and chuc > 0) else TEN_SO[dv])
    return " ".join(a)


def doc_so(value):
    """Số tiền → chữ. BẢN SAO THUẬT TOÁN của words() trong static/pawn-entry.js (dòng 21).

    "Bằng chữ" là dòng PHÁP LÝ trên biên nhận: phải ra ĐÚNG chuỗi nhân viên đã nhìn thấy lúc lập
    phiếu. Sửa một bên thì sửa cả hai; tests/test_gcd_print.py giữ bảng ~40 giá trị đối chiếu.
    ⚠ JS dùng BigInt nên n/=1000n là CHIA NGUYÊN — Python phải dùng //, không phải /.
    """
    try:
        n = int(value)
    except (TypeError, ValueError):
        return ""
    if n < 0:
        return "Số tiền không hợp lệ"
    if not n:
        return "Không đồng"
    if n > TIEN_TOI_DA:
        return "Số tiền vượt giới hạn"
    phan, i = [], 0
    while n:
        g = n % 1000
        if g:
            phan.insert(0, _nhom(g, n >= 1000) + " " + DON_VI[i])
        n //= 1000
        i += 1
    ra = " ".join(phan).strip() + " đồng"
    return ra[0].upper() + ra[1:]


# ── BẬC CO CHỮ (chống tràn, KHÔNG dùng JS, KHÔNG cắt cụt) ────────────────────────────────────
# Cắt cụt tên khách hay danh sách món trên một chứng từ pháp lý là lỗi nặng ⇒ tuyệt đối không
# overflow:hidden ở cấp KHỐI. Hết bậc thang thì cho xuống dòng trong h đã cấp, và trang xem trước
# hiện dải cảnh báo để nhân viên soi mắt trước khi in.
def suc_chua(key, layout):
    """Ước lượng số ký tự chứa được trong khối (bề rộng trung bình 1 ký tự ≈ 0,5 × cỡ chữ)."""
    v = layout[key]
    fs = float(v.get("fs") or 8)
    giay_w, giay_h = kho_giay(layout)
    rong_mm = giay_w * float(v["w"]) / 100.0
    cao_mm = giay_h * float(v.get("h") or 3.2) / 100.0
    rong_ky_tu = max(0.1, fs * 0.3528 * 0.5)
    cao_dong = max(0.1, fs * 0.3528 * 1.15)
    dong = max(1, int(cao_mm / cao_dong))
    return max(1, int(rong_mm * dong / rong_ky_tu))


# Vùng máy in KHÔNG in được: laser/inkjet phổ thông có biên cứng 4,2–6,4 mm mỗi mép và @page{margin:0}
# KHÔNG mở được vùng đó — driver sẽ cắt cụt, thu nhỏ cả trang, hoặc đẩy sang trang 2. Lấy 6 mm.
BIEN_CUNG_MM = 6.0


def khoi_sat_mep(layout):
    """Tên các khối ĐANG HIỆN mà lọt vào biên cứng của máy in — để trang xem trước cảnh báo.

    Ví dụ đã đo trên tờ thật: 'giay_to' có đáy ở 97,1% ≈ cách mép dưới 4,3 mm (nên mặc định TẮT).
    """
    # Chỉ soi MÉP TRÊN / MÉP DƯỚI và MÉP TRÁI — nơi cắt cụt là mất trọn một dòng. KHÔNG soi mép
    # phải: bề rộng khối chỉ là ĐỘ DÀI CHỖ TRỐNG trên tờ giấy, chữ canh trái nên không chạm tới đó.
    giay_w, giay_h = kho_giay(layout)
    bx, by = BIEN_CUNG_MM / giay_w * 100, BIEN_CUNG_MM / giay_h * 100
    ra = []
    for b in BLOCKS:
        v = layout[b["key"]]
        if v.get("an"):
            continue
        if (float(v["top"]) < by or float(v["top"]) + float(v.get("h") or 0) > 100 - by
                or float(v["left"]) < bx):
            ra.append(b["ten"])
    return ra


def bac_co_chu(text, key, layout):
    """Trả (bậc 1|2|3, có_tràn). Bậc 1 = 100% cỡ chữ, 2 = 88%, 3 = 76%."""
    if key not in CO_CHU:
        return 1, False
    n = len(text or "")
    suc = suc_chua(key, layout)
    if n <= suc:
        return 1, False
    for bac in (2, 3):
        if n <= suc / CO_TY_LE[bac]:
            return bac, False
    return 3, True
