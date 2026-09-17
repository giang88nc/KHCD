# -*- coding: utf-8 -*-
"""
ma_vach — MÃ VẠCH CODE 39 CHO SỐ BIÊN NHẬN TRÊN GIẤY CẦM ĐỒ (KHCD in thật).

BẢN SAO NGUYÊN VĂN THUẬT TOÁN CỦA KHBL — KHÔNG ĐƯỢC SỬA MỘT KÝ TỰ.
    Gốc: D:/PYTHON/KHBL/apps/pos/ma_vach.py   (hằng CODE39 · hàm so_ma_vach · hàm png_code39)
Thuật toán này đang in mã vạch của GIẤY ĐẢM BẢO và ĐÃ QUÉT ĐƯỢC ngoài thực tế. Chép thay vì viết
lại: một Code 39 tự chế sai tỷ lệ vạch rộng/hẹp vẫn "nhìn như mã vạch" mà máy quét không đọc nổi,
và lỗi đó chỉ lộ ra khi khách đã cầm tờ giấy về nhà.

NẾP ĐÃ CÓ TIỀN LỆ TRONG NHÀ: KHJ apps/common/anh_cccd.py là bản sao byte-identical của KHBL
apps/pos/anh_cccd.py, kèm bài kiểm so sha256. Ở đây làm y vậy — đoạn nằm giữa hai mốc
MOC_BAT_DAU / MOC_KET_THUC dưới đây phải băm ra ĐÚNG sha256 của vùng tương ứng bên KHBL, và
tests/test_gcd_ma_vach.py FAIL ngay khi lệch một ký tự.
    SỬA THUẬT TOÁN = sửa bên KHBL trước, rồi chép lại nguyên vùng sang đây. Không sửa tại đây.
    Sinh lại vùng này: lấy tệp KHBL từ 'CODE39 = {' tới dòng mốc HẾT VÙNG SAO CHÉP (KHBL đặt
    cùng câu mốc), dán vào giữa hai mốc ở đây.

⚠ HAI TỆP KHÁC KIỂU XUỐNG DÒNG (KHBL lưu LF, KHCD lưu CRLF) nên bài kiểm đọc cả hai ở CHẾ ĐỘ VĂN
BẢN (universal newline) rồi mới băm — cái buộc phải giống nhau là KÝ TỰ, không phải byte thô.

HỢP ĐỒNG HAI BÊN: KHBL vẽ mã vạch cho bản XEM TRƯỚC ở trang cấu hình, KHCD vẽ cho tờ IN THẬT.
Cùng một mã phiếu thì hai bên phải ra CÙNG MỘT chuỗi data URI — nếu không thì Giám đốc căn một
đằng, máy in ra một nẻo (đúng kiểu lỗi font/line-height đã làm lệch 9 mm ở lượt trước).

VÌ SAO LÀ ẢNH PNG CHỨ KHÔNG PHẢI DIV/CSS: vạch vẽ bằng div sẽ bị trình duyệt co về lưới pixel lúc
in, vạch hẹp thành mờ hoặc mất hẳn và máy quét chịu. Ảnh 1-bit đen/trắng thì mỗi vạch là một khối
pixel đặc, in ra ĐEN ĐẬM.

VÌ SAO KHÔNG DÙNG background-image: bản in GCD cố ý KHÔNG có print-color-adjust (xem
static/gcd-print.css) nên mọi thứ vẽ bằng background sẽ bị trình duyệt bỏ khi in ⇒ mã vạch bắt
buộc phải là thẻ <img> thật trong DOM.
"""
import base64
import re
from io import BytesIO

# ═══ BẮT ĐẦU VÙNG SAO CHÉP — KHÔNG SỬA MỘT KÝ TỰ ═══
CODE39 = {
    "0": "nnnwwnwnn", "1": "wnnwnnnnw", "2": "nnwwnnnnw", "3": "wnwwnnnnn",
    "4": "nnnwwnnnw", "5": "wnnwwnnnn", "6": "nnwwwnnnn", "7": "nnnwnnwnw",
    "8": "wnnwnnwnn", "9": "nnwwnnwnn", "-": "nnnwnnnww", "*": "nwnnwnwnn",
}


def so_ma_vach(ma):
    """SỐ mà mã vạch mang theo = BỎ mọi ký tự không phải chữ số, GIỮ NGUYÊN thứ tự, KHÔNG rút gọn.

    MÃ PHIẾU THẬT ĐANG CHẠY — đếm trên sổ KHCD ngày 16/09/2026, 25.465 mã khác nhau:
        'KH22609020810'   → '22609020810'    11 chữ số · 18.854 mã — đường cầm đồ hằng ngày
        'CU2606000000625' → '2606000000625'  13 chữ số ·  6.594 mã — phiếu chuyển từ hệ cũ
      lác đác vài mã 9 / 10 / 12 chữ số. Bản xem trước bên KHBL dùng mã GIẢ 'CD26090100012' (11 số,
      đúng độ dài thường gặp) — đừng đọc 'CD…' thành tiền tố thật.

    ⚠ ĐÂY LÀ HỢP ĐỒNG GIỮA KHBL VÀ KHCD. Hai bên phải sinh RA ĐÚNG MỘT chuỗi cho cùng một mã phiếu,
    nếu không thì bản xem trước một đằng, tờ in ra một nẻo.

    VÌ SAO BỎ CHỮ CÁI chứ không mã hoá chúng: bảng `CODE39` ở trên chỉ có chữ số (bản chép nguyên đã
    quét được thực tế), thêm A-Z vào là ĐỘNG VÀO THUẬT TOÁN ĐANG CHẠY THẬT của Giấy đảm bảo.
    VÌ SAO KHÔNG RÚT GỌN 9 số như `_ma_gdb()` của Giấy đảm bảo: mã cầm đồ dài 11–13 chữ số, cắt còn
    9 là VỨT BỎ thông tin ⇒ hai phiếu khác nhau có thể ra cùng một mã vạch. Chứng từ cầm đồ là giấy
    tờ pháp lý, quét nhầm phiếu là trả nhầm hàng.

    TRA NGƯỢC VỀ ĐÚNG PHIẾU: bỏ chữ cái xong vẫn phải còn DUY NHẤT. Cách tra an toàn bên KHCD là so
    theo PHẦN SỐ chứ đừng ghép chuỗi tiền tố + số:
        ... WHERE REPLACE(...) -- hoặc lọc trong Python: so_ma_vach(row.sku) == so_quet_duoc
    ⚠ ĐIỀU KIỆN PHẢI GIỮ: PHẦN SỐ của mọi mã phiếu không được trùng nhau. Kho hiện có HAI tiền tố
    ('KH…' và 'CU…') chứ không phải một — đã soát cả 25.465 mã: bỏ chữ cái rồi KHÔNG còn cặp nào
    trùng (hai nhóm khác độ dài). Ngày nào sinh thêm loại mã mà phần số đụng mã đang có (ví dụ
    'GH22609020810' cho gia hạn) thì hai tờ giấy mang CÙNG một mã vạch — lúc đó phải đổi sang mã
    vạch có chữ cái, không vá bằng cách đoán tiền tố.
    ⚠ NHÓM 'CU…' 13 số là nhóm SÁT NGƯỠNG nhất: với bề rộng khối mặc định, vạch hẹp chỉ còn
    ≈ 0,152 mm — nhỉnh hơn ngưỡng đỏ 0,15 mm một chút (xem `canh_bao_vach`). Quét thử một tờ 'CU…'
    trước khi in loạt.
    """
    return re.sub(r"\D", "", str(ma or ""))


def png_code39(code):
    """PNG Code 39 chuẩn, có start/stop và quiet-zone cho máy quét mã vạch.

    Không dùng các ``div`` CSS để browser không co vạch lẻ thành pixel mờ khi in.

    Đầu vào rỗng / không có chữ số nào → vẽ mã của số '0' (ảnh hợp lệ, KHÔNG ném lỗi): trang xem
    trước và trang in không bao giờ được chết chỉ vì một phiếu thiếu mã.
    """
    from PIL import Image, ImageDraw

    value = re.sub(r"[^0-9]", "", str(code or "")) or "0"
    chars = "*" + value + "*"
    narrow, wide, quiet, height = 4, 12, 40, 96
    widths = []
    for pos, char in enumerate(chars):
        widths.extend(wide if unit == "w" else narrow for unit in CODE39[char])
        if pos < len(chars) - 1:
            widths.append(narrow)  # khoảng cách chuẩn giữa hai ký tự Code 39
    image = Image.new("1", (quiet * 2 + sum(widths), height), 1)
    draw, cursor = ImageDraw.Draw(image), quiet
    for pos, char in enumerate(chars):
        for index, unit in enumerate(CODE39[char]):
            width = wide if unit == "w" else narrow
            if index % 2 == 0:
                draw.rectangle((cursor, 0, cursor + width - 1, height - 1), fill=0)
            cursor += width
        if pos < len(chars) - 1:
            cursor += narrow
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=False)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def svg_qr(noi_dung):
    """QR (SVG data URI) của MÃ PHIẾU, in trên cuống tiệm giữ của Giấy cầm đồ.

    SVG chứ không PNG: cuống chỉ rộng ~55mm nên ô QR chỉ quanh 17mm — PNG ở cỡ đó bị trình duyệt
    nội suy thành mép xám lúc in, máy quét 2D đọc chậm hẳn. SVG là vector, máy in rasterise ở đúng
    DPI của nó. Đây cũng là nếp ĐÃ CHẠY THẬT của phiếu đặt cọc (apps/pos/deposit_print_config.py).

    ⚠ KHÁC mã vạch Code 39 ở một điểm QUAN TRỌNG: QR mang NGUYÊN mã phiếu KỂ CẢ CHỮ CÁI
    (`KH22609020810`), không phải chỉ phần chữ số. Bảng CODE39 ở trên chỉ có chữ số nên mã vạch
    buộc phải bỏ tiền tố và tra ngược theo PHẦN SỐ; QR thì quét ra đúng mã phiếu, khỏi suy đoán
    tiền tố — hai thứ bổ cho nhau chứ không thay nhau.

    Đầu vào rỗng → trả '' (KHÔNG vẽ QR của chuỗi rỗng). Khác hẳn png_code39 vốn cố ý vẽ mã số 0 để
    trang in không bao giờ chết: QR rỗng quét ra rỗng, nhân viên sẽ tưởng máy quét hỏng và loay
    hoay với cái máy thay vì nhìn ra tờ phiếu thiếu mã.
    """
    ma = str(noi_dung or "").strip()
    if not ma:
        return ""
    import segno

    return segno.make(ma, micro=False).svg_data_uri()
# ═══ HẾT VÙNG SAO CHÉP ═══


# ══════════════════════════════════════════════════════════════════════════════════════════════
# LỚP DÙNG CỦA KHCD — phần dưới đây là mã RIÊNG, KHÔNG nằm trong vùng đối chiếu sha256.
# ══════════════════════════════════════════════════════════════════════════════════════════════
MA_NGUON_KHBL = 'D:/PYTHON/KHBL/apps/pos/ma_vach.py'
VUNG_TU = 'CODE39 = {'                  # mốc MỞ vùng sao chép bên KHBL (đóng bằng MOC_KET_THUC)
MOC_BAT_DAU = '# \u2550\u2550\u2550 B\u1eaeT \u0110\u1ea6U V\u00d9NG SAO CH\u00c9P \u2014 KH\u00d4NG S\u1eecA M\u1ed8T K\u00dd T\u1ef0 \u2550\u2550\u2550'
MOC_KET_THUC = '# \u2550\u2550\u2550 H\u1ebeT V\u00d9NG SAO CH\u00c9P \u2550\u2550\u2550'

# Ảnh mã vạch do png_code39() vẽ: bề rộng tính bằng MÔ-ĐUN HẸP (vạch hẹp = 1 mô-đun).
# Một ký tự Code 39 = 3 vạch rộng + 6 vạch hẹp = 3*3 + 6 = 15 mô-đun, cộng 1 mô-đun ngăn cách.
MO_DUN_MOI_KY_TU = 16
MO_DUN_QUIET = 10                       # quiet-zone hai bên: 40 px / (vạch hẹp 4 px) = 10 mô-đun
# HAI NGƯỠNG, CỐ Ý KHÔNG GỘP LÀM MỘT — mã câm thì nhân viên chỉ thấy "quét không ra" và tưởng máy
# quét hỏng, nên trang xem trước phải nói trước; nhưng kêu ĐỎ trên đường chạy hằng ngày thì vài hôm
# là không ai đọc dải cảnh báo nào nữa, kể cả dải báo lệch tiền.
#   · 0,19 mm (7,5 mil) = mức THOẢI MÁI của máy quét CCD/laser cầm tay. Dưới mức này vẫn thường đọc
#     được, nhưng PHẢI QUÉT THỬ THẬT → một dòng XÁM nhắc việc, không phải báo động.
#   · 0,15 mm (6 mil) = mức máy quét quầy phổ thông bắt đầu chịu thua → dải ĐỎ, phải sửa trước khi in.
# Bố cục KHBL chốt hôm nay (rộng 18,8% trên tờ 210 mm, mã 11 số) cho vạch hẹp ≈ 0,174 mm: NẰM GIỮA
# hai ngưỡng ⇒ chạy bình thường, kèm dòng xám nhắc quét thử. Đó là trạng thái ĐÚNG NHƯ THIẾT KẾ,
# không phải lỗi — bề rộng đã là trần cứng của tờ giấy in sẵn (xem gcd_layout.BLOCKS).
VACH_HEP_CAN_THU_MM = 0.19
VACH_HEP_TOI_THIEU_MM = 0.15


def vung_sao_chep(duong=None):
    """Trả ĐÚNG đoạn mã đã chép (không gồm hai dòng mốc), đọc ở chế độ văn bản.

    duong=None                        → chính tệp này.
    duong=<KHBL/apps/pos/ma_vach.py>  → bóc vùng tương ứng bên kia: từ VUNG_TU tới dòng mốc
                                        MOC_KET_THUC (KHBL dùng ĐÚNG câu mốc đó).
    Bài kiểm băm sha256 hai chuỗi rồi so: lệch nghĩa là hai bên đã trôi khỏi nhau.

    ⚠ TRƯỚC 16/09/2026 vùng bên KHBL được lấy "tới HẾT TỆP" — nghĩa là KHBL viết thêm bất cứ hàm
    nào ở cuối tệp (ví dụ lớp đo bề rộng vạch) là bài kiểm này đỏ dù thuật toán không đổi một chữ.
    Nay KHBL đã đặt dòng mốc kết thúc y hệt bên này; không thấy mốc thì vẫn lấy tới hết tệp để
    bản KHBL cũ chưa kịp cập nhật vẫn so được.
    """
    import io
    import os
    if duong and os.path.normcase(os.path.abspath(duong)) != os.path.normcase(os.path.abspath(__file__)):
        s = io.open(duong, encoding='utf-8').read()
        return s[s.index(VUNG_TU):].split('\n' + MOC_KET_THUC, 1)[0].rstrip('\n')
    s = io.open(__file__, encoding='utf-8').read()
    return s.split(MOC_BAT_DAU + '\n', 1)[1].split('\n' + MOC_KET_THUC, 1)[0]


def van_tay(duong=None):
    """sha256 của vùng sao chép — con số bài kiểm đem đối chiếu hai bên."""
    import hashlib
    return hashlib.sha256(vung_sao_chep(duong).encode('utf-8')).hexdigest()


def anh_ma_vach(ma_phieu):
    """Mã phiếu → data URI PNG Code 39; '' nếu mã không có chữ số nào hoặc dựng ảnh hụt.

    ⚠ KHÔNG tự chế chuỗi số ở đây: dùng so_ma_vach() của vùng sao chép, đó là HỢP ĐỒNG với KHBL.

    Trả '' thay vì ảnh rác khi mã không có chữ số: png_code39() gặp chuỗi rỗng sẽ vẽ mã vạch của
    số 0 — tức là IN RA MỘT MÃ VẠCH SAI lên chứng từ, tệ hơn hẳn việc không in vạch nào (template
    tự bỏ khối). Hành vi vẽ-số-0 của KHBL vẫn GIỮ NGUYÊN trong vùng sao chép, đây chỉ là lớp quyết
    định CÓ VẼ HAY KHÔNG, nên hai bên vẫn ra cùng một data URI với mọi mã phiếu thật.
    Mọi lỗi dựng ảnh (thiếu Pillow, hết bộ nhớ…) cũng nuốt tại chỗ: MẤT MÃ VẠCH CÒN HƠN MẤT TỜ
    PHIẾU — cùng nguyên tắc với gcd_layout, không đường nào được ném lỗi lên trang in.
    """
    so = so_ma_vach(ma_phieu)
    if not so:
        return ''
    try:
        return png_code39(so)
    except Exception:
        return ''


def vach_hep_mm(ma_phieu, rong_phan_tram, giay_rong_mm):
    """Bề rộng VẠCH HẸP (mm) khi ảnh mã vạch bị kéo cho vừa khối rộng `rong_phan_tram` %.

    Đây là con số quyết định mã có quét được hay không, và nó THAY ĐỔI THEO ĐỘ DÀI MÃ PHIẾU: cùng
    một khối 24,5% mà mã dài thêm 2 chữ số là vạch hẹp mỏng đi ~8%. Mã phiếu lịch sử (giữ nguyên
    theo README) có thể dài hơn mã KH2 hiện hành ⇒ phải đo theo TỪNG PHIẾU, không phải đo một lần.
    Trả 0.0 khi không có mã vạch (khỏi phải báo động cho tờ không in vạch).
    """
    so = so_ma_vach(ma_phieu)
    if not so:
        return 0.0
    mo_dun = MO_DUN_QUIET * 2 + (len(so) + 2) * MO_DUN_MOI_KY_TU - 1   # +2 = start/stop '*'
    return float(rong_phan_tram) / 100.0 * float(giay_rong_mm) / mo_dun
