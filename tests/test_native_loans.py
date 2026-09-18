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
    if op==7:
        import io
        from PIL import Image
        image=io.BytesIO();Image.new('RGB',(100,80),'white').save(image,format='PNG');image.seek(0)
        data['lost_photo']=(image,'cam-ket.png')
    return data

def cancel(client,lid):
    with client.application.app_context():p=L.loan(lid);finger=L.fingerprint(p)
    return client.post('/camdo/lap-phieu/huy-phien',data=dict(csrf_token='token',pid=lid,fingerprint=finger,request_key=uuid.uuid4().hex,confirmed='yes'))

def test_create_native_only_and_views(native,client):
    lid,data=create(client)
    assert client.post('/camdo/lap-phieu',data=data,headers={'Accept':'application/json'}).status_code==201
    with native.app_context():
        for table in ('pawn','pawn_log','khcd_event','khcd_pawn_desk','khcd_pawn_customer','khcd_pawn_photo'):assert db.one('SELECT COUNT(*) n FROM '+table)['n']==0
        assert db.one('SELECT COUNT(*) n FROM cd_loans')['n']==1
        assert db.one('SELECT COUNT(*) n FROM cd_payments')['n']==1
        payment=db.one('SELECT * FROM cd_payments')
        assert payment['channel'] is None and payment['cashPay']==payment['amount'] and payment['cardPay']==0
        sku=L.loan(lid)['sku']
    r=client.get('/camdo/lap-phieu/tra-phieu',query_string={'q':sku});assert r.status_code==200,r.data
    assert r.json['cancellation']['allowed']
    for path in ('/camdo','/camdo/thong-ke','/camdo/lap-phieu/phien-giao-dich',f'/camdo/bien-nhan/{lid}',f'/camdo/bien-nhan/{lid}/doi-soat'):
        assert client.get(path).status_code==200,path
    assert cancel(client,lid).status_code==200
    with native.app_context():
        for table in ('cd_loans','cd_loan_items','cd_loan_logs','cd_payments'):
            assert db.one('SELECT COUNT(*) n FROM '+table)['n']==0

@pytest.mark.parametrize('operation',[2,3,4,5,6,7])
def test_operations_and_reversal(native,client,operation):
    lid,_=create(client)
    with native.app_context():
        db.execute('UPDATE cd_loans SET interest_from=%s WHERE id=%s',(now()-timedelta(days=30),lid))
        first=L.latest(lid);terms=L.unpack(first['terms_json']);terms['after']=L.snapshot(L.loan(lid))
        db.execute('UPDATE cd_loan_logs SET terms_json=%s WHERE id=%s',(L.C.packed(terms),first['id']))
    data=opdata(client,lid,operation)
    r=client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=data);assert r.status_code==200,r.json
    data.pop('lost_photo',None)
    assert client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=data).status_code==200
    with native.app_context():
        p=L.loan(lid);assert L.cancellation(p)['allowed']
        assert db.one('SELECT COUNT(*) n FROM cd_loan_logs')['n']==2
        assert p['principal_balance']=={2:11000000,3:9000000,4:10000000,5:0,6:0,7:10000000}[operation]
    r=cancel(client,lid);assert r.status_code==200,r.json
    with native.app_context():
        p=L.loan(lid);assert p['loan_state']=='ACTIVE';assert p['principal_balance']==10000000
        assert db.one('SELECT COUNT(*) n FROM cd_loan_logs WHERE loan_id=%s',(lid,))['n']==1
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
        before=C.digest(C.source(pid));review=C.inspect(pid);lid=C.convert(pid,review['review_hash']);original_plan=C.normalized(C.target(pid)[1])
    d=opdata(client,lid,4)
    assert client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=d).status_code==200
    with native.app_context():assert C.digest(C.source(pid))==before
    assert cancel(client,lid).status_code==200
    with native.app_context():
        assert C.digest(C.source(pid))==before
        restored=C.normalized(C.target(pid)[1])
        assert restored==original_plan, {k:(original_plan['loan'][k],v) for k,v in restored['loan'].items() if v!=original_plan['loan'][k]}
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
        assert L.latest(lid)['id']==first
        assert L.checkout_summary(L.loan(lid))['qr_url']==f'/camdo/phien/{first}/qr'
    assert client.get(f'/camdo/phien/{second}/qr').status_code==404
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
    expected_ref=L.reference(now(),lid,data['log_id'])
    assert preview.json['bank_reference']==expected_ref
    assert parsed['info']==expected_ref
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
        assert len(rows)==1
        bank=rows[0]
        info=L.unpack(bank['bank_snapshot']);assert bank['cashPay']==10000000 and bank['cardPay']==0 and info['transfer_status']=='PREPARED'
        assert QR.parse(info['qr_payload'])['amount']==1234567
    image=client.get(f"/camdo/phien/{data['log_id']}/qr")
    assert image.status_code==200 and image.content_type=='image/png'
    assert client.post(url,data={**data,'mode':'save','request_key':uuid.uuid4().hex}).status_code==400
    assert cancel(client,lid).status_code==200
    with native.app_context():
        assert L.latest(lid) is None
        assert not db.one('SELECT id FROM cd_loans WHERE id=%s',(lid,))


def test_outgoing_payment_time_latest_and_direction_guards(native,client):
    lid,_=create(client);data=outgoing_request(native,client,lid);url=f'/camdo/bien-nhan/{lid}/chi-chuyen-khoan'
    with native.app_context():db.execute('UPDATE cd_loan_logs SET happened_at=%s WHERE id=%s',(now()-timedelta(minutes=30),data['log_id']))
    assert client.post(url,data=data).status_code==400
    op=opdata(client,lid,4)
    assert client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=op).status_code==200
    assert client.post(url,data=data).status_code==400
    with native.test_request_context():assert not L.payment_edit_state(L.loan(lid))['allowed']

def test_lost_session_deleted_and_restores_unlock(native,client):
    import io
    from PIL import Image
    image=io.BytesIO();Image.new('RGB',(120,80),'white').save(image,format='PNG')
    lid,_=create(client);data=opdata(client,lid,7)
    response=client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data={**data,'lost_photo':(io.BytesIO(image.getvalue()),'commitment.png')})
    assert response.status_code==200,response.json
    with native.app_context():
        log=L.latest(lid);terms=L.unpack(log['terms_json'])
        assert 'lost_photo' in terms
        assert 'lost_photo' not in L.unpack(L.loan(lid)['documents_json'])
    url=f"/camdo/phien/{log['id']}/cam-ket"
    assert client.get(url).status_code==200
    assert client.get(url).content_type=='image/jpeg'
    assert url in client.get(f'/camdo/bien-nhan/{lid}').get_data(as_text=True)
    assert cancel(client,lid).status_code==200
    assert client.get(url).status_code==404
    with native.app_context():assert not L.lost_locked(L.loan(lid))


def test_invalid_lost_photo_rolls_back_session(native,client):
    import io
    lid,_=create(client);data=opdata(client,lid,7)
    response=client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data={**data,'lost_photo':(io.BytesIO(b'not an image'),'bad.jpg')})
    assert response.status_code==409
    with native.app_context():
        assert not L.loan(lid)['receipt_lost']
        assert L.latest(lid)['operation_id']==1


def test_lost_interest_lock_passcode_and_unlock_audit(native,client):
    from khcd import auth
    from django.contrib.auth.hashers import make_password
    lid,_=create(client)
    with native.app_context():
        db.execute('UPDATE cd_loans SET interest_from=%s WHERE id=%s',(today()-timedelta(days=5),lid))
        db.execute('UPDATE '+auth.source_table()+' SET passcode=%s WHERE id=1',(make_password('654321'),))
    data=opdata(client,lid,7)
    assert Decimal(data['confirmed_total'])==50000
    assert client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=data).status_code==200
    with native.app_context():
        p=L.loan(lid);assert L.lost_locked(p)
        assert L.latest(lid)['interest']==50000
    for operation in (2,3,4,5,6,7):
        assert client.post(f'/camdo/bien-nhan/{lid}/tinh-phien',data=dict(csrf_token='token',operation=operation)).status_code==409
    with native.app_context():assert L.cancellation(L.loan(lid))['allowed']
    url=f'/camdo/bien-nhan/{lid}/mo-khoa-bao-mat'
    unlock=dict(csrf_token='token',request_key=uuid.uuid4().hex,reason='Đã đối soát cam kết',passcode='wrong')
    assert client.post(url,data=unlock).status_code==400
    unlock['passcode']='654321'
    assert client.post(url,data=unlock).status_code==200
    assert client.post(url,data=unlock).status_code==200
    with native.app_context():
        p=L.loan(lid);assert not L.lost_locked(p) and p['receipt_lost']
        assert L.latest(lid)['operation_id']==8
        assert L.check(lid)['errors']==0
    data=opdata(client,lid,4,transaction_date=str(today()+timedelta(days=15)))
    assert Decimal(data['confirmed_total'])==150000
    with native.app_context():
        p=L.loan(lid)
        assert L.parse_date(p['interest_from'])==today()
        assert L.checkout_summary(p)['operation']==L.OPS[7]
        assert not db.one('SELECT id FROM cd_payments WHERE log_id=%s',(L.latest(lid)['id'],))


def test_lost_paper_procedure_requires_no_extra_form_fields(native,client):
    lid,_=create(client);data=opdata(client,lid,7)
    result=client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=data)
    assert result.status_code==200,result.json
    with native.app_context():
        assert L.latest(lid)['operation_id']==7
        assert L.lost_locked(L.loan(lid))


def test_lost_cancel_expires_at_five_minutes(native,client,monkeypatch):
    lid,_=create(client);data=opdata(client,lid,7)
    assert client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=data).status_code==200
    with native.app_context():
        stamp=L.latest(lid)['happened_at']
        monkeypatch.setattr(L,'now',lambda:stamp+timedelta(seconds=299))
        assert L.cancellation(L.loan(lid))['allowed']
        monkeypatch.setattr(L,'now',lambda:stamp+timedelta(seconds=300))
        assert not L.cancellation(L.loan(lid))['allowed']
    assert cancel(client,lid).status_code==409
    with native.app_context():assert L.lost_locked(L.loan(lid))


def test_delete_unlock_restores_lock_without_new_history(native,client):
    from khcd import auth
    from django.contrib.auth.hashers import make_password
    lid,_=create(client);data=opdata(client,lid,7)
    assert client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=data).status_code==200
    with native.app_context():
        db.execute('UPDATE '+auth.source_table()+' SET passcode=%s WHERE id=1',(make_password('654321'),))
        lost_id=L.latest(lid)['id'];start=L.loan(lid)['interest_from']
    assert client.post(f'/camdo/bien-nhan/{lid}/mo-khoa-bao-mat',data=dict(csrf_token='token',request_key=uuid.uuid4().hex,reason='QA',passcode='654321')).status_code==200
    with native.app_context():deleted_id=L.latest(lid)['id']
    assert cancel(client,lid).status_code==200
    with native.app_context():
        assert not db.one('SELECT id FROM cd_loan_logs WHERE id=%s',(deleted_id,))
        assert L.latest(lid)['id']==lost_id
        assert L.lost_locked(L.loan(lid))
        assert L.loan(lid)['interest_from']==start
        assert L.check(lid)['errors']==0


def test_delete_transaction_rolls_back_on_log_delete_failure(native,client,monkeypatch):
    lid,_=create(client);data=opdata(client,lid,4)
    assert client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=data).status_code==200
    with native.app_context():
        log_id=L.latest(lid)['id'];before=L.fingerprint(L.loan(lid))
    execute=db.execute
    def fail(sql,*args,**kwargs):
        if sql.startswith('DELETE FROM cd_loan_logs'):raise RuntimeError('QA delete failure')
        return execute(sql,*args,**kwargs)
    monkeypatch.setattr(db,'execute',fail)
    with pytest.raises(RuntimeError):cancel(client,lid)
    with native.app_context():
        assert L.latest(lid)['id']==log_id
        assert L.fingerprint(L.loan(lid))==before
        assert db.one('SELECT COUNT(*) n FROM cd_payments WHERE log_id=%s',(log_id,))['n']>0


def test_opening_delete_rolls_back_all_tables_on_failure(native,client,monkeypatch):
    lid,_=create(client)
    execute=db.execute
    def fail(sql,*args,**kwargs):
        if sql.startswith('DELETE FROM cd_loans '):raise RuntimeError('QA master delete failure')
        return execute(sql,*args,**kwargs)
    monkeypatch.setattr(db,'execute',fail)
    with pytest.raises(RuntimeError):cancel(client,lid)
    with native.app_context():
        assert L.loan(lid)['principal_balance']==10000000
        assert L.latest(lid)['operation_id']==1
        assert db.one('SELECT COUNT(*) n FROM cd_loan_items WHERE loan_id=%s',(lid,))['n']==1
        assert db.one('SELECT COUNT(*) n FROM cd_payments')['n']==1


def test_lost_missing_photo_rejected_without_writes(native,client):
    lid,_=create(client);data=opdata(client,lid,7);data.pop('lost_photo')
    with native.app_context():before=L.fingerprint(L.loan(lid));log_id=L.latest(lid)['id']
    response=client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=data)
    assert response.status_code==409
    assert 'ảnh' in response.json['error']
    with native.app_context():
        assert L.fingerprint(L.loan(lid))==before
        assert L.latest(lid)['id']==log_id


def test_commitment_word_download(native,client):
    from pathlib import Path
    url='/camdo/mau/giay-cam-ket-bao-mat'
    response=client.get(url)
    assert response.status_code==200
    assert response.data==(Path(native.root_path)/'resources'/'giay-cam-ket-bao-mat-kim-hanh-2.docx').read_bytes()
    assert 'attachment' in response.headers['Content-Disposition']
    assert 'wordprocessingml' in response.content_type
    assert native.test_client().get(url).status_code==302


@pytest.mark.parametrize('operation',[5,6])
def test_sessions_filter_includes_closed_receipts(native,client,operation):
    lid,_=create(client);data=opdata(client,lid,operation)
    assert client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=data).status_code==200
    response=client.get('/camdo/lap-phieu/phien-giao-dich',query_string=dict(d1=str(today()),d2=str(today()),kind=operation))
    assert response.status_code==200
    assert response.json['total']==1
    assert response.json['rows'][0]['operation_id']==operation
    assert response.json['rows'][0]['loan_id']==lid
    assert response.json['rows'][0]['can_open']


@pytest.mark.parametrize('mode,expected,interest',[('principal',10000000,0),('principal_interest',10050000,50000),('actual',15000000,0)])
def test_liquidation_modes_multi_items(native,client,mode,expected,interest):
    lid,_=create(client)
    with native.app_context():
        db.execute("UPDATE gold_prices SET buy=6000000 WHERE gold_type='9999'")
        db.execute('UPDATE cd_loans SET interest_from=%s WHERE id=%s',(today()-timedelta(days=5),lid))
        db.execute('UPDATE cd_loan_items SET net_weight=2.5,gross_weight=2.5 WHERE loan_id=%s',(lid,))
        p=L.loan(lid);terms=L.unpack(p['terms_json']);terms['assets_hash']=L.assets_hash(lid)
        db.execute('UPDATE cd_loans SET terms_json=%s WHERE id=%s',(L.C.packed(terms),lid))
    data=opdata(client,lid,6,liquidation_mode=mode)
    assert Decimal(data['confirmed_total'])==expected
    response=client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=data)
    assert response.status_code==200,response.json
    with native.app_context():
        p=L.loan(lid);log=L.latest(lid)
        assert p['loan_state']=='LIQUIDATED' and p['principal_balance']==0
        assert log['interest']==interest
        assert log['extra_amount']-log['discount_amount']==expected-10000000-interest
        assert L.unpack(log['terms_json'])['liquidation']['mode']==mode
        assert L.check(lid)['errors']==0


def test_liquidation_sums_multiple_gold_items_and_rechecks_price(native,client):
    lid,_=create(client)
    with native.app_context():
        db.execute("UPDATE gold_prices SET buy=6000000 WHERE gold_type='9999'")
        db.execute("UPDATE gold_prices SET buy=4000000 WHERE gold_type='610'")
        L.insert('cd_loan_items',dict(loan_id=lid,line_no=2,gold_code='61',description='Vòng',unit='chỉ',gross_weight=1,stone_weight=0,net_weight=1,unit_price=1,valuation=1))
        p=L.loan(lid);terms=L.unpack(p['terms_json']);terms['assets_hash']=L.assets_hash(lid)
        db.execute('UPDATE cd_loans SET terms_json=%s WHERE id=%s',(L.C.packed(terms),lid))
    data=opdata(client,lid,6,liquidation_mode='actual')
    assert Decimal(data['confirmed_total'])==16000000
    with native.app_context():db.execute("UPDATE gold_prices SET buy=3000000 WHERE gold_type='610'")
    assert client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=data).status_code==409
    with native.app_context():assert L.loan(lid)['loan_state']=='ACTIVE'


def test_liquidation_actual_below_principal_and_missing_price(native,client):
    lid,_=create(client)
    with native.app_context():
        p=L.loan(lid)
        db.execute("UPDATE gold_prices SET buy=0 WHERE gold_type='9999'")
        with pytest.raises(L.BusinessError):L.estimate(p,6,dict(liquidation_mode='actual'))
        assert L.estimate(p,6,{})['net']==10000000
        db.execute("UPDATE gold_prices SET buy=4000000 WHERE gold_type='9999'")
        estimate=L.estimate(p,6,dict(liquidation_mode='actual'))
        assert estimate['net']==8000000 and estimate['discount']==2000000 and estimate['interest']==0


def test_authoritative_shared_gold_prices(native,client):
    from khcd.services import gold_options
    with native.app_context():
        db.execute("UPDATE gold_price SET value=1 WHERE scut='99'")
        db.execute("UPDATE gold_prices SET buy=6123000 WHERE gold_type='9999'")
        options={g['id']:g for g in gold_options()}
        assert options['99']['price']==6123000 and options['99']['unit']=='chỉ'
        assert options['bk']['price']==0
        payload=dict(items_json=json.dumps([dict(gold='99',description='Nhẫn',gross='1',stone='0',price='1')]))
        with pytest.raises(L.BusinessError):L.desk.items(payload,list(options.values()))
        payload['items_json']=payload['items_json'].replace('"price": "1"','"price": "6123000"')
        assert Decimal(L.desk.items(payload,list(options.values()))[0]['subtotal'])==6123000
        db.execute("UPDATE gold_prices SET is_current=0 WHERE gold_type='9999'")
        assert next(g for g in gold_options() if g['id']=='99')['price']==0
    response=client.get('/camdo/gia-vang')
    assert response.status_code==200 and response.headers['Cache-Control']=='no-store'
