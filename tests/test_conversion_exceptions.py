import json
from datetime import datetime

import pytest
from khcd import db, loan_conversion as C, customer_master as M
from test_loan_conversion import receipt, preview, save, BASE


def inspect_exception(client, pid):
    response=client.get(BASE+'/doi-soat',query_string={'pid':pid,'allow_exceptions':'yes'})
    assert response.status_code==200,response.text
    return response.json


def submit(client, pid, plan, mode='yes', batch=False):
    return client.post(BASE+('/hang-loat/luu-phieu' if batch else '/luu'),data={
        'csrf_token':'token','pid':pid,'confirmed':'yes','review_hash':plan['review_hash'],'allow_exceptions':mode})


def change_dates(app, pid, timestamp):
    with app.app_context():
        db.execute('UPDATE pawn SET date1=%s,date2=%s,date3=%s WHERE id=%s',(timestamp,timestamp,timestamp,pid))
        db.execute('UPDATE pawn_log SET date1=%s,date2=%s,date3=%s WHERE pawn_id=%s',(timestamp,timestamp,timestamp,pid))


@pytest.mark.parametrize('batch',[False,True])
def test_approved_errors_preserved_and_audited(app,client,receipt,batch):
    with app.app_context():
        db.execute('DELETE FROM khcd_pawn_customer WHERE pawn_id=%s',(receipt,))
        db.execute("UPDATE pawn SET gold1='0',gold2='0',mota1='KHÁC: tài sản cũ' WHERE id=%s",(receipt,))
        db.execute('UPDATE pawn_log SET total=-1 WHERE pawn_id=%s',(receipt,))
        before=C.source(receipt)
    strict=preview(client,receipt)
    assert not strict['can_convert'] and save(client,receipt,strict).status_code==409
    plan=inspect_exception(client,receipt)
    assert plan['can_convert'],plan['checks']
    assert {c['code'] for c in plan['exception_policy']['accepted']}==C.EXCEPTION_CODES
    assert len([c for c in plan['checks'] if c.get('accepted_exception')])==3
    result=submit(client,receipt,plan,batch=batch)
    assert result.status_code==200,result.text
    assert submit(client,receipt,plan,batch=batch).json['loan_id']==result.json['loan_id']
    with app.app_context():
        assert C.source(receipt)==before
        loan,target=C.target(receipt)
        assert loan['cust_id']=='' and json.loads(loan['customer_snapshot']) is None
        assert not target['items'] and len(target['logs'])==1
        assert sum(p['amount'] for p in target['payments'])==6000001
        policy=C.stored_exceptions(loan)
        assert policy==plan['exception_policy']
        assert policy['qualifying_log_id']==before['logs'][0]['id']
        assert loan['target_hash']==C.plan_hash(target)
        audit=db.one("SELECT after_json FROM khcd_event WHERE kind='loan_convert'")
        assert json.loads(audit['after_json'])['exception_policy']==policy
    detail=client.get('/camdo/bien-nhan/'+str(result.json['loan_id']))
    assert detail.status_code==200 and 'KHÁC: tài sản cũ' in detail.text
    checks=client.get('/camdo/bien-nhan/'+str(result.json['loan_id'])+'/doi-soat').json['checks']
    assert len([c for c in checks if c.get('accepted_exception')])==3
    assert not any(c['state']=='error' and c.get('code') in C.EXCEPTION_CODES for c in checks)


@pytest.mark.parametrize('timestamp,eligible',[
    (datetime(2026,3,14),True),
    (datetime(2026,3,13,23,59,59),False),
    (datetime(2026,9,14,12),True),
    (datetime(2026,9,14,12,0,1),False),
])
def test_six_calendar_month_window(app,client,receipt,monkeypatch,timestamp,eligible):
    monkeypatch.setattr(C,'now',lambda:datetime(2026,9,14,12))
    change_dates(app,receipt,timestamp)
    plan=inspect_exception(client,receipt)
    assert plan['exception_policy']['window_start']=='2026-03-14'
    assert plan['exception_policy']['eligible']==eligible
    assert plan['can_convert']==eligible
    if not eligible:assert submit(client,receipt,plan).status_code==409


@pytest.mark.parametrize('current,start',[
    (datetime(2024,8,31,12),'2024-02-29'),
    (datetime(2025,8,31,12),'2025-02-28'),
    (datetime(2026,1,31,12),'2025-07-31'),
])
def test_calendar_month_end_and_leap_year(monkeypatch,current,start):
    monkeypatch.setattr(C,'now',lambda:current)
    plan={'loan':{'terms_json':'{}'},'checks':[]}
    policy=C.exception_policy(plan,{'logs':[{'id':1,'status_id':1,'date2':datetime.fromisoformat(start)}]},True)
    assert policy['eligible'] and policy['window_start']==start


def test_receipt_date_cannot_replace_recent_history(app,client,receipt,monkeypatch):
    monkeypatch.setattr(C,'now',lambda:datetime(2026,9,14,12))
    change_dates(app,receipt,datetime(2026,3,13))
    with app.app_context():
        db.execute('UPDATE pawn SET date2=%s WHERE id=%s',(datetime(2026,9,14),receipt))
        db.execute('DELETE FROM khcd_pawn_customer WHERE pawn_id=%s',(receipt,))
    plan=inspect_exception(client,receipt)
    assert not plan['can_convert']
    assert {'CUSTOMER','RECENT_TRANSACTION','INTEREST_ANCHOR'}<={c['code'] for c in plan['checks'] if c['state']=='error'}


@pytest.mark.parametrize('mutation,code',[
    ('DELETE FROM pawn_log WHERE pawn_id=%s','HISTORY'),
    ('UPDATE pawn SET value=1 WHERE id=%s','FINAL_BALANCE'),
    ('UPDATE pawn SET wgg1=0 WHERE id=%s','WEIGHT'),
    ("UPDATE pawn SET phone='' WHERE id=%s",'PHONE'),
])
def test_other_errors_remain_blocking(app,client,receipt,mutation,code):
    with app.app_context():db.execute(mutation,(receipt,))
    plan=inspect_exception(client,receipt)
    assert not plan['can_convert']
    assert any(c['code']==code and c['state']=='error' for c in plan['checks'])
    assert submit(client,receipt,plan).status_code==409


def test_customer_outage_still_blocks(client,receipt,monkeypatch):
    def fail(cid):raise M.Unavailable('KK offline')
    monkeypatch.setattr(M,'get',fail)
    plan=inspect_exception(client,receipt)
    assert not plan['can_convert']
    assert any(c['code']=='KK_UNAVAILABLE' and c['state']=='error' for c in plan['checks'])
    assert submit(client,receipt,plan).status_code==409


def test_unknown_customer_does_not_trigger_phone_matching(app,client,receipt,monkeypatch):
    calls=[]
    def missing(cid):calls.append(cid);return {'customer':None}
    monkeypatch.setattr(M,'get',missing)
    plan=inspect_exception(client,receipt)
    assert plan['can_convert'] and calls==['CU_TEST']
    assert submit(client,receipt,plan).status_code==200
    with app.app_context():
        loan=db.one('SELECT cust_id,phone,customer_snapshot FROM cd_loans')
        assert loan=={'cust_id':'CU_TEST','phone':'0900000001','customer_snapshot':'null'}


def test_mode_cannot_change_after_preview(client,receipt):
    strict=preview(client,receipt)
    relaxed=inspect_exception(client,receipt)
    assert strict['review_hash']!=relaxed['review_hash']
    assert submit(client,receipt,strict).status_code==409
    assert submit(client,receipt,relaxed,mode='no').status_code==409
    assert submit(client,receipt,relaxed,mode='no',batch=True).status_code==409


def test_window_rechecked_on_save_and_strict_old_valid_receipt_allowed(app,client,receipt,monkeypatch):
    monkeypatch.setattr(C,'now',lambda:datetime(2026,9,14,12))
    change_dates(app,receipt,datetime(2026,3,14))
    plan=inspect_exception(client,receipt)
    assert plan['can_convert']
    monkeypatch.setattr(C,'now',lambda:datetime(2026,9,15))
    assert submit(client,receipt,plan).status_code==409
    assert not inspect_exception(client,receipt)['can_convert']
    strict=preview(client,receipt)
    assert strict['can_convert'] and save(client,receipt,strict).status_code==200


def test_accepted_error_does_not_expire_or_hide_new_drift(app,client,receipt,monkeypatch):
    monkeypatch.setattr(C,'now',lambda:datetime(2026,9,14,12))
    change_dates(app,receipt,datetime(2026,3,14))
    with app.app_context():db.execute('UPDATE pawn_log SET total=-1 WHERE pawn_id=%s',(receipt,))
    result=submit(client,receipt,inspect_exception(client,receipt))
    assert result.status_code==200
    url='/camdo/bien-nhan/'+str(result.json['loan_id'])+'/doi-soat'
    monkeypatch.setattr(C,'now',lambda:datetime(2027,9,14,12))
    assert any(c.get('accepted_exception') for c in client.get(url).json['checks'])
    with app.app_context():db.execute('UPDATE pawn_log SET total=-2 WHERE pawn_id=%s',(receipt,))
    checks=client.get(url).json['checks']
    assert any(c.get('code')=='CASHFLOW' and c['state']=='error' for c in checks)
    assert any(c.get('code')=='EXISTING' and c['state']=='error' for c in checks)


def test_exception_source_drift_before_save_is_rejected(app,client,receipt):
    plan=inspect_exception(client,receipt)
    with app.app_context():db.execute("UPDATE pawn SET note='changed' WHERE id=%s",(receipt,))
    assert submit(client,receipt,plan,batch=True).status_code==409
