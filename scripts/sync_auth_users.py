"""Sync only auth_user from KHBL. No plaintext passwords, source writes or deletions."""
import sys
import json
from pathlib import Path
from datetime import datetime

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from khcd import create_app,db,auth

def main():
    app=create_app()
    with app.app_context():
        # Validate/read source before changing the destination schema.
        db.one('SELECT COUNT(*) n FROM '+auth.source_table())
        exists=db.one('SELECT COUNT(*) n FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s',('auth_user',))['n']
        folder=ROOT/'backups';folder.mkdir(exist_ok=True)
        backup=folder/f'auth_user_before_sync_{datetime.now():%Y%m%d_%H%M%S_%f}.json'
        snapshot=dict(database=app.config['DB_NAME'],table_existed=bool(exists),rows=db.all('SELECT * FROM auth_user') if exists else [])
        backup.write_text(json.dumps(snapshot,default=str,ensure_ascii=False,indent=2),encoding='utf-8')
        db.execute(auth.AUTH_DDL)
        result=auth.sync_all()
        print('Synced auth_user:',result)
        print('Destination backup:',backup)

if __name__=='__main__':main()
