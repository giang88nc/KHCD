"""
gcd_print — IN BIÊN NHẬN CẦM ĐỒ LÊN GIẤY A5 NGANG ĐÃ IN SẴN.

BA ĐƯỜNG TÁCH BẠCH (đường in cũ /bien-nhan/<lid>/in GIỮ NGUYÊN làm lưới an toàn):
    GET  /camdo/bien-nhan/<lid>/giay            IN THẬT — chỉ CHỮ + MÃ VẠCH, KHÔNG ảnh nền/màu nền.
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

MÃ VẠCH SỐ BIÊN NHẬN (16/09/2026): khối `ma_phieu_vach` không chứa chữ mà chứa ẢNH — `_anh()` gọi
khcd/ma_vach.py (bản sao thuật toán Code 39 của KHBL) dựng PNG data URI từ CHÍNH mã phiếu đang in,
template đổ ra thẻ <img>. Data URI chứ không phải tệp riêng: đường in phía máy chủ nạp trang qua
file:/// trong thư mục tạm, một tệp ảnh rời nữa là một đường hụt nữa. KHÔNG vẽ mã vạch bằng CSS —
bản in này cố ý không có print-color-adjust nên mọi thứ vẽ bằng background sẽ biến mất trên giấy.

THỨ TỰ TRUY VẤN (bắt buộc): phiếu + khách + món TRƯỚC, bố cục CUỐI CÙNG — db.one() dùng chung
connection của request, đọc chéo khj_bl mà chết connection thì mọi truy vấn sau cũng chết và rơi
vào errorhandler 503, tức là MẤT TỜ PHIẾU.
"""
import datetime as dt
import hashlib
import os
import re

from flask import Blueprint, Response, render_template, request, url_for

from . import db, gcd_layout as G, gcd_may_in as M, live_loans as live, ma_vach as MV, pawn_desk as desk
from .domain import money, parse_date

bp = Blueprint("gcd", __name__, url_prefix="/camdo")


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

    ⚠ 17/09/2026: BỎ mặc định `unit or "chỉ"`. Đơn vị in ra nay do MÃ VÀNG quyết
    (pawn_desk.don_vi), còn cột `unit` trong sổ để NULL ở 992/999 dòng — điền đại "chỉ" vào đây là
    khẳng định một đơn vị không có trong sổ, và nếu món đó là bạch kim/vàng trắng thì sai 3,75 lần.
    """
    return [dict(gold=(i["gold_code"] or ""), description=(i["description"] or ""),
                 unit=(i["unit"] or ""), net=str(i["net_weight"] or 0)) for i in items]


def _mon(ctx, layout):
    """Danh sách DÒNG MÓN HÀNG — MỘT nguồn duy nhất cho cả thân biên nhận lẫn hai bảng cuống.

    Tách ra làm hàm riêng chứ không chép lại ở chỗ thứ hai: cuống tiệm giữ và bản giao khách mà
    liệt kê món khác nhau thì đối chiếu kiểu gì lúc khách tới chuộc.
    """
    ct = {**G.CT_MAC_DINH, **(layout.get(G.CT_KEY) or {})}
    rows = _rows(ctx["items"])
    if ct.get("mon_gop", 1):
        return [desk.summary(rows)] if rows else []
    return [desk.summary([r]) for r in rows]


def _phien(ctx):
    """Giao dịch GẦN NHẤT của phiếu → {nghiệp vụ} · giờ · tiền Thu/Chi cho bảng cuống.

    Vì sao đọc giao dịch chứ không đọc trạng thái phiếu: cuống tiệm giữ là chứng từ của LƯỢT VIỆC
    vừa làm (Cầm mới / Cầm thêm / Trả bớt / Gia hạn / Chuộc đồ / Thanh lý / Báo mất), không phải
    ảnh chụp trạng thái. In lại tờ cũ vẫn ra lượt cuối — đúng ý.

    Thu = tiền KHÁCH TRẢ (cd_payments direction='IN') · Chi = tiền TRẢ KHÁCH ('OUT'), đúng nghĩa
    `received`/`paid` mà LOG_SQL của live_loans đang dùng cho màn Phiên giao dịch. Đừng đặt lại
    nghĩa ở đây: hai màn hình nói ngược nhau về cùng một lượt tiền là hỏng đối soát.

    ⚠ BỎ QUA nghiệp vụ 8 "Mở khóa báo mất" — GIỐNG mọi chỗ khác của hệ (live_loans lọc
    `operation_id<>8` ở màn Phiên giao dịch). Lượt mở khóa ghi log với MỌI khoản tiền = 0 và không
    sinh dòng cd_payments nào; lấy nó làm "lượt gần nhất" thì cuống in "Mở khóa báo mất" kèm dòng
    Thu/Chi trống, trong khi lượt việc có tiền thật (vd "Cầm thêm · Chi 5.000.000") bị giấu mất.

    Phiếu chưa có dòng log nào (kho cũ `pawn`, hoặc live tắt), hay đọc sổ hỏng → trả None và các ô
    đó ĐỂ TRỐNG. Tuyệt đối không bịa: thà cuống thiếu một dòng còn hơn in sai nghiệp vụ lên chứng
    từ. Cả trang in cũng không được chết vì một câu truy vấn phụ.
    """
    p = ctx["loan"]
    try:
        log = db.one("SELECT id,operation_id,happened_at,interest_from,due_at,days,interest,"
                     "principal_change FROM cd_loan_logs"
                     " WHERE loan_id=%s AND operation_id<>8"
                     " ORDER BY happened_at DESC,id DESC LIMIT 1", (p["id"],))
        if not log:
            return None
        t = db.one("SELECT COALESCE(SUM(IF(direction='IN',amount,0)),0) thu,"
                   "COALESCE(SUM(IF(direction='OUT',amount,0)),0) chi"
                   " FROM cd_payments WHERE log_id=%s", (log["id"],)) or {}
    except Exception:
        return None
    # Giám đốc chốt 17/09/2026: BỎ hẳn nhãn "Thu/Chi:", chỉ in MỘT số theo dấu của nó —
    #   ròng > 0 → "Thu <số>"   ·   ròng < 0 → "Chi <số>"   ·   = 0 → để trống, template bỏ cả dòng.
    # Ròng = tiền khách trả − tiền trả khách trong CÙNG lượt việc (một lượt vừa thu vừa chi là
    # chuyện thường: cầm thêm 700.000 nhưng khấu lãi 205.000 ⇒ thực chi 495.000).
    rong = money(t.get("thu") or 0) - money(t.get("chi") or 0)
    if rong > 0:
        tien = "Thu " + _vnd(rong)
    elif rong < 0:
        tien = "Chi " + _vnd(-rong)
    else:
        tien = ""
    luc = parse_date(log["happened_at"])
    gio = log["happened_at"]
    # SỐ NGÀY GIA HẠN THÊM — suy từ chính ba cột của dòng log, khỏi mở terms_json:
    #   ngày tính lãi hiệu lực = interest_from + days  (đúng cách estimate() tính lãi)
    #   gia hạn thêm            = due_at − ngày hiệu lực
    # Đã đối chiếu 4 lượt gia hạn thật trong sổ: cả bốn đều ra +30 ngày, khớp kỳ hạn mặc định.
    gia_han = 0
    try:
        if log["due_at"] and log["interest_from"]:
            hieu_luc = parse_date(log["interest_from"]) + dt.timedelta(days=int(log["days"] or 0))
            gia_han = (parse_date(log["due_at"]) - hieu_luc).days
    except (TypeError, ValueError):
        gia_han = 0
    return {"log_id": log["id"],
            "op": log["operation_id"],
            "nghiep_vu": live.OPS.get(log["operation_id"], ""),
            "luc": gio.strftime("%H:%M %d/%m/%Y") if hasattr(gio, "strftime") else str(luc),
            "thu_chi": tien,
            "ngay": int(log["days"] or 0),
            "lai": money(log["interest"] or 0),
            "doi_goc": money(log["principal_change"] or 0),
            "gia_han": gia_han if gia_han > 0 else 0}


def _bang(ctx, layout):
    """HAI BẢNG CUỐNG — CÙNG MỘT bộ dữ liệu, hai bản giống hệt nhau (GĐ chốt 16/09/2026).

    Dựng một lần rồi dùng cho cả hai khối: lệch nhau một chữ là hai nửa tờ giấy nói hai chuyện.
    Cả hai khối đều TẮT thì khỏi dựng — riêng QR đã tốn một lượt vẽ SVG.

    `ctx["phien"]` đã được route đọc SẴN (trước khi đọc bố cục chéo sang khj_bl, đúng thứ tự truy
    vấn bắt buộc ghi ở đầu tệp); không có thì tự đọc — đường nào cũng phải ra tờ giấy.
    """
    if all(layout[k].get("an") for k in G.KHOI_BANG):
        return {}
    p, kh = ctx["loan"], ctx["customer"] or {}
    phien = (ctx.get("phien") if "phien" in ctx else _phien(ctx)) or {}
    try:
        # Cùng luật với mã vạch: MẤT MÃ CÒN HƠN MẤT TỜ PHIẾU. svg_qr nạp segno lúc chạy, thiếu thư
        # viện / hết bộ nhớ là nổ — template đã có sẵn {% if b.qr %} nên trả '' là tờ giấy vẫn ra.
        qr = MV.svg_qr(p["sku"])
    except Exception:
        qr = ""
    b = {"nghiep_vu": phien.get("nghiep_vu", ""),
         "luc": phien.get("luc", ""),
         # QR mang NGUYÊN mã phiếu kể cả chữ cái — khác mã vạch Code 39 chỉ mang phần chữ số.
         "qr": qr,
         "ma": p["sku"],
         "ten": (kh.get("name") or "").strip(),
         "dt": (kh.get("phone") or p.get("phone") or "").strip(),
         "noi_dung": _mon(ctx, layout),
         "thu_chi": phien.get("thu_chi", ""),
         # Ô "Cầm" luôn là DƯ GỐC hiện tại của phiếu (GĐ chốt), không phải gốc ban đầu — kể cả khi
         # khối `so_tien_so` ở thân phiếu đang được cấu hình in gốc ban đầu.
         "cam": _vnd(p["principal_balance"])}
    return {k: b for k in G.KHOI_BANG}


TEN_TIEM = "CẦM ĐỒ KIM HẠNH 2"
# Nghiệp vụ CÓ in khối tóm tắt giao dịch trên cuống (Giám đốc chốt 17/09/2026):
#   2 Cầm thêm · 3 Trả bớt · 4 Gia hạn.
# KHÔNG in: 1 Cầm mới (chưa có gì để tóm tắt) · 5 Chuộc đồ · 6 Thanh lý · 7 Báo mất (ba nghiệp vụ
# này Giám đốc chốt là KHÔNG CẦN IN GIẤY) · 0 Hủy phiên · 8 Mở khóa báo mất.
OP_CO_TOM_TAT = (2, 3, 4)


def _che_sdt(sdt):
    """Số điện thoại in trên chứng từ: giữ 3 số đầu + 3 số cuối, che 4 số giữa — '090****567'.

    Tờ biên nhận đi theo món hàng vào tủ và khách cầm về; in trọn số là phát tán số khách. Giữ đủ
    hai đầu để nhân viên đối chiếu nhanh với sổ, còn muốn số đầy đủ thì tra trong hệ thống.
    """
    so = re.sub(r"\D", "", str(sdt or ""))
    return (so[:3] + "****" + so[-3:]) if len(so) >= 7 else ""


def _ma_theo_doi(p, phien):
    """Mã truy vết in trên cuống: '2609020839-977-3435-01' (Giám đốc chốt 17/09/2026).

        <mã phiếu bỏ tiền tố KH2> - <loan_id> - <log_id của lượt việc> - <lần in thứ mấy>

    Đây là thứ để lần ngược từ TỜ GIẤY về đúng lượt việc trong sổ: mã phiếu thôi thì chỉ tới được
    phiếu, không biết tờ này in ra sau lượt nào và là bản in thứ mấy.
    ⚠ LẦN IN = count_print + 1: cd_loans.count_print là số lần ĐÃ in, còn nút IN tăng nó lên SAU khi
    trang đã dựng xong ⇒ tờ đang chuẩn bị ra là lần kế tiếp. Bấm in hai lần trên cùng một trang thì
    hai tờ mang cùng số; mở lại trang mới ra số mới.
    ⚠ Chỉ bỏ tiền tố 'KH2'; mã đời cũ 'CU…' giữ nguyên vì không có tiền tố đó.
    """
    ma = str(p.get("sku") or "").strip()
    if ma.upper().startswith("KH2"):
        ma = ma[3:]
    return "%s-%s-%s-%02d" % (ma, p.get("id") or 0, (phien or {}).get("log_id") or 0,
                              int(p.get("count_print") or 0) + 1)


def _tom_tat_giao_dich(phien):
    """Ba dòng tóm tắt lượt việc trên cuống (Giám đốc chốt 17/09/2026):

        Trả bớt: 7.000.000 ₫        ← Gia hạn thì in "+30 ngày" thay cho số tiền
        Số ngày cầm: 1 ngày
        Tiền lời: 11.000 ₫

    Nghiệp vụ ngoài danh sách OP_CO_TOM_TAT → KHÔNG in dòng nào (khối rỗng, template bỏ qua).
    """
    if not phien or phien.get("op") not in OP_CO_TOM_TAT:
        return []
    op = phien["op"]
    if op == 4:
        dau = "%s: +%d ngày" % (phien["nghiep_vu"], phien.get("gia_han") or 0)
    else:
        dau = "%s: %s ₫" % (phien["nghiep_vu"], _vnd(abs(phien.get("doi_goc") or 0)))
    return [dau,
            "Số ngày cầm: %d ngày" % (phien.get("ngay") or 0),
            "Tiền lời: %s ₫" % _vnd(phien.get("lai") or 0)]


def _noi_dung(ctx, layout):
    """Chữ đổ vào từng khối. Trả dict key → danh sách DÒNG (không có HTML, template tự thoát)."""
    p, kh, items = ctx["loan"], ctx["customer"] or {}, ctx["items"]
    ct = {**G.CT_MAC_DINH, **(layout.get(G.CT_KEY) or {})}
    phien = ctx.get("phien") if "phien" in ctx else _phien(ctx)
    mon = _mon(ctx, layout)
    tien = p["original_principal"] if ct.get("tien") != "du_hien_tai" else p["principal_balance"]
    mo, den = parse_date(p["opened_at"]), parse_date(p["due_at"])
    ten = kh.get("name") or ""
    # Giám đốc chốt 17/09/2026: ô "Nhận của Ông/Bà" mang thêm SĐT đã che 4 số giữa.
    che = _che_sdt(kh.get("phone") or p.get("phone"))
    ten_sdt = (ten + " | " + che) if (ten and che) else (ten or che)
    ma_theo_doi = _ma_theo_doi(p, phien)

    return {
        # Ba ô này in CÙNG một mã truy vết (Giám đốc chốt 17/09/2026) — trước đây in mã phiếu trần.
        "so_cuong_1": [ma_theo_doi],
        "so_cuong_2": [ma_theo_doi],
        "cuong_chi_tiet": _tom_tat_giao_dich(phien),
        "ma_phieu": [p["sku"]],
        "khach_ten": [ten_sdt],
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
        # Giám đốc chốt 17/09/2026: ô này là DẤU TÊN TIỆM cố định, không còn là trạng thái phiếu.
        # ⚠ Hệ quả: dòng "BÁO MẤT BIÊN NHẬN" không còn xuất hiện trên tờ in — phiếu báo mất nay chỉ
        # nhận biết trong hệ thống. Vẫn TẮT SẴN như trước; bật ở trang cấu hình nếu muốn đóng dấu.
        "trang_thai": [TEN_TIEM],
        # Cũng là mã truy vết như hai ô cuống (Giám đốc chốt 17/09/2026) — trước in "CCCD <số>".
        # Bỏ in CCCD lên giấy cũng là bớt một chỗ phát tán giấy tờ tuỳ thân của khách.
        "giay_to": [ma_theo_doi],
    }


def _anh(ctx, layout):
    """Khối ẢNH → data URI. Hôm nay chỉ có mã vạch Số biên nhận.

    Khối đang TẮT thì KHÔNG vẽ: dựng ảnh tốn vài ms và cả bộ nhớ, không việc gì phải trả giá cho
    một khối mà CSS sẽ display:none ngay sau đó.
    """
    if layout[G.KHOI_MA_VACH].get("an"):
        return {}
    return {G.KHOI_MA_VACH: MV.anh_ma_vach(ctx["loan"]["sku"])}


def _khoi(ctx, layout):
    """20 khối theo đúng thứ tự BLOCKS — template lặp danh sách này nên DOM luôn đủ data-gcd.

    Ba loại khối: CHỮ (`dong`) · ẢNH mã vạch (`anh`) · BẢNG cuống (`bang`). Template chọn theo
    đúng thứ tự đó, đừng đoán theo tên khoá.
    """
    noi = _noi_dung(ctx, layout)
    anh = _anh(ctx, layout)
    bang = _bang(ctx, layout)
    ra, tran = [], []
    for b in G.BLOCKS:
        dong = [d for d in noi.get(b["key"], []) if d not in (None, "")]
        bac, qua = G.bac_co_chu(" ".join(dong), b["key"], layout)
        if qua:
            tran.append(b["ten"])
        ra.append(dict(key=b["key"], ten=b["ten"], dong=dong, anh=anh.get(b["key"], ""),
                       bang=bang.get(b["key"]),
                       cls="gcd-co-%d" % bac, an=bool(layout[b["key"]].get("an"))))
    return ra, tran


def _vach_hep(ctx, layout):
    """Bề rộng vạch hẹp (mm) của mã vạch trên tờ giấy THẬT, hoặc 0 nếu tờ này không in mã vạch.

    Vì sao phải đo LÚC IN chứ không đo một lần lúc cấu hình: con số này phụ thuộc ĐỘ DÀI mã phiếu.
    Mã KH2 hiện hành có 11 chữ số, nhưng README ghi rõ "giữ nguyên mã lịch sử" — phiếu cũ có thể
    dài hơn, và mỗi 2 chữ số thêm vào làm vạch mỏng đi ~8%. Mỏng quá ngưỡng thì máy quét CÂM MÀ
    KHÔNG BÁO GÌ, nhân viên chỉ thấy "quét không ra" và tưởng máy quét hỏng.
    Nhân thêm _in.ty_le: thu nhỏ cả tờ giấy là thu nhỏ luôn mã vạch.
    """
    if layout[G.KHOI_MA_VACH].get("an"):
        return 0.0
    inn = {**G.IN_MAC_DINH, **(layout.get(G.IN_KEY) or {})}
    rong = float(layout[G.KHOI_MA_VACH]["w"]) * float(inn["ty_le"]) / 100.0
    return MV.vach_hep_mm(ctx["loan"]["sku"], rong, G.kho_giay(layout)[0])


def _css_url(nen):
    return url_for("gcd.mau_in_css", **({"nen": 1} if nen else {}))


PHIEU_DONG = {"REDEEMED": "Phiếu đã CHUỘC ĐỒ", "LIQUIDATED": "Phiếu đã THANH LÝ"}


def _khoa_in(p):
    """Lý do KHÔNG cho in giấy cầm đồ; chuỗi rỗng = được in.

    Chuộc đồ · Thanh lý · Báo mất không cần in giấy (GĐ chốt 17/09/2026). Xét TRẠNG THÁI PHIẾU
    chứ không xét lượt gần nhất của _phien: _phien bỏ qua op 8, nên sau khi MỞ KHÓA báo mất lượt
    gần nhất vẫn là op 7 — mà phiếu đã mở khóa thì phải in lại được. lost_locked đã tính đúng việc đó.
    """
    if p.get("loan_state") in PHIEU_DONG:
        return PHIEU_DONG[p["loan_state"]] + " — không cần in giấy."
    if live.lost_locked(p):
        return "Phiếu đang KHÓA BÁO MẤT — mở khóa báo mất rồi mới in lại được."
    return ""


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
    # Hai mức, xem ma_vach: dưới mức tối thiểu là dải ĐỎ phải sửa; nằm giữa là dòng XÁM nhắc quét thử.
    vach = _vach_hep(ctx, layout)
    return render_template(
        "loan_print_gcd.html", title=p["sku"] + " · Giấy cầm đồ", loan=p, customer=ctx["customer"],
        khoi=khoi, tran=tran, mep=G.khoi_sat_mep(layout), nen=nen, thuoc=thuoc, nguon=nguon,
        vach_mm=("%.3f" % vach).replace(".", ","),
        vach_hep=bool(vach and vach < MV.VACH_HEP_TOI_THIEU_MM),
        vach_thu=bool(vach and MV.VACH_HEP_TOI_THIEU_MM <= vach < MV.VACH_HEP_CAN_THU_MM),
        vach_toi_thieu=str(MV.VACH_HEP_TOI_THIEU_MM).replace(".", ","),
        vach_can_thu=str(MV.VACH_HEP_CAN_THU_MM).replace(".", ","),
        inn=inn, ct=ct, may_tt=may_tt, pdf=pdf, khoa_in=_khoa_in(p),
        lech_tien=lech_tien, goc=_vnd(p["original_principal"]), du=_vnd(p["principal_balance"]),
        warning=ctx["warning"], css_url=css_url, css_tinh_url=css_tinh_url,
        print_count_url=None if pdf else url_for("live.print_count", lid=lid),
        may_url=None if pdf else url_for("gcd.in_may_chu", lid=lid),
        print_url=None if pdf else url_for("gcd.giay", lid=lid),
        detail_url=None if pdf else url_for("live.print_receipt", lid=lid))


@bp.get("/bien-nhan/<int:lid>/giay")
def giay(lid):
    # 1) Phiếu + khách + món TRƯỚC — KỂ CẢ sổ phiên cho bảng cuống: mọi truy vấn khj_cd phải
    #    xong TRƯỚC lượt đọc chéo khj_bl ở bước 2. Đọc chéo mà làm hỏng connection dùng chung thì
    #    câu SELECT nào chạy sau cũng chết, và bảng cuống sẽ mất nghiệp vụ/giờ mà không ai biết.
    ctx = live.receipt_context(lid)
    ctx["phien"] = _phien(ctx)
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


@bp.get("/bien-nhan/<int:lid>/giay-manh")
def giay_manh(lid):
    """MẢNH tờ GCD để IN THẲNG TẠI QUẦY (cách của BÁN LẺ: nhét tờ vào trang đang mở rồi window.print()
    từ chính cửa sổ đó; máy quầy chạy Edge --kiosk-printing nên không có hộp thoại, không chuyển trang).

    Dựng bằng ĐÚNG _dung_trang() rồi cắt lấy <section class="gcd-a5"> — vẫn MỘT BẢN VẼ với trang in và
    bản PDF, không có template thứ hai để trôi. Phiếu bị khóa in → 423 JSON để trang quầy báo lý do.
    Không có ảnh nền, không thước: mảnh này chỉ có CHỮ + MÃ VẠCH như bản in thật."""
    ctx = live.receipt_context(lid)
    khoa = _khoa_in(ctx["loan"])
    if khoa:
        return {"ok": False, "khoa": True, "ly_do": khoa}, 423
    ctx["phien"] = _phien(ctx)
    layout, nguon = G.doc_bo_cuc()
    html = _dung_trang(ctx, layout, nguon, nen=False, thuoc=False, may_tt=None, lid=lid,
                       css_url=_css_url(False), css_tinh_url=url_for("static", filename="gcd-print.css") + "?v=1")
    m = re.search(r'<section class="gcd-a5" id="gcd-to">.*?</section>', html, re.S)
    if not m:
        return {"ok": False, "ly_do": "Không dựng được tờ giấy cầm đồ."}, 500
    res = Response(m.group(0), content_type="text/html; charset=utf-8")
    res.headers["X-KHCD-Bo-Cuc"] = nguon
    return res


@bp.post("/bien-nhan/<int:lid>/in-may-chu")
def in_may_chu(lid):
    """In thẳng tới máy in đã lưu trong cấu hình. LUÔN trả JSON 200, KHÔNG BAO GIỜ trả lỗi.

    {"ok":true,"thong_diep":"Đã gửi tới …"}  hoặc  {"ok":false,"ly_do":"…"} — ly_do là câu giải
    thích ngắn để trang nói một dòng rồi mở hộp thoại in của trình duyệt. Người dùng luôn in được;
    khác biệt duy nhất là có phải tự chọn máy in hay không, nên đây KHÔNG phải trạng thái lỗi.
    """
    # Thứ tự bắt buộc: mọi truy vấn khj_cd (phiếu + khách + món + sổ phiên) TRƯỚC, bố cục (đọc
    # chéo khj_bl) CUỐI CÙNG.
    ctx = live.receipt_context(lid)
    khoa = _khoa_in(ctx["loan"])
    if khoa:
        # Nút IN đã tắt trên trang; chặn cả ở đây để POST gõ tay cũng không làm hỏng tờ giấy in sẵn.
        return {"ok": False, "khoa": True, "ly_do": khoa}
    ctx["phien"] = _phien(ctx)
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
