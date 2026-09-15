import os
import uuid
from pathlib import Path
import pytest
import pymysql
from dotenv import dotenv_values
from khcd import auth
from django.contrib.auth.hashers import make_password
from khcd import create_app
from scripts.migrate import upgrade

@pytest.fixture(scope='session')
def mysql_config():
    path=os.environ.get('KHCD_TEST_ENV')
    if not path: pytest.skip('Set KHCD_TEST_ENV to a local admin config for isolated MySQL tests.')
    cfg=dotenv_values(path)
    name='khj_cd_test_'+uuid.uuid4().hex[:12]
    conn=pymysql.connect(host=cfg['DB_HOST'],port=int(cfg['DB_PORT']),user=cfg['DB_USER'],password=cfg['DB_PASSWORD'],autocommit=True,charset='utf8mb4')
    with conn.cursor() as c:
        c.execute(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
        c.execute(f'CREATE DATABASE `{name}_auth` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
        c.execute('USE `'+name+'_auth`');c.execute(auth.AUTH_DDL)
        # Copy schema only. No real customer records enter the test database.
        for table in ('customer','pawn','pawn_log','pawn_status','gold_price'):
            c.execute(f'SHOW CREATE TABLE `{cfg["DB_NAME"]}`.`{table}`')
            ddl=c.fetchone()[1]
            c.execute('USE `'+name+'`');c.execute(ddl)
    upgrade(conn)
    from khcd.loan_conversion import DDL as CONVERSION_DDL
    with conn.cursor() as c:
        for ddl in CONVERSION_DDL:c.execute(ddl)
    with conn.cursor() as c:c.execute(auth.AUTH_DDL)
    with conn.cursor() as c:
        c.execute("INSERT INTO gold_price (id,name,scut,unit,sort) VALUES (1,'VÀNG 610','61','chỉ',1),(2,'VÀNG 9999','99','chỉ',2),(7,'Khác','#','#',7)")
        for i,label in [(1,'Cầm mới'),(4,'Gia hạn'),(5,'Chuộc đồ')]:c.execute('INSERT INTO pawn_status (id,name) VALUES (%s,%s)',(i,label))
    yield dict(cfg,DB_NAME=name,AUTH_SOURCE_DB=name+'_auth',DB_READ_ONLY=False,TESTING=True,SECRET_KEY='test-key-only',MIN_INTEREST_DAYS=1,CUSTOMER_MASTER='legacy')
    assert name.startswith('khj_cd_test_') and len(name)==24
    with conn.cursor() as c:
        c.execute('DROP DATABASE `'+name+'`')
        c.execute('DROP DATABASE `'+name+'_auth`')
    conn.close()

@pytest.fixture
def app(mysql_config):
    app=create_app(mysql_config)
    with app.app_context():
        from khcd import db
        for t in ('cd_payments','cd_loan_logs','cd_loan_items','cd_loans','khcd_pawn_photo','khcd_pawn_desk','khcd_event','khcd_customer_meta','khcd_pawn_meta','khcd_pawn_customer','pawn_log','pawn','customer'):
            db.execute('DELETE FROM '+t)
        db.execute('DELETE FROM auth_user')
        db.execute('DELETE FROM '+auth.source_table())
        db.execute('INSERT INTO '+auth.source_table()+''' (id,username,password,first_name,last_name,email,is_active,is_staff,is_superuser,date_joined)
          VALUES (1,'khj_admin',%s,'Test','Admin','',1,1,1,UTC_TIMESTAMP())''',(make_password('test-pass'),))
        auth.sync_all()
    from khcd.views import attempts
    attempts.clear()
    return app

@pytest.fixture
def client(app):
    c=app.test_client()
    with app.app_context():
        user=auth.sync_user(username='khj_admin');signature=auth.session_signature(user)
    with c.session_transaction() as s:
        s.update(user='khj_admin',user_id=1,auth_version=1,auth_signature=signature,csrf='token')
    return c
