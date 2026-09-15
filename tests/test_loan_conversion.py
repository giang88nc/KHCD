import pytest
from khcd import db, loan_conversion as C, customer_master as M, services
from khcd.domain import BusinessError, now

BASE='/camdo/phieu-cam-do/chuyen-doi'

@pytest.fixture
def receipt(app,monkeypatch):
    def get(cid):return {'customer':dict(id=cid,name='Khách thử chuyển đổi',phone='0900000001',phone2='',phone3='')}
    monkeypatch.setattr(M,'get',get)
    timestamp=now()
    with app.app_context():
        pid=db.execute("INSERT INTO pawn (sku,phone,date1,date2,date3,gold1,wgg1,whh1,mota1,value,percent,status) VALUES ('CONVERT_TEST','0900000001',%s,%s,%s,'99',2,0.1,'Nhẫn',10000000,3,1)",(timestamp,timestamp,timestamp))
        db.execute("INSERT INTO khcd_pawn_customer (pawn_id,pmv_cust_id,source,linked_at) VALUES (%s,'CU_TEST','selected',%s)",(pid,now()))
        db.execute('INSERT INTO pawn_log (pawn_id,status_id,date1,date2,date3,sotien,tienlai,total,mbank,percent,days) VALUES (%s,1,%s,%s,%s,10000000,0,-4000000,-6000000,3,30)',(pid,timestamp,timestamp,timestamp))
    return pid

def preview(client,pid):
    r=client.get(BASE+'/doi-soat',query_string={'pid':pid});assert r.status_code==200,r.text
    return r.json

def save(client,pid,p):
    return client.post(BASE+'/luu',data={'csrf_token':'token','pid':pid,'review_hash':p['review_hash'],'confirmed':'yes'})

def test_conversion_preserves_source_money_and_is_idempotent(app,client,receipt):
    with app.app_context():before=C.source(receipt)
    p=preview(client,receipt);assert p['can_convert'],p['checks']
    r=save(client,receipt,p);assert r.status_code==200,r.text
    assert save(client,receipt,p).json['loan_id']==r.json['loan_id']
    assert preview(client,receipt)['converted']
    with app.app_context():
        assert C.source(receipt)==before
        loan=db.one('SELECT * FROM cd_loans');assert loan['phone']=='0900000001' and loan['cust_id']=='CU_TEST'
        assert loan['loan_state']=='ACTIVE' and loan['last_operation_id']==1 and loan['migration_state']=='STAGED'
        assert db.one('SELECT SUM(amount) n FROM cd_payments')['n']==10000000
        assert db.one('SELECT COUNT(*) n FROM cd_loan_logs')['n']==1
        assert db.one("SELECT COUNT(*) n FROM khcd_event WHERE kind='loan_convert'")['n']==1

def test_changed_source_after_preview_rejected(app,client,receipt):
    p=preview(client,receipt)
    with app.app_context():db.execute("UPDATE pawn SET note='changed' WHERE id=%s",(receipt,))
    assert save(client,receipt,p).status_code==409
    with app.app_context():assert db.one('SELECT COUNT(*) n FROM cd_loans')['n']==0

def test_log_failure_rolls_back_every_destination(app,client,receipt,monkeypatch):
    p=preview(client,receipt)
    monkeypatch.setattr(services,'event',lambda *a,**kw:(_ for _ in ()).throw(BusinessError('audit failed')))
    assert save(client,receipt,p).status_code==409
    with app.app_context():
        for table in C.TABLES:assert db.one('SELECT COUNT(*) n FROM '+table)['n']==0

def test_mismatch_report_is_detailed_and_cannot_be_bypassed(app,client,receipt):
    with app.app_context():db.execute('UPDATE pawn_log SET total=-1 WHERE pawn_id=%s',(receipt,))
    p=preview(client,receipt);assert not p['can_convert']
    assert any(c['code']=='CASHFLOW' and c['state']=='error' and c['source']!=c['target'] for c in p['checks'])
    assert save(client,receipt,p).status_code==409

def test_missing_customer_and_history_are_not_invented(app,client,receipt):
    with app.app_context():
        db.execute('DELETE FROM pawn_log WHERE pawn_id=%s',(receipt,));db.execute('DELETE FROM khcd_pawn_customer WHERE pawn_id=%s',(receipt,))
    p=preview(client,receipt)
    assert {'CUSTOMER','HISTORY'}<={c['code'] for c in p['checks'] if c['state']=='error'}
    assert not p['can_convert']

def test_admin_csrf_and_readonly(app,client,receipt,monkeypatch):
    p=preview(client,receipt)
    assert client.post(BASE+'/luu',data={'pid':receipt}).status_code==400
    app.config['DB_READ_ONLY']=True
    assert save(client,receipt,p).status_code==409
    from khcd import auth
    monkeypatch.setattr(auth,'current_user',lambda:dict(is_superuser=False))
    assert client.get(BASE+'/doi-soat?pid='+str(receipt)).status_code==403

def test_existing_copy_drift_is_reported_without_overwrite(app,client,receipt):
    p=preview(client,receipt);assert save(client,receipt,p).status_code==200
    with app.app_context():db.execute("UPDATE cd_loan_items SET description='tampered'")
    p=preview(client,receipt);assert not p['converted'] and not p['can_convert']
    assert any(c['code']=='EXISTING' and c['state']=='error' for c in p['checks'])
    assert save(client,receipt,p).status_code==409

def test_principal_changes_are_not_extra_discount_columns(app,client,receipt):
    with app.app_context():
        for op,amount,li,extra,discount,cash in [(2,2000000,100000,2000,1000,-1899000),(3,1000000,50000,0,0,1050000),(5,11000000,20000,0,0,11020000)]:
            db.execute('INSERT INTO pawn_log (pawn_id,status_id,date1,date2,date3,sotien,tienlai,tienthem,tienbot,total,mbank,percent,days) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0,3,1)',(receipt,op,now(),now(),now(),amount,li,extra,discount,cash))
        db.execute('UPDATE pawn SET value=11000000,status=5 WHERE id=%s',(receipt,))
    p=preview(client,receipt);assert p['can_convert'],p['checks'];assert p['summary']['principal']=='0'
    assert save(client,receipt,p).status_code==200
    with app.app_context():
        loan=db.one('SELECT loan_state,principal_balance FROM cd_loans');assert loan=={'loan_state':'REDEEMED','principal_balance':0}
        row=db.one('SELECT principal_change,extra_amount,discount_amount FROM cd_loan_logs WHERE operation_id=2')
        assert row=={'principal_change':2000000,'extra_amount':2000,'discount_amount':1000}

def test_two_concurrent_conversions_create_one_copy(app,client,receipt):
    from concurrent.futures import ThreadPoolExecutor
    from flask import session
    p=preview(client,receipt)
    def run():
        with app.test_request_context():
            session.update(user_id=1,user='khj_admin')
            return C.convert(receipt,p['review_hash'])
    with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(lambda _:run(),range(2)))
    assert ids[0]==ids[1]
    with app.app_context():assert db.one('SELECT COUNT(*) n FROM cd_loans')['n']==1

def test_photo_and_multiple_items_are_preserved(app,client,receipt):
    import json
    items=[dict(gold='99',description='Nhẫn',unit='chỉ',gross='2',stone='0.1',net='1.9',price='1000000',subtotal='1900000')]*3
    with app.app_context():
        db.execute("UPDATE pawn SET gold2='99',wgg2=2,whh2=0.1,mota2='Nhẫn' WHERE id=%s",(receipt,))
        db.execute('INSERT INTO khcd_pawn_desk (pawn_id,items_json,employee_id,employee_name,payment_json,content) VALUES (%s,%s,%s,%s,%s,%s)',(receipt,json.dumps(items),'EMP_TEST','NV thử','{}','Nội dung đầy đủ'))
        db.execute("INSERT INTO khcd_pawn_photo (pawn_id,kind,data) VALUES (%s,'anh_qr',%s)",(receipt,b'PHOTO_TEST'))
    p=preview(client,receipt);assert p['can_convert'],p['checks']
    assert save(client,receipt,p).status_code==200
    with app.app_context():
        assert db.one('SELECT COUNT(*) n FROM cd_loan_items')['n']==3
        loan=db.one('SELECT documents_json,legacy_json FROM cd_loans')
        assert json.loads(loan['documents_json'])['pawn_photo_refs'][0]['kind']=='anh_qr'
        assert json.loads(loan['legacy_json'])['desk']['content']=='Nội dung đầy đủ'

def test_customer_bridge_failure_is_a_blocking_detail(client,receipt,monkeypatch):
    def fail(cid):raise M.Unavailable('KK không kết nối được')
    monkeypatch.setattr(M,'get',fail)
    p=preview(client,receipt);assert not p['can_convert']
    assert any(c['code']=='KK_UNAVAILABLE' and c['detail']=='KK không kết nối được' for c in p['checks'])
