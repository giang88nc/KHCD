"""Mẫu in GIẤY CẦM ĐỒ A5 ngang: bố cục đọc chéo khj_bl, CSS sinh ra, và trang in.

CHẠY: chỉ đích danh tệp này, không bao giờ chạy cả bộ và không dùng discover.
    .venv\\Scripts\\python.exe -m pytest tests/test_gcd_print.py -q
Các bài cần CSDL sẽ TỰ BỎ QUA nếu chưa đặt KHCD_TEST_ENV (conftest tạo CSDL nháp rồi xoá).
Nhóm bài thuần hàm (đọc số, gộp giá trị, sinh CSS) chạy được không cần CSDL.
"""
import json
import os

import pytest

from khcd import gcd_layout as G


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
    assert len(G.BLOCKS) == 18          # 17 khối chữ + khối ẢNH mã vạch (thêm 16/09/2026)
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
    assert 'Cửa hàng có giữ các giấy tờ' not in G.khoi_sat_mep(m)
    assert 'Cửa hàng có giữ các giấy tờ' in G.khoi_sat_mep(G._gop(m, {'giay_to': {'an': 0}}))
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
