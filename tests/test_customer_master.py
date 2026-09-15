import secrets
import pytest
from khcd import db,customer_master as M,services
from khcd.domain import today
from scripts.link_customer_master import plan


@pytest.fixture
def master_app(app,monkeypatch):
    app.config['CUSTOMER_MASTER']='kk'
    row={'CustID':'CU_TEST_1','CustName':'Khách KK','Phone':'0900000001','GhiChu2':'0900000002','GhiChu3':'',
         'CMND':'000000000001','Address':'Địa chỉ KK','Active':'1'}
    def call(action,**payload):
        if action=='employees':return {'rows':[{'EmpID':'EMP_TEST','EmpName':'Nhân viên thử'}]}
        if action=='get':return {'customer':dict(row),'form':{'CustName':row['CustName'],'Phone':row['Phone'],'Gender':'1'},'version':'v1','can_edit':True}
        if action=='list':return {'rows':[dict(row)],'total':1,'can_edit':True}
        if action=='batch':return {'rows':[dict(row)]}
        if action=='search_ids':return {'ids':['CU_TEST_1']}
        if action=='save':return {'complete':True,'cust_id':'CU_TEST_1'}
        raise AssertionError(action)
    monkeypatch.setattr(M,'call',call)
    return app,row


def test_master_entry_uses_opaque_id_and_stable_link(master_app,client):
    app,row=master_app
    result=client.get('/camdo/khach-hang');assert result.status_code==200 and 'Khách KK' in result.text
    assert client.get('/camdo/lap-phieu/khach-hang?q=0900000002').json['customers'][0]['id']=='CU_TEST_1'
    data=dict(csrf_token='token',request_key=secrets.token_hex(16),customer_id='CU_TEST_1',gold1='99',wgg1='2',whh1='0',mota1='Nhẫn thử',value='10000000',daily_rate='0.1',date1=str(today()),term='30')
    response=client.post('/camdo/lap-phieu',data=data);assert response.status_code==302
    assert client.post('/camdo/lap-phieu',data=data).location==response.location
    with app.app_context():
        assert db.one('SELECT COUNT(*) n FROM customer')['n']==0
        assert db.one('SELECT pmv_cust_id FROM khcd_pawn_customer')['pmv_cust_id']=='CU_TEST_1'
        assert db.one('SELECT SUM(total) amount FROM pawn_log')['amount']==-10000000
    row['Phone']='0900000099';row['CustName']='Tên KK mới'
    detail=client.get(response.location)
    assert detail.status_code==200 and 'Tên KK mới' in detail.text and '0900000099' in detail.text
    with app.app_context():assert db.one('SELECT phone FROM pawn')['phone']=='0900000001'
    for path in ['/','/camdo/lap-phieu','/camdo/phieu-cam-do','/camdo/khach-hang/kk/CU_TEST_1']:
        assert client.get(path).status_code==200,path


def test_master_writes_no_legacy_and_csrf(master_app,client):
    app,row=master_app
    assert client.post('/camdo/khach-hang/moi',data={'CustName':'A'}).status_code==400
    result=client.post('/camdo/khach-hang/moi',data={'csrf_token':'token','CustName':'Khách KK','Gender':'1','save_token':secrets.token_urlsafe(24)})
    assert result.status_code==302 and '/kk/CU_TEST_1' in result.location
    with app.app_context():assert db.one('SELECT COUNT(*) n FROM customer')['n']==0
    assert client.post('/camdo/khach-hang/1/luu-tru',data={'csrf_token':'token','reason':'test'}).status_code==400


def test_outage_preserves_pawn_draft_and_no_write(master_app,client,monkeypatch):
    app,row=master_app
    def failed(*args,**kw):raise M.Unavailable('KK unavailable')
    monkeypatch.setattr(M,'call',failed)
    response=client.get('/camdo/khach-hang')
    assert response.status_code==200 and 'KK unavailable' in response.text and 'Không có khách phù hợp.' not in response.text
    assert client.get('/camdo/lap-phieu/khach-hang?q=a').status_code==503
    posted=client.post('/camdo/khach-hang/kk/CU_TEST_1',data={'csrf_token':'token','CustName':'Giữ tên nháp','Address':'Giữ địa chỉ nháp','save_token':'draft_'+('a'*24),'version':'v1'})
    assert posted.status_code==200 and 'Giữ tên nháp' in posted.text and 'Giữ địa chỉ nháp' in posted.text
    draft=client.post('/camdo/lap-phieu',data={'csrf_token':'token','customer_id':'CU_TEST_1','items_json':'[{"description":"Giữ mô tả nháp"}]','request_key':'draft_'+('b'*24)})
    assert draft.status_code==400 and 'Giữ mô tả nháp' in draft.text and 'CU_TEST_1' in draft.text
    with app.app_context():assert db.one('SELECT COUNT(*) n FROM customer')['n']==0


def test_linking_does_not_choose_first_duplicate_or_change_existing():
    local=[{'id':1,'name':'A','phone':'0900000001','cccd':'123456789'}]
    pawn=[{'id':1,'phone':'0900000001','customer_id':1}]
    a={'CustID':'CU_A','CustName':'A','CMND':'123456789','phone_keys':['0900000001']}
    b={**a,'CustID':'CU_B'}
    links,counts=plan(local,pawn,{'rows':[a,b],'receipts':[]},set())
    assert not links
    assert plan(local,pawn,{'rows':[a],'receipts':[]},{1})[0]==[]
    assert plan(local,pawn,{'rows':[a],'receipts':[]},set())[0]==[(1,'CU_A','phone_identity')]
    a['CMND']='999999999'
    assert plan(local,pawn,{'rows':[a],'receipts':[]},set())[0]==[]
