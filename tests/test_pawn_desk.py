import base64
import io
import json
import secrets
from decimal import Decimal
from datetime import timedelta
import pytest
from khcd import pawn_desk as D, customer_master as M, db, services
from khcd.domain import BusinessError, today, quote

GOLDS=[dict(id='99',name='VÀNG 9999',unit='chỉ')]
def item(**kw):return dict(gold='99',description='Nhẫn thử',gross='3.1000',stone='0.1000',price='1234567',**kw)
def data_items(rows):return {'items_json':json.dumps(rows)}

def test_weights_and_prices_recomputed_not_trusted():
    result=D.items(data_items([item(net='1000',subtotal='1')]*3),GOLDS)
    assert len(result)==3 and Decimal(result[0]['net'])==3
    assert result[0]['subtotal']=='3703701'
    assert D.summary(result).count('[99] Nhẫn thử 3.00c')==3
    row=item();row.update(gross='0.0001',stone='0',price='5000')
    assert D.items(data_items([row]),GOLDS)[0]['subtotal']=='1'

@pytest.mark.parametrize('changes',[{'gold':'#'},{'gross':'NaN'},{'gross':'0.00001'},{'stone':'4'},{'stone':'-1'},{'price':'1.1'},{'description':''}])
def test_invalid_items_rejected(changes):
    row=item();row.update(changes)
    with pytest.raises(BusinessError):D.items(data_items([row]),GOLDS)

@pytest.mark.parametrize('rows',[[],[item()]*31,{},['not a row']])
def test_item_count_and_shape(rows):
    with pytest.raises(BusinessError):D.items(data_items(rows),GOLDS)

def test_payment_split_and_guards():
    data=dict(pay_cash='1',pay_bank='1',bank_amount='6000000',bank_name='TEST',bank_account='123',bank_holder='TEST')
    assert D.payment(data,Decimal('10000000'))['cash']=='4000000'
    with pytest.raises(BusinessError):D.payment({**data,'pay_cash':''},Decimal('10000000'))
    with pytest.raises(BusinessError):D.payment({**data,'bank_amount':'10000001'},Decimal('10000000'))
    with pytest.raises(BusinessError):D.payment({**data,'bank_account':''},Decimal('10000000'))
    with pytest.raises(BusinessError):D.payment({},Decimal('1'))


def test_radio_payment_cash_full_bank_and_split():
    data=dict(payment_method='bank',cash_amount='4000000',bank_amount='6000000',bank_name='TEST',bank_account='123',bank_holder='TEST')
    assert D.payment(data,Decimal('10000000'))['cash']=='4000000'
    assert D.payment({**data,'cash_amount':'0','bank_amount':'10000000'},Decimal('10000000'))['cash']=='0'
    assert D.payment(dict(payment_method='cash',cash_amount='10000000',bank_amount='0'),Decimal('10000000'))['bank_amount']=='0'
    for changes in ({'cash_amount':'1'},{'payment_method':'other'},{'payment_method':'cash'},{'bank_amount':'6000000.1'},{'bank_holder':''}):
        with pytest.raises(BusinessError):D.payment({**data,**changes},Decimal('10000000'))


@pytest.mark.parametrize('raw,expected',[
    ('CD001',('sku','CD001')),('123',('sku','123')),
    ('https://localhost:8200/camdo/phieu-cam-do/12',('id',12)),
    ('/phieu-cam-do/12/',('id',12))])
def test_receipt_key_exact_identity(raw,expected):
    assert D.receipt_key(raw)==expected


@pytest.mark.parametrize('raw',['','X\nY','https://other.test/camdo/phieu-cam-do/12','/camdo/phieu-cam-do/12?edit=1','/camdo/lap-phieu'])
def test_receipt_key_rejects_invalid_or_external(raw):
    with pytest.raises(BusinessError):D.receipt_key(raw)

@pytest.fixture
def desk_app(app,monkeypatch):
    app.config['CUSTOMER_MASTER']='kk'
    customer={'CustID':'CU_DESK_TEST','CustName':'Khách thử riêng','Phone':'0900000001','CMND':'','Address':'','Active':'1'}
    def call(action,**payload):
        if action=='employees':return {'rows':[dict(EmpID='EMP_TEST',EmpName='Nhân viên thử')]}
        if action=='get':return {'customer':customer}
        if action=='list':return {'rows':[customer],'total':1,'can_edit':True}
        if action=='batch':return {'rows':[customer]}
        if action=='pawn_images':return {'images':{k:base64.b64encode(b'JPEG_TEST').decode() for k in payload['files']}}
        raise AssertionError(action)
    monkeypatch.setattr(M,'call',call)
    return app

def form_data():
    return dict(csrf_token='token',request_key=secrets.token_hex(16),desk_version='2',customer_id='CU_DESK_TEST',
        items_json=json.dumps([item()]*3),employee_id='EMP_TEST',value='10000000',date1=str(today()),term='30',monthly_rate='2.5',
        pay_cash='1',pay_bank='1',bank_amount='6000000',bank_name='TEST',bank_account='123',bank_holder='TEST')

def test_atomic_multi_item_bank_photo_replay_and_cancel(desk_app,client):
    data=form_data();response=client.post('/camdo/lap-phieu',data={**data,'anh_sp1':(io.BytesIO(b'image'),'test.jpg')},headers={'Accept':'application/json'})
    assert response.status_code==201,response.text
    pid=int(response.json['url'].rsplit('/',1)[1]);assert client.post('/camdo/lap-phieu',data=data,headers={'Accept':'application/json'}).json==response.json
    with desk_app.app_context():
        p=services.pawn(pid);assert len(p['desk']['items'])==3 and p['desk']['photos']==['anh_sp1']
        assert p['percent']==Decimal('2.5') and quote(p,today()+timedelta(days=30))['interest']==250000
        ledger=db.one('SELECT total,mbank FROM pawn_log WHERE pawn_id=%s',(pid,));assert ledger=={'total':Decimal('-4000000'),'mbank':Decimal('-6000000')}
        assert db.one('SELECT COUNT(*) n FROM khcd_event')['n']==1
        assert db.one('SELECT COUNT(*) n FROM customer')['n']==0
        fingerprint=p['fingerprint']
    detail=client.get(response.json['url']);assert detail.status_code==200 and detail.text.count('[99] Nhẫn thử')>=3
    assert '+2 tài sản' in client.get('/camdo/phieu-cam-do').text
    assert client.get(f'/camdo/phieu-cam-do/{pid}/anh/anh_sp1').data==b'JPEG_TEST'
    cancelled=client.post(f'/camdo/phieu-cam-do/{pid}/cancel',data=dict(csrf_token='token',fingerprint=fingerprint,request_key=secrets.token_hex(16),reason='TEST'))
    assert cancelled.status_code==302
    with desk_app.app_context():
        totals=db.one('SELECT SUM(total) cash,SUM(mbank) bank FROM pawn_log WHERE pawn_id=%s',(pid,));assert totals=={'cash':0,'bank':0}


def test_photo_failure_and_database_failure_leave_no_partial_pawn(desk_app,client,monkeypatch):
    original=M.call
    def failed(action,**payload):
        if action=='pawn_images':raise M.Unavailable('Ảnh không hợp lệ')
        return original(action,**payload)
    monkeypatch.setattr(M,'call',failed)
    r=client.post('/camdo/lap-phieu',data={**form_data(),'anh_sp1':(io.BytesIO(b'bad'),'bad.jpg')},headers={'Accept':'application/json'})
    assert r.status_code==400
    with desk_app.app_context():assert db.one('SELECT COUNT(*) n FROM pawn')['n']==0
    monkeypatch.setattr(M,'call',original)
    def fail_event(*args,**kwargs):raise BusinessError('Audit failed')
    monkeypatch.setattr(services,'event',fail_event)
    r=client.post('/camdo/lap-phieu',data=form_data(),headers={'Accept':'application/json'});assert r.status_code==400
    with desk_app.app_context():
        for table in ('pawn','pawn_log','khcd_pawn_desk','khcd_pawn_photo','khcd_pawn_customer'):
            assert db.one('SELECT COUNT(*) n FROM '+table)['n']==0


def test_edit_updates_summary_without_losing_extra_items(desk_app,client):
    result=client.post('/camdo/lap-phieu',data=form_data(),headers={'Accept':'application/json'});pid=int(result.json['url'].rsplit('/',1)[1])
    with desk_app.app_context():p=services.pawn(pid)
    r=client.post(result.json['url']+'/edit',data=dict(csrf_token='token',fingerprint=p['fingerprint'],request_key=secrets.token_hex(16),mota1='Đã sửa',mota2='Món hai'))
    assert r.status_code==302
    with desk_app.app_context():
        p=services.pawn(pid);assert len(p['desk']['items'])==3 and p['desk']['items'][0]['description']=='Đã sửa'
        assert '[99] Đã sửa 3.00c' in p['desk']['content'] and p['desk']['items'][2]['description']=='Nhẫn thử'


def test_lookup_exact_receipt_is_read_only_and_loaded_form_cannot_create(desk_app,client):
    result=client.post('/camdo/lap-phieu',data={**form_data(),'anh_qr':(io.BytesIO(b'image'),'qr.jpg')},headers={'Accept':'application/json'})
    assert result.status_code==201
    pid=int(result.json['url'].rsplit('/',1)[1])
    with desk_app.app_context():sku=services.pawn(pid)['sku']
    for query in (sku,result.json['url']):
        found=client.get('/camdo/lap-phieu/tra-phieu',query_string={'q':query})
        assert found.status_code==200,found.text
        p=found.json
        assert p['id']==pid and len(p['items'])==3 and p['customer']['id']=='CU_DESK_TEST'
        assert p['payment']['bank_amount']=='6000000' and p['valuation_known']
        assert 'anh_qr' in p['photos']
    assert client.get('/camdo/lap-phieu/tra-phieu?q=NO_SUCH_TEST_RECEIPT').status_code==404
    rejected=client.post('/camdo/lap-phieu',data={**form_data(),'loaded_pawn_id':str(pid)},headers={'Accept':'application/json'})
    assert rejected.status_code==400
    with desk_app.app_context():
        assert db.one('SELECT COUNT(*) n FROM pawn')['n']==1
        assert db.one('SELECT COUNT(*) n FROM khcd_event')['n']==1
        assert db.one('SELECT COUNT(*) n FROM pawn_log')['n']==1


def test_qr_requires_csrf_and_bank_list_is_read_only(desk_app,client,monkeypatch):
    calls=[]
    def call(action,**payload):
        calls.append(action)
        if action=='pawn_qr':return {'text':'CD_TEST'}
        if action=='pawn_banks':return {'rows':[{'id':2,'type':'pawn'}],'default_id':2}
        raise AssertionError(action)
    monkeypatch.setattr(M,'call',call)
    assert client.post('/camdo/lap-phieu/doc-qr',data={'kind':'receipt','text':'CD_TEST'}).status_code==400
    assert not calls
    assert client.post('/camdo/lap-phieu/doc-qr',data={'csrf_token':'token','kind':'receipt','text':'CD_TEST'}).json['text']=='CD_TEST'
    assert client.get('/camdo/lap-phieu/tai-khoan-thu').json['default_id']==2
    assert calls==['pawn_qr','pawn_banks']

def test_other_asset_ignores_weights_and_uses_whole_item_price():
    row=dict(gold='KHAC',description='Đồng hồ',gross='invalid',stone='-100',price='10000000')
    result=D.items(data_items([row]),[dict(id='KHAC',name='KHÁC',unit='món')])
    assert result[0]['net']=='0'
    assert result[0]['subtotal']=='10000000'
    assert D.summary(result)=='[KHÁC] Đồng hồ'
