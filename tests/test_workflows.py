import secrets
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
import pytest
from khcd import db,services as svc
from khcd.domain import today,now,quote,BusinessError

def customer(client):
    r=client.post('/camdo/khach-hang/moi',data=dict(csrf_token='token',name='KH KIỂM THỬ',phone='0900000001',cccd='000000000001',addr='Dữ liệu thử',note=''))
    assert r.status_code==302
    return int(r.location.rsplit('/',1)[1])

def new_pawn(client,cid):
    data=dict(csrf_token='token',request_key=secrets.token_hex(16),customer_id=cid,gold1='99',wgg1='2.1234',whh1='0.1',mota1='Nhẫn thử nghiệm',value='10000000',daily_rate='0.1',date1=str(today()),term='30',safe='TEST',note='')
    r=client.post('/camdo/lap-phieu',data=data)
    assert r.status_code==302,r.data.decode()
    return int(r.location.rsplit('/',1)[1]),data

def action_data(app,pid,action='redeem'):
    with app.app_context():
        p=svc.pawn(pid)
        logs=db.one('SELECT COUNT(*) n FROM pawn_log WHERE pawn_id=%s AND status_id=4 AND DATE(date2)=%s',(pid,today()))
        q=quote(p,today(),0 if logs['n'] else 1)
    return dict(csrf_token='token',request_key=secrets.token_hex(16),fingerprint=p['fingerprint'],effective_date=str(today()),confirmed_total=str(q['total'] if action=='redeem' else q['interest']),new_due=str(today()+timedelta(days=60)))

def test_crud_and_exactly_once_redeem(app,client):
    cid=customer(client);pid,data=new_pawn(client,cid)
    assert client.post('/camdo/lap-phieu',data=data).status_code==302
    edit=action_data(app,pid);edit.update(safe='Két B',mota1='Nhẫn đã kiểm tra',mota2='',note='Cập nhật')
    assert client.post(f'/camdo/phieu-cam-do/{pid}/edit',data=edit).status_code==302
    pay=action_data(app,pid)
    assert client.post(f'/camdo/phieu-cam-do/{pid}/redeem',data=pay).status_code==302
    assert client.post(f'/camdo/phieu-cam-do/{pid}/redeem',data=pay).status_code==302
    with app.app_context():
        assert db.one('SELECT COUNT(*) n FROM pawn')['n']==1
        assert db.one('SELECT COUNT(*) n FROM pawn_log WHERE status_id=5')['n']==1
        assert svc.pawn(pid)['status']==5
        assert db.one("SELECT SUM(interest) n FROM khcd_event WHERE kind='redeem'")['n']==10000
    assert client.post(f'/camdo/khach-hang/{cid}/luu-tru',data=dict(csrf_token='token',reason='Đóng hồ sơ thử')).status_code==302
    assert 'KH KIỂM THỬ' not in client.get('/camdo/khach-hang').data.decode()
    assert 'KH KIỂM THỬ' in client.get('/camdo/khach-hang?archived=1').data.decode()
    assert client.post(f'/camdo/khach-hang/{cid}/khoi-phuc',data=dict(csrf_token='token')).status_code==302
    assert 'KH KIỂM THỬ' in client.get('/camdo/khach-hang').data.decode()

def test_renew_then_redeem_same_day_no_double_interest(app,client):
    pid,_=new_pawn(client,customer(client))
    with app.app_context():db.execute('UPDATE pawn SET date1=%s,date2=%s WHERE id=%s',(now()-timedelta(days=30),now()-timedelta(days=30),pid))
    renew=action_data(app,pid,'renew')
    assert renew['confirmed_total']=='300000'
    assert client.post(f'/camdo/phieu-cam-do/{pid}/renew',data=renew).status_code==302
    pay=action_data(app,pid)
    assert pay['confirmed_total']=='10000000'
    assert client.post(f'/camdo/phieu-cam-do/{pid}/redeem',data=pay).status_code==302
    with app.app_context():assert db.one('SELECT SUM(tienlai) n FROM pawn_log')['n']==300000

def test_transaction_rolls_back_when_audit_fails(app,client,monkeypatch):
    pid,_=new_pawn(client,customer(client));data=action_data(app,pid)
    def fail(*a,**kw):raise RuntimeError('simulated audit failure')
    monkeypatch.setattr(svc,'event',fail)
    with pytest.raises(RuntimeError):client.post(f'/camdo/phieu-cam-do/{pid}/redeem',data=data)
    with app.app_context():
        assert svc.pawn(pid)['status']==1
        assert db.one('SELECT COUNT(*) n FROM pawn_log WHERE status_id=5')['n']==0

def test_concurrent_redeem_only_one_commits(app,client):
    pid,_=new_pawn(client,customer(client));a=action_data(app,pid);b=dict(a,request_key=secrets.token_hex(16))
    with client.session_transaction() as s: login_session=dict(s)
    def submit(data):
        c=app.test_client()
        with c.session_transaction() as s:s.update(login_session)
        return c.post(f'/camdo/phieu-cam-do/{pid}/redeem',data=data).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:codes=list(pool.map(submit,[a,b]))
    assert sorted(codes)==[302,400]
    with app.app_context():assert db.one('SELECT COUNT(*) n FROM pawn_log WHERE status_id=5')['n']==1

def test_cancel_preserves_history_and_reverses_cash(app,client):
    pid,_=new_pawn(client,customer(client));data=action_data(app,pid);data['reason']='Lập nhầm, đã thu hồi tiền'
    assert client.post(f'/camdo/phieu-cam-do/{pid}/cancel',data=data).status_code==302
    with app.app_context():
        assert svc.pawn(pid)['status']==0
        assert db.one('SELECT SUM(total) n FROM pawn_log')['n']==0
        assert db.one('SELECT COUNT(*) n FROM pawn')['n']==1

def test_auth_csrf_validation_and_readonly(app,client):
    anon=app.test_client();assert anon.get('/camdo/khach-hang').status_code==302
    assert client.post('/camdo/khach-hang/moi',data=dict(name='X')).status_code==400
    cid=customer(client)
    assert client.post('/camdo/khach-hang/moi',data=dict(csrf_token='token',name='Duplicate',phone='0900000001')).status_code==400
    pid,data=new_pawn(client,cid)
    pay=action_data(app,pid);pay['confirmed_total']='1'
    assert client.post(f'/camdo/phieu-cam-do/{pid}/redeem',data=pay).status_code==400
    data.update(request_key=secrets.token_hex(16),gold1='#')
    assert client.post('/camdo/lap-phieu',data=data).status_code==400
    app.config['DB_READ_ONLY']=True
    assert client.post(f'/camdo/phieu-cam-do/{pid}/redeem',data=action_data(app,pid)).status_code==400

def test_all_pages_filters_and_xss_escaping(app,client):
    cid=customer(client);pid,_=new_pawn(client,cid)
    with app.app_context():db.execute('UPDATE customer SET name=%s WHERE id=%s',('<script>alert(1)</script>',cid))
    for url in ['/', '/?period=month','/camdo/phieu-cam-do','/camdo/phieu-cam-do?status=all','/camdo/lap-phieu',f'/camdo/phieu-cam-do/{pid}','/camdo/khach-hang',f'/camdo/khach-hang/{cid}','/camdo/thong-ke','/camdo/thong-ke?tab=audit']:
        r=client.get(url);assert r.status_code==200,(url,r.data.decode())
        assert b'<script>alert(1)</script>' not in r.data
    assert client.get('/camdo/thong-ke?start=2026-03-02&end=2026-01-01').status_code==400

def test_legacy_non_gold_requires_review(app,client):
    pid,_=new_pawn(client,customer(client))
    with app.app_context():db.execute("UPDATE pawn SET gold1='#' WHERE id=%s",(pid,))
    assert client.post(f'/camdo/phieu-cam-do/{pid}/redeem',data=action_data(app,pid)).status_code==400
    with app.app_context():assert svc.pawn(pid)['status']==1

def test_legacy_zero_second_asset_is_empty(app,client):
    pid,_=new_pawn(client,customer(client))
    with app.app_context():
        db.execute("UPDATE pawn SET gold2='0',wgg2=0,whh2=0 WHERE id=%s",(pid,))
        assert svc.pawn(pid)['supported_asset'] is True
        assert svc.pawn(pid)['gold2'] is None
    assert client.post(f'/camdo/phieu-cam-do/{pid}/redeem',data=action_data(app,pid)).status_code==302
