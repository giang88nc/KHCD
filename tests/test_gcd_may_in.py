"""In GIẤY CẦM ĐỒ phía máy chủ + đường rơi về hộp thoại in của trình duyệt.

CHẠY: chỉ đích danh tệp này, KHÔNG BAO GIỜ chạy cả bộ, KHÔNG dùng discover.
    .venv\\Scripts\\python.exe -m pytest tests/test_gcd_may_in.py -q

Toàn bộ bài trong tệp này chạy KHÔNG CẦN CSDL và KHÔNG CHẠM MÁY IN THẬT: mọi lời gọi tiến trình
ngoài (PowerShell Get-Printer · Edge --print-to-pdf · công cụ đẩy bản in) đều đi qua một cửa duy
nhất `gcd_may_in._chay`, và bài kiểm thay cửa đó bằng hàm giả. Đó cũng là lý do module chỉ có MỘT
hàm chạy tiến trình ngoài — không được gọi subprocess ở chỗ khác, nếu không bài kiểm sẽ in thật.
"""
import os
import subprocess
import tempfile

import pytest

from khcd import gcd_layout as G, gcd_may_in as M


@pytest.fixture(autouse=True)
def sach_nho():
    """Danh sách máy in nhớ tạm 120 giây trong tiến trình — mỗi bài phải bắt đầu từ sổ trắng."""
    M.quen_nho()
    yield
    M.quen_nho()


def _chay_gia(ket_qua):
    """Thay M._chay. ket_qua: (mã trả về, bytes đầu ra, quá_giờ)."""
    ghi = []

    def chay(lenh, gio_cho):
        ghi.append((list(lenh), gio_cho))
        return ket_qua(lenh, gio_cho) if callable(ket_qua) else ket_qua

    chay.ghi = ghi
    return chay


# ── 1. TÊN MÁY IN TRONG SỔ CỦA KHBL ──────────────────────────────────────────────────────────
# Sổ do KHBL ghi, KHCD chỉ đọc. Nhận nhiều tên trường rồi mới rơi về "ten": hai dự án có thể đặt
# tên trường khác nhau mà sổ vẫn dùng được, thay vì im lặng in hụt.
def test_ten_thiet_bi_uu_tien_truong_thiet_bi():
    assert M.ten_thiet_bi({"ten": "Máy quầy 1", "thiet_bi": "HP LaserJet M404"}) == "HP LaserJet M404"


def test_ten_thiet_bi_roi_ve_ten_khi_khong_co_truong_rieng():
    assert M.ten_thiet_bi({"ten": " Microsoft Print to PDF "}) == "Microsoft Print to PDF"


def test_ten_thiet_bi_rac():
    assert M.ten_thiet_bi(None) == ""
    assert M.ten_thiet_bi({}) == ""
    assert M.ten_thiet_bi({"ten": "   "}) == ""
    assert M.ten_thiet_bi({"ten": 123}) == ""


# ── 2. KHỚP TÊN VỚI DANH SÁCH THẬT CỦA WINDOWS ───────────────────────────────────────────────
DS_THAT = ["OneNote (Desktop) (redirected 1)", "Microsoft Print to PDF",
           "Microsoft XPS Document Writer", "Send To OneNote 16"]


def test_khop_ten_y_nguyen():
    assert M.khop_ten("Microsoft Print to PDF", DS_THAT) == "Microsoft Print to PDF"


def test_khop_ten_bo_qua_hoa_thuong_va_khoang_trang_thua():
    # Gõ tay vào ô cấu hình sai đúng hai thứ này là chuyện thường; lệch một chữ hoa mà hụt cả
    # đường in thì người vận hành không bao giờ đoán ra. Trả về ĐÚNG tên Windows đang gọi.
    assert M.khop_ten("  microsoft   print to pdf ", DS_THAT) == "Microsoft Print to PDF"


def test_khop_ten_khong_con_thi_rong():
    assert M.khop_ten("HP LaserJet", DS_THAT) == ""
    assert M.khop_ten("", DS_THAT) == ""
    assert M.khop_ten("Microsoft Print to PDF", []) == ""


# ── 3. HỎI DANH SÁCH MÁY IN (PowerShell Get-Printer) ─────────────────────────────────────────
def test_liet_ke_doc_mang_json(monkeypatch):
    monkeypatch.setattr(M, "_chay", _chay_gia((0, b'["May A","May B"]', False)))
    ds, loi = M.liet_ke()
    assert ds == ["May A", "May B"] and loi == ""


def test_liet_ke_mot_may_in_tra_chuoi_tran(monkeypatch):
    # ConvertTo-Json với ĐÚNG MỘT phần tử trả chuỗi trần chứ không phải mảng — bẫy kinh điển.
    monkeypatch.setattr(M, "_chay", _chay_gia((0, b'"May duy nhat"', False)))
    assert M.liet_ke()[0] == ["May duy nhat"]


def test_liet_ke_khong_co_may_in_nao_khong_phai_loi(monkeypatch):
    # Máy chủ không có máy in nào: HỎI ĐƯỢC, câu trả lời là "không có" ⇒ danh sách rỗng, KHÔNG lỗi.
    monkeypatch.setattr(M, "_chay", _chay_gia((0, b"", False)))
    assert M.liet_ke() == ([], "")


def test_liet_ke_qua_gio_va_ma_loi(monkeypatch):
    monkeypatch.setattr(M, "_chay", _chay_gia((None, b"", True)))
    assert M.liet_ke()[0] == [] and "quá" in M.liet_ke(lam_moi=True)[1]
    M.quen_nho()
    monkeypatch.setattr(M, "_chay", _chay_gia((1, b"toang", False)))
    assert "mã 1" in M.liet_ke()[1]


def test_liet_ke_nuot_moi_loi_khong_nem_ra_ngoai(monkeypatch):
    def no(lenh, gio_cho):
        raise FileNotFoundError("khong co powershell")
    monkeypatch.setattr(M, "_chay", no)
    ds, loi = M.liet_ke()
    assert ds == [] and "FileNotFoundError" in loi      # tìm máy in hụt KHÔNG ĐƯỢC làm hỏng trang in


def test_liet_ke_nho_tam_khong_ban_powershell_moi_luot(monkeypatch):
    chay = _chay_gia((0, b'["May A"]', False))
    monkeypatch.setattr(M, "_chay", chay)
    M.liet_ke(); M.liet_ke(); M.liet_ke()
    assert len(chay.ghi) == 1
    assert M.liet_ke(lam_moi=True)[0] == ["May A"] and len(chay.ghi) == 2


# ── 4. BẬC THANG ĐIỀU KIỆN — RẺ TRƯỚC, TỐN SAU ───────────────────────────────────────────────
def _layout(may_in="", ban_in=1):
    m = G.mac_dinh()
    m[G.IN_KEY]["may_in"] = may_in
    m[G.IN_KEY]["ban_in"] = ban_in
    return m


def test_chua_chon_may_in_thi_dung_ngay_khong_goi_powershell(monkeypatch):
    # Trạng thái HÔM NAY của hệ: chưa ai lưu cấu hình. Trang in không được bắn một PowerShell nào.
    chay = _chay_gia((0, b"[]", False))
    monkeypatch.setattr(M, "_chay", chay)
    tt = M.kiem_tra(_layout(""))
    assert tt["san_sang"] is False and "Chưa chọn máy in" in tt["ly_do"] and chay.ghi == []


def test_so_may_in_khong_co_ban_ghi(monkeypatch):
    """Không tra được tên thiết bị ⇒ KHÔNG in máy chủ, rơi về hộp thoại trình duyệt.

    Câu báo cố ý nói theo ngôn ngữ người vận hành ("không khớp máy in nào trên máy chủ")
    chứ không nhắc "sổ máy in" — người đứng quầy không cần biết dữ liệu nằm ở sổ nào.
    """
    monkeypatch.setattr(G, "doc_may_in_that", lambda: {})
    monkeypatch.setattr(G, "doc_may_in", lambda ma: None)
    tt = M.kiem_tra(_layout("quay1"))
    assert not tt["san_sang"] and "không khớp máy in nào" in tt["ly_do"] and tt["ten"] == "quay1"


def test_uu_tien_may_in_that_giam_doc_da_chon(monkeypatch):
    """Máy in Giám đốc TÌM → CHỌN → LƯU bên KHBL (khoá gcd_may_in) phải THẮNG sổ khai tay.

    Đây chính là lỗi hợp đồng ngày 15/09/2026: KHCD chỉ đọc sổ may_in_ds nên máy in Giám đốc
    chọn không bao giờ tới nơi. Bài kiểm này khoá lại để không tái diễn.
    """
    monkeypatch.setattr(G, "doc_may_in_that", lambda: {"ten": "HP LaserJet M404"})
    monkeypatch.setattr(G, "doc_may_in", lambda ma: {"ten_windows": "MAY-IN-SO-KHAI-TAY"})
    tt = M.kiem_tra(_layout(""))          # _in.may_in ĐỂ TRỐNG mà vẫn phải nhận ra máy in
    assert tt["ten"] == "HP LaserJet M404"
    assert "Chưa chọn máy in" not in tt["ly_do"]


def test_so_may_in_doc_hut_khong_nem_loi(monkeypatch):
    def no(ma):
        raise RuntimeError("mat ket noi khj_bl")
    monkeypatch.setattr(G, "doc_may_in", no)
    tt = M.kiem_tra(_layout("quay1"))
    assert not tt["san_sang"] and tt["ly_do"]              # rơi về trình duyệt, không nổ 500


def test_thieu_edge(monkeypatch):
    monkeypatch.setattr(G, "doc_may_in", lambda ma: {"ten": "May A"})
    monkeypatch.setattr(M, "edge", lambda: None)
    tt = M.kiem_tra(_layout("quay1"))
    assert not tt["san_sang"] and "Edge" in tt["ly_do"]


def test_thieu_cong_cu_day_ban_in_la_trang_thai_hom_nay(monkeypatch):
    # Máy chủ CÓ Edge nhưng KHÔNG có SumatraPDF/PDFtoPrinter ⇒ đường phía máy chủ hụt, và đây
    # chính là hiện trạng 15/09/2026. Chưa hỏi Get-Printer ở bậc này.
    chay = _chay_gia((0, b"[]", False))
    monkeypatch.setattr(M, "_chay", chay)
    monkeypatch.setattr(G, "doc_may_in", lambda ma: {"ten": "May A"})
    monkeypatch.setattr(M, "edge", lambda: r"C:\msedge.exe")
    monkeypatch.setattr(M, "cong_cu_day", lambda: (None, ""))
    tt = M.kiem_tra(_layout("quay1"))
    assert not tt["san_sang"] and "công cụ đẩy bản in" in tt["ly_do"] and chay.ghi == []


def _du_cong_cu(monkeypatch, ban=None):
    monkeypatch.setattr(G, "doc_may_in", lambda ma: ban if ban is not None else {"ten": "Microsoft Print to PDF"})
    monkeypatch.setattr(M, "edge", lambda: r"C:\msedge.exe")
    monkeypatch.setattr(M, "cong_cu_day", lambda: (r"C:\Sumatra\SumatraPDF.exe", "sumatra"))


def test_hoi_danh_sach_hut(monkeypatch):
    _du_cong_cu(monkeypatch)
    monkeypatch.setattr(M, "liet_ke", lambda: ([], "Get-Printer quá 8 giây"))
    tt = M.kiem_tra(_layout("quay1"))
    assert not tt["san_sang"] and "danh sách máy in" in tt["ly_do"]


def test_may_in_khong_con_trong_danh_sach(monkeypatch):
    _du_cong_cu(monkeypatch, ban={"ten": "HP LaserJet M404"})
    monkeypatch.setattr(M, "liet_ke", lambda: (DS_THAT, ""))
    tt = M.kiem_tra(_layout("quay1"))
    assert not tt["san_sang"] and "không còn máy in" in tt["ly_do"] and "HP LaserJet M404" in tt["ly_do"]


def test_du_dieu_kien_thi_san_sang_va_lay_dung_ten_windows(monkeypatch):
    _du_cong_cu(monkeypatch, ban={"ten": "nhãn quầy", "thiet_bi": "microsoft print to pdf"})
    monkeypatch.setattr(M, "liet_ke", lambda: (DS_THAT, ""))
    tt = M.kiem_tra(_layout("quay1", ban_in=2))
    assert tt["san_sang"] is True
    assert tt["ten"] == "Microsoft Print to PDF"           # ĐÚNG chữ Windows đang gọi, không phải chữ đã gõ
    assert tt["ban_in"] == 2 and tt["loai"] == "sumatra"


# ── 5. LỆNH GỬI RA NGOÀI ─────────────────────────────────────────────────────────────────────
def test_lenh_edge_dung_trang_that_va_khong_dinh_gi_toi_anh_nen():
    lenh = M._lenh_edge(r"C:\msedge.exe", r"C:\tam\phieu.html", r"C:\tam\phieu.pdf", r"C:\tam")
    assert "--headless=new" in lenh and "--print-to-pdf=" + r"C:\tam\phieu.pdf" in lenh
    assert lenh[-1].startswith("file:///") and lenh[-1].endswith("phieu.html")
    # Bản gửi máy in chỉ có CHỮ: không một switch nào bật in nền/màu nền.
    # (--disable-background-networking có chữ "background" nhưng là chuyện mạng, không phải in nền.)
    assert not any("print-background" in x or "color-adjust" in x for x in lenh)
    # Edge đẻ tiến trình con: user-data-dir phải nằm TRONG thư mục tạm để xoá là sạch.
    assert any(x.startswith("--user-data-dir=" + r"C:\tam") for x in lenh)


def test_lenh_day_sumatra():
    ds = M._lenh_day(r"C:\S.exe", "sumatra", "May A", r"C:\p.pdf")
    assert ds == [[r"C:\S.exe", "-print-to", "May A", "-silent", "-exit-when-done", r"C:\p.pdf"]]


def test_lenh_day_sumatra_nhieu_ban():
    ds = M._lenh_day(r"C:\S.exe", "sumatra", "May A", r"C:\p.pdf", ban_in=3)
    assert len(ds) == 1 and "-print-settings" in ds[0] and "3x" in ds[0]


def test_lenh_day_pdftoprinter_lap_lenh_vi_khong_ho_tro_so_ban():
    ds = M._lenh_day(r"C:\P.exe", "pdftoprinter", "May A", r"C:\p.pdf", ban_in=2)
    assert ds == [[r"C:\P.exe", r"C:\p.pdf", "May A"]] * 2


def test_lenh_day_kep_so_ban_theo_gioi_han_chung():
    assert len(M._lenh_day(r"C:\P.exe", "pdftoprinter", "A", "p.pdf", ban_in=99)) == G.BAN_IN_TOI_DA
    assert len(M._lenh_day(r"C:\P.exe", "pdftoprinter", "A", "p.pdf", ban_in=0)) == 1


# ── 6. DỰNG PDF + ĐẨY — LUÔN DỌN TỆP TẠM ─────────────────────────────────────────────────────
TT_OK = {"san_sang": True, "ten": "May A", "cong_cu": r"C:\S.exe", "loai": "sumatra", "ban_in": 1}


def _dem_thu_muc_tam():
    return len([x for x in os.listdir(tempfile.gettempdir()) if x.startswith(M.TIEN_TO_TAM)])


def test_chua_san_sang_thi_khong_chay_gi(monkeypatch):
    chay = _chay_gia((0, b"", False))
    monkeypatch.setattr(M, "_chay", chay)
    ok, loi = M.in_ngay("<html></html>", tt={"san_sang": False, "ly_do": "Chưa chọn máy in."})
    assert ok is False and loi == "Chưa chọn máy in." and chay.ghi == []


def test_in_ngay_dung_duong_day_du_va_don_tep_tam(monkeypatch):
    monkeypatch.setattr(M, "edge", lambda: r"C:\msedge.exe")
    truoc = _dem_thu_muc_tam()

    def chay(lenh, gio_cho):
        if "--headless=new" in lenh:                       # giả Edge: đẻ ra tệp PDF
            pdf = [x for x in lenh if x.startswith("--print-to-pdf=")][0].split("=", 1)[1]
            thu_muc = os.path.dirname(pdf)
            with open(pdf, "wb") as f:
                f.write(b"%PDF-1.4" + b"x" * 2000)
            # Trang và hai tệp CSS phải nằm CẠNH NHAU — Edge nạp qua file:/// nên đường dẫn tương đối.
            assert os.path.isfile(os.path.join(thu_muc, "phieu.html"))
            assert os.path.isfile(os.path.join(thu_muc, "mau-in.css"))
            assert os.path.isfile(os.path.join(thu_muc, "gcd-print.css"))
        return (0, b"", False)

    ghi = _chay_gia(chay)
    monkeypatch.setattr(M, "_chay", ghi)
    ok, chu = M.in_ngay("<html>TỜ PHIẾU</html>",
                        tep_chu={"mau-in.css": ".gcd-a5{}"},
                        chep=[os.path.join(os.path.dirname(M.__file__), "static", "gcd-print.css")],
                        tt=TT_OK)
    assert ok is True and chu == "Đã gửi tới May A."
    assert len(ghi.ghi) == 2                               # dựng PDF rồi đẩy — đúng hai lượt
    assert _dem_thu_muc_tam() == truoc                     # tờ phiếu có tên+địa chỉ khách: KHÔNG được nằm lại


def test_edge_qua_gio_thi_roi_ve_va_van_don_tep(monkeypatch):
    monkeypatch.setattr(M, "edge", lambda: r"C:\msedge.exe")
    truoc = _dem_thu_muc_tam()
    monkeypatch.setattr(M, "_chay", _chay_gia((None, b"", True)))
    ok, loi = M.in_ngay("<html></html>", tt=TT_OK)
    assert ok is False and "dựng bản in quá" in loi and _dem_thu_muc_tam() == truoc


def test_edge_khong_ra_pdf_thi_roi_ve(monkeypatch):
    monkeypatch.setattr(M, "edge", lambda: r"C:\msedge.exe")
    monkeypatch.setattr(M, "_chay", _chay_gia((0, b"", False)))   # chạy xong nhưng không đẻ tệp
    ok, loi = M.in_ngay("<html></html>", tt=TT_OK)
    assert ok is False and "không dựng được" in loi


def test_cong_cu_in_tra_ma_loi_thi_roi_ve(monkeypatch):
    monkeypatch.setattr(M, "edge", lambda: r"C:\msedge.exe")

    def chay(lenh, gio_cho):
        if "--headless=new" in lenh:
            pdf = [x for x in lenh if x.startswith("--print-to-pdf=")][0].split("=", 1)[1]
            with open(pdf, "wb") as f:
                f.write(b"%PDF-1.4" + b"x" * 2000)
            return (0, b"", False)
        return (2, b"printer offline", False)

    monkeypatch.setattr(M, "_chay", _chay_gia(chay))
    ok, loi = M.in_ngay("<html></html>", tt=TT_OK)
    assert ok is False and "mã 2" in loi


def test_no_bat_ngo_van_khong_nem_ra_ngoai(monkeypatch):
    monkeypatch.setattr(M, "edge", lambda: r"C:\msedge.exe")

    def no(lenh, gio_cho):
        raise OSError("WinError 2")
    monkeypatch.setattr(M, "_chay", no)
    truoc = _dem_thu_muc_tam()
    ok, loi = M.in_ngay("<html></html>", tt=TT_OK)
    assert ok is False and loi == "OSError" and _dem_thu_muc_tam() == truoc


def test_giet_ca_cay_khi_qua_gio(monkeypatch):
    """Quá giờ phải gọi taskkill /T (cả cây) — giết mỗi tiến trình cha là để Edge con nằm lại."""
    goi = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: goi.append(list(a[0])))
    monkeypatch.setattr(os, "kill", lambda *a: None)
    M._giet_cay(4242)
    assert goi and goi[0][:4] == ["taskkill", "/T", "/F", "/PID"] and goi[0][4] == "4242"


# ── 7. BẢN DỰNG CHO EDGE LÀ TRANG IN THẬT, KHÔNG PHẢI BẢN CÓ NỀN ─────────────────────────────
@pytest.fixture
def ung_dung():
    """Ứng dụng KHÔNG chạm CSDL — chỉ để render_template. Không gọi một truy vấn nào."""
    from khcd import create_app
    return create_app({"SECRET_KEY": "chi-de-render", "DB_NAME": "khong_dung_toi",
                       "DB_READ_ONLY": True, "TESTING": True})


def _ctx_gia():
    from datetime import date
    from decimal import Decimal
    return {"loan": {"sku": "KH2260900000001", "original_principal": Decimal("5000000"),
                     "principal_balance": Decimal("5000000"), "opened_at": date(2026, 9, 1),
                     "due_at": date(2026, 10, 1), "monthly_rate": Decimal("3"), "safe": 1,
                     "note": "", "employee_name": "Nguyện", "loan_state": "ACTIVE",
                     "receipt_lost": 0, "phone": ""},
            "customer": {"name": "Nguyễn Văn A", "addr": "Cần Thơ", "phone": "0900000000", "cccd": ""},
            "items": [{"gold_code": "99", "description": "Nhẫn", "unit": "chỉ", "net_weight": Decimal("1.5")}],
            "warning": None}


def test_ban_dung_cho_edge_khong_co_nen_khong_co_js(ung_dung):
    from khcd import gcd_print as P
    with ung_dung.test_request_context():
        html = P._dung_trang(_ctx_gia(), G.mac_dinh(), "sql", nen=False, pdf=True,
                             css_url="mau-in.css", css_tinh_url="gcd-print.css", lid=1)
    assert "gcd-nen" not in html                    # ẢNH NỀN không có đường nào lọt vào bản gửi máy in
    assert "GCD.jpg" not in html
    assert "<script" not in html                    # Edge chạy ẩn không cần JS, và không được chờ JS
    assert 'href="mau-in.css"' in html and 'href="gcd-print.css"' in html   # tệp cạnh trang, file:///
    assert "gcd-thanh" not in html                  # bỏ thanh công cụ
    # Tờ giấy vẫn ĐỦ 17 khối — cùng một bản vẽ với bản trên màn hình.
    for b in G.BLOCKS:
        assert 'data-gcd="%s"' % b["key"] in html


def test_ban_tren_man_hinh_van_giu_js_va_hai_tep_css(ung_dung):
    from khcd import gcd_print as P
    with ung_dung.test_request_context():
        html = P._dung_trang(_ctx_gia(), G.mac_dinh(), "sql", nen=False, pdf=False,
                             may_tt=M.kiem_tra(_layout("")), lid=1,
                             css_url="/camdo/bien-nhan/mau-in.css", css_tinh_url="/static/gcd-print.css?v=1")
    assert "gcd-print.js" in html and "receipt-print.js" in html
    # Chưa chọn máy in ⇒ nút IN giữ NGUYÊN thân phận cũ: receipt-print.js bấm là window.print() ngay.
    assert 'id="tracked-print-button"' in html and 'id="gcd-nut-in"' not in html
    assert "hộp thoại in của trình duyệt" in html   # một dòng giải thích, dải XÁM


def test_du_dieu_kien_thi_nut_in_doi_sang_duong_may_chu(ung_dung, monkeypatch):
    from khcd import gcd_print as P
    _du_cong_cu(monkeypatch)
    monkeypatch.setattr(M, "liet_ke", lambda: (DS_THAT, ""))
    with ung_dung.test_request_context():
        html = P._dung_trang(_ctx_gia(), G.mac_dinh(), "sql", nen=False, pdf=False,
                             may_tt=M.kiem_tra(_layout("quay1")), lid=1,
                             css_url="/camdo/bien-nhan/mau-in.css", css_tinh_url="/static/gcd-print.css?v=1")
    assert 'id="gcd-nut-in"' in html and 'id="tracked-print-button"' not in html
    assert "data-may-url=" in html and "Microsoft Print to PDF" in html
