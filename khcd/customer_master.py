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
    if action=='save' or (action=='popup' and str(payload.get('method','GET')).upper()!='GET'):cache_clear()   # ghi → bỏ cache hồ sơ
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


# DS nhân viên KK (T_EMPLOYEE) đổi rất hiếm nhưng trang quầy hỏi cầu nối MỖI lượt mở — và cầu nối mở kết nối
# ODBC mới tới SQL Server 2005 trên PC KK mỗi lần, thỉnh thoảng treo vài giây (đo 18/09/2026: một lượt 5,4 s).
# Cache trong tiến trình 10 phút; bên cần chắc chắn (kiểm EmpID lúc lập phiếu) gọi employees(refresh=True) khi không thấy.
EMPLOYEES_TTL=600
_employees_cache={'at':0.0,'rows':None}

def employees(refresh=False):
    """Danh sách nhân viên KK, cache 10 phút trong tiến trình (bỏ cache khi chạy kiểm thử)."""
    if current_app.testing:return call('employees')['rows']
    if not refresh and _employees_cache['rows'] is not None and time.time()-_employees_cache['at']<EMPLOYEES_TTL:
        return _employees_cache['rows']
    rows=call('employees')['rows']
    _employees_cache.update(at=time.time(),rows=rows)
    return rows


def adapt(row):
    if not row:return None
    return dict(row,id=str(row['CustID']),name=row.get('CustName') or '',phone=row.get('Phone') or '',
                phone2=row.get('GhiChu2') or '',phone3=row.get('GhiChu3') or '',cccd=row.get('CMND') or '',addr=row.get('Address') or '')


# CACHE HỒ SƠ KHÁCH KK theo CustID (18/09/2026): mỗi lượt get/batch qua cầu nối mở kết nối ODBC tới SQL Server
# 2005 trên PC KK, đo 200–380 ms — Tổng quan (2 batch), Khách hàng, popup XEM đều trả giá này. Hồ sơ khách
# đổi rất hiếm ⇒ giữ 2 phút trong tiến trình; MỌI lượt ghi (save / popup POST) xóa sạch cache để không đọc cũ.
CUSTOMER_TTL=120
_customer_cache={}   # cid -> (thời điểm, hồ sơ đã adapt)

def _cache_get(cid):
    hit=_customer_cache.get(str(cid))
    return dict(hit[1]) if hit and time.time()-hit[0]<CUSTOMER_TTL and not current_app.testing else None

def _cache_put(row):
    if row and not current_app.testing:_customer_cache[str(row['id'])]=(time.time(),dict(row))

def cache_clear():
    _customer_cache.clear();_listing_cache.clear()

def get(cid):
    cached=_cache_get(cid)
    if cached is not None:return {'customer':cached,'cached':True}
    result=call('get',id=str(cid));result['customer']=adapt(result['customer'])
    _cache_put(result['customer'])
    return result


_listing_cache={}   # (q,page) -> (thời điểm, kết quả) — tìm khách trên KK 220–390 ms; giữ 60 s, xóa khi có ghi
LISTING_TTL=60

def listing(q='',page=1):
    key=(str(q),int(page));hit=_listing_cache.get(key)
    if hit and time.time()-hit[0]<LISTING_TTL and not current_app.testing:return hit[1]
    result=call('list',q=q,page=page)
    result['rows']=[adapt(r) for r in result['rows']]
    for r in result['rows']:_cache_put(r)
    if not current_app.testing:_listing_cache[key]=(time.time(),result)
    return result


def hydrate(rows):
    """Persisted CustID only. Never resolve an old pawn by today's phone value."""
    if not rows:return rows
    ids=sorted({str(r['pmv_cust_id']) for r in rows if r.get('pmv_cust_id')})
    lookup={};error=None
    for cid in list(ids):
        hit=_cache_get(cid)
        if hit is not None:lookup[cid]=hit;ids.remove(cid)
    if ids:
        try:
            for r in call('batch',ids=ids)['rows']:
                lookup[str(r['CustID'])]=adapt(r);_cache_put(lookup[str(r['CustID'])])
        except Unavailable as exc:error=str(exc)
    for row in rows:
        c=lookup.get(str(row.get('pmv_cust_id') or ''))
        row.update(customer_name=c['name'] if c else None,cccd=c['cccd'] if c else None,
                   addr=c['addr'] if c else None,customer_phone=c['phone'] if c else None,
                   customer_id=c['id'] if c else None,
                   customer_source_error=error or (None if c else 'Chưa có liên kết khách KK đã xác định.'))
    return rows


def history(cid):
    if str(current_app.config.get('CD_LIVE','0'))=='1':return db.all("SELECT id,sku,principal_balance value,CASE loan_state WHEN 'ACTIVE' THEN 1 WHEN 'REDEEMED' THEN 5 WHEN 'LIQUIDATED' THEN 6 ELSE 0 END status,opened_at date1 FROM cd_loans WHERE cust_id=%s ORDER BY id DESC LIMIT 30",(cid,))
    return db.all('SELECT p.id,p.sku,p.value,p.status,p.date1 FROM pawn p JOIN khcd_pawn_customer k ON k.pawn_id=p.id WHERE k.pmv_cust_id=%s ORDER BY p.id DESC LIMIT 30',(cid,))
