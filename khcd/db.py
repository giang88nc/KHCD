import os
import threading
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

# POOL KẾT NỐI (18/09/2026): trước đây MỖI request mở một kết nối MySQL mới (~30–45 ms, đo trên máy chủ) —
# chiếm gần nửa thời gian của một trang thường. Kết nối trả về pool ở teardown sau khi rollback (không để
# transaction dở), ping(reconnect=True) khi lấy ra để hồi phục sau khi MySQL đóng kết nối rảnh. Pool tách theo
# (host, port, user, db) để CSDL kiểm thử không dùng nhầm kết nối của CSDL thật.
_pools = {}
_pool_lock = threading.Lock()
POOL_MAX = 8

def _pool_key(config):
    return (config['DB_HOST'], int(config['DB_PORT']), config['DB_USER'], config['DB_NAME'])

def db():
    if 'db' not in g:
        conn = None
        key = _pool_key(current_app.config)
        with _pool_lock:
            pool = _pools.setdefault(key, [])
            while pool and conn is None:
                cand = pool.pop()
                try:
                    cand.ping(reconnect=True); conn = cand
                except Exception:
                    try: cand.close()
                    except Exception: pass
        g.db = conn or connect(current_app.config)
        g.db_pool_key = key
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
    if str(current_app.config.get('CD_LIVE','0'))=='1':
        rows=all("SELECT TABLE_NAME,ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ('cd_loans','cd_loan_items','cd_loan_logs','cd_payments')")
        if len(rows)!=4 or any(r['ENGINE']!='InnoDB' for r in rows):raise BusinessError('SQL mới cần đủ bốn bảng InnoDB trước khi ghi.')
        return
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
    key = g.pop('db_pool_key', None)
    if not conn:
        return
    try:
        conn.rollback()   # request lỗi giữa transaction → trả kết nối sạch, không kéo khóa sang request sau
        if key is not None and getattr(conn, 'open', False):
            with _pool_lock:
                pool = _pools.setdefault(key, [])
                if len(pool) < POOL_MAX:
                    pool.append(conn); return
    except Exception:
        pass
    try: conn.close()
    except Exception: pass
