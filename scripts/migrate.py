"""Back up first, then apply additive, resumable legacy schema upgrade."""
import os
import sys
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import dotenv_values
import pymysql

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
DDL=[
'''CREATE TABLE IF NOT EXISTS khcd_pawn_customer (
 pawn_id INT NOT NULL PRIMARY KEY, pmv_cust_id VARCHAR(30) NOT NULL,
 source VARCHAR(32) NOT NULL, linked_at DATETIME NOT NULL,
 INDEX ix_pmv_customer(pmv_cust_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4''',
'''CREATE TABLE IF NOT EXISTS khcd_event (
 id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
 kind VARCHAR(32) NOT NULL, pawn_id INT NULL, customer_id INT NULL,
 actor VARCHAR(255) NOT NULL, created_at DATETIME NOT NULL, effective_date DATE NOT NULL,
 principal DECIMAL(18,0) NOT NULL DEFAULT 0, interest DECIMAL(18,0) NOT NULL DEFAULT 0,
 note VARCHAR(255) NOT NULL DEFAULT '', before_json JSON NULL, after_json JSON NULL,
 request_key VARCHAR(64) NOT NULL UNIQUE,
 INDEX ix_event_date (effective_date,id), INDEX ix_event_pawn (pawn_id,id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci''',
'''CREATE TABLE IF NOT EXISTS khcd_pawn_meta (
 pawn_id INT NOT NULL PRIMARY KEY, customer_id INT NOT NULL,
 INDEX ix_customer (customer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4''',
'''CREATE TABLE IF NOT EXISTS khcd_customer_meta (
 customer_id INT NOT NULL PRIMARY KEY, archived TINYINT NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4''',
]

def upgrade(conn):
    from khcd.pawn_desk import DDL as DESK_DDL
    with conn.cursor() as c:
        for table in ('customer','pawn','pawn_log'):
            c.execute(f'ALTER TABLE `{table}` ENGINE=InnoDB')
        c.execute('ALTER TABLE pawn MODIFY value DECIMAL(18,0) NULL, MODIFY percent DECIMAL(12,8) NULL, MODIFY wgg1 DECIMAL(12,4) NULL, MODIFY whh1 DECIMAL(12,4) NULL, MODIFY wgg2 DECIMAL(12,4) NULL, MODIFY whh2 DECIMAL(12,4) NULL')
        c.execute('ALTER TABLE pawn_log MODIFY sotien DECIMAL(18,0) NULL, MODIFY tienthem DECIMAL(18,0) NULL, MODIFY tienbot DECIMAL(18,0) NULL, MODIFY tienlai DECIMAL(18,0) NULL, MODIFY total DECIMAL(18,0) NULL, MODIFY mbank DECIMAL(18,0) NULL, MODIFY percent DECIMAL(12,8) NULL')
        for sql in DDL + DESK_DDL: c.execute(sql)
        for table,name,columns in [('pawn','ix_khcd_phone','phone'),('pawn','ix_khcd_status_due','status,date3'),('pawn','ix_khcd_sku','sku'),('pawn_log','ix_khcd_pawn','pawn_id,id'),('pawn_log','ix_khcd_date','date2,status_id'),('customer','ix_khcd_phone','phone')]:
            c.execute('SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND INDEX_NAME=%s',(table,name))
            if c.fetchone()[0]==0: c.execute(f'CREATE INDEX {name} ON {table} ({columns})')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--env',default=str(ROOT/'.env'))
    parser.add_argument('--dump-exe',default=r'D:\PYTHON\mysql8\bin\mysqldump.exe')
    parser.add_argument('--backup-env',help='Optional backup account targeting the same host, port and database')
    args=parser.parse_args()
    cfg=dotenv_values(args.env)
    backup_cfg=dotenv_values(args.backup_env) if args.backup_env else cfg
    if any(backup_cfg.get(k)!=cfg.get(k) for k in ('DB_HOST','DB_PORT','DB_NAME')):
        raise SystemExit('Backup configuration must target exactly the same host, port and database.')
    if not cfg.get('DB_PASSWORD'): raise SystemExit('Thieu DB_PASSWORD trong .env.')
    conn=pymysql.connect(host=cfg['DB_HOST'],port=int(cfg['DB_PORT']),user=cfg['DB_USER'],password=cfg['DB_PASSWORD'],database=cfg['DB_NAME'],autocommit=True)
    with conn.cursor() as c:
        # No silent rounding of fractional money from a legacy installation.
        for table,cols in [('pawn',['value']),('pawn_log',['sotien','tienthem','tienbot','tienlai','total','mbank'])]:
            for col in cols:
                c.execute(f'SELECT COUNT(*) FROM {table} WHERE {col} IS NOT NULL AND {col}<>ROUND({col},0)')
                if c.fetchone()[0]: raise SystemExit(f'Can doi soat so tien le tai {table}.{col}; chua thay doi CSDL.')
        before={}
        for table in ('customer','pawn','pawn_log'):
            c.execute(f'SELECT COUNT(*) FROM {table}');before[table]=c.fetchone()[0]
    folder=ROOT/'backups';folder.mkdir(exist_ok=True)
    backup=folder/f"{cfg['DB_NAME']}_{datetime.now():%Y%m%d_%H%M%S}.sql"
    env=os.environ.copy();env['MYSQL_PWD']=backup_cfg['DB_PASSWORD']
    command=[args.dump_exe,'--host='+cfg['DB_HOST'],'--port='+cfg['DB_PORT'],'--user='+backup_cfg['DB_USER'],
             '--skip-lock-tables','--routines','--triggers','--hex-blob','--no-tablespaces','--set-gtid-purged=OFF',cfg['DB_NAME']]
    # Database-scoped READ locks cover both MyISAM and InnoDB. Do not require
    # global RELOAD privileges or use READ LOCAL, which permits MyISAM inserts.
    with conn.cursor() as c:
        c.execute("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE'")
        tables=[row[0] for row in c.fetchall()]
        if not tables:raise SystemExit('Khong co bang de sao luu; chua thay doi CSDL.')
        c.execute('LOCK TABLES '+','.join('`'+name.replace('`','``')+'` READ' for name in tables))
    try:
        with backup.open('wb') as out:
            proc=subprocess.run(command,stdout=out,stderr=subprocess.PIPE,env=env,timeout=180)
    finally:
        with conn.cursor() as c:c.execute('UNLOCK TABLES')
    if proc.returncode or backup.stat().st_size<1024:
        raise SystemExit('Sao luu that bai; khong thay doi CSDL. Kiem tra quyen mysqldump.')
    upgrade(conn)
    with conn.cursor() as c:
        for table,count in before.items():
            c.execute(f'SELECT COUNT(*) FROM {table}')
            if c.fetchone()[0]!=count: raise SystemExit('So luong du lieu thay doi; can doi soat ban sao luu.')
    conn.close()
    print('Nang cap xong. Bao toan so luong:',before)
    print('Ban sao luu:',backup)

if __name__=='__main__': main()
