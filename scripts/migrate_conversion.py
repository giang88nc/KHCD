"""Add four staged conversion tables only, after a consistent backup."""
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from dotenv import dotenv_values
import pymysql
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from khcd.loan_conversion import DDL


def main():
    cfg=dotenv_values(ROOT/'.env')
    conn=pymysql.connect(host=cfg['DB_HOST'],port=int(cfg['DB_PORT']),user=cfg['DB_USER'],password=cfg['DB_PASSWORD'],database=cfg['DB_NAME'],autocommit=True)
    with conn.cursor() as c:
        c.execute("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ('pawn','pawn_log','customer') AND ENGINE='InnoDB'")
        if c.fetchone()[0]!=3:raise SystemExit('Base tables must be InnoDB before a transactional backup.')
    folder=ROOT/'backups';folder.mkdir(exist_ok=True)
    backup=folder/f"{cfg['DB_NAME']}_conversion_{datetime.now():%Y%m%d_%H%M%S}.sql"
    env=os.environ.copy();env['MYSQL_PWD']=cfg['DB_PASSWORD']
    command=[r'D:\PYTHON\mysql8\bin\mysqldump.exe','--host='+cfg['DB_HOST'],'--port='+cfg['DB_PORT'],'--user='+cfg['DB_USER'],
        '--single-transaction','--skip-lock-tables','--hex-blob','--no-tablespaces','--set-gtid-purged=OFF',cfg['DB_NAME']]
    with backup.open('wb') as out:result=subprocess.run(command,stdout=out,stderr=subprocess.PIPE,env=env)
    if result.returncode or backup.stat().st_size<1024:raise SystemExit('Backup failed; no schema changes applied.')
    with conn.cursor() as c:
        for sql in DDL:c.execute(sql)
        c.execute("SELECT TABLE_NAME,ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ('cd_loans','cd_loan_items','cd_loan_logs','cd_payments')")
        print('Ready:',c.fetchall())
    conn.close();print('Backup:',backup)

if __name__=='__main__':main()
