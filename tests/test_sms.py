"""GỬI SMS: mức nhắc theo chu kỳ, ẩn sau khi đã nhắc, tắt/hoãn, tự hủy khi có giao dịch mới, đối soát 2 sổ.
Chạy trên CSDL nháp (chép DDL 2 bảng zalo từ khj_bl); không đụng sổ thật."""
import json, re
from datetime import timedelta
import pytest
from test_native_loans import native, create, opdata
from khcd import db, sms as S
from khcd.domain import today, now

BASE = '/camdo/gui-sms'


@pytest.fixture
def so_zns(native):
    with native.app_context():
        native.config['ZNS_DB'] = native.config['DB_NAME']
        for t in ('zalo_templates', 'zalo_messages'):
            ddl = db.one('SHOW CREATE TABLE `khj_bl`.`' + t + '`')['Create Table']
            db.execute('DROP TABLE IF EXISTS `' + t + '`'); db.execute(re.sub(r' AUTO_INCREMENT=\d+', '', ddl))
        for t in ('cd_sms_log', 'cd_sms_control', 'cd_sms_rules', 'cd_sms_settings', 'cd_sms_rules_history'): db.execute('DROP TABLE IF EXISTS ' + t)
        S._schema_ok.clear()
        db.execute("INSERT INTO zalo_templates (oa_account_id,template_id,template_name,template_tag,status,quality,price_sdt,price_uid,params_json,raw_json,active,last_synced_at,created_at,updated_at) VALUES "
                   "(1,'635511','Thông báo cầm đồ','TRANSACTION','ENABLE','null',300,210,%s,'{}',1,NOW(),NOW(),NOW())",
                   (json.dumps([{'name': k, 'require': True, 'type': 'STRING', 'maxLength': 30} for k in ('pawn_code', 'customer_name', 'anh_chi', 'promise_date', 'days', 'notes')]),))
        # Dòng của CARE360 — không bao giờ được đụng
        db.execute("INSERT INTO zalo_messages (oa_account_id,external_template_id,channel,source_type,trn_id,recipient_ciphertext,recipient_masked,recipient_hash,template_data_json,tracking_id,dedupe_key,status,attempt_count,created_at,updated_at) "
                   "VALUES (1,'606575','phone','auto_rule','TRB1','x','090***001','h','{}','trk_care360','dk_care360','queued',0,NOW(),NOW())")
    return native


def lui_ngay(app, lid, ngay):
    with app.app_context():
        moc = now() - timedelta(days=ngay)
        db.execute('UPDATE cd_loan_logs SET happened_at=%s WHERE loan_id=%s', (moc, lid))
        db.execute('UPDATE cd_loans SET opened_at=%s,interest_from=%s,due_at=%s WHERE id=%s', (moc, moc, moc + timedelta(days=30), lid))

def gio(h=9):
    return (now() + timedelta(days=1)).replace(hour=h, minute=0).strftime('%Y-%m-%dT%H:%M')

def len_lich(client, lid, **kw):
    return client.post(BASE + '/len-lich', data=dict(csrf_token='token', loan=[str(lid)], gio=gio(), **kw), follow_redirects=True)

def q(app, sql, params=()):
    with app.app_context(): return db.all(sql, params)

def da_gui(app):
    with app.app_context(): db.execute("UPDATE zalo_messages SET status='sent',sent_at=NOW() WHERE source_type='khcd_pawn' AND status='queued'")


def test_phan_loai_sdt_xung_ho_ten(so_zns):
    with so_zns.test_request_context('/'):
        assert [S.phan_loai(d) for d in (14, 15, 29, 30, 44, 45, 59, 60, 67, 400)] == ['', 'nhac1', 'nhac1', 'nhac2', 'nhac2', 'nhac3', 'nhac3', 'nhac4', 'nhac4', 'nhac4']
        qt = S.quy_tac(); notes = {m['key']: m['notes'] for m in qt['muc']}
        assert 'thanh lý trong 15 ngày' in notes['nhac3'] and 'THANH LÝ trong 7 ngày' in notes['nhac4'] and qt['han_chot'] == 67
        # Xưng hô CHỈ theo Gender của KK — không đoán theo tên
        assert S.anh_chi_cua(True) == 'Anh' and S.anh_chi_cua(False) == 'Chị' and S.anh_chi_cua(None) == 'Anh/Chị'
        # Tiền tố trong tên THẮNG Gender khi mâu thuẫn (Gender=False trên KK phần lớn là mặc định); không có tiền tố thì không đoán
        assert S.anh_chi_cua(False, 'Anh Thành') == 'Anh' and S.anh_chi_cua(True, 'chị Hoa') == 'Chị' and S.anh_chi_cua(None, 'Anh Tuấn') == 'Anh'
        assert S.anh_chi_cua(None, 'Nguyễn Thị Hoa') == 'Anh/Chị' and S.anh_chi_cua(False, 'Nguyễn Anh Thư') == 'Chị' and S.anh_chi_cua(True, 'Anh') == 'Anh'
    assert S.ten_khong_tien_to('Chị Quỳnh') == 'Quỳnh' and S.ten_khong_tien_to('Anh Tuấn') == 'Tuấn' and S.ten_khong_tien_to('ANH  TUẤN') == 'TUẤN'
    assert S.ten_khong_tien_to('Nguyễn Thị Anh') == 'Nguyễn Thị Anh' and S.ten_khong_tien_to('Anh') == 'Anh' and S.ten_khong_tien_to('') == ''
    d, local, masked, h = S.chuan_hoa_sdt('0912 345 678')
    assert (d, local, masked) == ('84912345678', '0912345678', '091***678') and len(h) == 64
    assert S.chuan_hoa_sdt('+84912345678')[1] == '0912345678' and S.chuan_hoa_sdt('02838123456') is None and S.chuan_hoa_sdt('') is None
    assert S.dedupe(1, 10, 'nhac1') != S.dedupe(1, 11, 'nhac1'), 'khóa chống trùng phải theo CHU KỲ'


def test_quy_tac_luu_rang_buoc_va_bien_notes(so_zns, client, monkeypatch):
    app = so_zns; lid, _ = create(client); lui_ngay(app, lid, 12)
    from khcd import customer_master as M
    def hydrate(rows):
        for r in rows: r.update(customer_name='Chị Quỳnh', customer_phone='0912345678', customer_gender=False)
        return rows
    monkeypatch.setattr(M, 'hydrate', hydrate)
    assert 'name="loan"' not in client.get(BASE).get_data(as_text=True)               # 12 ngày < 15
    form = dict(csrf_token='token', han_chot='40', gio_tu='8', gio_den='20', gio_mac_dinh='9', xung_ho_mac_dinh='Quý khách')
    for n, days, notes in ((1, 10, 'Lần {lan}: quá {days} ngày, thanh lý sau ngày {ngay_thanh_ly} (còn {so_ngay_con_lai} ngày).'), (2, 20, 'Lần 2'), (3, 30, 'Lần 3'), (4, 35, 'Lần 4')):
        form.update({'days_%d' % n: str(days), 'notes_%d' % n: notes, 'label_%d' % n: 'Nhắc lần %d' % n, 'active_%d' % n: '1'})
    url = BASE + '/quy-tac'
    assert client.post(url, data=dict(form, days_2='5')).status_code == 400                       # ngày phải tăng dần
    assert client.post(url, data=dict(form, han_chot='35')).status_code == 400                    # hạn chót > lần cuối
    assert client.post(url, data=dict(form, notes_2='xem http://x.vn')).status_code == 400        # không link
    assert client.post(url, data=dict(form, notes_2='{ten_la}')).status_code == 400                # biến lạ
    assert client.post(url, data=form).status_code == 302
    assert len(q(app, 'SELECT id FROM cd_sms_rules_history')) >= 5
    html = client.get(BASE).get_data(as_text=True)
    assert 'name="loan"' in html and 'Chị Quỳnh' in html                                          # 12 ngày ≥ 10 → tới hạn lần 1; cột khách: "Chị" + "Quỳnh"
    len_lich(client, lid)
    z = q(app, "SELECT template_data_json t,customer_name FROM zalo_messages WHERE source_type='khcd_pawn'")[0]; bien = json.loads(z['t'])
    han = (now() - timedelta(days=12) + timedelta(days=40)).strftime('%d/%m/%Y')
    assert bien['anh_chi'] == 'Chị' and bien['customer_name'] == 'Quỳnh' and z['customer_name'] == 'Quỳnh'
    assert bien['promise_date'] == (now() - timedelta(days=12)).strftime('%d/%m/%Y') and bien['days'] == '12'          # quá hạn kể từ ngày GD gần nhất
    assert bien['notes'] == 'Lần 1: quá 12 ngày, thanh lý sau ngày %s (còn 28 ngày).' % han
    # Tài khoản thường: xem được, không lưu được
    with app.app_context():
        from khcd import auth
        db.execute('UPDATE ' + auth.source_table() + ' SET is_superuser=0 WHERE id=1'); user = auth.sync_user(username='khj_admin'); sig = auth.session_signature(user)
    with client.session_transaction() as s_: s_['auth_signature'] = sig
    assert client.post(url, data=form).status_code == 400 and 'Chỉ tài khoản quản trị' in client.get(BASE).get_data(as_text=True)


def test_da_nhac_thi_an_toi_muc_ke_va_4_muc(so_zns, client):
    app = so_zns; lid, _ = create(client); lui_ngay(app, lid, 20)
    html = client.get(BASE).get_data(as_text=True)
    assert 'Nhắc lần 1' in html and 'name="loan"' in html and 'sendsms.png' in html
    assert 'Đã lên lịch 1 tin mới' in len_lich(client, lid).get_data(as_text=True)
    z = q(app, "SELECT * FROM zalo_messages WHERE source_type='khcd_pawn'"); g = q(app, 'SELECT * FROM cd_sms_log')
    assert len(z) == 1 and len(g) == 1 and g[0]['zalo_message_id'] == z[0]['id'] and g[0]['level'] == 'nhac1' and g[0]['tracking_id'] == z[0]['tracking_id']
    m = z[0]; bien = json.loads(m['template_data_json'])
    assert m['status'] == 'queued' and m['channel'] == 'phone' and m['external_template_id'] == '635511' and m['recipient_ciphertext'] == 'khcd_no_cipher' and m['send_rule_id'] is None
    assert m['customer_phone'] == '0900000001' and m['recipient_masked'] == '090***001' and m['dedupe_key'] == S.dedupe(lid, g[0]['cycle_log_id'], 'nhac1')
    assert set(bien) == {'pawn_code', 'customer_name', 'anh_chi', 'promise_date', 'days', 'notes'} and bien['days'] == '20' and bien['notes'].startswith('Nhắc lần 1')
    # Đang chờ: không tick được; đã gửi: vẫn ẩn khỏi "Cần nhắc" cho tới mức kế
    assert 'name="loan"' not in client.get(BASE).get_data(as_text=True)
    da_gui(app); html = client.get(BASE).get_data(as_text=True)
    assert 'name="loan"' not in html and q(app, 'SELECT status FROM cd_sms_log')[0]['status'] == 'sent'
    assert 'Đã nhắc' in client.get(BASE + '?loai=tat_ca').get_data(as_text=True)
    # Lên lịch lại mức 1 trong cùng chu kỳ → bị từ chối
    assert 'đã xử lý trong chu kỳ này' in len_lich(client, lid, muc_chon='nhac1').get_data(as_text=True)
    # d=31 → hiện lại ở mức 2; d=46 → mức 3 báo thanh lý 15 ngày; d=61 → mức 4 cuối báo 7 ngày
    for ngay, muc, cau in ((31, 'nhac2', 'Nhắc lần 2'), (46, 'nhac3', 'thanh lý trong 15 ngày'), (61, 'nhac4', 'THANH LÝ trong 7 ngày')):
        lui_ngay(app, lid, ngay)
        assert 'name="loan"' in client.get(BASE + '?loai=' + muc).get_data(as_text=True), muc
        len_lich(client, lid)
        dong = q(app, 'SELECT level,vars_json FROM cd_sms_log ORDER BY id DESC LIMIT 1')[0]
        assert dong['level'] == muc and cau in json.loads(dong['vars_json'])['notes']
        da_gui(app); client.get(BASE)
    # Đủ 4 lần + quá hạn chót → nhóm Chờ thanh lý, không còn tick, không có tin thanh lý riêng
    lui_ngay(app, lid, 70); html = client.get(BASE + '?loai=cho_thanh_ly').get_data(as_text=True)
    assert 'Chờ thanh lý' in html and 'name="loan"' not in html and len(q(app, "SELECT id FROM zalo_messages WHERE source_type='khcd_pawn'")) == 4
    # Popup XEM biên nhận có lịch sử nhắc
    assert 'Nhắc khách (ZNS)' in client.get('/camdo/bien-nhan/%d/xem' % lid).get_data(as_text=True)


def test_nhay_coc_chi_mot_tin_va_sua_huy_doi_gio(so_zns, client):
    app = so_zns; lid, _ = create(client); lui_ngay(app, lid, 50)
    len_lich(client, lid)                                   # chưa nhắn lần nào, d=50 → chỉ MỘT tin mức 3
    g = q(app, 'SELECT * FROM cd_sms_log'); assert len(g) == 1 and g[0]['level'] == 'nhac3'; mid = g[0]['id']
    len_lich(client, lid, ghi_chu='Gọi lại chiều')          # upsert vào tin đang chờ
    assert len(q(app, 'SELECT id FROM cd_sms_log')) == 1 and json.loads(q(app, "SELECT template_data_json t FROM zalo_messages WHERE source_type='khcd_pawn'")[0]['t'])['notes'] == 'Gọi lại chiều'
    assert client.post(BASE + '/%d/sua' % mid, data=dict(csrf_token='token', gio=gio(22), notes='x', anh_chi='Chị')).status_code == 400
    assert client.post(BASE + '/%d/sua' % mid, data=dict(csrf_token='token', gio=gio(15), notes='Hẹn 25/09', anh_chi='Chị')).status_code == 302
    z = q(app, "SELECT scheduled_at,template_data_json FROM zalo_messages WHERE source_type='khcd_pawn'")[0]
    assert z['scheduled_at'].hour == 15 and json.loads(z['template_data_json'])['anh_chi'] == 'Chị'
    assert client.post(BASE + '/doi-gio', data=dict(csrf_token='token', msg=[str(mid)], gio=gio(11))).status_code == 302
    assert q(app, "SELECT scheduled_at s FROM zalo_messages WHERE source_type='khcd_pawn'")[0]['s'].hour == 11 and q(app, 'SELECT scheduled_at s FROM cd_sms_log')[0]['s'].hour == 11
    assert client.post(BASE + '/%d/huy' % mid, data=dict(csrf_token='token', ly_do='thử')).status_code == 302
    assert q(app, "SELECT status FROM zalo_messages WHERE source_type='khcd_pawn'")[0]['status'] == 'cancelled' and q(app, 'SELECT status FROM cd_sms_log')[0]['status'] == 'cancelled'
    assert q(app, "SELECT status FROM zalo_messages WHERE source_type='auto_rule'")[0]['status'] == 'queued'      # dòng CARE360 nguyên vẹn
    len_lich(client, lid)                                   # hủy rồi lên lịch lại → mở lại chính dòng cũ
    assert [r['status'] for r in q(app, 'SELECT status FROM cd_sms_log')] == ['queued'] and len(q(app, "SELECT id FROM zalo_messages WHERE source_type='khcd_pawn'")) == 1


def test_giao_dich_moi_tu_huy_tin_cho_va_mo_chu_ky_moi(so_zns, client):
    app = so_zns; lid, _ = create(client); lui_ngay(app, lid, 20); len_lich(client, lid)
    r = client.post(f'/camdo/bien-nhan/{lid}/chot-phien', data=opdata(client, lid, 4)); assert r.status_code == 200, r.get_data(as_text=True)
    z = q(app, "SELECT status,cancel_reason FROM zalo_messages WHERE source_type='khcd_pawn'")[0]
    assert z['status'] == 'cancelled' and 'giao dịch mới' in z['cancel_reason'] and q(app, 'SELECT status FROM cd_sms_log')[0]['status'] == 'cancelled'
    assert 'name="loan"' not in client.get(BASE).get_data(as_text=True)              # vừa gia hạn: d=0, chưa tới hạn
    lui_ngay(app, lid, 16); len_lich(client, lid)                                     # chu kỳ mới → lại được nhắc lần 1 (khóa khác)
    g = q(app, 'SELECT level,status,cycle_log_id FROM cd_sms_log ORDER BY id')
    assert [(x['level'], x['status']) for x in g] == [('nhac1', 'cancelled'), ('nhac1', 'queued')] and g[0]['cycle_log_id'] != g[1]['cycle_log_id']


def test_tat_hoan_nhac_va_doi_soat(so_zns, client):
    app = so_zns; lid, _ = create(client); lui_ngay(app, lid, 20); len_lich(client, lid)
    url = BASE + '/phieu/%d/nhac' % lid
    assert client.post(url, data=dict(csrf_token='token', che_do='tat', ly_do='')).status_code == 400            # bắt buộc lý do
    assert client.post(url, data=dict(csrf_token='token', che_do='tat', ly_do='Khách quen, tự ra')).status_code == 302
    assert q(app, "SELECT status FROM zalo_messages WHERE source_type='khcd_pawn'")[0]['status'] == 'cancelled'     # tắt nhắc → hủy tin chờ
    assert 'name="loan"' not in client.get(BASE).get_data(as_text=True) and 'Khách quen' in client.get(BASE + '?loai=khong_nhac').get_data(as_text=True)
    assert 'đang tắt nhắc' in len_lich(client, lid).get_data(as_text=True).lower()
    assert client.post(url, data=dict(csrf_token='token', che_do='bat')).status_code == 302
    assert 'name="loan"' in client.get(BASE).get_data(as_text=True)
    assert client.post(url, data=dict(csrf_token='token', che_do='hoan', ly_do='Hẹn ra tiệm', den_ngay=str(today() - timedelta(days=1)))).status_code == 400
    assert client.post(url, data=dict(csrf_token='token', che_do='hoan', ly_do='Hẹn ra tiệm', den_ngay=str(today() + timedelta(days=5)))).status_code == 302
    assert 'name="loan"' not in client.get(BASE).get_data(as_text=True)
    client.post(url, data=dict(csrf_token='token', che_do='bat')); len_lich(client, lid)
    # Đối soát: dòng bên sổ KHBL biến mất → log 'missing' + băng cảnh báo; dòng khcd_pawn không có log cũng báo
    with app.app_context():
        db.execute("DELETE FROM zalo_messages WHERE source_type='khcd_pawn' AND status='queued'")
        db.execute("INSERT INTO zalo_messages (oa_account_id,external_template_id,channel,source_type,trn_id,recipient_ciphertext,recipient_masked,recipient_hash,template_data_json,tracking_id,dedupe_key,status,attempt_count,created_at,updated_at) "
                   "VALUES (1,'635511','phone','khcd_pawn','X','x','090***001','h','{}','trk_mo_coi','dk_mo_coi','queued',0,NOW(),NOW())")
    html = client.get(BASE + '?tab=loi').get_data(as_text=True)
    assert 'ĐỐI SOÁT' in html and 'mất bên sổ KHBL' in html and q(app, "SELECT COUNT(*) n FROM cd_sms_log WHERE status='missing'")[0]['n'] == 1


def test_khong_sdt_va_so_zns_hong(so_zns, client, monkeypatch):
    app = so_zns; lid, _ = create(client); lui_ngay(app, lid, 5)
    assert 'name="loan"' not in client.get(BASE).get_data(as_text=True)               # 5 ngày: chưa tới hạn nhắc
    lui_ngay(app, lid, 70)
    with app.app_context(): db.execute("UPDATE cd_loans SET phone='02838' WHERE id=%s", (lid,))
    from khcd import customer_master as M
    monkeypatch.setattr(M, 'hydrate', lambda rows: rows)
    html = client.get(BASE + '?loai=nhac4').get_data(as_text=True)
    assert 'Nhắc lần 4 (cuối)' in html and '⛔' in html and 'name="loan"' not in html
    assert 'không có SĐT' in len_lich(client, lid).get_data(as_text=True)
    app.config['ZNS_DB'] = 'khj_khong_co_db_nay'
    r = client.get(BASE); assert r.status_code == 200 and 'Chưa đọc được sổ tin ZNS' in r.get_data(as_text=True)
