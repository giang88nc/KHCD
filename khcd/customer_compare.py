"""Candidate comparison only. Never writes customer records or confirms a mapping."""
import re
import unicodedata
from . import db


def phone_key(value):
    value=re.sub(r'[ \t\r\n\u00a0().-]', '', str(value or ''))
    if value.startswith('+84'): value='0'+value[3:]
    elif value.startswith('0084'): value='0'+value[4:]
    elif value.startswith('84') and len(value) in (11,12): value='0'+value[2:]
    return value if re.fullmatch(r'0[0-9]{9,10}',value) else ''


def identity_key(value):
    value=re.sub(r'[ \t\r\n\u00a0]','',str(value or ''))
    return value if re.fullmatch(r'(?:[0-9]{9}|[0-9]{12})',value) else ''


def text_key(value):
    return ' '.join(unicodedata.normalize('NFC',str(value or '')).casefold().split())


def local_directory():
    # The phone is normalized in memory; the operational key is never modified.
    return db.all('SELECT id,name,phone,cccd,addr FROM customer ORDER BY id')


def candidates(record,rows):
    phone=phone_key(record.get('phone'));identity=identity_key(record.get('cccd'))
    return [r for r in rows if (phone and phone_key(r.get('phone'))==phone) or
            (identity and identity_key(r.get('cccd'))==identity)]


def status(record,matches):
    phone=phone_key(record.get('phone'));identity=identity_key(record.get('cccd'))
    if len(matches)>1: return {'key':'multiple','label':'Nhiều ứng viên','tone':'warning','count':len(matches)}
    if matches:
        other=matches[0];other_id=identity_key(other.get('cccd'))
        if identity and other_id and identity!=other_id:
            return {'key':'conflict','label':'Khác CCCD','tone':'danger','count':1}
        if phone and phone_key(other.get('phone'))==phone:
            return {'key':'candidate','label':'Ứng viên trùng SĐT','tone':'success','count':1}
        return {'key':'identity','label':'Trùng CCCD · khác SĐT','tone':'warning','count':1}
    if not phone and not identity:
        return {'key':'insufficient','label':'Thiếu thông tin đối chiếu','tone':'neutral','count':0}
    return {'key':'missing','label':'Chưa tìm thấy đối ứng','tone':'neutral','count':0}


def comparison(cd,pmv):
    result=[]
    for field,label,normalizer in [('name','Họ tên',text_key),('phone','Số điện thoại',phone_key),
                                  ('cccd','CCCD / CMND',identity_key),('addr','Địa chỉ',text_key)]:
        left=str(cd.get(field) or '');right=str(pmv.get(field) or '')
        normalized_left=normalizer(left);normalized_right=normalizer(right)
        if not left.strip() and not right.strip():state='empty';description='Hai bên chưa có'
        elif not left.strip():state='missing';description='CĐ chưa có'
        elif not right.strip():state='missing';description='PMV chưa có'
        elif field in ('phone','cccd') and (not normalized_left or not normalized_right):state='invalid';description='Cần kiểm tra định dạng'
        elif normalized_left==normalized_right:state='same';description='Trùng khớp' if left==right else 'Tương đương cách viết'
        else:state='different';description='Khác thông tin'
        result.append(dict(field=field,label=label,cd=left,pmv=right,state=state,description=description,
            note='Giữ nguyên khóa liên kết phiếu' if field=='phone' else 'Chỉ so sánh; chưa thay đổi dữ liệu'))
    return result
