"""MÃ VẠCH Code 39 của SỐ BIÊN NHẬN trên Giấy cầm đồ — bản sao thuật toán, ảnh sinh ra, và tờ in.

CHẠY: chỉ đích danh tệp này, KHÔNG BAO GIỜ chạy cả bộ và không dùng discover.
    .venv\\Scripts\\python.exe -m pytest tests/test_gcd_ma_vach.py -q
Nhóm bài thuần hàm (vân tay · giải mã ảnh · hợp đồng số · bố cục · CSS) chạy KHÔNG CẦN CSDL.
Nhóm bài web tự BỎ QUA nếu chưa đặt KHCD_TEST_ENV (conftest tạo CSDL nháp rồi xoá).

BA THỨ TỆP NÀY CANH GIỮ, theo đúng thứ tự quan trọng:
  1. THUẬT TOÁN KHÔNG ĐƯỢC TRÔI KHỎI KHBL — so sha256 vùng sao chép (nếp anh_cccd.py của KHJ).
  2. ẢNH SINH RA PHẢI QUÉT ĐƯỢC — tệp này có bộ GIẢI MÃ Code 39 riêng, đọc ngược ảnh PNG ra chuỗi
     số. So mã nguồn thôi thì chưa đủ: chép đúng chữ mà Pillow đổi hành vi là mã vẫn câm.
  3. HAI BÊN KHỚP NHAU — khối `ma_phieu_vach` (key · thứ tự · số đo) và chuỗi CSS_ANH phải giống
     hệt bản KHBL. Lượt trước font và line-height lệch nhau đã làm chữ lệch tới 9 mm.
"""
import base64
import io
import json
import os
import re

import pytest

from khcd import gcd_layout as G, ma_vach as MV


KHBL_MA_VACH = r'D:\PYTHON\KHBL\apps\pos\ma_vach.py'
KHBL_GCD_LAYOUT = r'D:\PYTHON\KHBL\apps\pos\gcd_layout.py'
MA_THAT = 'KH22609000123'          # mã phiếu KH2 hiện hành: KH2 + yymm + 6 số
SO_THAT = '22609000123'            # phần chữ số của nó — 11 số


# ── 1. VÂN TAY THUẬT TOÁN: BẢN SAO KHÔNG ĐƯỢC TRÔI KHỎI KHBL ─────────────────────────────────
@pytest.mark.skipif(not os.path.exists(KHBL_MA_VACH), reason='Chưa có bản gốc bên KHBL.')
def test_van_tay_thuat_toan_khop_khbl():
    """sha256 vùng sao chép hai bên phải BẰNG NHAU.

    Đọc cả hai ở CHẾ ĐỘ VĂN BẢN: KHBL lưu LF còn KHCD lưu CRLF, cái buộc phải giống nhau là KÝ TỰ
    chứ không phải byte thô. Lệch ⇒ ai đó đã sửa thuật toán một bên: sửa bên KHBL rồi CHÉP LẠI.
    """
    assert MV.van_tay() == MV.van_tay(KHBL_MA_VACH), (
        'Thuật toán mã vạch KHCD đã trôi khỏi KHBL. Chép lại vùng giữa hai mốc trong khcd/ma_vach.py '
        'từ %s (lấy từ "CODE39 = {" tới hết tệp).' % KHBL_MA_VACH)


def test_vung_sao_chep_boc_dung_doan():
    """Mốc bóc vùng phải cắt đúng chỗ — hỏng mốc thì bài kiểm trên so nhầm hai chuỗi rỗng."""
    vung = MV.vung_sao_chep()
    assert vung.startswith('CODE39 = {')
    assert 'def so_ma_vach(' in vung and 'def png_code39(' in vung
    assert MV.MOC_BAT_DAU not in vung and MV.MOC_KET_THUC not in vung
    assert 'def anh_ma_vach(' not in vung      # lớp riêng của KHCD phải NẰM NGOÀI vùng đối chiếu
    assert len(vung) > 1000


def test_van_tay_bat_duoc_sua_doi(tmp_path):
    """Đổi MỘT ký tự trong bản gốc là vân tay phải khác ngay — nếu không, bài kiểm số 1 vô dụng."""
    gia = tmp_path / 'ma_vach_gia.py'
    goc = io.open(KHBL_MA_VACH, encoding='utf-8').read() if os.path.exists(KHBL_MA_VACH) else (
        'CODE39 = {"0": "nnnwwnwnn"}\n')
    gia.write_text(goc.replace('narrow, wide, quiet, height = 4, 12, 40, 96',
                               'narrow, wide, quiet, height = 3, 12, 40, 96'), encoding='utf-8')
    assert MV.van_tay(str(gia)) != MV.van_tay()


# ── 2. BẢNG MÃ CODE 39 ───────────────────────────────────────────────────────────────────────
def test_bang_ma_dung_hinh_dang():
    """Mỗi ký tự Code 39 = 9 phần tử, đúng 3 phần tử RỘNG. Sai là mã không hợp lệ."""
    assert set(MV.CODE39) == set('0123456789-*')
    for ky_tu, vach in MV.CODE39.items():
        assert len(vach) == 9, ky_tu
        assert vach.count('w') == 3, ky_tu
        assert set(vach) <= {'n', 'w'}, ky_tu
    assert len(set(MV.CODE39.values())) == len(MV.CODE39)     # không ký tự nào trùng mẫu vạch


# ── 3. GIẢI MÃ NGƯỢC ẢNH PNG — BẰNG CHỨNG MÃ QUÉT ĐƯỢC ───────────────────────────────────────
BANG_NGUOC = {v: k for k, v in MV.CODE39.items()}


def _mo_anh(uri):
    from PIL import Image
    assert uri.startswith('data:image/png;base64,')
    return Image.open(io.BytesIO(base64.b64decode(uri.split(',', 1)[1])))


def _chuoi_vach(im):
    """Đọc một hàng pixel giữa ảnh → danh sách (màu, số pixel liên tiếp)."""
    px, (w, h) = im.load(), im.size
    hang, ra, mau, dem = [px[x, h // 2] for x in range(w)], [], None, 0
    for v in hang:
        if v == mau:
            dem += 1
        else:
            if mau is not None:
                ra.append((mau, dem))
            mau, dem = v, 1
    ra.append((mau, dem))
    return ra


def _giai_ma(uri):
    """Bộ GIẢI MÃ Code 39 độc lập: ảnh PNG → chuỗi ký tự kể cả start/stop '*'.

    Cố ý KHÔNG dùng lại hằng nào của thuật toán ngoài bảng mã: nếu bài kiểm suy ngược bằng chính
    những con số của thuật toán thì nó chỉ đang tự soi gương.
    """
    vach = _chuoi_vach(_mo_anh(uri))
    giua = vach[1:-1]                                   # bỏ quiet-zone hai đầu
    hep = min(n for _, n in giua)
    bits = ''.join('w' if n > hep * 2 else 'n' for _, n in giua)
    ra = ''
    for i in range(0, len(bits), 10):                   # 9 phần tử + 1 khoảng ngăn cách
        ra += BANG_NGUOC[bits[i:i + 9]]
    return ra


@pytest.mark.parametrize('ma,so', [
    (MA_THAT, SO_THAT),
    ('KH22609999999', '22609999999'),
    ('KH22601000001', '22601000001'),
    ('CD26090100012', '26090100012'),                   # dạng mã ví dụ trong ghi chú của KHBL
    ('CD260915TEST000001', '260915000001'),             # mã lịch sử có chữ xen giữa
    ('0', '0'),
])
def test_giai_ma_nguoc_ra_dung_so(ma, so):
    """Quét ảnh ra phải ĐÚNG chuỗi số của mã phiếu, có start/stop '*' hai đầu."""
    assert _giai_ma(MV.anh_ma_vach(ma)) == '*' + so + '*'


def test_anh_dung_hinh_hoc():
    """Ảnh 1-bit đen/trắng · quiet-zone hai đầu · chỉ hai bề rộng vạch, tỷ lệ RỘNG:HẸP = 3:1."""
    im = _mo_anh(MV.anh_ma_vach(MA_THAT))
    assert im.mode == '1', 'Ảnh phải là 1-bit: vạch xám khi in là máy quét câm.'
    vach = _chuoi_vach(im)
    assert vach[0][0] == 255 and vach[-1][0] == 255, 'Thiếu quiet-zone → máy quét không bắt được mép mã.'
    assert vach[0][1] >= 10 * 4 and vach[-1][1] >= 10 * 4
    be_rong = sorted({n for _, n in vach[1:-1]})
    assert len(be_rong) == 2, 'Chỉ được có vạch HẸP và vạch RỘNG, thấy: %s' % be_rong
    assert be_rong[1] == be_rong[0] * 3, 'Tỷ lệ Code 39 phải là 3:1.'
    assert {m for m, _ in vach} == {0, 255}, 'Phải là ĐEN tuyệt đối trên TRẮNG, không có mức xám.'


def test_so_run_dung_cong_thuc():
    """13 ký tự (11 số + 2 start/stop) × 9 phần tử + 12 khoảng ngăn = 129 vạch giữa quiet-zone."""
    assert len(_chuoi_vach(_mo_anh(MV.anh_ma_vach(MA_THAT)))) - 2 == 13 * 9 + 12


# ── 4. HỢP ĐỒNG "SỐ ĐEM ĐI MÃ HOÁ" ───────────────────────────────────────────────────────────
def test_so_ma_vach_bo_chu_giu_thu_tu():
    assert MV.so_ma_vach(MA_THAT) == SO_THAT
    assert MV.so_ma_vach('CD-2609/01 00012') == '260901' + '00012'
    assert MV.so_ma_vach('') == '' and MV.so_ma_vach(None) == ''
    assert MV.so_ma_vach('ABC') == ''


def test_khong_rut_gon_9_so():
    """Vì sao KHÔNG dùng _ma_gdb() của Giấy đảm bảo: rút 9 số làm HAI PHIẾU KHÁC NHAU TRÙNG MÃ.

    Đây là bài kiểm giữ lại LÝ DO, không phải giữ lại mã: mai mốt ai đó "gọn hoá" cho mã vạch ngắn
    lại là bài này đỏ ngay, kèm ví dụ cụ thể hai phiếu sẽ trùng.
    """
    a, b = 'KH22609000123', 'KH22609001123'
    rut = lambda s: (lambda d: d[:6] + d[-3:])(re.sub(r'\D', '', s))      # noqa: E731 — bản rút gọn
    assert rut(a) == rut(b) == '226090123', 'Ví dụ trong ghi chú đã sai, sửa lại ghi chú.'
    assert MV.so_ma_vach(a) != MV.so_ma_vach(b)
    assert _giai_ma(MV.anh_ma_vach(a)) != _giai_ma(MV.anh_ma_vach(b))


def test_ma_khong_co_chu_so_thi_khong_ve_vach():
    """Mã không có chữ số → '' chứ KHÔNG phải mã vạch của số 0.

    png_code39() bên KHBL cố ý vẽ số 0 để trang xem trước không chết; nhưng in một mã vạch SAI lên
    chứng từ giao khách còn tệ hơn không in vạch nào, nên lớp KHCD chặn ở đây.
    """
    assert MV.anh_ma_vach('') == ''
    assert MV.anh_ma_vach(None) == ''
    assert MV.anh_ma_vach('ABC') == ''
    assert MV.png_code39('') .startswith('data:image/png;base64,')        # bản gốc vẫn giữ nguyên


def test_loi_dung_anh_khong_lam_chet_to_phieu(monkeypatch):
    """Pillow hụt → mất mã vạch, KHÔNG mất tờ phiếu (cùng nguyên tắc với gcd_layout)."""
    monkeypatch.setattr(MV, 'png_code39', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('hết RAM')))
    assert MV.anh_ma_vach(MA_THAT) == ''


def test_cung_dau_vao_cung_data_uri():
    """Hợp đồng với KHBL: cùng mã phiếu ⇒ cùng một chuỗi data URI, không có yếu tố ngẫu nhiên."""
    assert MV.anh_ma_vach(MA_THAT) == MV.anh_ma_vach(MA_THAT) == MV.png_code39(SO_THAT)


# ── 5. BỀ RỘNG VẠCH HẸP — CON SỐ QUYẾT ĐỊNH MÃ CÓ QUÉT ĐƯỢC KHÔNG ────────────────────────────
def test_vach_hep_khop_anh_that():
    """Công thức đếm mô-đun phải khớp SỐ PIXEL THẬT của ảnh — hai cách tính độc lập cho một kết quả."""
    im = _mo_anh(MV.anh_ma_vach(MA_THAT))
    hep_px = min(n for _, n in _chuoi_vach(im)[1:-1])
    mo_dun_theo_anh = im.size[0] / hep_px
    mo_dun_theo_cong_thuc = MV.MO_DUN_QUIET * 2 + (len(SO_THAT) + 2) * MV.MO_DUN_MOI_KY_TU - 1
    assert mo_dun_theo_anh == mo_dun_theo_cong_thuc == 227


def test_vach_hep_mm_theo_kho_khoi():
    """Khối rộng 18,8% trên tờ 210 mm ⇒ vạch hẹp ≈ 0,174 mm = 7 mil.

    Đây là trạng thái ĐÚNG NHƯ THIẾT KẾ: nằm GIỮA hai ngưỡng ⇒ in bình thường, kèm dòng xám nhắc
    quét thử. Bề rộng đã là trần cứng của tờ giấy in sẵn, không nới thêm được.
    """
    mm = MV.vach_hep_mm(MA_THAT, 18.8, 210)
    assert round(mm, 4) == 0.1739
    assert MV.VACH_HEP_TOI_THIEU_MM <= mm < MV.VACH_HEP_CAN_THU_MM
    # Mã dài thêm 4 chữ số là vạch mỏng đi rõ rệt — lý do phải đo theo TỪNG phiếu, không đo một lần.
    assert MV.vach_hep_mm('KH2260900012345', 18.8, 210) < mm
    # Bóp khối hẹp lại là tụt hẳn xuống dưới mức máy quét quầy chịu được.
    assert MV.vach_hep_mm(MA_THAT, 14.2, 210) < MV.VACH_HEP_TOI_THIEU_MM
    assert MV.vach_hep_mm('', 18.8, 210) == 0.0


def test_hai_nguong_khong_gop_lam_mot():
    """Kêu ĐỎ trên đường chạy hằng ngày là vài hôm không ai đọc dải cảnh báo nào nữa."""
    assert MV.VACH_HEP_TOI_THIEU_MM < MV.VACH_HEP_CAN_THU_MM
    mac_dinh = G.mac_dinh()[G.KHOI_MA_VACH]['w']
    assert MV.vach_hep_mm(MA_THAT, mac_dinh, 210) >= MV.VACH_HEP_TOI_THIEU_MM, (
        'Bố cục mặc định KHÔNG được rơi vào dải ĐỎ — dải đỏ là để bắt người ta bóp nhầm khối.')


# ── 6. KHỐI BỐ CỤC PHẢI KHỚP KHBL ────────────────────────────────────────────────────────────
def test_khoi_ma_vach_co_trong_blocks():
    m = G.mac_dinh()
    assert G.KHOI_MA_VACH == 'ma_phieu_vach'
    assert len(G.BLOCKS) == 20
    keys = [b['key'] for b in G.BLOCKS]
    assert keys.index(G.KHOI_MA_VACH) == keys.index('ma_phieu') - 1, 'Mã vạch phải đứng ngay TRƯỚC ô SỐ:'
    assert m[G.KHOI_MA_VACH] == {'left': 77.4, 'top': 5.6, 'w': 18.8, 'h': 6.0, 'fs': 8, 'an': 0}
    assert G.KHOI_MA_VACH not in G.CO_CHU, 'Khối ảnh không có chữ để co.'


def test_khoi_ma_vach_khong_lot_bien_cung():
    """Đỉnh 5,6% của 148 mm ≈ 8,3 mm, đáy 11,6% ≈ 17,2 mm — ngoài biên cứng 6 mm của máy in."""
    assert 'Mã vạch Số biên nhận' not in G.khoi_sat_mep(G.mac_dinh())


def _doc_blocks_khbl(duong):
    """Bóc mặc định từng khối trong mã nguồn KHBL (không import được: module đó cần Django)."""
    s = io.open(duong, encoding='utf-8').read()
    out = {}
    for m in re.finditer(r'"key"\s*:\s*"(\w+)".*?(?="key"|\Z)', s, re.S):
        blob, d = m.group(0), {}
        for k in ('left', 'top', 'w', 'h', 'fs', 'an'):
            g = re.search(r'"%s"\s*:\s*(-?[\d.]+)' % k, blob)
            if g:
                d[k] = float(g.group(1))
        out[m.group(1)] = d
    return out


@pytest.mark.skipif(not os.path.exists(KHBL_GCD_LAYOUT), reason='Chưa có bản song sinh bên KHBL.')
def test_khoi_ma_vach_khop_mac_dinh_khbl():
    """KHBL là nơi GĐ kéo khối, KHCD là nơi in ra giấy. Lệch mặc định thì TRƯỚC lần lưu đầu tiên,
    cái GĐ căn khác cái máy in ra — kiểu lệch âm thầm tốn cả buổi mới tìm ra."""
    khbl = _doc_blocks_khbl(KHBL_GCD_LAYOUT)
    assert G.KHOI_MA_VACH in khbl, 'Bên KHBL chưa có khối mã vạch — hai bên đang lệch danh sách khối.'
    assert khbl[G.KHOI_MA_VACH] == {k: float(v) for k, v in G.mac_dinh()[G.KHOI_MA_VACH].items()}
    assert list(khbl) == [b['key'] for b in G.BLOCKS], 'Danh sách hoặc THỨ TỰ khối lệch nhau.'


@pytest.mark.skipif(not os.path.exists(KHBL_GCD_LAYOUT), reason='Chưa có bản song sinh bên KHBL.')
def test_css_anh_khop_tung_ky_tu_voi_khbl():
    """CSS_ANH quyết định HÌNH DÁNG ảnh trên giấy ⇒ phải giống từng ký tự, không chỉ giống ý.

    Đúng chỗ đã cháy lượt trước: font và line-height mỗi bên một kiểu, chữ lệch tới 9 mm.
    """
    s = io.open(KHBL_GCD_LAYOUT, encoding='utf-8').read()
    m = re.search(r'CSS_ANH = \((.*?)\)\n', s, re.S)
    assert m, 'Bên KHBL không còn hằng CSS_ANH — hợp đồng hình dáng ảnh đã đổi, đọc lại rồi chép sang.'
    khbl = ''.join(re.findall(r'"([^"]*)"', m.group(1)))
    assert G.CSS_ANH == khbl
    for phai_co in ('object-fit:fill', 'image-rendering:pixelated', 'display:block!important'):
        assert phai_co in G.CSS_ANH


def test_css_sinh_ra_co_khoi_anh():
    css = G.css(G.mac_dinh())
    assert G.CSS_ANH in css, 'Hình dáng ảnh phải do css() sinh ra, không để trong static/.'
    assert '[data-gcd="ma_phieu_vach"]{position:absolute!important;left:77.4%!important;top:5.6%!important;' \
           'width:18.8%!important;height:6%!important;font-size:8pt!important}' in css
    assert 'background-image' not in css and 'print-color-adjust' not in css


def test_css_an_khoi_ma_vach():
    css = G.css(G._gop(G.mac_dinh(), {'ma_phieu_vach': {'an': 1}}))
    assert '[data-gcd="ma_phieu_vach"]{display:none!important}' in css


# ── 7. DỰNG TRANG IN — KHÔNG CẦN CSDL ────────────────────────────────────────────────────────
# Máy này chưa có KHCD_TEST_ENV nên nhóm bài web ở cuối tệp tự bỏ qua. Nhưng ba yêu cầu gốc của
# Giám đốc (mã vạch phải RA GIẤY · bản in KHÔNG được có nền · xem trước CÓ nền vẫn phải thấy mã
# vạch) nằm hết ở lớp dựng trang, nên dựng thẳng bằng Jinja với dữ liệu giả — không đụng CSDL,
# không đụng máy in. Chỉ nạp ĐÚNG template thật, nên sửa template mà quên khối ảnh là đỏ ngay.
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'khcd', 'templates')


def _ctx_gia(sku=MA_THAT):
    """Đúng hình dạng live_loans.receipt_context() ở phần gcd_print cần — không hơn."""
    return {'loan': {'sku': sku, 'original_principal': 15000000, 'principal_balance': 15000000,
                     'opened_at': '2026-09-01 08:00:00', 'due_at': '2026-10-01 08:00:00',
                     'monthly_rate': 3.0, 'safe': '1', 'employee_name': 'Nhân viên QA',
                     'note': '', 'receipt_lost': 0, 'loan_state': 'ACTIVE', 'phone': '0900000001'},
            'customer': {'name': 'Nguyễn Văn Khách', 'addr': 'Khóm 4, Năm Căn', 'cccd': '079100000001',
                         'phone': '0900000001'},
            'items': [{'gold_code': '99', 'description': 'Nhẫn trơn', 'unit': 'chỉ', 'net_weight': 1.9}],
            'warning': ''}


def _dung(layout=None, nen=False, pdf=False):
    """Render loan_print_gcd.html thật bằng Jinja trần (khỏi app/CSDL), trả HTML."""
    from jinja2 import Environment, FileSystemLoader
    from khcd import gcd_print as P
    layout = layout or G.mac_dinh()
    ctx = _ctx_gia()
    khoi, tran = P._khoi(ctx, layout)
    vach = P._vach_hep(ctx, layout)
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)
    env.globals.update(url_for=lambda *a, **k: '#', session={'csrf': 'token'})
    return env.get_template('loan_print_gcd.html').render(
        title=MA_THAT, loan=ctx['loan'], customer=ctx['customer'], khoi=khoi, tran=tran,
        mep=G.khoi_sat_mep(layout), nen=nen, thuoc=False, nguon='sql', pdf=pdf,
        inn=G.IN_MAC_DINH, ct=G.CT_MAC_DINH, may_tt=None, warning='', lech_tien=False,
        vach_mm=('%.3f' % vach).replace('.', ','),
        vach_hep=bool(vach and vach < MV.VACH_HEP_TOI_THIEU_MM),
        vach_thu=bool(vach and MV.VACH_HEP_TOI_THIEU_MM <= vach < MV.VACH_HEP_CAN_THU_MM),
        vach_toi_thieu=str(MV.VACH_HEP_TOI_THIEU_MM).replace('.', ','),
        vach_can_thu=str(MV.VACH_HEP_CAN_THU_MM).replace('.', ','),
        css_url='#', css_tinh_url='#', print_count_url='#', may_url='#', print_url='#', detail_url='#')


def _the_anh(html):
    return re.findall(r'<img[^>]*data-gcd="ma_phieu_vach"[^>]*>', html)


def test_render_ban_in_that_co_ma_vach_khong_co_nen():
    """Yêu cầu gốc: tờ in ra CHỈ có chữ và mã vạch, TUYỆT ĐỐI không ảnh nền."""
    html = _dung()
    the = _the_anh(html)
    assert len(the) == 1, 'Phải có đúng MỘT thẻ ảnh mã vạch, thấy %d.' % len(the)
    assert 'class="gcd-anh"' in the[0] and 'src="data:image/png;base64,' in the[0]
    assert 'gcd-nen' not in html and 'GCD.jpg' not in html
    assert 'style="' not in the[0], 'CSP style-src self chặn câm style nội tuyến.'
    assert '<style' not in html


def test_render_anh_dung_la_ma_vach_cua_phieu_dang_in():
    """Quét ảnh LẤY TỪ HTML ĐÃ RENDER ra phải đúng số của chính phiếu đang in.

    So chuỗi HTML thôi thì chưa đủ: view có thể vẽ mã vạch của một phiếu khác mà bài kiểm vẫn xanh.
    """
    html = _dung()
    uri = re.search(r'data-gcd="ma_phieu_vach"[^>]*src="([^"]+)"', html).group(1)
    assert _giai_ma(uri) == '*' + SO_THAT + '*'
    assert MA_THAT in html              # số đọc được vẫn do khối ma_phieu in ra như cũ


def test_render_xem_truoc_co_nen_van_hien_ma_vach():
    """Yêu cầu gốc: chế độ xem trước có nền vẫn phải thấy mã vạch để còn căn ô."""
    html = _dung(nen=True)
    assert len(_the_anh(html)) == 1
    assert 'class="gcd-nen no-print"' in html


def test_render_ban_gui_may_in_cung_co_ma_vach():
    """Bản dựng PDF phía máy chủ dùng CHUNG template ⇒ cũng có mã vạch, và vẫn không có nền."""
    html = _dung(pdf=True)
    assert len(_the_anh(html)) == 1
    assert 'gcd-nen' not in html and 'GCD.jpg' not in html


def test_render_du_18_data_gcd():
    """Quên một data-gcd trong template thì khối đó KHÔNG BAO GIỜ được định vị trên bản in."""
    assert set(re.findall(r'data-gcd="([a-z0-9_]+)"', _dung())) == {b['key'] for b in G.BLOCKS}


def test_render_tat_khoi_thi_khong_ve_anh():
    """Khối TẮT → không sinh ảnh (khỏi tốn công vẽ) nhưng DOM vẫn còn data-gcd để CSS neo."""
    html = _dung(G._gop(G.mac_dinh(), {'ma_phieu_vach': {'an': 1}}))
    assert _the_anh(html) == []
    assert 'data-gcd="ma_phieu_vach"' in html


def test_render_bo_cuc_mac_dinh_chi_nhac_quet_thu():
    """Đường chạy hằng ngày: một dòng XÁM nhắc quét thử, TUYỆT ĐỐI không dải đỏ."""
    html = _dung()
    assert 'MÃ VẠCH QUÁ HẸP' not in html
    assert 'phải quét thử trên tờ in đầu' in html and 'gcd-bao-xam no-print' in html


def test_render_bao_do_khi_ma_vach_qua_hep():
    html = _dung(G._gop(G.mac_dinh(), {'ma_phieu_vach': {'w': 10}}))
    assert 'MÃ VẠCH QUÁ HẸP' in html and 'gcd-bao-do no-print' in html
    assert 'phải quét thử trên tờ in đầu' not in html      # hai dải không bao giờ hiện cùng lúc


def test_render_thu_nho_ty_le_in_cung_lam_vach_hep():
    """Thu nhỏ cả tờ giấy là thu nhỏ luôn mã vạch — cảnh báo phải tính cả _in.ty_le."""
    html = _dung(G._gop(G.mac_dinh(), {'ma_phieu_vach': {'w': 16}, '_in': {'ty_le': 55}}))
    assert 'MÃ VẠCH QUÁ HẸP' in html


def test_render_tat_khoi_thi_khong_bao_gi():
    """Khối TẮT thì không có mã vạch để mà hẹp — đừng báo động cho tờ không in vạch."""
    html = _dung(G._gop(G.mac_dinh(), {'ma_phieu_vach': {'an': 1, 'w': 5}}))
    assert 'MÃ VẠCH QUÁ HẸP' not in html and 'phải quét thử trên tờ in đầu' not in html


# ══ CÁC BÀI CẦN CSDL ═════════════════════════════════════════════════════════════════════════
PMV_STATE_COT = ('(id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY, `key` VARCHAR(100) NOT NULL UNIQUE,'
                 ' `value` LONGTEXT NOT NULL, updated_at DATETIME(6) NULL) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4')


@pytest.fixture(autouse=True)
def nho_rieng(tmp_path, monkeypatch):
    """Bản chép dự phòng phải nằm trong thư mục nháp — KHÔNG được đè instance/gcd_layout.json thật."""
    monkeypatch.setattr(G, '_duong_nho', lambda: str(tmp_path / 'gcd_layout.json'))
    G.quen_nho()
    yield
    G.quen_nho()


@pytest.fixture
def phieu(app):
    """Một biên nhận mang mã KH2 thật để in, nằm trong CSDL nháp của conftest."""
    from khcd import db
    with app.app_context():
        db.execute('CREATE TABLE IF NOT EXISTS ' + G._bang_cau_hinh() + ' ' + PMV_STATE_COT)
        lid = db.execute(
            "INSERT INTO cd_loans (legacy_pawn_id,sku,phone,cust_id,loan_state,last_operation_id,receipt_lost,"
            "opened_at,interest_from,due_at,original_principal,principal_balance,monthly_rate,safe,"
            "employee_id,employee_name,note,customer_snapshot,terms_json,documents_json,legacy_json,"
            "source_hash,target_hash,migration_state,converted_at,converted_by,converted_username) VALUES "
            "(NULL,'" + MA_THAT + "','0900000001','','ACTIVE',1,0,'2026-09-01 08:00:00','2026-09-01 08:00:00',"
            "'2026-10-01 08:00:00',15000000,12000000,3.0,'1','EMP1','Nhân viên QA','',%s,"
            "'{}','{}','{}','','','LIVE','2026-09-01 08:00:00',1,'khj_admin')",
            (json.dumps({'name': 'Nguyễn Văn Khách', 'addr': 'Khóm 4, TT. Năm Căn, Cà Mau',
                         'cccd': '079100000001', 'phone': '0900000001'}, ensure_ascii=False),))
        db.execute("INSERT INTO cd_loan_items (loan_id,line_no,gold_code,description,unit,gross_weight,"
                   "stone_weight,net_weight,unit_price,valuation) VALUES "
                   "(%s,1,'99','Nhẫn trơn','chỉ',2.0000,0.1000,1.9000,7000000,13300000)", (lid,))
    return lid


def _dat_bo_cuc(app, data):
    from khcd import db
    with app.app_context():
        db.execute('REPLACE INTO ' + G._bang_cau_hinh() + ' (`key`,`value`) VALUES (%s,%s)',
                   (G.KEY, json.dumps(data, ensure_ascii=False)))
    G.quen_nho()


def test_ban_in_that_co_ma_vach_va_khong_co_nen(client, phieu):
    """Yêu cầu gốc: tờ in ra CHỈ có chữ và mã vạch, TUYỆT ĐỐI không ảnh nền."""
    html = client.get('/camdo/bien-nhan/%d/giay' % phieu).get_data(as_text=True)
    the = _the_anh(html)
    assert len(the) == 1, 'Phải có đúng MỘT thẻ ảnh mã vạch, thấy %d.' % len(the)
    assert 'class="gcd-anh"' in the[0] and 'src="data:image/png;base64,' in the[0]
    assert 'gcd-nen' not in html and 'GCD.jpg' not in html
    assert 'style="' not in the[0], 'CSP style-src self chặn câm style nội tuyến.'


def test_anh_tren_trang_dung_la_ma_vach_cua_phieu_nay(client, phieu):
    """Quét ảnh LẤY TỪ HTML ĐÃ RENDER ra phải đúng số của chính phiếu đang in.

    So chuỗi HTML thôi thì chưa đủ: view có thể vẽ mã vạch của một phiếu khác mà bài kiểm vẫn xanh.
    """
    html = client.get('/camdo/bien-nhan/%d/giay' % phieu).get_data(as_text=True)
    uri = re.search(r'data-gcd="ma_phieu_vach"[^>]*src="([^"]+)"', html).group(1)
    assert _giai_ma(uri) == '*' + SO_THAT + '*'
    assert MA_THAT in html                      # số đọc được vẫn do khối ma_phieu in ra như cũ


def test_xem_truoc_co_nen_van_hien_ma_vach(client, phieu):
    """Yêu cầu gốc: chế độ xem trước có nền vẫn phải thấy mã vạch để căn ô."""
    html = client.get('/camdo/bien-nhan/%d/giay?nen=1' % phieu).get_data(as_text=True)
    assert len(_the_anh(html)) == 1
    assert 'class="gcd-nen no-print"' in html


def test_ban_gui_may_in_cung_co_ma_vach(client, phieu, app):
    """Bản dựng PDF phía máy chủ dùng CHUNG template ⇒ cũng phải có mã vạch, và vẫn không có nền."""
    from khcd import live_loans as live
    with app.app_context():
        ctx = live.receipt_context(phieu)
        layout, nguon = G.doc_bo_cuc()
        from khcd import gcd_print as P
        html = P._dung_trang(ctx, layout, nguon, nen=False, pdf=True, lid=phieu,
                             css_url='mau-in.css', css_tinh_url='gcd-print.css')
    assert len(_the_anh(html)) == 1
    assert 'gcd-nen' not in html and 'GCD.jpg' not in html


def test_tat_khoi_thi_khong_ve_anh(client, phieu, app):
    """Khối TẮT → không sinh ảnh (khỏi tốn công vẽ) nhưng DOM vẫn còn data-gcd để CSS neo."""
    _dat_bo_cuc(app, {'ma_phieu_vach': {'an': 1}})
    html = client.get('/camdo/bien-nhan/%d/giay' % phieu).get_data(as_text=True)
    assert _the_anh(html) == []
    assert 'data-gcd="ma_phieu_vach"' in html
    css = client.get('/camdo/bien-nhan/mau-in.css').get_data(as_text=True)
    assert '[data-gcd="ma_phieu_vach"]{display:none!important}' in css


def test_bo_cuc_mac_dinh_chi_nhac_quet_thu_khong_keu_do(client, phieu):
    """Đường chạy hằng ngày: một dòng XÁM nhắc quét thử, TUYỆT ĐỐI không dải đỏ.

    Dải đỏ nổ mỗi lần in thì vài hôm là không ai đọc dải cảnh báo nào nữa, kể cả dải báo lệch tiền.
    """
    html = client.get('/camdo/bien-nhan/%d/giay' % phieu).get_data(as_text=True)
    assert 'MÃ VẠCH QUÁ HẸP' not in html
    assert 'phải quét thử trên tờ in đầu' in html
    assert 'gcd-bao-xam no-print' in html


def test_bao_do_khi_ma_vach_qua_hep(client, phieu, app):
    """Bóp khối xuống dưới mức máy quét quầy chịu được ⇒ kêu ĐỎ TRƯỚC KHI in, không im lặng."""
    _dat_bo_cuc(app, {'ma_phieu_vach': {'w': 10}})
    html = client.get('/camdo/bien-nhan/%d/giay' % phieu).get_data(as_text=True)
    assert 'MÃ VẠCH QUÁ HẸP' in html
    assert 'gcd-bao-do no-print' in html                       # kêu trên màn, không in ra giấy
    assert 'phải quét thử trên tờ in đầu' not in html          # hai dải không bao giờ hiện cùng lúc


def test_thu_nho_ty_le_in_cung_lam_vach_hep(client, phieu, app):
    """Thu nhỏ cả tờ giấy là thu nhỏ luôn mã vạch — cảnh báo phải tính cả _in.ty_le."""
    _dat_bo_cuc(app, {'ma_phieu_vach': {'w': 16}, '_in': {'ty_le': 55}})
    html = client.get('/camdo/bien-nhan/%d/giay' % phieu).get_data(as_text=True)
    assert 'MÃ VẠCH QUÁ HẸP' in html


def test_tat_khoi_thi_khong_bao_gi(client, phieu, app):
    """Khối TẮT thì không có mã vạch để mà hẹp — đừng báo động cho tờ không in vạch."""
    _dat_bo_cuc(app, {'ma_phieu_vach': {'an': 1, 'w': 5}})
    html = client.get('/camdo/bien-nhan/%d/giay' % phieu).get_data(as_text=True)
    assert 'MÃ VẠCH QUÁ HẸP' not in html and 'phải quét thử trên tờ in đầu' not in html


def test_css_route_van_kem_hinh_dang_anh(client, phieu):
    css = client.get('/camdo/bien-nhan/mau-in.css').get_data(as_text=True)
    assert G.CSS_ANH in css
    assert 'background-image' not in css                      # nền không có đường nào lọt vào bản in
