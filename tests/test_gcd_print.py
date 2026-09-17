"""Mẫu in GIẤY CẦM ĐỒ A5 ngang: bố cục đọc chéo khj_bl, CSS sinh ra, và trang in.

CHẠY: chỉ đích danh tệp này, không bao giờ chạy cả bộ và không dùng discover.
    .venv\\Scripts\\python.exe -m pytest tests/test_gcd_print.py -q
Các bài cần CSDL sẽ TỰ BỎ QUA nếu chưa đặt KHCD_TEST_ENV (conftest tạo CSDL nháp rồi xoá).
Nhóm bài thuần hàm (đọc số, gộp giá trị, sinh CSS) chạy được không cần CSDL.
"""
import json
import os

import pytest

from khcd import gcd_layout as G, ma_vach as MV


# ── 1. ĐỌC SỐ TIỀN BẰNG CHỮ ───────────────────────────────────────────────────────────────────
# Đối chiếu tay với words() trong khcd/static/pawn-entry.js dòng 21 — "Bằng chữ" là dòng PHÁP LÝ,
# phải ra ĐÚNG chuỗi nhân viên đã nhìn thấy lúc lập phiếu. Bẫy: mốt · lăm · lẻ · mười · mươi.
BANG_DOC_SO = [
    (0, 'Không đồng'),
    (1, 'Một đồng'),
    (4, 'Bốn đồng'),
    (5, 'Năm đồng'),
    (9, 'Chín đồng'),
    (10, 'Mười đồng'),
    (11, 'Mười một đồng'),
    (14, 'Mười bốn đồng'),
    (15, 'Mười lăm đồng'),
    (20, 'Hai mươi đồng'),
    (21, 'Hai mươi mốt đồng'),
    (25, 'Hai mươi lăm đồng'),
    (99, 'Chín mươi chín đồng'),
    (100, 'Một trăm đồng'),
    (101, 'Một trăm lẻ một đồng'),
    (105, 'Một trăm lẻ năm đồng'),
    (110, 'Một trăm mười đồng'),
    (111, 'Một trăm mười một đồng'),
    (115, 'Một trăm mười lăm đồng'),
    (121, 'Một trăm hai mươi mốt đồng'),
    (999, 'Chín trăm chín mươi chín đồng'),
    (1000, 'Một nghìn đồng'),
    (1001, 'Một nghìn không trăm lẻ một đồng'),
    (1005, 'Một nghìn không trăm lẻ năm đồng'),
    (1015, 'Một nghìn không trăm mười lăm đồng'),
    (1100, 'Một nghìn một trăm đồng'),
    (10000, 'Mười nghìn đồng'),
    (100000, 'Một trăm nghìn đồng'),
    (500000, 'Năm trăm nghìn đồng'),
    (1000000, 'Một triệu đồng'),
    (1500000, 'Một triệu năm trăm nghìn đồng'),
    (2050000, 'Hai triệu không trăm năm mươi nghìn đồng'),
    (15000000, 'Mười lăm triệu đồng'),
    (21000000, 'Hai mươi mốt triệu đồng'),
    (105000000, 'Một trăm lẻ năm triệu đồng'),
    (550000000, 'Năm trăm năm mươi triệu đồng'),
    (1000000000, 'Một tỷ đồng'),
    (1005000000, 'Một tỷ không trăm lẻ năm triệu đồng'),
    (999999999999, 'Chín trăm chín mươi chín tỷ chín trăm chín mươi chín triệu chín trăm chín mươi chín nghìn chín trăm chín mươi chín đồng'),
]


@pytest.mark.parametrize('so,chu', BANG_DOC_SO)
def test_doc_so(so, chu):
    assert G.doc_so(so) == chu


def test_doc_so_bien():
    assert G.doc_so(1000000000000) == 'Số tiền vượt giới hạn'      # vượt 999.999.999.999
    assert G.doc_so(-1) == 'Số tiền không hợp lệ'
    assert G.doc_so('abc') == ''
    from decimal import Decimal
    assert G.doc_so(Decimal('5000000')) == 'Năm triệu đồng'        # kiểu DECIMAL từ MySQL


# ── 2. MẶC ĐỊNH + GỘP BẢN LƯU ────────────────────────────────────────────────────────────────
def test_mac_dinh_du_khoi():
    m = G.mac_dinh()
    assert len(G.BLOCKS) == 20          # 17 chữ + 1 ẢNH mã vạch + 2 BẢNG cuống (16/09/2026)
    for b in G.BLOCKS:
        assert b['key'] in m and 'left' in m[b['key']] and 'an' in m[b['key']]
    assert m[G.IN_KEY]['kho'] == 'A5N'                 # KHÔNG phải "auto": tờ NGANG 210mm sẽ tràn
    assert (m[G.IN_KEY]['kho_w'], m[G.IN_KEY]['kho_h']) == (210, 148)
    assert set(m) == {b['key'] for b in G.BLOCKS} | {G.IN_KEY, G.CT_KEY, G.NEN_KEY}
    # Tiền mặc định phải TRÙNG con số trang in cũ đang in (principal_balance).
    assert m[G.CT_KEY]['tien'] == 'du_hien_tai'


def test_gop_loai_rac():
    m = G._gop(G.mac_dinh(), {
        'khong_co_khoi_nay': {'left': 10},             # khoá lạ
        'mon_hang': {'left': 'NaN', 'top': float('inf'), 'w': -50, 'h': 999, 'fs': 2, 'lung_tung': 1},
        'khach_ten': {'an': 2},                        # an chỉ nhận 0/1
        'so_tien_so': {'an': 1},
        G.IN_KEY: {'kho': 'KHONG_CO', 'canh': 'xien', 'dx': 9999, 'ty_le': 1, 'may_in': 'may;rm -rf', 'ban_in': 99},
        G.CT_KEY: {'tien': 'tien_gi_do'},
    })
    assert 'khong_co_khoi_nay' not in m
    assert m['mon_hang']['left'] == G.BLOCK_MAP['mon_hang']['left']   # NaN bị bỏ, giữ mặc định
    assert m['mon_hang']['top'] == G.BLOCK_MAP['mon_hang']['top']     # Infinity bị bỏ
    assert m['mon_hang']['w'] == 1 and m['mon_hang']['h'] == 100      # kẹp về biên
    assert m['mon_hang']['fs'] == 3                                   # kẹp sàn cỡ chữ
    assert 'lung_tung' not in m['mon_hang']
    assert m['khach_ten']['an'] == 0 and m['so_tien_so']['an'] == 1
    assert m[G.IN_KEY]['kho'] == 'A5N' and m[G.IN_KEY]['canh'] == 'giua'
    assert m[G.IN_KEY]['dx'] == 80 and m[G.IN_KEY]['ty_le'] == 50
    assert m[G.IN_KEY]['may_in'] == '' and m[G.IN_KEY]['ban_in'] == 4
    assert m[G.CT_KEY]['tien'] == 'du_hien_tai'


# ── 3. CSS SINH RA ───────────────────────────────────────────────────────────────────────────
def test_css_khung_giay():
    css = G.css(G.mac_dinh())
    # position:relative BẮT BUỘC: KHCD không có khbl.css khai sẵn, thiếu nó là 17 khối neo vào
    # viewport và bố cục vỡ toàn bộ.
    assert '.gcd-a5{position:relative!important;' in css
    assert 'width:210mm!important' in css and 'aspect-ratio:210/148' in css
    assert '@media print{@page{size:210mm 148mm;margin:0}' in css


def test_css_khong_bao_gio_co_nen():
    """Bản in thật chỉ có CHỮ. Một URL ảnh lọt vào đây là in nền lên giấy in sẵn."""
    css = G.css(G.mac_dinh())
    assert 'url(' not in css and 'GCD.jpg' not in css and 'background-image' not in css
    # print-color-adjust chính là công tắc ÉP trình duyệt in nền — không bao giờ được sinh ra.
    assert 'print-color-adjust' not in css
    # Ngược lại, phải CHỦ ĐỘNG tắt nền khi in.
    assert 'background:none!important' in css
    assert '.gcd-nen,.no-print{display:none!important}' in css
    assert '.gcd-nen{' not in css                       # toạ độ _nen chỉ dành cho css_nen()


def test_css_du_khoi_va_an():
    layout = G._gop(G.mac_dinh(), {'trang_thai': {'an': 0}, 'khach_ten': {'an': 1}})
    css = G.css(layout)
    for b in G.BLOCKS:
        assert '[data-gcd="%s"]{position:absolute!important' % b['key'] in css
    assert '[data-gcd="khach_ten"]{display:none!important}' in css
    assert '[data-gcd="trang_thai"]{display:none!important}' not in css


def test_css_so_khong_co_duoi_thua():
    """_so() dùng "%g" để chuỗi Python và JS giống nhau TỪNG KÝ TỰ (bài đối chiếu KHBL ↔ KHCD)."""
    assert G._so(3.0) == '3' and G._so(20.40) == '20.4' and G._so(0.88) == '0.88'
    css = G.css(G._gop(G.mac_dinh(), {'ky_han': {'left': 42.0, 'fs': 9.0}}))
    assert 'left:42%!important' in css and 'font-size:9pt!important' in css
    assert 'left:42.0%' not in css


def test_css_bac_co_chu():
    css = G.css(G.mac_dinh())
    for key in G.CO_CHU:
        assert '[data-gcd="%s"].gcd-co-2{font-size:calc(' % key in css
        assert '[data-gcd="%s"].gcd-co-3{font-size:calc(' % key in css
    assert '[data-gcd="ky_han"].gcd-co-2' not in css      # ô số ngắn không cần bậc thang


def test_css_in_kho_va_ty_le():
    assert '@page{size:210mm 148mm;margin:0}' in G.css_in({'kho': 'A5N'})
    # Khổ tờ giấy là THAM SỐ: đo tờ thật ra 205×145 thì @page phải đi theo, không phải hằng số.
    assert '@page{size:205mm 145mm;margin:0}' in G.css_in({'kho': 'A5N', 'kho_w': 205, 'kho_h': 145})
    assert '@page{size:auto;margin:0}' in G.css_in({'kho': 'auto'})
    assert '@page{size:auto;margin:0}' in G.css_in({'kho': 'khong_co_kho_nay'})
    assert 'transform' not in G.css_in({'ty_le': 100})
    assert 'transform:scale(0.8)!important' in G.css_in({'ty_le': 80})
    assert 'left:-5mm!important;top:3mm!important' in G.css_in({'dx': -5, 'dy': 3})
    assert 'margin:0!important' in G.css_in({'canh': 'trai'})


def test_css_nen_tach_han():
    nen = G.css_nen(G._gop(G.mac_dinh(), {G.NEN_KEY: {'x': 1.5, 'w': 99}}))
    assert nen.startswith('.gcd-nen{left:1.5%;top:0%;width:99%;height:100%}')


# ── 4. BẬC CO CHỮ ────────────────────────────────────────────────────────────────────────────
def test_bac_co_chu():
    m = G.mac_dinh()
    assert G.bac_co_chu('Nguyễn Văn A', 'khach_diachi', m) == (1, False)
    assert G.bac_co_chu('x' * 5000, 'mon_hang', m) == (3, True)      # 30 món → hết bậc, phải cảnh báo
    assert G.bac_co_chu('x' * 5000, 'ky_han', m) == (1, False)       # khối không thuộc diện co chữ
    ngan, _ = G.bac_co_chu('a' * 60, 'khach_diachi', m)
    assert ngan in (1, 2, 3)


def test_bat_khoi_sat_mep():
    """Đo trên tờ thật: 'giay_to' mặc định có đáy ở 98,6% — cách mép dưới 2,1 mm, nằm gọn trong
    biên cứng 4,2–6,4 mm của laser/inkjet phổ thông. Trang xem trước phải nói ra."""
    m = G.mac_dinh()
    # 'giay_to' mặc định đã TẮT nên không báo; bật lên là báo ngay (đáy 97,1% ≈ 4,3 mm từ mép dưới).
    ten_giay_to = G.BLOCK_MAP['giay_to']['ten']
    assert ten_giay_to not in G.khoi_sat_mep(m)
    assert ten_giay_to in G.khoi_sat_mep(G._gop(m, {'giay_to': {'an': 0}}))
    # 'Số phiếu — cuống trên' đỉnh 1,0% ≈ 1,5 mm từ mép trên — nằm sâu trong biên cứng.
    assert G.khoi_sat_mep(G.mac_dinh()) == ['Số phiếu — cuống trên']
    assert 'Nhận của Ông/Bà' not in G.khoi_sat_mep(G.mac_dinh())
    assert G.khoi_sat_mep(G._gop(G.mac_dinh(), {'so_cuong_1': {'top': 6}})) == []


# ── 5. ĐỐI CHIẾU VỚI BẢN SONG SINH BÊN KHBL ──────────────────────────────────────────────────
KHBL_GCD = r'D:\PYTHON\KHBL\apps\pos\gcd_layout.py'


def _doc_blocks_khbl(duong):
    """Bóc mặc định từng khối trong mã nguồn KHBL (không import được: module đó cần Django)."""
    import re
    s = open(duong, encoding='utf-8').read()
    out = {}
    for m in re.finditer(r'"key"\s*:\s*"(\w+)".*?(?="key"|\Z)', s, re.S):
        blob, d = m.group(0), {}
        for k in ('left', 'top', 'w', 'h', 'fs', 'an'):
            g = re.search(r'"%s"\s*:\s*(-?[\d.]+)' % k, blob)
            if g:
                d[k] = float(g.group(1))
        out[m.group(1)] = d
    return out


@pytest.mark.skipif(not os.path.exists(KHBL_GCD), reason='Chưa có bản song sinh bên KHBL.')
def test_khop_mac_dinh_voi_khbl():
    """KHBL là nơi GĐ nhìn và kéo; KHCD là nơi in ra giấy. Hai bên LỆCH MẶC ĐỊNH thì TRƯỚC lần lưu
    đầu tiên, cái GĐ thấy khác cái máy in ra — kiểu lệch âm thầm tốn cả buổi mới tìm ra.

    Chỉ so DỮ LIỆU dùng chung (17 key + số đo). KHÔNG so chuỗi CSS: hai bên có markup riêng nên
    selector khác nhau ([data-gcd="x"] ở KHCD, .gcd-a5__x ở KHBL) — mỗi bên tự sinh CSS cho markup
    của mình, cái dùng chung là JSON trong pmv_state.
    """
    khbl = _doc_blocks_khbl(KHBL_GCD)
    khcd = {k: {p: float(v[p]) for p in v} for k, v in G.mac_dinh().items() if k in {b['key'] for b in G.BLOCKS}}
    assert list(khbl) == [b['key'] for b in G.BLOCKS], 'Danh sách khối lệch nhau'
    lech = {k: (khbl[k], khcd[k]) for k in khcd if khbl.get(k) != khcd[k]}
    assert not lech, 'Số đo mặc định lệch KHBL ↔ KHCD: %s' % lech


# ══ CÁC BÀI CẦN CSDL ═════════════════════════════════════════════════════════════════════════
PMV_STATE_COT = ('(id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY, `key` VARCHAR(100) NOT NULL UNIQUE,'
                 ' `value` LONGTEXT NOT NULL, updated_at DATETIME(6) NULL) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4')


@pytest.fixture(autouse=True)
def nho_rieng(tmp_path, monkeypatch):
    """Bản chép dự phòng phải nằm trong thư mục nháp — không được đè instance/gcd_layout.json thật."""
    monkeypatch.setattr(G, '_duong_nho', lambda: str(tmp_path / 'gcd_layout.json'))
    G.quen_nho()
    yield
    G.quen_nho()


@pytest.fixture
def phieu(app):
    """Một biên nhận đủ dùng để in, nằm trong CSDL nháp của conftest."""
    from khcd import db
    with app.app_context():
        db.execute('CREATE TABLE IF NOT EXISTS ' + G._bang_cau_hinh() + ' ' + PMV_STATE_COT)
        lid = db.execute(
            "INSERT INTO cd_loans (legacy_pawn_id,sku,phone,cust_id,loan_state,last_operation_id,receipt_lost,"
            "opened_at,interest_from,due_at,original_principal,principal_balance,monthly_rate,safe,"
            "employee_id,employee_name,note,customer_snapshot,terms_json,documents_json,legacy_json,"
            "source_hash,target_hash,migration_state,converted_at,converted_by,converted_username) VALUES "
            "(NULL,'CD260915TEST000001','0900000001','','ACTIVE',1,0,'2026-09-01 08:00:00','2026-09-01 08:00:00',"
            "'2026-10-01 08:00:00',15000000,12000000,3.0,'1','EMP1','Nhân viên QA','ghi chú thử',%s,"
            "'{}','{}','{}','','','LIVE','2026-09-01 08:00:00',1,'khj_admin')",
            (json.dumps({'name': 'Nguyễn Văn Khách', 'addr': 'Khóm 4, TT. Năm Căn, Năm Căn, Cà Mau',
                         'cccd': '079100000001', 'phone': '0900000001'}, ensure_ascii=False),))
        db.execute("INSERT INTO cd_loan_items (loan_id,line_no,gold_code,description,unit,gross_weight,"
                   "stone_weight,net_weight,unit_price,valuation) VALUES (%s,1,'99','Nhẫn trơn','chỉ',2.0000,0.1000,1.9000,7000000,13300000)", (lid,))
        db.execute("INSERT INTO cd_loan_items (loan_id,line_no,gold_code,description,unit,gross_weight,"
                   "stone_weight,net_weight,unit_price,valuation) VALUES (%s,2,'61','Dây chuyền','chỉ',3.0000,0.0000,3.0000,4000000,12000000)", (lid,))
    return lid


def _dat_bo_cuc(app, data):
    from khcd import db
    with app.app_context():
        db.execute('REPLACE INTO ' + G._bang_cau_hinh() + ' (`key`,`value`) VALUES (%s,%s)',
                   (G.KEY, json.dumps(data, ensure_ascii=False)))
    G.quen_nho()


def test_trang_in_du_17_khoi(client, phieu):
    """Kiểm trên HTML ĐÃ RENDER: so danh sách data-gcd với BLOCKS. So chuỗi CSS thôi thì KHÔNG bắt
    được lỗi template quên một data-gcd — khối đó sẽ không bao giờ được định vị trên bản in."""
    import re
    r = client.get('/camdo/bien-nhan/%d/giay' % phieu)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert set(re.findall(r'data-gcd="([a-z0-9_]+)"', html)) == {b['key'] for b in G.BLOCKS}


def test_ban_in_that_khong_co_nen(client, phieu):
    html = client.get('/camdo/bien-nhan/%d/giay' % phieu).get_data(as_text=True)
    assert 'gcd-nen' not in html          # phần tử ảnh nền không được sinh ra ở bản in thật
    assert 'GCD.jpg' not in html
    assert '<style' not in html           # CSP style-src 'self' chặn câm CSS nội tuyến
    assert 'style="' not in html


def test_xem_truoc_co_nen_va_khong_in_duoc_nen(client, phieu):
    html = client.get('/camdo/bien-nhan/%d/giay?nen=1' % phieu).get_data(as_text=True)
    assert 'class="gcd-nen no-print"' in html      # có nền, nhưng mang no-print
    assert 'tracked-print-button' not in html      # chế độ xem trước không có nút in
    assert 'ĐANG XEM TRƯỚC CÓ NỀN' in html
    css = client.get('/camdo/bien-nhan/mau-in.css?nen=1').get_data(as_text=True)
    assert '.gcd-nen{left:' in css
    # Ảnh nền nằm ở static/gcd-print.css và bị @media print{.no-print{display:none!important}} tắt.
    tinh = client.get('/static/gcd-print.css').get_data(as_text=True)
    assert '.no-print{display:none!important}' in tinh
    assert '.gcd-nen{' in tinh and 'url("img/GCD.jpg")' in tinh


def test_che_do_thuoc(client, phieu):
    html = client.get('/camdo/bien-nhan/%d/giay?thuoc=1' % phieu).get_data(as_text=True)
    assert 'gcd-thuoc-ngang' in html and 'gcd-thap-4' in html
    assert 'GIẤY TRẮNG' in html
    assert 'tracked-print-button' not in html      # đo thước thì không đếm lượt in


def test_dem_luot_in_van_chay_o_duong_moi(client, phieu):
    """Sổ đếm lượt in (cd_loans.count_print) là dấu vết in lại của chứng từ cầm đồ — đường in mới
    KHÔNG được bỏ qua nó."""
    html = client.get('/camdo/bien-nhan/%d/giay' % phieu).get_data(as_text=True)
    assert 'id="tracked-print-button"' in html
    assert '/camdo/bien-nhan/%d/luot-in' % phieu in html
    truoc = client.get('/camdo/bien-nhan/%d/luot-in' % phieu).get_json()['count_print']
    assert truoc == 0


def test_css_route_dung_mime_va_cong_tac_fail_closed(client, phieu):
    r = client.get('/camdo/bien-nhan/mau-in.css')
    assert r.status_code == 200
    assert r.headers['Content-Type'].startswith('text/css')
    css = r.get_data(as_text=True)
    assert '@page{size:210mm 148mm;margin:0}' in css
    # Công tắc fail-closed: CSS bố cục nạp được thì mới bật tờ giấy lên khi in.
    assert '.gcd-a5{display:block!important}' in css
    assert '.gcd-canhbao-css{display:none!important}' in css
    assert '.gcd-nen{' not in css                  # bản thường tuyệt đối không mang nền
    tinh = client.get('/static/gcd-print.css').get_data(as_text=True)
    assert '.gcd-a5{display:none}' in tinh and '.gcd-canhbao-css{display:block}' in tinh


def test_mon_hang_dung_chuoi_nhan_vien_da_xac_nhan(client, phieu, app):
    """Chữ trên biên nhận giao khách phải TRÙNG chuỗi pawn_desk.summary() đã lưu/đã hiện ở quầy."""
    from khcd import db, pawn_desk as desk, gcd_print
    with app.app_context():
        items = db.all('SELECT * FROM cd_loan_items WHERE loan_id=%s ORDER BY line_no', (phieu,))
        mong_doi = desk.summary(gcd_print._rows(items))
    assert mong_doi == '[99] Nhẫn trơn 1.90c + [61] Dây chuyền 3.00c'
    html = client.get('/camdo/bien-nhan/%d/giay' % phieu).get_data(as_text=True)
    assert mong_doi in html


def test_tien_theo_cau_hinh(client, phieu, app):
    """Mặc định in DƯ GỐC HIỆN TẠI — trùng con số trang in cũ, hai đường in không được lệch nhau.
    Đổi sang GỐC BAN ĐẦU thì phải hiện dải cảnh báo ghi cả hai số."""
    html = client.get('/camdo/bien-nhan/%d/giay' % phieu).get_data(as_text=True)
    assert '12.000.000' in html and 'Mười hai triệu đồng' in html
    assert 'gốc ban đầu' not in html
    _dat_bo_cuc(app, {G.CT_KEY: {'tien': 'goc_ban_dau'}})
    html = client.get('/camdo/bien-nhan/%d/giay' % phieu).get_data(as_text=True)
    assert '15.000.000' in html and 'Mười lăm triệu đồng' in html
    assert 'gốc ban đầu' in html                    # dải cảnh báo lệch số


def test_bo_cuc_luu_o_khj_bl_duoc_ap_dung(client, phieu, app):
    _dat_bo_cuc(app, {'ma_phieu': {'left': 70.5, 'fs': 7}, 'giay_to': {'an': 1}})
    css = client.get('/camdo/bien-nhan/mau-in.css').get_data(as_text=True)
    assert '[data-gcd="ma_phieu"]{position:absolute!important;left:70.5%!important' in css
    assert 'font-size:7pt!important' in css
    assert '[data-gcd="giay_to"]{display:none!important}' in css


def test_doc_hut_khj_bl_van_in_duoc(client, phieu, app, monkeypatch):
    """Ba đường hụt (mất kết nối · thiếu quyền · JSON hỏng) đều phải ra bố cục dùng được.
    KHÔNG được để lọt lên errorhandler(pymysql.MySQLError) — nó biến mọi lỗi thành trang 503."""
    _dat_bo_cuc(app, {'ma_phieu': {'left': 70.5}})
    assert client.get('/camdo/bien-nhan/%d/giay' % phieu).status_code == 200   # nạp bản chép tệp
    G.quen_nho()

    def no():
        raise RuntimeError('khj_bl mat ket noi')
    # Chỉ làm hỏng đường ĐỌC CẤU HÌNH — phiếu/khách/món vẫn đọc bình thường, đúng như khi chỉ riêng
    # khj_bl mất kết nối. (Không vá khcd.db.one: vá thế là giết luôn truy vấn phiếu, sai tình huống.)
    monkeypatch.setattr(G, '_bang_cau_hinh', no)
    r = client.get('/camdo/bien-nhan/%d/giay' % phieu)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'bản chép dự phòng' in html             # đọc hụt → bản chép, vẫn in được
    css = client.get('/camdo/bien-nhan/mau-in.css').get_data(as_text=True)
    assert 'left:70.5%!important' in css


def test_json_hong_van_in_duoc(client, phieu, app):
    from khcd import db
    with app.app_context():
        db.execute('REPLACE INTO ' + G._bang_cau_hinh() + ' (`key`,`value`) VALUES (%s,%s)', (G.KEY, '{khong-phai-json'))
    G.quen_nho()
    r = client.get('/camdo/bien-nhan/%d/giay' % phieu)
    assert r.status_code == 200
    assert '[data-gcd="ma_phieu"]' in client.get('/camdo/bien-nhan/mau-in.css').get_data(as_text=True)


def test_trang_lap_phieu_khong_dung_bo_cuc(app, monkeypatch):
    """Trang lập phiếu TUYỆT ĐỐI không được phụ thuộc vào khj_bl: KHBL sập thì quầy vẫn lập phiếu."""
    goi = []
    monkeypatch.setattr(G, 'doc_bo_cuc', lambda *a, **k: goi.append(1) or (G.mac_dinh(), 'mac_dinh'))
    c = app.test_client()
    from khcd import auth
    with app.app_context():
        user = auth.sync_user(username='khj_admin')
        chu_ky = auth.session_signature(user)
    with c.session_transaction() as s:
        s.update(user='khj_admin', user_id=1, auth_version=1, auth_signature=chu_ky, csrf='token')
    assert c.get('/camdo/lap-phieu').status_code < 500
    assert goi == []


def test_khong_doi_hanh_vi_trang_in_cu(client, phieu):
    """Trang in cũ (lưới an toàn) giữ nguyên, chỉ thêm đường sang giấy in sẵn."""
    html = client.get('/camdo/bien-nhan/%d/in' % phieu).get_data(as_text=True)
    assert 'BIÊN NHẬN CẦM ĐỒ' in html and 'Dư gốc hiện tại' in html
    assert '/camdo/bien-nhan/%d/giay' % phieu in html


# ── BẢNG CUỐNG TIỆM GIỮ (GĐ chốt 16/09/2026) ──────────────────────────────────────────────────
# Chạy được KHÔNG CẦN CSDL: _bang() là hàm thuần, chỉ đọc ctx đã dựng sẵn.
_CTX_CUONG = {
    'loan': {'id': 1, 'sku': 'KH22609020810', 'principal_balance': 25000000, 'phone': '0900000001'},
    'customer': {'name': 'Khách Thử', 'phone': '0900000001'},
    'items': [],
}


def _gia_lap_cuong(monkeypatch):
    from khcd import gcd_print as P
    monkeypatch.setattr(P, '_mon', lambda ctx, layout: ['[99] Nhẫn thử 3.00c'])
    monkeypatch.setattr(P, '_phien', lambda ctx: {
        'nghiep_vu': 'Cầm mới', 'luc': '14:35 15/09/2026', 'thu_chi': 'Chi 25.000.000'})
    return P


def test_bang_cuong_hai_ban_giong_het(monkeypatch):
    """Hai bảng phải là CÙNG MỘT bộ dữ liệu: hai nửa tờ giấy nói hai chuyện là hỏng đối soát."""
    P = _gia_lap_cuong(monkeypatch)
    ra = P._bang(_CTX_CUONG, G.mac_dinh())
    assert set(ra) == set(G.KHOI_BANG)
    assert ra['cuong_bang_1'] is ra['cuong_bang_2']
    b = ra['cuong_bang_1']
    assert b['ma'] == 'KH22609020810' and b['ten'] == 'Khách Thử' and b['dt'] == '0900000001'
    assert b['nghiep_vu'] == 'Cầm mới' and b['thu_chi'] == 'Chi 25.000.000'
    assert b['cam'] == '25.000.000'                    # DƯ GỐC hiện tại, không phải gốc ban đầu
    assert b['noi_dung'] == ['[99] Nhẫn thử 3.00c']
    # QR mang NGUYÊN mã phiếu kể cả CHỮ CÁI — khác mã vạch Code 39 chỉ mang phần chữ số.
    assert b['qr'].startswith('data:image/svg+xml') and b['qr'] == MV.svg_qr('KH22609020810')
    assert MV.so_ma_vach('KH22609020810') == '22609020810'


def test_bang_cuong_tat_ca_hai_thi_khong_ve_qr(monkeypatch):
    """Tắt cả hai khối thì khỏi dựng — vẽ QR tốn một lượt, không việc gì trả giá cho khối display:none."""
    P = _gia_lap_cuong(monkeypatch)
    tat = G._gop(G.mac_dinh(), {'cuong_bang_1': {'an': 1}, 'cuong_bang_2': {'an': 1}})
    assert P._bang(_CTX_CUONG, tat) == {}
    mot = G._gop(G.mac_dinh(), {'cuong_bang_1': {'an': 1}})
    assert set(P._bang(_CTX_CUONG, mot)) == set(G.KHOI_BANG)   # còn một khối bật thì vẫn dựng


def test_phien_hong_thi_de_trong_chu_khong_bia(monkeypatch):
    """Đọc sổ phiên hỏng → các ô đó TRỐNG. Thà cuống thiếu một dòng còn hơn in sai nghiệp vụ."""
    from khcd import gcd_print as P, live_loans as live
    monkeypatch.setattr(P, '_mon', lambda ctx, layout: [])
    def no(_lid):
        raise RuntimeError('mat ket noi')
    monkeypatch.setattr(live, 'latest', no)
    assert P._phien(_CTX_CUONG) is None
    b = P._bang(_CTX_CUONG, G.mac_dinh())['cuong_bang_1']
    assert b['nghiep_vu'] == '' and b['luc'] == '' and b['thu_chi'] == ''
    assert b['ma'] == 'KH22609020810' and b['cam'] == '25.000.000'   # phần không phụ thuộc sổ VẪN in


def test_phien_khong_co_dong_log_nao(monkeypatch):
    from khcd import gcd_print as P, live_loans as live
    monkeypatch.setattr(live, 'latest', lambda _lid: None)
    assert P._phien(_CTX_CUONG) is None


def test_template_cuong_render_duoc_bang_jinja():
    """Vòng lặp khối bên trang in dùng {% with %} + {% include %} của Jinja2 — kiểm THẬT.

    Bài kiểm khối/CSS không chạm tới template, mà lỗi cú pháp Jinja chỉ lộ ra lúc IN: nhân viên
    bấm IN, trang 500, tờ giấy in sẵn đã nằm trong máy.
    """
    from jinja2 import Environment, FileSystemLoader
    from pathlib import Path
    moi_truong = Environment(loader=FileSystemLoader(
        str(Path(__file__).resolve().parent.parent / 'khcd' / 'templates')), autoescape=True)
    khoi = [dict(key='cuong_bang_1', anh='', dong=[], cls='gcd-co-1', an=False, bang=dict(
        nghiep_vu='Cầm mới', luc='14:35 15/09/2026', qr='data:image/svg+xml;charset=utf-8,x',
        ma='KH22609020810', ten='Khách Thử', dt='0900000001',
        noi_dung=['[99] Nhẫn thử 3.00c'], thu_chi='Chi 25.000.000', cam='25.000.000'))]
    ra = moi_truong.from_string(
        '{% for b in khoi %}{% if b.bang %}<div class="gcd-cuong" data-gcd="{{ b.key }}">'
        '{% with b=b.bang %}{% include "_gcd_cuong.html" %}{% endwith %}</div>{% endif %}{% endfor %}'
    ).render(khoi=khoi)
    assert 'data-gcd="cuong_bang_1"' in ra and 'class="gcd-cuong__qr"' in ra
    assert 'Cầm mới, 14:35 15/09/2026' in ra
    assert 'KH22609020810' in ra and 'Khách Thử' in ra and '0900000001' in ra
    # GĐ chốt 17/09: bỏ hẳn nhãn 'Thu/Chi:', chỉ còn một số tự nói hướng của nó.
    assert 'Thu/Chi:' not in ra and 'Chi 25.000.000' in ra
    # Nhãn dòng tiền cuối do Giám đốc chỉnh chữ (17/09 đổi 'Cầm:' → 'Tiền gốc:') — kiểm theo
    # CẤU TRÚC: hai dòng tiền, số dư gốc nằm trong <b>.
    assert ra.count('class="gcd-cuong__tien"') == 2 and '<b>25.000.000</b>' in ra
    assert '[99] Nhẫn thử 3.00c' in ra
    assert 'border' not in ra          # KHÔNG VIỀN: markup không được tự vẽ đường kẻ nào


def test_than_bang_cuong_giong_het_ban_khbl():
    """Thân bảng cuống hai kho phải giống TỪNG KÝ TỰ — chỉ khối chú thích đầu tệp được khác."""
    from pathlib import Path
    goc = Path(__file__).resolve().parent.parent
    cd = (goc / 'khcd' / 'templates' / '_gcd_cuong.html').read_text(encoding='utf-8')
    bl_p = Path('D:/PYTHON/KHBL/templates/pos/_gcd_cuong.html')
    if not bl_p.exists():
        pytest.skip('Không thấy kho KHBL trên máy này.')
    bl = bl_p.read_text(encoding='utf-8')
    than_cd = cd.split('#}', 1)[-1].lstrip()
    than_bl = bl.split('{% endcomment %}', 1)[-1].lstrip()
    assert than_cd.startswith('{% if b.nghiep_vu') and 'gcd-cuong__doc' in than_cd
    assert than_cd == than_bl


def test_phien_bo_qua_nghiep_vu_mo_khoa_bao_mat(monkeypatch):
    """Lượt 'Mở khóa báo mất' (op 8) ghi log với mọi khoản tiền = 0 và KHÔNG sinh cd_payments.

    Lấy nó làm 'lượt gần nhất' thì cuống in 'Mở khóa báo mất' kèm dòng Thu/Chi trống, giấu mất lượt
    việc có tiền thật. Cả hệ đều lọc operation_id<>8 — đường in phải lọc y vậy.
    """
    from khcd import db, gcd_print as P
    cau = []
    def gia(sql, args=None):
        cau.append(' '.join(sql.split()))
        if 'cd_loan_logs' in sql:
            return None
        return {}
    monkeypatch.setattr(db, 'one', gia)
    assert P._phien(_CTX_CUONG) is None
    assert any('operation_id<>8' in c.replace(' ', '') for c in cau), cau


def test_bang_cuong_rong_khong_in_dau_phay_tro(monkeypatch):
    """RENDER THẬT với ba ô rỗng: không được ra dấu phẩy trơ, không được ra nhãn Thu/Chi không số.

    Bài kiểm soi DICT không bắt được lỗi này — nó nằm trong template.
    """
    from jinja2 import Environment, FileSystemLoader
    from pathlib import Path
    from khcd import gcd_print as P, live_loans as live
    monkeypatch.setattr(P, '_mon', lambda ctx, layout: [])
    monkeypatch.setattr(live, 'latest', lambda _lid: None)
    monkeypatch.setattr(P, '_phien', lambda ctx: None)
    b = P._bang(_CTX_CUONG, G.mac_dinh())['cuong_bang_1']
    moi_truong = Environment(loader=FileSystemLoader(
        str(Path(__file__).resolve().parent.parent / 'khcd' / 'templates')), autoescape=True)
    ra = moi_truong.get_template('_gcd_cuong.html').render(b=b)
    assert 'gcd-cuong__doc' not in ra, 'Ô nghiệp vụ rỗng thì phải BỎ HẲN cột dọc, không in dấu phẩy'
    assert 'Thu/Chi:' not in ra, 'Không có số thì bỏ hẳn dòng, không in nhãn trơ'
    # phần không phụ thuộc sổ VẪN in: còn đúng MỘT dòng tiền (dư gốc), dòng thu/chi đã bỏ
    assert ra.count('class="gcd-cuong__tien"') == 1 and '<b>25.000.000</b>' in ra
    assert b['ma'] in ra


def test_buoc_nhay_cuong_khop_ban_khbl():
    """Hằng bước nhảy hai nửa cuống phải khớp KHBL từng số — nó quyết định chỗ đặt bảng dưới."""
    from pathlib import Path
    import ast
    assert abs(G.BUOC_CUONG_PCT - 46.81) < 0.005
    b1, b2 = G.BLOCK_MAP['cuong_bang_1'], G.BLOCK_MAP['cuong_bang_2']
    assert abs((b2['top'] - b1['top']) - G.BUOC_CUONG_PCT) <= 0.02
    p = Path('D:/PYTHON/KHBL/apps/pos/gcd_layout.py')
    if not p.exists():
        pytest.skip('Không thấy kho KHBL trên máy này.')
    cay = ast.parse(p.read_text(encoding='utf-8'))
    for n in cay.body:
        if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == 'BUOC_CUONG_PCT':
            assert ast.literal_eval(n.value) == G.BUOC_CUONG_PCT
            break
    else:
        raise AssertionError('KHBL chưa khai BUOC_CUONG_PCT')


# ── ĐƠN VỊ TRỌNG LƯỢNG + DÒNG TIỀN (Giám đốc chốt 17/09/2026) ─────────────────────────────────
def test_loai_vang_nhan_va_don_vi():
    """Quy tắc Giám đốc chốt 17/09/2026 — nhãn quy về MỘT cách viết, đơn vị theo mã."""
    from khcd import pawn_desk as D
    for ma in ('610', '18k', '61', ' 18K '):
        assert D.loai_vang(ma) == ('61', 'c'), ma
    for ma in ('980', '24k', '98'):
        assert D.loai_vang(ma) == ('98', 'c'), ma
    for ma in ('9999', 'N9999', '99.99', '99'):
        assert D.loai_vang(ma) == ('99', 'c'), ma
    for ma in ('sjc', 'SJC', 'pnj', 'PNJ'):
        assert D.loai_vang(ma) == ('sjc', 'c'), ma
    assert D.loai_vang('bk') == ('bk', 'g') and D.loai_vang('BK') == ('bk', 'g')
    # Không thuộc bảng → GIỮ NGUYÊN mã, KHÔNG in đơn vị (không đoán).
    for ma in ('vt', '#', 'khong-co-thuc'):
        assert D.loai_vang(ma) == (ma, ''), ma
    assert D.loai_vang('') == ('', '') and D.loai_vang(None) == ('', '')


def test_summary_quy_ve_mot_nhan_va_khong_doan_don_vi():
    """Cùng một loại vàng viết mấy kiểu vẫn ra MỘT nhãn; mã lạ thì không bịa đơn vị."""
    from khcd import pawn_desk as D
    mon = lambda g: dict(gold=g, description='Nhẫn thử', unit='', net='3')
    assert D.summary([mon('99')]) == '[99] Nhẫn thử 3.00c'
    assert D.summary([mon('N9999')]) == '[99] Nhẫn thử 3.00c'      # cùng loại, cùng nhãn
    assert D.summary([mon('18k')]) == '[61] Nhẫn thử 3.00c'
    assert D.summary([mon('24k')]) == '[98] Nhẫn thử 3.00c'
    assert D.summary([mon('pnj')]) == '[sjc] Nhẫn thử 3.00c'
    assert D.summary([mon('bk')]) == '[bk] Nhẫn thử 3.00g'
    assert D.summary([mon('vt')]) == '[vt] Nhẫn thử 3.00'          # chưa chắc → bỏ đơn vị
    assert D.summary([mon('99'), mon('bk')]) == '[99] Nhẫn thử 3.00c + [bk] Nhẫn thử 3.00g'
    assert D.summary([dict(gold='KHAC', description='Đồng hồ', unit='món', net='0')]) == '[KHÁC] Đồng hồ'


def test_dong_tien_theo_dau_khong_con_nhan(monkeypatch):
    from datetime import datetime as dtm
    """Ròng > 0 → 'Thu …' · < 0 → 'Chi …' · = 0 → để trống (template bỏ luôn dòng)."""
    from khcd import db, gcd_print as P
    def gia(thu, chi):
        def mot(sql, args=None):
            if 'cd_loan_logs' in sql:
                return {'id': 1, 'operation_id': 1, 'happened_at': dtm(2026, 9, 15, 14, 35),
                        'interest_from': dtm(2026, 9, 14), 'due_at': dtm(2026, 10, 14),
                        'days': 1, 'interest': 11000, 'principal_change': -7000000}
            return {'thu': thu, 'chi': chi}
        return mot
    monkeypatch.setattr(db, 'one', gia(1500000, 0))
    assert P._phien(_CTX_CUONG)['thu_chi'] == 'Thu 1.500.000'
    monkeypatch.setattr(db, 'one', gia(0, 25000000))
    assert P._phien(_CTX_CUONG)['thu_chi'] == 'Chi 25.000.000'
    # Một lượt vừa thu vừa chi: in SỐ RÒNG (cầm thêm 700.000, khấu lãi 205.000 ⇒ thực chi 495.000)
    monkeypatch.setattr(db, 'one', gia(205000, 700000))
    assert P._phien(_CTX_CUONG)['thu_chi'] == 'Chi 495.000'
    monkeypatch.setattr(db, 'one', gia(0, 0))
    assert P._phien(_CTX_CUONG)['thu_chi'] == ''


# ── KHÓA IN: Chuộc đồ · Thanh lý · Báo mất không cần in giấy (GĐ chốt 17/09/2026) ──────────────

def _p(state='ACTIVE', mat=0, terms='{}'):
    return {'loan_state': state, 'receipt_lost': mat, 'terms_json': terms}


def test_khoa_in_theo_trang_thai_phieu():
    from khcd import gcd_print as P
    assert P._khoa_in(_p()) == ''
    assert 'CHUỘC ĐỒ' in P._khoa_in(_p('REDEEMED'))
    assert 'THANH LÝ' in P._khoa_in(_p('LIQUIDATED'))
    assert 'BÁO MẤT' in P._khoa_in(_p(mat=1))
    # Báo mất đã MỞ KHÓA → in lại được.
    assert P._khoa_in(_p(mat=1, terms='{"lost_unlocked": true}')) == ''


def test_in_may_chu_tu_choi_phieu_khoa_truoc_khi_doc_bo_cuc(app, monkeypatch):
    from khcd import gcd_print as P
    monkeypatch.setattr(P.live, 'receipt_context', lambda lid: {'loan': _p('REDEEMED')})
    def cam(*a, **k):
        raise AssertionError('không được đọc bố cục / gửi máy in cho phiếu đã khóa in')
    monkeypatch.setattr(P.G, 'doc_bo_cuc', cam)
    monkeypatch.setattr(P.M, 'in_ngay', cam)
    with app.test_request_context('/camdo/bien-nhan/1/in-may-chu', method='POST'):
        kq = P.in_may_chu.__wrapped__(1) if hasattr(P.in_may_chu, '__wrapped__') else P.in_may_chu(1)
    assert kq['ok'] is False and kq['khoa'] is True and 'CHUỘC ĐỒ' in kq['ly_do']


def _dat_trang_thai(app, lid, state, mat=0, terms='{}'):
    from khcd import db
    with app.app_context():
        db.execute('UPDATE cd_loans SET loan_state=%s,receipt_lost=%s,terms_json=%s WHERE id=%s',
                   (state, mat, terms, lid))


@pytest.mark.parametrize('state,mat,terms', [
    ('REDEEMED', 0, '{}'), ('LIQUIDATED', 0, '{}'), ('ACTIVE', 1, '{}')])
def test_trang_in_tat_nut_in_khi_khoa(client, phieu, app, state, mat, terms):
    _dat_trang_thai(app, phieu, state, mat, terms)
    html = client.get('/camdo/bien-nhan/%d/giay' % phieu).get_data(as_text=True)
    assert 'id="gcd-nut-khoa" disabled' in html
    assert 'id="tracked-print-button"' not in html and 'id="gcd-nut-in"' not in html
    assert 'KHÔNG IN:' in html


def test_bao_mat_da_mo_khoa_van_in_duoc(client, phieu, app):
    _dat_trang_thai(app, phieu, 'ACTIVE', 1, '{"lost_unlocked": true}')
    html = client.get('/camdo/bien-nhan/%d/giay' % phieu).get_data(as_text=True)
    assert 'gcd-nut-khoa' not in html and 'KHÔNG IN:' not in html
    assert 'id="tracked-print-button"' in html or 'id="gcd-nut-in"' in html
