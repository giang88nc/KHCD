"""One-way Django user sync. KHBL owns identity; KHCD owns its login sessions."""
import hashlib
import hmac
import re
from flask import current_app, session
from django.conf import settings

if not settings.configured:
    settings.configure(PASSWORD_HASHERS=[
        'django.contrib.auth.hashers.PBKDF2PasswordHasher',
        'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
        'django.contrib.auth.hashers.ScryptPasswordHasher',
    ])
from django.contrib.auth.hashers import check_password, make_password
from . import db, domain

FIELDS=('id','password','last_login','is_superuser','username','first_name',
        'last_name','email','is_staff','is_active','date_joined','passcode')
# Source last_login must not overwrite the last successful login at KHCD.
UPDATED_FIELDS=tuple(k for k in FIELDS if k not in ('id','last_login'))
AUTH_DDL='''CREATE TABLE IF NOT EXISTS auth_user (
 id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
 password VARCHAR(128) NOT NULL,
 last_login DATETIME(6) NULL,
 is_superuser TINYINT(1) NOT NULL,
 username VARCHAR(150) NOT NULL UNIQUE,
 first_name VARCHAR(150) NOT NULL,
 last_name VARCHAR(150) NOT NULL,
 email VARCHAR(254) NOT NULL,
 is_staff TINYINT(1) NOT NULL,
 is_active TINYINT(1) NOT NULL,
 date_joined DATETIME(6) NOT NULL,
 passcode VARCHAR(128) NOT NULL DEFAULT ''
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci'''

def source_table():
    source=current_app.config['AUTH_SOURCE_DB']
    if not re.fullmatch(r'[A-Za-z0-9_]+',source) or source==current_app.config['DB_NAME']:
        raise RuntimeError('AUTH_SOURCE_DB must be a separate, valid database name.')
    return f'`{source}`.`auth_user`'

def upsert_user(source):
    """Never let a duplicate username silently update a different user ID."""
    existing=db.one('SELECT '+','.join(FIELDS)+' FROM auth_user WHERE id=%s FOR UPDATE',(source['id'],))
    conflict=db.one('SELECT id FROM auth_user WHERE username=%s AND id<>%s FOR UPDATE',(source['username'],source['id']))
    if conflict:
        raise RuntimeError('Conflicting auth_user IDs/usernames; reconcile before syncing.')
    if existing:
        if any(source[k]!=existing[k] for k in UPDATED_FIELDS):
            db.execute('UPDATE auth_user SET '+','.join(k+'=%s' for k in UPDATED_FIELDS)+' WHERE id=%s',
                tuple(source[k] for k in UPDATED_FIELDS)+(source['id'],))
    else:
        db.execute('INSERT INTO auth_user ('+','.join(FIELDS)+') VALUES ('+','.join(['%s']*len(FIELDS))+')',tuple(source[k] for k in FIELDS))
    return db.one('SELECT '+','.join(FIELDS)+' FROM auth_user WHERE id=%s',(source['id'],))

def sync_user(*,username=None,user_id=None):
    """Read source inside a transaction to avoid out-of-order concurrent refreshes."""
    conn=db.db();conn.begin()
    try:
        # READ lock serializes password/active changes in the source until copied.
        clause='id=%s' if user_id is not None else 'username=%s'
        value=user_id if user_id is not None else username
        source=db.one('SELECT '+','.join(FIELDS)+' FROM '+source_table()+' WHERE '+clause+' FOR SHARE',(value,))
        if source:
            result=upsert_user(source)
        else:
            db.execute('UPDATE auth_user SET is_active=0 WHERE '+clause,(value,))
            result=None
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise

def sync_all():
    conn=db.db();conn.begin()
    try:
        users=db.all('SELECT '+','.join(FIELDS)+' FROM '+source_table()+' ORDER BY id FOR SHARE')
        for user in users: upsert_user(user)
        # Preserve rows and historic references when accounts are removed upstream.
        db.execute('UPDATE auth_user target LEFT JOIN '+source_table()+' source ON target.id=source.id SET target.is_active=0 WHERE source.id IS NULL')
        conn.commit()
        return dict(total=len(users),active=sum(bool(u['is_active']) for u in users))
    except Exception:
        conn.rollback()
        raise

def session_signature(user):
    # Do not put password hashes themselves in client-side Flask sessions.
    value=f"khbl-auth-v1:{user['id']}:{user['password']}"
    return hmac.new(current_app.secret_key.encode(),value.encode(),hashlib.sha256).hexdigest()

def verify_password(password,encoded):
    try:
        # Native Django verification; no hash conversion and no source password reset.
        return check_password(password,encoded)
    except (ValueError,TypeError,OverflowError):
        return False

def authenticate(username,password):
    user=sync_user(username=username)
    if not user:
        make_password(password)  # Cost for an unknown user, as in Django's backend.
        return None
    valid=verify_password(password,user['password'])
    return user if valid and user['is_active'] else None

def establish_session(user):
    import secrets
    session.clear()
    session.update(user_id=user['id'],user=user['username'],auth_version=1,
        auth_signature=session_signature(user),csrf=secrets.token_urlsafe(32))
    session.permanent=True
    db.execute('UPDATE auth_user SET last_login=%s WHERE id=%s',
        (domain.now(),user['id']))   # giờ VN như mọi cột khj_cd (sửa 20/09/2026)

def current_user():
    if session.get('auth_version')!=1 or not isinstance(session.get('user_id'),int):
        return None
    user=sync_user(user_id=session['user_id'])
    if not user or not user['is_active'] or not hmac.compare_digest(session.get('auth_signature',''),session_signature(user)):
        return None
    session['user']=user['username']
    return user
