"""
gcd_print — IN BIÊN NHẬN CẦM ĐỒ LÊN GIẤY A5 NGANG ĐÃ IN SẴN.

BA ĐƯỜNG TÁCH BẠCH (đường in cũ /bien-nhan/<lid>/in GIỮ NGUYÊN làm lưới an toàn):
    GET  /camdo/bien-nhan/<lid>/giay            IN THẬT — chỉ CHỮ, KHÔNG ảnh nền, KHÔNG màu nền.
    GET  /camdo/bien-nhan/<lid>/giay?nen=1      XEM TRƯỚC CÓ NỀN — kiểm khớp ô trên màn hình.
    GET  /camdo/bien-nhan/<lid>/giay?thuoc=1    IN THƯỚC — căn máy in trên GIẤY TRẮNG (xem README).
    GET  /camdo/bien-nhan/mau-in.css            CSS bố cục sinh từ khj_bl.pmv_state['gcd_layout'].
    POST /camdo/bien-nhan/<lid>/in-may-chu      IN THẲNG tới máy in đã lưu (JSON), xem gcd_may_in.

MỘT BẢN VẼ DUY NHẤT: đường in phía máy chủ dựng PDF bằng Edge ẩn từ CHÍNH template này, cùng CSS
này — nên bản giấy, bản xem trước và bản PDF không thể trôi khỏi nhau. _dung_trang() là chỗ dựng
chung; hai route chỉ khác nhau ở ĐỊA CHỈ TỆP CSS (http cho trình duyệt, tệp cạnh trang cho Edge).

VÌ SAO CSS PHẢI ĐI QUA MỘT ROUTE RIÊNG: khcd/__init__.py đặt style-src 'self' KHÔNG có
'unsafe-inline' ⇒ thẻ <style> và thuộc tính style="..." trong template bị chặn CÂM. Route trả
Content-Type: text/css được 'self' cho qua mà KHÔNG phải nới CSP.

CHỐT CHẶN HỎNG-CÂM (nếu CSS bố cục không nạp được — phiên hết hạn trả HTML đăng nhập, sai MIME,
trình duyệt bỏ stylesheet không báo gì): static/gcd-print.css khai FAIL-CLOSED — khi in thì ẨN tờ
giấy và HIỆN dòng cảnh báo; CSS bố cục mới bật tờ giấy lên bằng !important. Hỏng ⇒ ra TỜ TRẮNG
(mất 1 tờ giấy) chứ KHÔNG phun 17 khối chồng lên góc trái tờ in sẵn. static/gcd-print.js kiểm
thêm getComputedStyle trước khi cho bấm in, và KHÔNG BAO GIỜ tự gọi window.print().

THỨ TỰ TRUY VẤN (bắt buộc): phiếu + khách + món TRƯỚC, bố cục CUỐI CÙNG — db.one() dùng chung
connection của request, đọc chéo khj_bl mà chết connection thì mọi truy vấn sau cũng chết và rơi
vào errorhandler 503, tức là MẤT TỜ PHIẾU.
"""
import hashlib
import os

from flask import Blueprint, Response, render_template, request, url_for

from . import gcd_layout as G, gcd_may_in as M, live_loans as live, pawn_desk as desk
from .domain import money, parse_date
from .loan_conversion import LABEL

bp = Blueprint("gcd", __name__, url_prefix="/camdo")

TU = {"1": "Tủ 18k", "2": "Tủ 24k", "3": "Tủ đồ lớn"}

# Công tắc FAIL-CLOSED, riêng của KHCD (không nằm trong gcd_layout.css() để chuỗi CSS còn đối
# chiếu được từng ký tự với bản KHBL). static/gcd-print.css khai NGƯỢC LẠI: khi in thì ẩn tờ giấy
# và hiện dòng cảnh báo. Chỉ khi CSS bố cục nạp ĐƯỢC thì hai dòng dưới đây mới lật công tắc.
BAT_TO_GIAY = "@media print{.gcd-a5{display:block!important}.gcd-canhbao-css{display:none!important}}"


def _vnd(v):
    return f"{money(v):,.0f}".replace(",", ".")


def _rows(items):
    """Món trong CSDL → đúng hình dạng pawn_desk.summary() đang dùng ở màn chốt phiếu.

    ⚠ KHÔNG viết hàm gộp món thứ hai: chuỗi này đã được ghi xuống khcd_pawn_desk.content và đang
    hiện ở bàn lập phiếu. Chữ trên biên nhận giao khách phải ĐÚNG chuỗi nhân viên đã xác nhận.
    """
    return [dict(gold=(i["gold_code"] or ""), description=(i["description"] or ""),
                 unit=(i["unit"] or "chỉ"), net=str(i["net_weight"] or 0)) for i in items]


def _noi_dung(ctx, layout):
    """Chữ đổ vào từng khối. Trả dict key → danh sách DÒNG (không có HTML, template tự thoát)."""
    p, kh, items = ctx["loan"], ctx["customer"] or {}, ctx["items"]
    ct = {**G.CT_MAC_DINH, **(layout.get(G.CT_KEY) or {})}
    rows = _rows(items)
    if ct.get("mon_gop", 1):
        mon = [desk.summary(rows)] if rows else []
    else:
        mon = [desk.summary([r]) for r in rows]
    tien = p["original_principal"] if ct.get("tien") != "du_hien_tai" else p["principal_balance"]
    mo, den = parse_date(p["opened_at"]), parse_date(p["due_at"])
    ten = kh.get("name") or ""
    trang_thai = LABEL.get(p["loan_state"], p["loan_state"] or "")
    if p.get("receipt_lost"):
        trang_thai += " · BÁO MẤT BIÊN NHẬN"

    cuong = list(mon)
    cuong.append("Lãi suất: %s%%/tháng" % (format(p["monthly_rate"], ".6f").rstrip("0").rstrip(".") if p["monthly_rate"] is not None else "—"))
    cuong.append("Tủ: " + TU.get(str(p["safe"] or ""), str(p["safe"] or "—")))
    if kh.get("phone") or p.get("phone"):
        cuong.append("SĐT: " + (kh.get("phone") or p.get("phone")))
    if p.get("note"):
        cuong.append("Ghi chú: " + p["note"])

    return {
        "so_cuong_1": [p["sku"]],
        "so_cuong_2": [p["sku"]],
        "cuong_chi_tiet": cuong,
        "ma_phieu": [p["sku"]],
        "khach_ten": [ten],
        "khach_diachi": [kh.get("addr") or ""],
        "mon_hang": mon,
        "so_tien_so": [_vnd(tien)],
        "so_tien_chu": [G.doc_so(tien)],
        # Kỳ hạn không có cột riêng: suy ra từ hai mốc ngày.
        "ky_han": [str((den - mo).days)],
        # Tờ in sẵn đã có sẵn chữ "năm ......" riêng ⇒ hai ô ngày chỉ in dd/mm, khỏi lặp năm.
        "ngay_lap": [mo.strftime("%d/%m")],
        "ngay_hen": [den.strftime("%d/%m")],
        "nam": [den.strftime("%Y")],
        "nhan_vien": [p.get("employee_name") or ""],
        "khach_ky": [ten],
        "trang_thai": [trang_thai],
        "giay_to": [("CCCD " + kh["cccd"]) if kh.get("cccd") else ""],
    }


def _khoi(ctx, layout):
    """17 khối theo đúng thứ tự BLOCKS — template lặp danh sách này nên DOM luôn đủ data-gcd."""
    noi = _noi_dung(ctx, layout)
    ra, tran = [], []
    for b in G.BLOCKS:
        dong = [d for d in noi.get(b["key"], []) if d not in (None, "")]
        bac, qua = G.bac_co_chu(" ".join(dong), b["key"], layout)
        if qua:
            tran.append(b["ten"])
        ra.append(dict(key=b["key"], ten=b["ten"], dong=dong, cls="gcd-co-%d" % bac,
                       an=bool(layout[b["key"]].get("an"))))
    return ra, tran


def _css_url(nen):
    return url_for("gcd.mau_in_css", **({"nen": 1} if nen else {}))


def _dung_trang(ctx, layout, nguon, nen=False, thuoc=False, may_tt=None, pdf=False,
                css_url=None, css_tinh_url=None, lid=None):
    """Dựng HTML trang in — DÙNG CHUNG cho trình duyệt và cho Edge dựng PDF.

    pdf=True: bỏ thanh công cụ, bỏ JS, bỏ favicon; hai tệp CSS trỏ vào tệp nằm CẠNH trang trong thư
    mục tạm (Edge nạp qua file:///). Phần TỜ GIẤY thì không đổi một ký tự nào — đó là cả điểm của
    việc dùng chung: bản gửi máy in và bản trên màn hình phải là cùng một bản vẽ.
    """
    khoi, tran = _khoi(ctx, layout)
    inn = {**G.IN_MAC_DINH, **(layout.get(G.IN_KEY) or {})}
    ct = {**G.CT_MAC_DINH, **(layout.get(G.CT_KEY) or {})}
    p = ctx["loan"]
    # Hai đường in hiện hai con số khác nhau là lỗi chứng từ ⇒ nói thẳng trên màn hình khi lệch.
    lech_tien = (ct.get("tien") != "du_hien_tai" and p["original_principal"] != p["principal_balance"])
    return render_template(
        "loan_print_gcd.html", title=p["sku"] + " · Giấy cầm đồ", loan=p, customer=ctx["customer"],
        khoi=khoi, tran=tran, mep=G.khoi_sat_mep(layout), nen=nen, thuoc=thuoc, nguon=nguon,
        inn=inn, ct=ct, may_tt=may_tt, pdf=pdf,
        lech_tien=lech_tien, goc=_vnd(p["original_principal"]), du=_vnd(p["principal_balance"]),
        warning=ctx["warning"], css_url=css_url, css_tinh_url=css_tinh_url,
        print_count_url=None if pdf else url_for("live.print_count", lid=lid),
        may_url=None if pdf else url_for("gcd.in_may_chu", lid=lid),
        print_url=None if pdf else url_for("gcd.giay", lid=lid),
        detail_url=None if pdf else url_for("live.print_receipt", lid=lid))


@bp.get("/bien-nhan/<int:lid>/giay")
def giay(lid):
    # 1) Phiếu + khách + món TRƯỚC.
    ctx = live.receipt_context(lid)
    # 2) Bố cục CUỐI CÙNG, và mọi lỗi đã được nuốt bên trong gcd_layout.
    layout, nguon = G.doc_bo_cuc()
    nen = request.args.get("nen") == "1"
    thuoc = request.args.get("thuoc") == "1"
    # 3) Máy chủ in thẳng được hay phải rơi về hộp thoại trình duyệt — QUYẾT ĐỊNH NGAY TẠI ĐÂY,
    #    không phải lúc bấm: bấm IN là thấy hộp thoại ngay, không ngồi chờ máy chủ thử rồi mới rơi.
    #    Chế độ xem trước/thước không in ra máy in nên khỏi hỏi.
    may_tt = None if (nen or thuoc) else M.kiem_tra(layout)
    return _dung_trang(ctx, layout, nguon, nen=nen, thuoc=thuoc, may_tt=may_tt, lid=lid,
                       css_url=_css_url(nen),
                       css_tinh_url=url_for("static", filename="gcd-print.css") + "?v=1")


@bp.post("/bien-nhan/<int:lid>/in-may-chu")
def in_may_chu(lid):
    """In thẳng tới máy in đã lưu trong cấu hình. LUÔN trả JSON 200, KHÔNG BAO GIỜ trả lỗi.

    {"ok":true,"thong_diep":"Đã gửi tới …"}  hoặc  {"ok":false,"ly_do":"…"} — ly_do là câu giải
    thích ngắn để trang nói một dòng rồi mở hộp thoại in của trình duyệt. Người dùng luôn in được;
    khác biệt duy nhất là có phải tự chọn máy in hay không, nên đây KHÔNG phải trạng thái lỗi.
    """
    # Thứ tự bắt buộc: phiếu + khách + món TRƯỚC, bố cục (đọc chéo khj_bl) CUỐI CÙNG.
    ctx = live.receipt_context(lid)
    layout, nguon = G.doc_bo_cuc()
    tt = M.kiem_tra(layout)
    if not tt["san_sang"]:
        return {"ok": False, "ly_do": tt["ly_do"]}
    # nen=False TUYỆT ĐỐI: bản gửi máy in chỉ có CHỮ. Thư mục tạm cũng không có ảnh GCD.jpg.
    html = _dung_trang(ctx, layout, nguon, nen=False, thuoc=False, may_tt=tt, pdf=True,
                       css_url="mau-in.css", css_tinh_url="gcd-print.css", lid=lid)
    ok, loi = M.in_ngay(html, tep_chu={"mau-in.css": G.css(layout) + "\n" + BAT_TO_GIAY},
                        chep=[os.path.join(bp.root_path, "static", "gcd-print.css")], tt=tt)
    return {"ok": True, "thong_diep": loi} if ok else {"ok": False, "ly_do": loi}


@bp.get("/bien-nhan/mau-in.css")
def mau_in_css():
    """CSS bố cục. Chỉ sinh từ gcd_layout — KHÔNG background, KHÔNG print-color-adjust.

    Ảnh nền chỉ được phép xuất hiện qua .gcd-nen (phần tử riêng, class no-print) và css_nen() khi
    người dùng hỏi ?nen=1, nên bản in thật không có đường nào chạm tới nó.
    """
    layout = G.load()
    noi_dung = G.css(layout) + "\n" + BAT_TO_GIAY
    if request.args.get("nen") == "1":
        noi_dung += "\n" + G.css_nen(layout)
    body = noi_dung.encode("utf-8")
    res = Response(body, content_type="text/css; charset=utf-8")
    res.headers["ETag"] = '"%s"' % hashlib.sha256(body).hexdigest()[:16]
    return res
