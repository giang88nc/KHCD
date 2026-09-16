from khcd import customer_master as master


def test_popup_static_cache_preserves_auth_and_revalidates(app,client,tmp_path,monkeypatch):
    root=tmp_path/'assets';(root/'css').mkdir(parents=True)
    file=root/'css'/'khbl.css';file.write_text('body{color:red}')
    app.config['KHBL_STATIC_ROOT']=str(root)
    monkeypatch.setattr(master,'call',lambda *a,**k: (_ for _ in ()).throw(AssertionError('Static asset must not use bridge')))
    url='/camdo/khach-hang/popup/assets/css/khbl.css'
    first=client.get(url+'?v='+str(file.stat().st_mtime_ns))
    assert first.status_code==200 and first.data==file.read_bytes()
    assert 'private' in first.headers['Cache-Control'] and 'max-age=86400' in first.headers['Cache-Control']
    assert client.get(url,headers={'If-None-Match':first.headers['ETag']}).status_code==304
    file.write_text('body{color:blue;background:white}')
    changed=client.get(url,headers={'If-None-Match':first.headers['ETag']})
    assert changed.status_code==200 and changed.data==file.read_bytes()
    assert app.test_client().get(url).status_code==302
    assert 'no-store' in app.test_client().get(url).headers['Cache-Control']
    assert client.get('/camdo/khach-hang/popup/assets/not-allowed.txt').status_code==404


def test_popup_frame_remains_private_no_store(app,client,monkeypatch):
    import base64
    app.config['CUSTOMER_MASTER']='kk'
    monkeypatch.setattr(master,'call',lambda *a,**k:dict(status=200,body=base64.b64encode(b'<div id="kh-form"></div>').decode()))
    response=client.get('/camdo/khach-hang/popup/photos?group=front')
    assert response.status_code==200
    assert response.headers['Cache-Control']=='no-store'
    assert 'SAMEORIGIN'==response.headers['X-Frame-Options']
    assert b'/assets/css/khbl.css?v=' in response.data
