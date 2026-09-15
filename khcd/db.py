import os
from contextlib import contextmanager
import pymysql
from flask import current_app, g
from .domain import BusinessError

def connect(config):
    return pymysql.connect(host=config['DB_HOST'], port=int(config['DB_PORT']),
        user=config['DB_USER'], password=config['DB_PASSWORD'], database=config['DB_NAME'],
        charset='utf8mb4', collation='utf8mb4_unicode_ci', cursorclass=pymysql.cursors.DictCursor,
        autocommit=True, connect_timeout=5, read_timeout=20, write_timeout=20,
        init_command="SET time_zone = '+07:00'")

def db():
    if 'db' not in g:
        g.db = connect(current_app.config)
    return g.db

def all(sql, params=()):
    with db().cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()

def one(sql, params=()):
    rows = all(sql, params)
    return rows[0] if rows else None

def execute(sql, params=()):
    with db().cursor() as cur:
        cur.execute(sql, params)
        return cur.lastrowid

def schema_ready():
    row = one("SELECT COUNT(*) n FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='khcd_event'")
    return bool(row['n'])

def require_write():
    if current_app.config['DB_READ_ONLY']:
        raise BusinessError('Đang xem dữ liệu ở chế độ chỉ đọc. Cần hoàn tất kết nối và nâng cấp CSDL trước khi ghi.')
    engines = all("SELECT TABLE_NAME,ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ('pawn','pawn_log','customer','khcd_event','khcd_pawn_meta','khcd_customer_meta')")
    required=('pawn','pawn_log','customer','khcd_event','khcd_pawn_meta','khcd_customer_meta')
    found={row['TABLE_NAME']:row['ENGINE'] for row in engines}
    problems=[name+'='+str(found.get(name,'thiếu bảng')) for name in required if found.get(name)!='InnoDB']
    if problems:
        raise BusinessError('CSDL chưa nâng cấp giao dịch an toàn: '+', '.join(problems)+'. Cần InnoDB để rollback khi lỗi. Sao lưu rồi chạy scripts/migrate.py trước khi ghi.')
    if current_app.config.get('CUSTOMER_MASTER')=='kk':
        link=one("SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='khcd_pawn_customer'")
        if not link or link['ENGINE']!='InnoDB':raise BusinessError('Chưa chuẩn bị liên kết CustID cho phiếu cầm.')

@contextmanager
def transaction():
    require_write()
    conn = db()
    conn.begin()
    try:
        yield
        conn.commit()
    except Exception:
        conn.rollback()
        raise

def close(_=None):
    conn = g.pop('db', None)
    if conn:
        conn.close()
