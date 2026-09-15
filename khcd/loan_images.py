"""Read legacy image references through authenticated routes; never copy/delete."""
import hashlib
import json
from pathlib import Path
from flask import current_app
from PIL import Image
from . import db

LABELS={'legacy1':'Ảnh phiếu cũ 1','legacy2':'Ảnh phiếu cũ 2','anh_truoc':'CCCD mặt trước','anh_sau':'CCCD mặt sau','anh_sp1':'Ảnh vàng 1','anh_sp2':'Ảnh vàng 2','anh_qr':'QR chuyển khoản khách'}
FORMATS={'JPEG':'image/jpeg','PNG':'image/png','WEBP':'image/webp','GIF':'image/gif'}

def documents(loan):
    try:
        value=json.loads(loan['documents_json'])
        return value if isinstance(value,dict) else {}
    except (ValueError,TypeError):return {}

def legacy_path(name):
    if not isinstance(name,str) or not name or name in ('.','..') or any(c in name for c in '/\\:\x00'):
        return None,'Tên ảnh không hợp lệ; không truy cập đường dẫn ngoài kho ảnh.'
    try:
        root=Path(current_app.config['LEGACY_PAWN_IMAGE_ROOT']).resolve()
        path=(root/name).resolve()
        if not path.is_relative_to(root):return None,'Đường dẫn ảnh ra ngoài kho được cấu hình.'
        if not path.is_file():return None,'Thiếu tệp ảnh trong thư mục nguồn đã cấu hình.'
        if path.stat().st_size>15*1024*1024:return None,'Ảnh vượt 15 MB; cần kiểm tra tệp nguồn.'
        with Image.open(path) as img:
            if img.format not in FORMATS or img.width*img.height>25_000_000:return None,'Định dạng hoặc kích thước ảnh không hỗ trợ.'
            mime=FORMATS[img.format];img.verify()
        return path,mime
    except (OSError,ValueError,RuntimeError,Image.DecompressionBombError):return None,'Tệp ảnh hỏng hoặc không đọc được.'

def inventory(loan):
    docs=documents(loan);rows=[]
    for slot,key in [('legacy1','legacy_img1'),('legacy2','legacy_img2')]:
        name=docs.get(key)
        if not name:continue
        path,detail=legacy_path(name)
        rows.append(dict(slot=slot,label=LABELS[slot],filename=name,available=bool(path),state='ok' if path else 'error',detail='Đọc trực tiếp ảnh cũ; chưa có checksum tại thời điểm chuyển.' if path else detail))
    refs=docs.get('pawn_photo_refs') or []
    if not isinstance(refs,list):
        rows.append(dict(slot='',label='Tham chiếu ảnh MySQL',filename='',available=False,state='error',detail='Cấu trúc danh sách ảnh không hợp lệ.'));refs=[]
    for ref in refs:
        if not isinstance(ref,dict):continue
        kind=ref.get('kind')
        if kind not in LABELS or kind.startswith('legacy'):continue
        found=db.one('SELECT OCTET_LENGTH(data) size,SHA2(data,256) sha256 FROM khcd_pawn_photo WHERE pawn_id=%s AND kind=%s',(loan['legacy_pawn_id'],kind))
        valid=bool(found and found['sha256']==ref.get('sha256') and found['size']==ref.get('size'))
        rows.append(dict(slot=kind,label=LABELS[kind],filename=kind,available=valid,state='ok' if valid else 'error',detail='Tái sử dụng ảnh MySQL, checksum khớp bản chuyển.' if valid else 'Ảnh thiếu hoặc đã thay đổi so với lúc chuyển.'))
    if not rows:rows.append(dict(slot='',label='Hồ sơ ảnh',filename='',available=False,state='warning',detail='Bản chuyển chưa có tham chiếu ảnh. Không đồng nghĩa đã đủ ảnh hồ sơ.'))
    return rows

def blob(loan,slot):
    refs=documents(loan).get('pawn_photo_refs') or []
    if not isinstance(refs,list):return None
    ref=next((r for r in refs if isinstance(r,dict) and r.get('kind')==slot),None)
    if not ref:return None
    row=db.one('SELECT data FROM khcd_pawn_photo WHERE pawn_id=%s AND kind=%s',(loan['legacy_pawn_id'],slot))
    if not row or hashlib.sha256(row['data']).hexdigest()!=ref.get('sha256'):return None
    return row['data']
