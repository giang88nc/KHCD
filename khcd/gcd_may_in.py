"""
gcd_may_in — IN GIẤY CẦM ĐỒ PHÍA MÁY CHỦ, VÀ ĐƯỜNG RƠI VỀ HỘP THOẠI IN CỦA TRÌNH DUYỆT.

GĐ chốt 15/09/2026: "tìm → chọn → lưu máy in vào cấu hình để sử dụng → nếu không gọi được máy in
đó → thì trình duyệt tự điều hướng chọn máy in".

    Chọn + lưu máy in : TRANG CẤU HÌNH BÊN KHBL (người ghi duy nhất, khoá pmv_state)
    Dùng máy in đã lưu: MODULE NÀY (KHCD chỉ ĐỌC cấu hình, không bao giờ ghi sang khj_bl)

HAI ĐƯỜNG IN, QUYẾT ĐỊNH TRƯỚC KHI BẤM — ĐÂY LÀ ĐIỂM THIẾT KẾ QUAN TRỌNG NHẤT:
    kiem_tra()  chạy LÚC DỰNG TRANG, không phải lúc bấm. Trang biết sẵn mình đi đường nào.
      · đủ điều kiện → nút IN gọi POST .../in-may-chu → in_ngay() → "Đã gửi tới <máy in>"
      · thiếu điều kiện → nút IN gọi thẳng window.print() NGAY LẬP TỨC, y hệt hành vi cũ
    Vì sao không thử phía máy chủ rồi mới rơi về: thử-rồi-rơi bắt người dùng CHỜ (dựng PDF mất vài
    giây) mới thấy hộp thoại. Hôm nay máy chủ KHÔNG có máy in vật lý và KHÔNG có công cụ đẩy bản in
    ⇒ đường rơi về là ĐƯỜNG CHẠY THẬT HẰNG NGÀY, nó phải mượt như trước, không đợi, không nháy trang.

BẬC THANG ĐIỀU KIỆN (rẻ trước, tốn sau — bậc nào hụt là dừng luôn, trả câu giải thích NGẮN):
    1. Cấu hình có chọn máy in chưa            (đọc JSON đã nhớ tạm — gần như miễn phí)
    2. Sổ máy in có bản ghi đó, có tên thiết bị Windows không
    3. Máy chủ có Microsoft Edge không          (os.path.exists)
    4. Máy chủ có công cụ đẩy PDF ra máy in không (os.path.exists)
    5. Tên máy in còn trong Get-Printer không   (gọi PowerShell — TỐN NHẤT, để cuối, nhớ tạm 120s)
    Hôm nay bậc 1 đã hụt (chưa ai lưu cấu hình) ⇒ trang in KHÔNG gọi PowerShell một lần nào.

DỰNG BẢN IN: CHỈ Microsoft Edge chạy ẩn --print-to-pdf, TỪ CHÍNH TRANG IN loan_print_gcd.html.
    Giữ MỘT BẢN VẼ DUY NHẤT: cùng template, cùng gcd_layout.css(), cùng gcd-print.css. Tuyệt đối
    không dựng PDF bằng thư viện vẽ khác — đó sẽ là bản vẽ thứ ba, lệch với cả bản xem trước lẫn
    bản in trình duyệt, và không ai biết bản nào đúng cho tới khi hỏng một tờ giấy in sẵn.

    Edge nạp trang qua file:/// trong thư mục tạm, KHÔNG qua HTTPS. Lý do: mọi endpoint của KHCD
    đều đòi đăng nhập ⇒ Edge chạy ẩn sẽ nhận trang đăng nhập. Cho Edge một "vé" bỏ qua đăng nhập là
    mở một lỗ xác thực mới trên hệ chạy tiền thật — không đáng, chỉ để in một tờ giấy. Đi file://
    còn tránh luôn chuyện chứng chỉ tự ký của LAN.

    ⚠ KHÔNG BAO GIỜ dựng PDF từ ?nen=1: bản in thật chỉ có CHỮ. gcd_print chỉ gọi vào đây với trang
    dựng ở chế độ in thật (nen=False), và thư mục tạm không hề có ảnh GCD.jpg để mà in ra.

TỆP TẠM: mỗi lượt in một thư mục tempfile riêng, XOÁ trong finally dù hỏng ở bước nào. Trước mỗi
lượt còn quét dọn thư mục khcd_gcd_* quá 1 giờ (máy mất điện giữa chừng thì lần in sau dọn hộ).
Tiến trình Edge/công cụ in quá giờ chờ bị GIẾT CẢ CÂY bằng taskkill /T /F — Edge đẻ tiến trình con,
giết mỗi tiến trình cha là để lại rác ngốn RAM trên máy chủ chạy 24/7.

KHÔNG CÀI GÌ MỚI: chỉ gọi PowerShell Get-Printer (có sẵn trong Windows) và msedge.exe (có sẵn).
Không pywin32, không thư viện PDF, không tải tệp nhị phân.
"""
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from flask import current_app

from . import gcd_layout as G

# ── GIỜ CHỜ (giây) ────────────────────────────────────────────────────────────────────────────
# Cộng lại tối đa ~43s. JS phía trang còn tự ngắt ở 30s rồi rơi về hộp thoại in, nên người dùng
# không bao giờ ngồi chờ hết chừng đó.
GIO_CHO_PS = 8            # hỏi danh sách máy in
GIO_CHO_PDF = 15          # Edge dựng PDF
GIO_CHO_DAY = 20          # đẩy PDF sang máy in
NHO_MAY = 120             # nhớ tạm danh sách máy in trong tiến trình (giây)
RAC_QUA_HAN = 3600        # thư mục tạm quá hạn này thì quét dọn (giây)

# CREATE_NO_WINDOW: máy chủ chạy ẩn hoàn toàn, không được nháy cửa sổ đen lên màn hình quầy.
CO_KHONG_CUA_SO = getattr(subprocess, "CREATE_NO_WINDOW", 0)

TIEN_TO_TAM = "khcd_gcd_"

# ── CÔNG CỤ TRÊN MÁY ─────────────────────────────────────────────────────────────────────────
EDGE_DUONG = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)

# Công cụ đẩy PDF ra máy in. Máy chủ hôm nay KHÔNG có cái nào ⇒ luôn rơi về trình duyệt.
# Muốn bật đường in phía máy chủ: chép SumatraPDF.exe (bản portable) vào D:\PYTHON\KHCD\ops\
# rồi RESET KHCD — không cần sửa một dòng mã nào.
# ⚠ CỐ Ý KHÔNG hỗ trợ Acrobat/Foxit (/t /h): chúng MỞ CỬA SỔ rồi nằm lại; trên máy chủ chạy ẩn
# 24/7 thì mỗi lượt in đẻ một tiến trình GUI treo, vài chục lượt là hết RAM.
CONG_CU = (
    ("sumatra", (r"C:\Program Files\SumatraPDF\SumatraPDF.exe",
                 r"C:\Program Files (x86)\SumatraPDF\SumatraPDF.exe",
                 r"D:\PYTHON\KHCD\ops\SumatraPDF.exe",
                 r"D:\PYTHON\KHCD\ops\SumatraPDF-portable.exe")),
    ("pdftoprinter", (r"C:\Program Files\PDFtoPrinter\PDFtoPrinter.exe",
                      r"D:\PYTHON\KHCD\ops\PDFtoPrinter.exe")),
)
# Đè bằng .env khi GĐ để công cụ ở chỗ khác: GCD_CONG_CU_IN=D:\...\SumatraPDF.exe (GCD_EDGE tương tự)
BIEN_CONG_CU = "GCD_CONG_CU_IN"
BIEN_EDGE = "GCD_EDGE"

# Tên thiết bị Windows nằm ở trường nào trong sổ máy in của KHBL. Sổ do KHBL ghi, KHCD chỉ đọc ⇒
# nhận nhiều tên trường rồi mới rơi về "ten": hai bên có thể đặt tên trường khác nhau mà sổ vẫn
# dùng được, thay vì im lặng in hụt. "ten" xếp CUỐI vì nó có thể chỉ là nhãn cho người ("Máy quầy 1").
TRUONG_TEN = ("thiet_bi", "ten_windows", "windows", "may", "may_windows", "device", "printer", "ten")


def _cau_hinh(bien):
    """Đọc biến đè: app.config trước (bài kiểm đặt được), rồi tới môi trường/.env."""
    try:
        v = current_app.config.get(bien)
    except Exception:
        v = None
    return (v or os.environ.get(bien, "") or "").strip()


def _tep_dau_tien(duong_dan):
    for d in duong_dan:
        try:
            if d and os.path.isfile(d):
                return d
        except OSError:
            continue
    return None


def edge():
    """Đường dẫn msedge.exe, hoặc None. Chỉ là os.path.isfile — rẻ, gọi mỗi lượt dựng trang cũng được."""
    return _tep_dau_tien((_cau_hinh(BIEN_EDGE),) + EDGE_DUONG)


def cong_cu_day():
    """(đường dẫn, loại) công cụ đẩy PDF ra máy in; (None, '') nếu máy chủ chưa có cái nào."""
    dat = _cau_hinh(BIEN_CONG_CU)
    if dat and os.path.isfile(dat):
        ten = os.path.basename(dat).lower()
        return dat, ("pdftoprinter" if "pdftoprinter" in ten else "sumatra")
    for loai, duong in CONG_CU:
        tep = _tep_dau_tien(duong)
        if tep:
            return tep, loai
    return None, ""


# ── CHẠY TIẾN TRÌNH NGOÀI (luôn giết cả cây khi quá giờ) ─────────────────────────────────────
def _giet_cay(pid):
    """Giết tiến trình VÀ MỌI TIẾN TRÌNH CON. Edge đẻ tiến trình con; giết mỗi cha là để lại rác."""
    try:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=10, creationflags=CO_KHONG_CUA_SO)
    except Exception:
        pass
    try:
        os.kill(pid, 9)                        # lưới cuối, taskkill không có/không chạy được
    except Exception:
        pass


def _chay(lenh, gio_cho):
    """Chạy lệnh ẩn, trả (mã trả về | None nếu quá giờ, đầu ra bytes, quá_giờ bool).

    Không bao giờ ném lỗi ra ngoài trừ khi không khởi chạy nổi — chỗ gọi bắt hết.
    """
    p = subprocess.Popen(lenh, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, creationflags=CO_KHONG_CUA_SO)
    try:
        ra, _ = p.communicate(timeout=gio_cho)
        return p.returncode, ra or b"", False
    except subprocess.TimeoutExpired:
        _giet_cay(p.pid)
        try:
            ra, _ = p.communicate(timeout=5)
        except Exception:
            ra = b""
        return None, ra or b"", True


# ── TÌM MÁY IN (PowerShell Get-Printer — không cài gì) ────────────────────────────────────────
# Hôm nay máy chủ chỉ có MÁY IN ẢO (Print to PDF, XPS, OneNote, cổng TS00x của phiên Remote
# Desktop). ĐÓ LÀ BÌNH THƯỜNG, không phải lỗi; cắm máy in mạng vào máy chủ là nó tự hiện ra.
PS_LENH = ("[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;"
           "Get-Printer | Select-Object -ExpandProperty Name | ConvertTo-Json -Compress")
_nho_ds = {"luc": 0.0, "ds": None, "loi": ""}


def liet_ke(lam_moi=False):
    """(danh sách tên máy in, câu lỗi). Nhớ tạm NHO_MAY giây — mỗi lượt in không bắn một PowerShell.

    Mọi lỗi nuốt tại chỗ và biến thành câu lỗi: không tìm được máy in thì rơi về trình duyệt,
    KHÔNG BAO GIỜ làm hỏng trang in.
    """
    if not lam_moi and _nho_ds["ds"] is not None and time.time() - _nho_ds["luc"] < NHO_MAY:
        return list(_nho_ds["ds"]), _nho_ds["loi"]
    ds, loi = [], ""
    try:
        ma, ra, het = _chay(["powershell", "-NoProfile", "-NonInteractive",
                             "-ExecutionPolicy", "Bypass", "-Command", PS_LENH], GIO_CHO_PS)
        if het:
            loi = "Get-Printer quá %d giây" % GIO_CHO_PS
        elif ma:
            loi = "Get-Printer trả mã %s" % ma
        else:
            chuoi = ra.decode("utf-8", "replace").strip()
            data = json.loads(chuoi) if chuoi else None
            if isinstance(data, str):              # đúng MỘT máy in → ConvertTo-Json trả chuỗi trần
                ds = [data]
            elif isinstance(data, list):
                ds = [x for x in data if isinstance(x, str) and x.strip()]
            # data is None (máy chủ không có máy in nào) → ds rỗng, loi rỗng: hỏi được, câu trả lời là "không có"
    except Exception as loi_chay:
        loi = "%s: %s" % (type(loi_chay).__name__, loi_chay)
    _nho_ds.update(luc=time.time(), ds=ds, loi=loi)
    return list(ds), loi


def quen_nho():
    """Xoá bộ nhớ tạm danh sách máy in (bài kiểm và nút đọc lại cấu hình dùng)."""
    _nho_ds.update(luc=0.0, ds=None, loi="")


def ten_thiet_bi(ban):
    """Tên máy in Windows lấy từ một bản ghi trong sổ máy in của KHBL."""
    if not isinstance(ban, dict):
        return ""
    for k in TRUONG_TEN:
        v = ban.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def khop_ten(ten, danh_sach):
    """Trả ĐÚNG tên như Windows đang gọi (để truyền cho công cụ in), hoặc "" nếu không còn.

    Khớp y nguyên trước; rồi khớp không phân biệt hoa-thường và khoảng trắng thừa — người gõ tay
    vào ô cấu hình rất hay sai đúng hai thứ đó, mà lệch một chữ hoa là hụt cả đường in.
    """
    ten = (ten or "").strip()
    if not ten:
        return ""
    if ten in danh_sach:
        return ten
    gon = " ".join(ten.split()).casefold()
    for x in danh_sach:
        if " ".join(x.split()).casefold() == gon:
            return x
    return ""


# ── BẬC THANG ĐIỀU KIỆN ──────────────────────────────────────────────────────────────────────
def kiem_tra(layout=None):
    """Máy chủ có in thẳng được không? Trả dict cho trang in dùng ngay lúc dựng HTML.

    {san_sang, ly_do, ten, ma, ban_in, cong_cu, loai}. ly_do là MỘT CÂU NGẮN cho người vận hành —
    nó hiện trên dải XÁM (không phải dải đỏ): rơi về trình duyệt KHÔNG PHẢI LỖI, vẫn in bình thường.
    """
    try:
        layout = layout if layout is not None else G.load()
    except Exception:
        layout = G.mac_dinh()
    inn = {**G.IN_MAC_DINH, **((layout or {}).get(G.IN_KEY) or {})}
    ra = {"san_sang": False, "ly_do": "", "ten": "", "ma": (inn.get("may_in") or ""),
          "ban_in": int(inn.get("ban_in") or 1), "cong_cu": None, "loai": ""}

    # 1. MÁY IN THẬT Giám đốc đã TÌM → CHỌN → LƯU bên KHBL (khoá gcd_may_in) là NGUỒN CHÍNH.
    #    Sổ may_in_ds chỉ là bản khai tay, dùng làm đường lùi khi chưa ai bấm "Tìm máy in".
    try:
        that = G.doc_may_in_that()
    except Exception:
        that = {}
    ten = str((that or {}).get("ten") or "").strip()
    if ten:
        ra["ma"] = ra["ma"] or "gcd_may_in"
        ra["ten"] = ten
    else:
        # 1b. Chưa chọn máy in — đây là trạng thái HÔM NAY của hệ, hoàn toàn bình thường.
        if not ra["ma"]:
            ra["ly_do"] = "Chưa chọn máy in trong cấu hình (Bán lẻ → Mẫu in GCD)."
            return ra
        # 2. Đường lùi: tra sổ khai tay; bản ghi phải mang tên thiết bị Windows.
        try:
            ban = G.doc_may_in(ra["ma"])
        except Exception:
            ban = None
        ten = ten_thiet_bi(ban)
        ra["ten"] = ten or ra["ma"]
        if not ten:
            ra["ly_do"] = ("Tên máy in trong cấu hình không khớp máy in nào trên máy chủ — "
                           "sẽ mở hộp thoại in để chọn tay.")
            return ra
    # 3–4. Công cụ trên máy chủ.
    if not edge():
        ra["ly_do"] = "Máy chủ không có Microsoft Edge để dựng bản in."
        return ra
    cc, loai = cong_cu_day()
    if not cc:
        ra["ly_do"] = "Máy chủ chưa có công cụ đẩy bản in ra máy in."
        return ra
    ra.update(cong_cu=cc, loai=loai)
    # 5. Máy in còn cắm vào máy chủ không (tốn nhất, để cuối cùng).
    ds, loi = liet_ke()
    if loi:
        ra["ly_do"] = "Không hỏi được danh sách máy in của máy chủ."
        return ra
    that = khop_ten(ten, ds)
    if not that:
        ra["ly_do"] = "Máy chủ không còn máy in tên “%s”." % ten
        return ra
    ra.update(san_sang=True, ten=that)
    return ra


# ── DỰNG PDF BẰNG EDGE ẨN, RỒI ĐẨY SANG MÁY IN ───────────────────────────────────────────────
def _don_rac():
    """Xoá thư mục tạm của lượt in cũ bị bỏ lại (mất điện giữa chừng, tiến trình bị giết)."""
    try:
        goc = tempfile.gettempdir()
        gio = time.time()
        for ten in os.listdir(goc):
            if not ten.startswith(TIEN_TO_TAM):
                continue
            d = os.path.join(goc, ten)
            try:
                if os.path.isdir(d) and gio - os.path.getmtime(d) > RAC_QUA_HAN:
                    shutil.rmtree(d, ignore_errors=True)
            except OSError:
                continue
    except Exception:
        pass


def _lenh_edge(exe, trang, pdf, thu_muc):
    """Edge chạy ẩn dựng PDF. --no-pdf-header-footer (bản mới) và --print-to-pdf-no-header (bản cũ)
    cùng truyền: Chromium bỏ qua switch lạ, truyền cả hai thì bản nào cũng không in đầu/chân trang."""
    return [exe, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
            "--disable-extensions", "--disable-sync", "--disable-background-networking",
            "--hide-scrollbars", "--no-pdf-header-footer", "--print-to-pdf-no-header",
            "--user-data-dir=" + os.path.join(thu_muc, "edge"),
            "--virtual-time-budget=2000", "--run-all-compositor-stages-before-draw",
            "--print-to-pdf=" + pdf, Path(trang).as_uri()]


def _lenh_day(cong_cu, loai, ten_may, pdf, ban_in=1):
    """Lệnh đẩy PDF sang máy in. Trả DANH SÁCH lệnh — công cụ không hỗ trợ nhiều bản thì lặp lệnh."""
    ban_in = max(1, min(int(ban_in or 1), G.BAN_IN_TOI_DA))
    if loai == "pdftoprinter":
        return [[cong_cu, pdf, ten_may]] * ban_in
    lenh = [cong_cu, "-print-to", ten_may, "-silent", "-exit-when-done"]
    if ban_in > 1:
        lenh += ["-print-settings", "%dx" % ban_in]
    lenh.append(pdf)
    return [lenh]


def in_ngay(html, tep_chu=None, chep=None, tt=None):
    """Dựng PDF từ CHÍNH trang in rồi đẩy sang máy in đã lưu. Trả (ok, thông điệp).

    html     — HTML trang in thật đã render (KHÔNG BAO GIỜ bản ?nen=1).
    tep_chu  — {tên tệp: nội dung chữ} đặt cạnh trang (CSS bố cục sinh từ gcd_layout).
    chep     — danh sách tệp chép vào cạnh trang (static/gcd-print.css).
    tt       — kết quả kiem_tra() đã san_sang.

    Hụt ở BẤT KỲ bước nào → (False, lý do ngắn) và chỗ gọi rơi về hộp thoại in của trình duyệt.
    Không ném lỗi ra ngoài: một tờ giấy không in được không được phép thành trang 500.
    """
    if not tt or not tt.get("san_sang"):
        return False, (tt or {}).get("ly_do") or "Máy chủ chưa sẵn sàng in."
    _don_rac()
    # mkdtemp phải nằm TRONG try: ổ C đầy, %TEMP% bị xoá, hay tài khoản dịch vụ thiếu quyền ghi
    # đều ném OSError — để lọt ra ngoài là view in trả 500 thay vì rơi êm về hộp thoại trình duyệt.
    try:
        thu_muc = tempfile.mkdtemp(prefix=TIEN_TO_TAM)
    except OSError as e:
        return False, "Không tạo được tệp tạm trên máy chủ (%s)." % str(e)[:80]
    try:
        trang = os.path.join(thu_muc, "phieu.html")
        with open(trang, "w", encoding="utf-8") as f:
            f.write(html)
        for ten, noi in (tep_chu or {}).items():
            with open(os.path.join(thu_muc, os.path.basename(ten)), "w", encoding="utf-8") as f:
                f.write(noi)
        for nguon in (chep or []):
            try:
                shutil.copyfile(nguon, os.path.join(thu_muc, os.path.basename(nguon)))
            except OSError:
                pass                            # thiếu CSS tĩnh → chốt chặn fail-closed lo phần còn lại

        pdf = os.path.join(thu_muc, "phieu.pdf")
        ma, _ra, het = _chay(_lenh_edge(edge(), trang, pdf, thu_muc), GIO_CHO_PDF)
        if het:
            return False, "dựng bản in quá %d giây" % GIO_CHO_PDF
        if not os.path.isfile(pdf) or os.path.getsize(pdf) < 500:
            return False, "Edge không dựng được bản in (mã %s)" % ma

        for lenh in _lenh_day(tt["cong_cu"], tt.get("loai"), tt["ten"], pdf, tt.get("ban_in", 1)):
            ma2, _ra2, het2 = _chay(lenh, GIO_CHO_DAY)
            if het2:
                return False, "gửi bản in quá %d giây" % GIO_CHO_DAY
            if ma2:
                return False, "công cụ in trả mã %s" % ma2
        return True, "Đã gửi tới %s." % tt["ten"]
    except Exception as loi:
        try:
            current_app.logger.warning("In phía máy chủ hụt (%s: %s)", type(loi).__name__, loi)
        except Exception:
            pass
        return False, "%s" % type(loi).__name__
    finally:
        # Tờ phiếu có tên và địa chỉ khách — thư mục tạm KHÔNG được phép nằm lại trên ổ đĩa.
        shutil.rmtree(thu_muc, ignore_errors=True)
