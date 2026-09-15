from datetime import datetime, timedelta
from khcd import db, customer_master as M
from khcd.domain import now,today
from test_loan_conversion import receipt

URL='/camdo/lap-phieu/phien-giao-dich'


def log(app,pid,stamp,op=4,cash=100,bank=200,interest=300):
    with app.app_context():
        return db.execute('''INSERT INTO pawn_log
            (pawn_id,status_id,date1,date2,date3,sotien,tienlai,total,mbank)
            VALUES (%s,%s,%s,%s,%s,10000000,%s,%s,%s)''',(pid,op,stamp,stamp,stamp,interest,cash,bank))


def test_default_today_uses_transaction_date_and_keeps_each_session(app,client,receipt):
    earlier=datetime.combine(today()-timedelta(days=3),datetime.min.time())
    with app.app_context():db.execute('UPDATE pawn_log SET date1=%s WHERE pawn_id=%s',(earlier,receipt))
    log(app,receipt,now());log(app,receipt,earlier)
    data=client.get(URL).json
    assert data['total']==2 and data['d1']==data['d2']==str(today())
    assert data['rows'][0]['id']>data['rows'][1]['id']
    assert data['totals']['received']=='300' and data['totals']['paid']=='10000000'
    assert data['totals']['cash']=='-3999900' and data['totals']['bank']=='-5999800'
    assert data['totals']['interest']=='300'
    assert all(r['can_open'] and r['pawn_id']==receipt for r in data['rows'])


def test_end_date_includes_last_second_and_totals_cover_all_pages(app,client,receipt):
    start=datetime(2026,4,1)
    for i in range(51):log(app,receipt,start+timedelta(seconds=i))
    last=log(app,receipt,datetime(2026,4,1,23,59,59))
    log(app,receipt,datetime(2026,4,2))
    args={'d1':'2026-04-01','d2':'2026-04-01'}
    first=client.get(URL,query_string=args).json
    second=client.get(URL,query_string=dict(args,page=2)).json
    assert first['total']==52 and len(first['rows'])==50 and len(second['rows'])==2
    assert first['rows'][0]['id']==last
    assert first['totals']==second['totals'] and first['totals']['received']=='15600'
    assert len({r['id'] for r in first['rows']+second['rows']})==52


def test_kk_search_uses_ids_and_retains_old_phone_without_matching_customer(app,client,receipt,monkeypatch):
    app.config['CUSTOMER_MASTER']='kk';calls=[]
    def call(action,**kwargs):
        calls.append((action,kwargs))
        if action=='search_ids':return {'ids':['CU_TEST'] if kwargs['q'] in ('Nguyễn QA','CCCD_QA','new-phone') else []}
        if action=='batch':return {'rows':[{'CustID':'CU_TEST','CustName':'Nguyễn QA','Phone':'new-phone'}]}
        raise AssertionError(action)
    monkeypatch.setattr(M,'call',call)
    for keyword in ('Nguyễn QA','CCCD_QA','new-phone','0900000001'):
        data=client.get(URL,query_string={'q':keyword}).json
        assert data['total']==1 and data['rows'][0]['customer_name']=='Nguyễn QA'
        assert data['rows'][0]['phone']=='0900000001'
    assert client.get(URL,query_string={'q':'not-found'}).json['total']==0
    assert all(action in ('search_ids','batch') for action,_ in calls)


def test_legacy_customer_join_does_not_duplicate_sessions(app,client,receipt):
    with app.app_context():
        for name in ('Trần QA','Khác QA'):db.execute("INSERT INTO customer (phone,name,cccd) VALUES ('0900000001',%s,'CCCD_QA')",(name,))
    for q in ('Trần QA','CCCD_QA','0900000001'):
        assert client.get(URL,query_string={'q':q}).json['total']==1
    assert client.get(URL,query_string={'q':'%'}).json['total']==0


def test_invalid_dates_auth_and_readonly(app,client,receipt):
    for args in ({'d1':'invalid'},{'d1':'2026-09-15','d2':'2026-09-14'},{'d1':'2020-01-01','d2':'2026-01-01'},{'page':'abc'}):
        assert client.get(URL,query_string=args).status_code==400
    app.config['DB_READ_ONLY']=True
    assert client.get(URL).status_code==200
    with client.session_transaction() as s:s.clear()
    assert client.get(URL).status_code in (302,401)


def test_missing_pawn_stays_visible_and_cannot_open(app,client,receipt):
    with app.app_context():db.execute('DELETE FROM pawn WHERE id=%s',(receipt,))
    data=client.get(URL).json
    assert data['total']==1 and not data['rows'][0]['can_open']
    assert data['totals']['paid']=='10000000'


def test_kk_search_outage_is_error_not_empty_result(app,client,receipt,monkeypatch):
    app.config['CUSTOMER_MASTER']='kk'
    def fail(*a,**kw):raise M.Unavailable('KK offline')
    monkeypatch.setattr(M,'call',fail)
    response=client.get(URL,query_string={'q':'QA'})
    assert response.status_code==503 and response.json['error']=='KK offline'
    unfiltered=client.get(URL).json
    assert unfiltered['total']==1 and unfiltered['warnings']
