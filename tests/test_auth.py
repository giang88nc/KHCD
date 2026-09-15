import pytest
from khcd import auth,db
from django.contrib.auth.hashers import make_password

def login(client,username='khj_admin',password='test-pass'):
    client.get('/login')
    with client.session_transaction() as s:csrf=s['csrf']
    return client.post('/login',data=dict(username=username,password=password,csrf_token=csrf))

def test_django_password_format():
    encoded=make_password('Mật khẩu thử 123')
    assert encoded.startswith('pbkdf2_sha256$')
    assert auth.verify_password('Mật khẩu thử 123',encoded)
    assert not auth.verify_password('wrong',encoded)
    assert not auth.verify_password('x','!unusable')
    assert not auth.verify_password('x','pbkdf2_sha256$not-valid')

def test_sync_exact_hash_flags_passcode_and_idempotency(app):
    with app.app_context():
        source=db.one('SELECT * FROM '+auth.source_table()+' WHERE id=1')
        db.execute('UPDATE '+auth.source_table()+" SET passcode='!unusable-test',is_staff=0,first_name='Mới' WHERE id=1")
        assert auth.sync_all()==dict(total=1,active=1)
        auth.sync_all()
        target=db.one('SELECT * FROM auth_user WHERE id=1')
        assert target['password']==source['password']
        assert target['passcode']=='!unusable-test' and target['first_name']=='Mới' and target['is_staff']==0
        assert db.one('SELECT COUNT(*) n FROM auth_user')['n']==1

def test_valid_login_source_unchanged_and_local_last_login(app):
    with app.app_context():before=db.one('SELECT * FROM '+auth.source_table()+' WHERE id=1')
    c=app.test_client();assert login(c).status_code==302
    assert c.get('/').status_code==200
    with c.session_transaction() as s:
        assert s['user_id']==1 and s['user']=='khj_admin'
        assert before['password'] not in str(dict(s))
    with app.app_context():
        assert db.one('SELECT * FROM '+auth.source_table()+' WHERE id=1')==before
        assert db.one('SELECT last_login FROM auth_user WHERE id=1')['last_login'] is not None
        auth.sync_all()
        assert db.one('SELECT last_login FROM auth_user WHERE id=1')['last_login'] is not None

def test_wrong_unknown_inactive_and_old_env_login_denied(app):
    c=app.test_client()
    assert login(c,password='wrong').status_code==401
    assert login(c,username='missing').status_code==401
    with app.app_context():db.execute('UPDATE '+auth.source_table()+' SET is_active=0 WHERE id=1')
    assert login(c).status_code==401
    with c.session_transaction() as s:s.clear();s['user']='khj_admin';s['csrf']='old'
    assert c.get('/').status_code==302

@pytest.mark.parametrize('change',['inactive','password','deleted'])
def test_existing_session_revoked_after_source_change(app,change):
    c=app.test_client();assert login(c).status_code==302
    with app.app_context():
        if change=='deleted':db.execute('DELETE FROM '+auth.source_table()+' WHERE id=1')
        elif change=='inactive':db.execute('UPDATE '+auth.source_table()+' SET is_active=0 WHERE id=1')
        else:db.execute('UPDATE '+auth.source_table()+' SET password=%s WHERE id=1',(make_password('new-pass'),))
    assert c.get('/').status_code==302
    with c.session_transaction() as s:assert not s.get('user_id')
    if change=='password':
        assert login(c).status_code==401
        assert login(c,password='new-pass').status_code==302
    with app.app_context():assert db.one('SELECT COUNT(*) n FROM auth_user')['n']==1

def test_new_nonstaff_account_auto_sync_and_audit_actor(app):
    with app.app_context():
        db.execute('INSERT INTO '+auth.source_table()+''' (id,username,password,first_name,last_name,email,is_active,is_staff,is_superuser,date_joined)
        VALUES (2,'ketoan_test',%s,'Kế toán','','',1,0,0,UTC_TIMESTAMP())''',(make_password('new-user-pass'),))
    c=app.test_client();assert login(c,'ketoan_test','new-user-pass').status_code==302
    with c.session_transaction() as s:token=s['csrf']
    assert c.post('/camdo/khach-hang/moi',data=dict(csrf_token=token,name='Test',phone='0900000002')).status_code==302
    with app.app_context():
        assert db.one('SELECT is_superuser FROM auth_user WHERE id=2')['is_superuser']==0
        assert db.one('SELECT actor FROM khcd_event')['actor']=='ketoan_test'

def test_source_unavailable_fails_closed(app,client):
    app.config['AUTH_SOURCE_DB']='khcd_source_missing_test'
    assert client.get('/camdo/khach-hang').status_code==503

def test_username_conflict_rolls_back_instead_of_merging(app):
    with app.app_context():
        db.execute('UPDATE auth_user SET id=99 WHERE id=1')
        with pytest.raises(RuntimeError,match='Conflicting'):auth.sync_all()
        assert db.one('SELECT id FROM auth_user')['id']==99

def test_login_rate_limit(app):
    c=app.test_client()
    for _ in range(5):assert login(c,password='incorrect').status_code==401
    assert login(c).status_code==429
