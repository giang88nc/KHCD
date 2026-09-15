"""Create local secrets; never overwrite an existing configuration."""
import sys
import secrets
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
env=ROOT/'.env'
if env.exists():
    print('Da co .env; giu nguyen cau hinh.');sys.exit(0)
content=(ROOT/'.env.example').read_text(encoding='utf-8')
content=content.replace('SECRET_KEY=','SECRET_KEY='+secrets.token_hex(32))
env.write_text(content,encoding='utf-8')
(ROOT/'instance').mkdir(exist_ok=True)
print('Da tao .env. Dien DB_PASSWORD, chay scripts/sync_auth_users.py. Dang nhap bang tai khoan KHBL.')
