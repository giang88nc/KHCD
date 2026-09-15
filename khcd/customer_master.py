"""KK master customer access through the private, authenticated KHBL service."""
import hashlib
import hmac
import json
import time
import uuid
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from flask import current_app, g
from . import db
from .domain import BusinessError


class Unavailable(BusinessError):
    pass


def enabled():
    return current_app.config.get('CUSTOMER_MASTER')=='kk'


def call(action,**payload):
    if current_app.testing:
        raise Unavailable('Kết nối khách thật bị chặn trong kiểm thử.')
    actor=getattr(g,'auth_user',None)
    if not actor:raise Unavailable('Cần đăng nhập để truy cập khách KK.')
    try:
        key=Path(current_app.config['CUSTOMER_BRIDGE_KEY_FILE']).read_text().strip().encode()
        body=json.dumps(dict(payload,action=action,actor=actor['id'],actor_proof=hmac.new(key,actor['password'].encode(),hashlib.sha256).hexdigest()),ensure_ascii=False).encode()
        stamp=str(int(time.time()));nonce=uuid.uuid4().hex
        signature=hmac.new(key,stamp.encode()+b'\n'+nonce.encode()+b'\n'+body,hashlib.sha256).hexdigest()
        req=Request('http://127.0.0.1:18202/v1/customers',data=body,headers={'Content-Type':'application/json',
            'X-KHCD-Time':stamp,'X-KHCD-Nonce':nonce,'X-KHCD-Signature':signature})
        with urlopen(req,timeout=90 if action in ('popup','pawn_images','pawn_qr') else 45 if action=='save' else 20) as response:
            result=json.load(response)
        if result.get('error'):raise Unavailable(result['error'])
        return result
    except HTTPError as error:
        try:message=json.load(error).get('error')
        except Exception:message=None
        raise Unavailable(message or 'Dịch vụ khách KK từ chối yêu cầu.') from None
    except (OSError,URLError,ValueError):
        raise Unavailable('Chưa kết nối được khách KK. Nếu vừa lưu, giữ mã yêu cầu và kiểm tra kết quả trước khi gửi lại.') from None


def adapt(row):
    if not row:return None
    return dict(row,id=str(row['CustID']),name=row.get('CustName') or '',phone=row.get('Phone') or '',
                phone2=row.get('GhiChu2') or '',phone3=row.get('GhiChu3') or '',cccd=row.get('CMND') or '',addr=row.get('Address') or '')


def get(cid):
    result=call('get',id=str(cid));result['customer']=adapt(result['customer'])
    return result


def listing(q='',page=1):
    result=call('list',q=q,page=page)
    result['rows']=[adapt(r) for r in result['rows']]
    return result


def hydrate(rows):
    """Persisted CustID only. Never resolve an old pawn by today's phone value."""
    if not rows:return rows
    ids=sorted({str(r['pmv_cust_id']) for r in rows if r.get('pmv_cust_id')})
    lookup={};error=None
    if ids:
        try:
            lookup={str(r['CustID']):adapt(r) for r in call('batch',ids=ids)['rows']}
        except Unavailable as exc:error=str(exc)
    for row in rows:
        c=lookup.get(str(row.get('pmv_cust_id') or ''))
        row.update(customer_name=c['name'] if c else None,cccd=c['cccd'] if c else None,
                   addr=c['addr'] if c else None,customer_phone=c['phone'] if c else None,
                   customer_id=c['id'] if c else None,
                   customer_source_error=error or (None if c else 'Chưa có liên kết khách KK đã xác định.'))
    return rows


def history(cid):
    return db.all('SELECT p.id,p.sku,p.value,p.status,p.date1 FROM pawn p JOIN khcd_pawn_customer k ON k.pawn_id=p.id WHERE k.pmv_cust_id=%s ORDER BY p.id DESC LIMIT 30',(cid,))
