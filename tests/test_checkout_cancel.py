from datetime import timedelta
from decimal import Decimal
import pytest
from khcd import db, services as svc
from khcd.domain import now
from test_workflows import customer, new_pawn, action_data

def payload(app,pid):
    return dict(action_data(app,pid),pid=pid,reason='Lập nhầm, đã thu hồi tiền',returned_funds='yes')

@pytest.mark.parametrize('age,allowed',[(299,True),(300,False),(301,False),(-5,False)])
def test_five_minute_boundary(app,client,monkeypatch,age,allowed):
    pid,_=new_pawn(client,customer(client));fixed=now().replace(microsecond=0)
    with app.app_context():
        db.execute("UPDATE khcd_event SET created_at=%s WHERE pawn_id=%s AND kind='create'",(fixed-timedelta(seconds=age),pid))
    monkeypatch.setattr(svc,'now',lambda:fixed)
    r=client.post('/camdo/lap-phieu/huy-phien',data=payload(app,pid))
    assert r.status_code==(200 if allowed else 409)
    with app.app_context():assert svc.pawn(pid)['status']==(0 if allowed else 1)

def test_cash_bank_reversal_once(app,client):
    pid,_=new_pawn(client,customer(client))
    with app.app_context():db.execute('UPDATE pawn_log SET total=-3000000,mbank=-7000000 WHERE pawn_id=%s',(pid,))
    data=payload(app,pid)
    assert client.post('/camdo/lap-phieu/huy-phien',data=data).status_code==200
    assert client.post('/camdo/lap-phieu/huy-phien',data=data).status_code==200
    with app.app_context():
        assert db.one('SELECT SUM(total) c,SUM(mbank) b FROM pawn_log')['c']==0
        assert db.one('SELECT SUM(mbank) b FROM pawn_log')['b']==0
        assert db.one('SELECT COUNT(*) n FROM pawn_log WHERE status_id=0')['n']==1
        assert db.one("SELECT note FROM khcd_event WHERE kind='cancel'")['note']==data['reason']
        assert db.one('SELECT COUNT(*) n FROM pawn')['n']==1

@pytest.mark.parametrize('change',["UPDATE pawn_log SET total=-1", "DELETE FROM khcd_event WHERE kind='create'", "UPDATE pawn_log SET status_id=4"])
def test_unreconciled_opening_blocked(app,client,change):
    pid,_=new_pawn(client,customer(client))
    with app.app_context():db.execute(change)
    assert client.post('/camdo/lap-phieu/huy-phien',data=payload(app,pid)).status_code==409

def test_confirmation_csrf_and_rollback(app,client,monkeypatch):
    pid,_=new_pawn(client,customer(client));data=payload(app,pid)
    assert client.post('/camdo/lap-phieu/huy-phien',data=dict(data,returned_funds='')).status_code==409
    assert client.post('/camdo/lap-phieu/huy-phien',data=dict(data,csrf_token='bad')).status_code==400
    def fail(*a,**k):raise RuntimeError('audit failure')
    monkeypatch.setattr(svc,'event',fail)
    with pytest.raises(RuntimeError):client.post('/camdo/lap-phieu/huy-phien',data=data)
    with app.app_context():
        assert svc.pawn(pid)['status']==1
        assert db.one('SELECT COUNT(*) n FROM pawn_log')['n']==1

def test_template_and_receipt_metadata(app,client):
    pid,_=new_pawn(client,customer(client))
    with app.app_context():sku=svc.pawn(pid)['sku']
    r=client.get('/camdo/lap-phieu/tra-phieu',query_string={'q':sku})
    assert r.status_code==200
    assert r.json['cancellation']['allowed']
    assert r.json['fingerprint']
    html=client.get('/camdo/lap-phieu').get_data(as_text=True)
    assert html.count('id="principal"')==1
    assert html.index('id="pawn-photos"')<html.index('class="desk-right desk-checkout"')<html.index('id="principal"')
