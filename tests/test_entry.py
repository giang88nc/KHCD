import secrets
from khcd import db
from khcd.domain import today


def test_inline_customer_then_create_once(app,client):
    created=client.post('/camdo/lap-phieu/khach-hang',data=dict(csrf_token='token',name='Khách tại quầy',phone='0900000099',cccd='000000000099',addr='Địa chỉ thử'))
    assert created.status_code==201
    cid=created.json['customer']['id']
    found=client.get('/camdo/lap-phieu/khach-hang?q=000000000099')
    assert found.json['customers'][0]['id']==cid
    duplicate=client.post('/camdo/lap-phieu/khach-hang',data=dict(csrf_token='token',name='Trùng khách',phone='0900000099'))
    assert duplicate.status_code==400 and 'đã có' in duplicate.json['error']
    data=dict(csrf_token='token',request_key=secrets.token_hex(16),customer_id=cid,gold1='99',wgg1='2',whh1='0.2',mota1='Nhẫn vàng',value='10000000',daily_rate='0.1',date1=str(today()),term='30')
    first=client.post('/camdo/lap-phieu',data=data)
    assert first.status_code==302
    assert client.post('/camdo/lap-phieu',data=data).location==first.location
    with app.app_context():
        assert db.one('SELECT COUNT(*) n FROM pawn')['n']==1
        assert db.one('SELECT SUM(total) n FROM pawn_log')['n']==-10000000
        assert db.one("SELECT COUNT(*) n FROM khcd_event WHERE kind='customer_create'")['n']==1
    for path in ['/camdo/lap-phieu','/camdo/lap-phieu']:
        page=client.get(path)
        assert page.status_code==200
        assert 'Khách tại quầy' in page.text
        assert '/static/img/ico/pawn.png' in page.text


def test_invalid_entry_preserves_input_and_no_money_write(app,client):
    created=client.post('/camdo/lap-phieu/khach-hang',data=dict(csrf_token='token',name='Khách thử',phone='0900000099'))
    cid=created.json['customer']['id']
    key=secrets.token_hex(16)
    data=dict(csrf_token='token',request_key=key,customer_id=cid,gold1='99',wgg1='2',whh1='3',mota1='Nhẫn "đặc biệt"',value='10000000',daily_rate='0.1',date1=str(today()),term='30',note='<script>alert(1)</script>')
    response=client.post('/camdo/lap-phieu',data=data)
    assert response.status_code==400
    assert key in response.text and '10000000' in response.text and 'Khách thử' in response.text
    assert '<script>alert(1)</script>' not in response.text
    assert '&lt;script&gt;' in response.text
    with app.app_context():assert db.one('SELECT COUNT(*) n FROM pawn_log')['n']==0


def test_entry_customer_auth_csrf_readonly_and_archive(app,client):
    anonymous=app.test_client()
    assert anonymous.get('/camdo/lap-phieu/khach-hang?q=090').status_code==302
    assert client.post('/camdo/lap-phieu/khach-hang',data={'phone':'0900000099'}).status_code==400
    created=client.post('/camdo/lap-phieu/khach-hang',data=dict(csrf_token='token',name='Khách thử',phone='0900000099'))
    cid=created.json['customer']['id']
    assert client.post(f'/camdo/khach-hang/{cid}/luu-tru',data=dict(csrf_token='token',reason='Thử lưu trữ')).status_code==302
    assert not client.get('/camdo/lap-phieu/khach-hang?q=0900000099').json['customers']
    assert f'data-phone="0900000099"' not in client.get(f'/camdo/lap-phieu?customer_id={cid}').text
    app.config['DB_READ_ONLY']=True
    blocked=client.post('/camdo/lap-phieu/khach-hang',data=dict(csrf_token='token',name='Không được ghi',phone='0900000088'))
    assert blocked.status_code==400
    with app.app_context():assert db.one('SELECT COUNT(*) n FROM customer')['n']==1
