import base64
import pytest
from khcd import create_app, auth, db, customer_master as M


@pytest.fixture
def popup(monkeypatch):
    app=create_app({'TESTING':True,'SECRET_KEY':'popup-unit-only','CUSTOMER_MASTER':'kk','DB_READ_ONLY':False})
    user={'id':1,'username':'popup-test','password':'unused','first_name':'','last_name':'','is_superuser':True}
    monkeypatch.setattr(auth,'current_user',lambda:user)
    monkeypatch.setattr(db,'require_write',lambda:None)
    calls=[]
    def call(action,**payload):
        calls.append((action,payload))
        return {'status':200,'body':base64.b64encode(b'<form id="kh-form"></form>').decode(),
                'headers':{'Content-Type':'text/html; charset=utf-8'}}
    monkeypatch.setattr(M,'call',call)
    client=app.test_client()
    with client.session_transaction() as session:
        session['csrf']='popup-csrf';session['user']='popup-test';session['user_id']=1
    return app,client,calls


def test_popup_requires_auth_and_csrf(popup,monkeypatch):
    app,client,calls=popup
    route='/camdo/khach-hang/popup/api/banle/khach-hang/luu/'
    assert client.post(route,data=b'{}',content_type='application/json').status_code==400
    assert not calls
    monkeypatch.setattr(auth,'current_user',lambda:None)
    assert client.get('/camdo/khach-hang/popup/frame').status_code==302
    assert not calls


def test_raw_upload_and_json_are_preserved(popup):
    app,client,calls=popup
    for raw,ct in [(b'{"scans":["synthetic"]}','application/json'),
                   (b'--test\r\nContent-Disposition: form-data; name="anh_truoc"; filename="test.jpg"\r\nContent-Type: image/jpeg\r\n\r\n\xff\xd8\xff\r\n--test--\r\n', 'multipart/form-data; boundary=test')]:
        response=client.post('/camdo/khach-hang/popup/api/banle/khach-hang/qr/phan-tich/',data=raw,
            content_type=ct,headers={'X-CSRFToken':'popup-csrf'})
        assert response.status_code==200
        assert base64.b64decode(calls[-1][1]['body'])==raw
        assert calls[-1][1]['content_type']==ct


def test_frame_is_same_origin_and_main_policy_stays_strict(popup):
    app,client,calls=popup
    response=client.get('/camdo/khach-hang/popup/frame')
    assert response.status_code==200
    assert '<form id="kh-form">' in response.text
    assert 'data-popup-csrf="popup-csrf"' in response.text
    assert response.headers['X-Frame-Options']=='SAMEORIGIN'
    assert "frame-ancestors 'self'" in response.headers['Content-Security-Policy']
    assert calls[-1][1]['path']=='/banle/khach-hang/them/'
    response=client.get('/camdo/khach-hang/popup/frame?cust_id=CU_TEST')
    assert calls[-1][1]['path']=='/banle/khach-hang/CU_TEST/sua/'
    response=client.get('/missing-popup-test-page')
    assert response.headers['X-Frame-Options']=='DENY'
    assert "'unsafe-inline'" not in response.headers['Content-Security-Policy']


def test_success_only_when_bridge_completes(popup,monkeypatch):
    app,client,calls=popup
    def saved(*args,**kwargs):
        return {'status':204,'body':'','headers':{'HX-Trigger':'{"khachSaved":{"custId":"CU_TEST"}}'}}
    monkeypatch.setattr(M,'call',saved)
    result=client.post('/camdo/khach-hang/popup/api/banle/khach-hang/luu/',headers={'X-CSRFToken':'popup-csrf'})
    assert result.status_code==204 and 'CU_TEST' in result.headers['HX-Trigger']
    def offline(*args,**kwargs):raise M.Unavailable('Service unavailable')
    monkeypatch.setattr(M,'call',offline)
    result=client.post('/camdo/khach-hang/popup/api/banle/khach-hang/luu/',headers={'X-CSRFToken':'popup-csrf'})
    assert result.status_code==503 and 'HX-Trigger' not in result.headers
