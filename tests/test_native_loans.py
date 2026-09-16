import json,uuid
from datetime import timedelta
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
import pytest
from khcd import db,live_loans as L,customer_master as M
from khcd.domain import today,now

@pytest.fixture
def native(app,monkeypatch,tmp_path):
    app.config.update(CD_LIVE='1',CUSTOMER_MASTER='kk',LOAN_MEDIA_ROOT=str(tmp_path))
    monkeypatch.setattr(M,'get',lambda cid:{'customer':dict(id=str(cid),CustID=str(cid),name='Khách QA',phone='0900000001',cccd='000000000001',addr='',Active=1)})
    def call(action,**kw):
        if action=='employees':return {'rows':[dict(EmpID='E1',EmpName='Nhân viên QA')]}
        if action=='pawn_banks':return {'rows':[dict(id=1,bank_name='QA Bank',bank_number='000001',bank_user='QA',type='pawn')],'default_id':1}
        if action=='batch':return {'rows':[]}
        raise RuntimeError('Unexpected external call '+action)
    monkeypatch.setattr(M,'call',call)
    return app

def create(client):
    data=dict(csrf_token='token',request_key=uuid.uuid4().hex,customer_id='CU_QA',employee_id='E1',safe='1',desk_version='2',date1=str(today()),term='30',monthly_rate='3',value='10000000',payment_method='bank',cash_amount='3000000',bank_amount='7000000',bank_name='QA Bank',bank_account='123',bank_holder='QA',note='Lập thử',items_json=json.dumps([dict(gold='99',description='Nhẫn QA',gross='2',stone='0',price='6000000')]))
    r=client.post('/camdo/lap-phieu',data=data,headers={'Accept':'application/json'})
    assert r.status_code==201,r.get_data(as_text=True)
    return int(r.json['url'].rsplit('/',1)[-1]),data

def opdata(client,lid,op,**kw):
    data=dict(csrf_token='token',operation=str(op),request_key=uuid.uuid4().hex,amount='1000000',extra='0',discount='0',bank_amount='0',due=str(today()+timedelta(days=30)),note='QA phiên',**kw)
    r=client.post(f'/camdo/bien-nhan/{lid}/tinh-phien',data=data)
    assert r.status_code==200,r.json
    data.update(fingerprint=r.json['fingerprint'],confirmed_total=str(abs(Decimal(r.json['net']))))
    return data

def cancel(client,lid):
    with client.application.app_context():p=L.loan(lid);finger=L.fingerprint(p)
    return client.post('/camdo/lap-phieu/huy-phien',data=dict(csrf_token='token',pid=lid,fingerprint=finger,request_key=uuid.uuid4().hex,reason='Hủy QA',returned_funds='yes'))

def test_create_native_only_and_views(native,client):
    lid,data=create(client)
    assert client.post('/camdo/lap-phieu',data=data,headers={'Accept':'application/json'}).status_code==201
    with native.app_context():
        for table in ('pawn','pawn_log','khcd_event','khcd_pawn_desk','khcd_pawn_customer','khcd_pawn_photo'):assert db.one('SELECT COUNT(*) n FROM '+table)['n']==0
        assert db.one('SELECT COUNT(*) n FROM cd_loans')['n']==1
        assert db.one('SELECT COUNT(*) n FROM cd_payments')['n']==2
        sku=L.loan(lid)['sku']
    r=client.get('/camdo/lap-phieu/tra-phieu',query_string={'q':sku});assert r.status_code==200,r.data
    assert r.json['cancellation']['allowed']
    for path in ('/camdo','/camdo/thong-ke','/camdo/lap-phieu/phien-giao-dich',f'/camdo/bien-nhan/{lid}',f'/camdo/bien-nhan/{lid}/doi-soat'):
        assert client.get(path).status_code==200,path
    assert cancel(client,lid).status_code==200
    with native.app_context():
        assert L.loan(lid)['principal_balance']==0
        assert db.one("SELECT SUM(IF(direction='IN',amount,-amount)) n FROM cd_payments")['n']==0
        assert L.check(lid)['errors']==0

@pytest.mark.parametrize('operation',[2,3,4,5,6,7])
def test_operations_and_reversal(native,client,operation):
    lid,_=create(client)
    with native.app_context():db.execute('UPDATE cd_loans SET interest_from=%s WHERE id=%s',(now()-timedelta(days=30),lid))
    data=opdata(client,lid,operation)
    r=client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=data);assert r.status_code==200,r.json
    assert client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=data).status_code==200
    with native.app_context():
        p=L.loan(lid);assert L.cancellation(p)['allowed']
        assert db.one('SELECT COUNT(*) n FROM cd_loan_logs')['n']==2
        assert p['principal_balance']=={2:11000000,3:9000000,4:10000000,5:0,6:0,7:10000000}[operation]
    r=cancel(client,lid);assert r.status_code==200,r.json
    with native.app_context():
        p=L.loan(lid);assert p['loan_state']=='ACTIVE';assert p['principal_balance']==10000000
        assert not L.cancellation(p)['allowed']
        assert L.check(lid)['errors']==0

def test_time_boundary_stale_and_rollback(native,client,monkeypatch):
    lid,_=create(client)
    with native.app_context():db.execute('UPDATE cd_loan_logs SET happened_at=%s',(now()-timedelta(seconds=300),))
    assert cancel(client,lid).status_code==409
    a=opdata(client,lid,4);b=opdata(client,lid,5)
    assert client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=a).status_code==200
    assert client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=b).status_code==409
    d=opdata(client,lid,3)
    def fail(*a,**k):raise RuntimeError('payment failed')
    monkeypatch.setattr(L,'post_payments',fail)
    with pytest.raises(RuntimeError):client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=d)
    with native.app_context():assert L.loan(lid)['principal_balance']==10000000

def test_create_failure_rolls_back(native,client,monkeypatch):
    def fail(*a,**k):raise RuntimeError('ledger write failed')
    monkeypatch.setattr(L,'post_log',fail)
    with pytest.raises(RuntimeError):create(client)
    with native.app_context():
        assert db.one('SELECT COUNT(*) n FROM cd_loans')['n']==0
        assert db.one('SELECT COUNT(*) n FROM cd_loan_items')['n']==0

def test_add_settles_interest_and_same_day(native,client):
    lid,_=create(client)
    with native.app_context():db.execute('UPDATE cd_loans SET interest_from=%s WHERE id=%s',(now()-timedelta(days=30),lid))
    d=opdata(client,lid,2);assert client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=d).status_code==200
    d=opdata(client,lid,4);assert Decimal(d['confirmed_total'])==11000
    assert client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=d).status_code==200
    d=opdata(client,lid,5);assert Decimal(d['confirmed_total'])==11011000

def test_concurrent_confirm(native,client):
    lid,_=create(client);a=opdata(client,lid,5);b=dict(a,request_key=uuid.uuid4().hex)
    with client.session_transaction() as s:credentials=dict(s)
    def send(data):
        c=native.test_client()
        with c.session_transaction() as s:s.update(credentials)
        return c.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=data).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:codes=list(pool.map(send,[a,b]))
    assert sorted(codes)==[200,409]
    with native.app_context():assert db.one('SELECT COUNT(*) n FROM cd_loan_logs WHERE operation_id=5')['n']==1


def test_native_photos_and_tamper_detection(native,client,monkeypatch):
    from pathlib import Path
    monkeypatch.setattr(L.desk,'prepare_photos',lambda _: {'anh_sp1':b'fake-image-test'})
    lid,_=create(client)
    assert client.get(f'/camdo/bien-nhan/{lid}/anh/anh_sp1').data==b'fake-image-test'
    assert client.get(f'/camdo/bien-nhan/{lid}/in').status_code==200
    with native.app_context():db.execute("UPDATE cd_loan_items SET description='changed' WHERE loan_id=%s",(lid,))
    d=opdata(client,lid,4)
    assert client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=d).status_code==409
    for file in Path(native.config['LOAN_MEDIA_ROOT']).iterdir():file.write_bytes(b'corrupted')
    assert client.get(f'/camdo/bien-nhan/{lid}/anh/anh_sp1').status_code==404

def test_readonly_csrf_and_legacy_disabled(native,client):
    lid,_=create(client);d=opdata(client,lid,4)
    assert client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=dict(d,csrf_token='wrong')).status_code==400
    assert client.post('/camdo/phieu-cam-do/1/cancel',data=dict(csrf_token='token')).status_code==400
    native.config['DB_READ_ONLY']=True
    assert client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=d).status_code==409

def test_concurrent_create_key(native,client):
    _,data=create(client);data['request_key']=uuid.uuid4().hex
    with client.session_transaction() as s:credentials=dict(s)
    def send(_):
        c=native.test_client()
        with c.session_transaction() as s:s.update(credentials)
        r=c.post('/camdo/lap-phieu',data=data,headers={'Accept':'application/json'})
        assert r.status_code==201,r.data
        return r.json['sku']
    with ThreadPoolExecutor(max_workers=2) as pool:skus=list(pool.map(send,[1,2]))
    assert skus[0]==skus[1]
    with native.app_context():assert db.one('SELECT COUNT(*) n FROM cd_loans')['n']==2


def test_converted_loan_operates_without_source_writes(native,client,monkeypatch):
    from test_loan_conversion import receipt
    from flask import session
    from khcd import loan_conversion as C
    pid=receipt.__wrapped__(native,monkeypatch)
    with native.test_request_context():
        session.update(user='khj_admin',user_id=1)
        before=C.digest(C.source(pid));review=C.inspect(pid);lid=C.convert(pid,review['review_hash'])
    d=opdata(client,lid,4)
    assert client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=d).status_code==200
    with native.app_context():assert C.digest(C.source(pid))==before
    assert cancel(client,lid).status_code==200
    with native.app_context():
        assert C.digest(C.source(pid))==before
        assert L.check(lid)['errors']==0


def test_retry_from_pre_cutover_does_not_create_duplicate(native,client):
    from flask import session
    from khcd.services import event
    _,data=create(client);key=uuid.uuid4().hex;data['request_key']=key
    with native.test_request_context():
        session.update(user='khj_admin',user_id=1)
        event('create',pawn_id=999999,key=key)
    r=client.post('/camdo/lap-phieu',data=data,headers={'Accept':'application/json'})
    assert r.status_code==400
    with native.app_context():assert db.one('SELECT COUNT(*) n FROM cd_loans')['n']==1


def test_checkout_latest_session_and_next_interest(native,client):
    lid,_=create(client)
    with native.app_context():
        p=L.loan(lid);c=L.checkout_summary(p)
        assert Decimal(c['forecast_interest'])==300000
        assert c['note']=='Lập thử'
        db.execute('UPDATE cd_loans SET interest_from=%s WHERE id=%s',(now()-timedelta(days=30),lid))
    d=opdata(client,lid,3);d['note']='Trả bớt hôm nay'
    assert client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=d).status_code==200
    with native.app_context():
        c=L.checkout_summary(L.loan(lid))
        assert c['operation']=='Trả bớt' and c['note']=='Trả bớt hôm nay'
        assert c['payment']['cash']=='1300000'
        assert c['direction']=='THU TỪ KHÁCH'
        assert Decimal(c['forecast_interest'])==270000
    d=opdata(client,lid,2);d['note']=''
    assert client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=d).status_code==200
    with native.app_context():assert L.checkout_summary(L.loan(lid))['note']==''
    d=opdata(client,lid,5)
    assert client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=d).status_code==200
    with native.app_context():
        c=L.checkout_summary(L.loan(lid));assert c['closed'] and c['forecast_interest'] is None

def test_checkout_does_not_carry_settled_add_interest(native,client):
    lid,_=create(client)
    with native.app_context():db.execute('UPDATE cd_loans SET interest_from=%s WHERE id=%s',(now()-timedelta(days=30),lid))
    d=opdata(client,lid,2)
    assert client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=d).status_code==200
    with native.app_context():assert Decimal(L.checkout_summary(L.loan(lid))['forecast_interest'])==330000


def test_qr_belongs_to_each_payment_not_asset(native,client,monkeypatch):
    from io import BytesIO
    # The shared image service is replaced only inside this isolated test.
    monkeypatch.setattr(L.desk,'prepare_photos',lambda files:{'anh_qr':b'qr-opening','anh_sp1':b'product'})
    lid,_=create(client)
    with native.app_context():
        p=L.loan(lid);first=L.latest(lid)['id'];docs=L.unpack(p['documents_json'])
        assert 'anh_qr' not in docs['native'] and 'anh_sp1' in docs['native']
        assert L.checkout_summary(p)['qr_url']==f'/camdo/phien/{first}/qr'
    assert client.get(f'/camdo/phien/{first}/qr').data==b'qr-opening'
    monkeypatch.setattr(L.desk,'prepare_photos',lambda files:{'anh_qr':files['anh_qr'].read()})
    data=opdata(client,lid,4);data.update(bank_amount=data['confirmed_total'],bank_id='1',anh_qr=(BytesIO(b'qr-renewal'),'qr.jpg'))
    r=client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=data,content_type='multipart/form-data');assert r.status_code==200,r.json
    with native.app_context():second=L.latest(lid)['id'];assert second!=first
    assert client.get(f'/camdo/phien/{second}/qr').data==b'qr-renewal'
    assert client.get(f'/camdo/phien/{first}/qr').data==b'qr-opening'
    assert cancel(client,lid).status_code==200
    with native.app_context():
        third=L.latest(lid)['id'];assert L.checkout_summary(L.loan(lid))['qr_url'] is None
    assert client.get(f'/camdo/phien/{third}/qr').status_code==404
    assert native.test_client().get(f'/camdo/phien/{first}/qr').status_code==302
    html=client.get(f'/camdo/bien-nhan/{lid}').get_data(as_text=True)
    import base64
    assert base64.b64encode(b'qr-opening').decode() not in html

def test_qr_requires_bank_payment(native,client,monkeypatch):
    from io import BytesIO
    lid,_=create(client);data=opdata(client,lid,4)
    monkeypatch.setattr(L.desk,'prepare_photos',lambda files:{'anh_qr':b'qr'})
    data['anh_qr']=(BytesIO(b'qr'),'qr.jpg')
    assert client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=data,content_type='multipart/form-data').status_code==409
    with native.app_context():assert db.one('SELECT COUNT(*) n FROM cd_loan_logs')['n']==1

def test_print_count_does_not_change_financial_fingerprint(native,client):
    lid,_=create(client)
    url=f'/camdo/bien-nhan/{lid}/luot-in'
    with native.app_context():before=L.fingerprint(L.loan(lid))
    assert client.get(url).json['count_print']==0
    assert client.get(f'/camdo/bien-nhan/{lid}/in').status_code==200
    assert client.get(url).json['count_print']==0
    assert client.post(url,data={'csrf_token':'token'}).json['count_print']==1
    assert client.post(url,data={'csrf_token':'token'}).json['count_print']==2
    with native.app_context():assert L.fingerprint(L.loan(lid))==before

def test_receipt_history_exact_id_includes_old_sessions(native,client):
    lid,_=create(client)
    other,_=create(client)
    with native.app_context():
        db.execute('UPDATE cd_loan_logs SET happened_at=%s WHERE loan_id=%s',(now()-timedelta(days=800),lid))
    result=client.get('/camdo/lap-phieu/phien-giao-dich',query_string={'loan_id':lid})
    assert result.status_code==200
    assert result.json['total']==1
    assert {r['loan_id'] for r in result.json['rows']}=={lid}
    assert client.get('/camdo/lap-phieu/phien-giao-dich',query_string={'loan_id':'invalid'}).status_code==400

def test_yearly_receipt_sequence_rules(native,client):
    from datetime import datetime
    from khcd.domain import BusinessError
    lid,_=create(client)
    with native.app_context():
        assert L.next_receipt_code(datetime(2090,1,1))=='KH29001000001'
        db.execute('UPDATE cd_loans SET sku=%s WHERE id=%s',('KH29009000042',lid))
        assert L.next_receipt_code(datetime(2090,10,1))=='KH29010000043'
        assert L.next_receipt_code(datetime(2091,1,1))=='KH29101000001'
        for malformed in ['CD9009000042','KH29013000999','KH29009000000','KH29009000999X','kh29009000999']:
            db.execute('UPDATE cd_loans SET sku=%s WHERE id=%s',(malformed,lid))
            assert L.next_receipt_code(datetime(2090,9,1))=='KH29009000001'
        db.execute('UPDATE cd_loans SET sku=%s WHERE id=%s',('KH29001999999',lid))
        with pytest.raises(BusinessError,match='999999'):L.next_receipt_code(datetime(2090,12,1))


def test_concurrent_distinct_receipts_get_distinct_sequence(native,client):
    lid,data=create(client)
    with client.session_transaction() as s:credentials=dict(s)
    def send(_):
        c=native.test_client()
        with c.session_transaction() as s:s.update(credentials)
        payload={**data,'request_key':uuid.uuid4().hex}
        r=c.post('/camdo/lap-phieu',data=payload,headers={'Accept':'application/json'})
        assert r.status_code==201,r.data
        return r.json['sku']
    with ThreadPoolExecutor(max_workers=3) as pool:skus=list(pool.map(send,range(3)))
    assert len(set(skus))==3
    assert all(s.startswith('KH2'+now().strftime('%y%m')) and len(s)==13 for s in skus)
    assert sorted(int(s[-6:]) for s in skus)==[2,3,4]

def test_recover_saved_receipt_by_request_key(native,client):
    lid,data=create(client)
    response=client.get('/camdo/lap-phieu/ket-qua-luu',query_string={'request_key':data['request_key']})
    assert response.status_code==200
    with native.app_context():
        assert response.json['sku']==L.loan(lid)['sku']
        assert db.one('SELECT COUNT(*) n FROM cd_loans')['n']==1
    assert client.get('/camdo/lap-phieu/ket-qua-luu',query_string={'request_key':'not-found'}).status_code==404
    with native.app_context():db.execute('UPDATE cd_loan_logs SET actor_id=999999 WHERE loan_id=%s',(lid,))
    assert client.get('/camdo/lap-phieu/ket-qua-luu',query_string={'request_key':data['request_key']}).status_code==404

@pytest.mark.parametrize('safe',['','0','4'])
def test_new_receipt_requires_safe(native,client,safe):
    _,data=create(client)
    data.update(request_key=uuid.uuid4().hex,safe=safe)
    response=client.post('/camdo/lap-phieu',data=data,headers={'Accept':'application/json'})
    assert response.status_code==400
    assert 'Tủ đồ' in response.json['error']
    with native.app_context():assert db.one('SELECT COUNT(*) n FROM cd_loans')['n']==1

def test_renewal_effective_date_next_rate_and_cancel(native,client):
    lid,_=create(client)
    start=today()-timedelta(days=40)
    with native.app_context():db.execute('UPDATE cd_loans SET interest_from=%s WHERE id=%s',(start,lid))
    chosen=today()-timedelta(days=10)
    data=opdata(client,lid,4,transaction_date=str(chosen),next_monthly_rate='2.5')
    data['due']=str(chosen+timedelta(days=30))
    q=client.post(f'/camdo/bien-nhan/{lid}/tinh-phien',data=data).json
    assert q['days']=='30' and q['interest']=='300000'
    data.update(confirmed_total=q['net'],fingerprint=q['fingerprint'])
    result=client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=data)
    assert result.status_code==200,result.json
    with native.app_context():
        p=L.loan(lid);log=L.latest(lid)
        assert str(p['interest_from'])[:10]==str(chosen)
        assert p['monthly_rate']==Decimal('2.5')
        assert log['monthly_rate']==Decimal('3')
        assert log['happened_at'].date()==today()
    assert cancel(client,lid).status_code==200
    with native.app_context():
        p=L.loan(lid)
        assert p['monthly_rate']==Decimal('3')
        assert str(p['interest_from'])[:10]==str(start)


def test_renewal_future_date_and_date_guards(native,client):
    lid,_=create(client)
    data=dict(operation='4',transaction_date=str(today()+timedelta(days=30)),due=str(today()+timedelta(days=60)),next_monthly_rate='2')
    with native.app_context():
        p=L.loan(lid);q=L.estimate(p,4,data)
        assert q['days']==30 and q['interest']==300000
        from khcd.domain import BusinessError
        with pytest.raises(BusinessError):L.estimate(p,4,{**data,'transaction_date':str(today()-timedelta(days=1))})
        with pytest.raises(BusinessError):L.estimate(p,4,{**data,'due':data['transaction_date']})
        with pytest.raises(BusinessError):L.estimate(p,4,{**data,'next_monthly_rate':'0'})


def test_current_rate_override_and_interest_minimum(native,client):
    lid,_=create(client)
    with native.app_context():
        p=L.loan(lid)
        p['principal_balance']=Decimal('100000')
        q=L.estimate(p,4,dict(due=str(today()+timedelta(days=30)),current_monthly_rate='1.0'))
        assert q['days']==1 and q['interest']==5000
        assert q['applied_rate']==Decimal('1')
        assert q['next_monthly_rate']==Decimal('3')
    d=opdata(client,lid,4,current_monthly_rate='2.0')
    assert Decimal(d['confirmed_total'])==6667
    response=client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=d)
    assert response.status_code==200,response.json
    with native.app_context():
        assert L.latest(lid)['monthly_rate']==Decimal('2')
        assert L.loan(lid)['monthly_rate']==Decimal('3')
    assert cancel(client,lid).status_code==200


@pytest.mark.parametrize('operation,expected_net,expected_balance',[(2,-1950000,12000000),(3,2050000,8000000)])
def test_principal_change_settles_old_interest_and_new_terms(native,client,operation,expected_net,expected_balance):
    lid,_=create(client)
    with native.app_context():db.execute('UPDATE cd_loans SET interest_from=%s WHERE id=%s',(today()-timedelta(days=5),lid))
    data=opdata(client,lid,operation,next_monthly_rate='2.5',transaction_date=str(today()))
    data['amount']='2000000';data['extra']='10000';data['discount']='10000'
    q=client.post(f'/camdo/bien-nhan/{lid}/tinh-phien',data=data).json
    assert Decimal(q['interest'])==50000
    assert Decimal(q['net'])==expected_net
    assert Decimal(q['principal_after'])==expected_balance
    data.update(confirmed_total=str(abs(expected_net)),fingerprint=q['fingerprint'])
    response=client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=data)
    assert response.status_code==200,response.json
    with native.app_context():
        p=L.loan(lid);log=L.latest(lid)
        assert p['principal_balance']==expected_balance and p['monthly_rate']==Decimal('2.5')
        assert str(p['interest_from'])[:10]==str(today())
        assert L.unpack(p['terms_json'])['interest_carry']=='0'
        assert log['interest']==50000
        pay=db.one('SELECT * FROM cd_payments WHERE log_id=%s',(log['id'],))
        assert pay['amount']==abs(expected_net)
        assert pay['direction']==('OUT' if operation==2 else 'IN')
    assert cancel(client,lid).status_code==200
    with native.app_context():
        assert L.loan(lid)['principal_balance']==10000000
        assert L.loan(lid)['monthly_rate']==Decimal('3')

def outgoing_request(native,client,lid):
    with native.test_request_context():
        p=L.loan(lid);state=L.payment_edit_state(p)
        return dict(csrf_token='token',mode='preview',log_id=state['log_id'],payment_version=state['version'],request_key=uuid.uuid4().hex,bank_amount='1234567',bank_code='VCB',bank_account='0011223344',bank_holder='NGUYEN VAN A',bank_reference=p['sku'])


def test_outgoing_qr_exact_amount_and_atomic_payment_edit(native,client):
    from khcd import banking_qr as QR
    lid,_=create(client);url=f'/camdo/bien-nhan/{lid}/chi-chuyen-khoan'
    data=outgoing_request(native,client,lid)
    with native.app_context():before=L.fingerprint(L.loan(lid));count=db.one('SELECT COUNT(*) n FROM cd_loan_logs')['n']
    preview=client.post(url,data=data)
    assert preview.status_code==200,preview.json
    parsed=QR.parse(preview.json['qr_payload'])
    assert preview.json['bank_reference']=='THANH TOÁN TIỀN VÀNG KH'+str(data['log_id'])
    assert parsed['info']=='THANH TOAN TIEN VANG KH'+str(data['log_id'])
    assert parsed['hop_le'] and parsed['amount']==1234567 and parsed['account']=='0011223344'
    saved=client.post(url,data={**data,'mode':'save'})
    assert saved.status_code==200,saved.json
    assert client.post(url,data={**data,'mode':'save'}).status_code==200
    with native.app_context():
        assert L.fingerprint(L.loan(lid))==before
        assert db.one('SELECT COUNT(*) n FROM cd_loan_logs')['n']==count
        log=L.latest(lid);rows=db.all('SELECT * FROM cd_payments WHERE log_id=%s',(log['id'],))
        assert sum(p['amount'] for p in rows)==10000000
        assert len(L.unpack(log['terms_json'])['payment_changes'])==1
        bank=next(p for p in rows if p['channel']=='BANK')
        info=L.unpack(bank['bank_snapshot']);assert bank['amount']==1234567 and info['transfer_status']=='PREPARED'
        assert QR.parse(info['qr_payload'])['amount']==bank['amount']
    image=client.get(f"/camdo/phien/{data['log_id']}/qr")
    assert image.status_code==200 and image.content_type=='image/png'
    assert client.post(url,data={**data,'mode':'save','request_key':uuid.uuid4().hex}).status_code==400
    assert cancel(client,lid).status_code==200
    with native.app_context():assert L.latest(lid)['operation_id']==0


def test_outgoing_payment_time_latest_and_direction_guards(native,client):
    lid,_=create(client);data=outgoing_request(native,client,lid);url=f'/camdo/bien-nhan/{lid}/chi-chuyen-khoan'
    with native.app_context():db.execute('UPDATE cd_loan_logs SET happened_at=%s WHERE id=%s',(now()-timedelta(minutes=30),data['log_id']))
    assert client.post(url,data=data).status_code==400
    op=opdata(client,lid,4)
    assert client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=op).status_code==200
    assert client.post(url,data=data).status_code==400
    with native.test_request_context():assert not L.payment_edit_state(L.loan(lid))['allowed']
