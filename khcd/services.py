import hashlib
import json
import uuid
from datetime import timedelta
from decimal import Decimal
from flask import current_app, session
from . import db
from . import customer_master as master
from . import pawn_desk as desk
from .domain import ACTIVE, BusinessError, decimal, money, now, today, parse_date, quote

PAWN_SELECT = """SELECT p.*, c.id customer_id, c.name customer_name, c.cccd, c.addr,
 COALESCE(g.name,CASE p.gold1 WHEN '18k' THEN 'VÀNG 18K (cũ)' WHEN '24k' THEN 'VÀNG 24K (cũ)' WHEN '99.99' THEN 'VÀNG 9999 (cũ)' END) gold_name,
 COALESCE(g.unit,CASE WHEN p.gold1 IN ('18k','24k','99.99') THEN 'chỉ' END) gold_unit,
 COALESCE(g2.name,CASE p.gold2 WHEN '18k' THEN 'VÀNG 18K (cũ)' WHEN '24k' THEN 'VÀNG 24K (cũ)' WHEN '99.99' THEN 'VÀNG 9999 (cũ)' END) gold2_name,
 COALESCE(g2.unit,CASE WHEN p.gold2 IN ('18k','24k','99.99') THEN 'chỉ' END) gold2_unit
 FROM pawn p LEFT JOIN (SELECT phone,MIN(id) id FROM customer GROUP BY phone) cm ON cm.phone=p.phone
 LEFT JOIN customer c ON c.id=cm.id
 LEFT JOIN gold_price g ON g.scut=p.gold1
 LEFT JOIN gold_price g2 ON g2.scut=p.gold2"""


def pawn_select():
    if not master.enabled():return PAWN_SELECT
    return PAWN_SELECT.replace('c.id customer_id, c.name customer_name, c.cccd, c.addr,',
        'k.pmv_cust_id, NULL customer_id, NULL customer_name, NULL cccd, NULL addr,').replace(
        'LEFT JOIN (SELECT phone,MIN(id) id FROM customer GROUP BY phone) cm ON cm.phone=p.phone\n LEFT JOIN customer c ON c.id=cm.id',
        'LEFT JOIN khcd_pawn_customer k ON k.pawn_id=p.id')

def fingerprint(p):
    fields = ('id','date1','date2','date3','value','percent','status','phone','safe','note','mota1','mota2')
    return hashlib.sha256(json.dumps({k:str(p.get(k)) for k in fields}, sort_keys=True).encode()).hexdigest()

def pawn(pawn_id):
    row = db.one(pawn_select()+' WHERE p.id=%s', (pawn_id,))
    if row:
        if master.enabled():master.hydrate([row])
        # PHP uses string "0" to mean the optional second asset is absent.
        if row['gold2']=='0': row['gold2']=None
        row['daily_rate'] = Decimal(str(row['percent'] or 0))/30
        row['fingerprint'] = fingerprint(row)
        row['active'] = row['status'] in ACTIVE
        known={str(g['id']) for g in gold_options()} | {'18k','24k','99.99'}
        row['supported_asset'] = row['gold1'] in known and (not row['gold2'] or row['gold2'] in known)
        row['desk'] = desk.load(pawn_id)
        if row['desk']:
            row['supported_asset'] = all(r['gold'] in known for r in row['desk']['items'])
    return row

def required(data, key, label, maxlen=255):
    val = str(data.get(key,'')).strip()
    if not val or len(val)>maxlen:
        raise BusinessError(f'{label} bắt buộc, tối đa {maxlen} ký tự.')
    return val

def optional(data, key, maxlen=255):
    val = str(data.get(key,'')).strip()
    if len(val)>maxlen:
        raise BusinessError(f'Nội dung {key} quá dài (tối đa {maxlen} ký tự).')
    return val

def event(kind, pawn_id=None, customer_id=None, before=None, after=None, interest=0,
          principal=0, effective=None, note='', key=None):
    return db.execute("""INSERT INTO khcd_event
      (kind,pawn_id,customer_id,actor,created_at,effective_date,principal,interest,note,before_json,after_json,request_key)
      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
      (kind,pawn_id,customer_id,session.get('user','system'),now(),effective or today(),principal,interest,note,
       json.dumps(before,default=str,ensure_ascii=False) if before else None,
       json.dumps(after,default=str,ensure_ascii=False) if after else None,key or str(uuid.uuid4())))

def lock_writes():
    # Covers uniqueness checks on legacy schemas that have no unique phone/SKU keys.
    row=db.one("SELECT GET_LOCK(CONCAT(DATABASE(),':khcd_write'),10) acquired")
    if row['acquired'] != 1:
        raise BusinessError('Có giao dịch đang xử lý. Vui lòng thử lại sau.')

def unlock_writes():
    db.one("SELECT RELEASE_LOCK(CONCAT(DATABASE(),':khcd_write')) released")

def save_customer(data, customer_id=None):
    if master.enabled():raise BusinessError('Khách hàng đã chuyển sang KK. Dùng biểu mẫu khách PMV để lưu.')
    import re
    name=required(data,'name','Họ tên')
    phone=required(data,'phone','Điện thoại',11)
    if not re.fullmatch(r'0\d{9,10}',phone):
        raise BusinessError('Điện thoại gồm 10–11 chữ số, bắt đầu bằng 0.')
    cccd=optional(data,'cccd')
    if cccd and not re.fullmatch(r'(?:\d{9}|\d{12})',cccd):
        raise BusinessError('CCCD/CMND phải có 9 hoặc 12 chữ số.')
    vals=dict(name=name,phone=phone,cccd=cccd,addr=optional(data,'addr'),note=optional(data,'note'))
    birthday=parse_date(data['bday'],'Ngày sinh') if data.get('bday') else None
    if birthday and birthday>today():
        raise BusinessError('Ngày sinh không được ở tương lai.')
    db.require_write()
    lock_writes()
    try:
        with db.transaction():
            old=db.one('SELECT id,name,phone,cccd,addr,note,bday FROM customer WHERE id=%s FOR UPDATE',(customer_id,)) if customer_id else None
            if customer_id and not old:
                raise BusinessError('Không tìm thấy khách hàng.')
            if old and old['phone'] != phone and db.one('SELECT id FROM pawn WHERE phone=%s LIMIT 1',(old['phone'],)):
                raise BusinessError('SĐT đang liên kết phiếu cũ. Giữ nguyên SĐT để bảo toàn liên kết hồ sơ.')
            if db.one('SELECT id FROM customer WHERE phone=%s AND id<>%s LIMIT 1',(phone,customer_id or 0)):
                raise BusinessError('Số điện thoại đã có trong danh sách khách hàng.')
            if cccd and db.one('SELECT id FROM customer WHERE cccd=%s AND id<>%s LIMIT 1',(cccd,customer_id or 0)):
                raise BusinessError('CCCD/CMND đã được sử dụng.')
            if old:
                db.execute('UPDATE customer SET name=%s,phone=%s,cccd=%s,addr=%s,note=%s,bday=%s,updated=%s WHERE id=%s',
                    (*vals.values(),birthday,today(),customer_id))
            else:
                customer_id=db.execute('INSERT INTO customer (name,phone,cccd,addr,note,bday,created) VALUES (%s,%s,%s,%s,%s,%s,%s)',
                    (*vals.values(),birthday,now()))
            event('customer_edit' if old else 'customer_create',customer_id=customer_id,before=old,after={**vals,'bday':birthday})
        return customer_id
    finally:
        unlock_writes()

def archive_customer(customer_id, note):
    if master.enabled():raise BusinessError('Nguồn khách CĐ đã ngưng ghi; không lưu trữ hồ sơ nguồn cũ.')
    with db.transaction():
        c=db.one('SELECT id,name,phone FROM customer WHERE id=%s FOR UPDATE',(customer_id,))
        if not c:
            raise BusinessError('Không tìm thấy khách hàng.')
        if db.one('SELECT id FROM pawn WHERE phone=%s AND status IN (1,2,3,4,7) LIMIT 1',(c['phone'],)):
            raise BusinessError('Khách hàng còn phiếu đang cầm; chưa thể lưu trữ.')
        db.execute('INSERT INTO khcd_customer_meta (customer_id,archived) VALUES (%s,1) ON DUPLICATE KEY UPDATE archived=1',(customer_id,))
        event('customer_delete',customer_id=customer_id,before=c,note=note)

def restore_customer(customer_id):
    if master.enabled():raise BusinessError('Nguồn khách CĐ đã ngưng ghi; không khôi phục hồ sơ nguồn cũ.')
    with db.transaction():
        c=db.one('SELECT id,name FROM customer WHERE id=%s FOR UPDATE',(customer_id,))
        if not c: raise BusinessError('Không tìm thấy khách hàng.')
        db.execute('UPDATE khcd_customer_meta SET archived=0 WHERE customer_id=%s',(customer_id,))
        event('customer_restore',customer_id=customer_id,after=c)

def gold_options():
    # KHAC is a non-weight asset; keep existing gold codes unchanged.
    return db.all("SELECT scut id,name,unit,value price FROM gold_price WHERE name <> 'Khác' AND unit IN ('chỉ','gram') AND scut IS NOT NULL ORDER BY sort,id") + [dict(id="KHAC",name="KHÁC",unit="món",price=0)]

def create_pawn(data, files=None):
    from .live_loans import enabled
    if enabled():raise BusinessError("SQL cũ chỉ đọc; lập phiếu tại quầy SQL mới.")
    data=dict(data)
    if data.get('loaded_pawn_id'):raise BusinessError('Phiếu đang mở chỉ để xem. Chọn Cầm mới để lập phiếu khác.')
    try:
        cid=str(data.get('customer_id','')).strip() if master.enabled() else int(data.get('customer_id',''))
        term=int(data.get('term','30'))
    except ValueError:
        raise BusinessError('Chọn khách hàng và kỳ hạn hợp lệ.')
    if not 1<=term<=365:
        raise BusinessError('Kỳ hạn phải từ 1 đến 365 ngày.')
    principal=decimal(data.get('value'),'Tiền cầm',minimum=Decimal('1'))
    if principal != money(principal):
        raise BusinessError('Tiền cầm phải là số nguyên đồng.')
    extended=data.get('desk_version')=='2'
    monthly=decimal(data.get('monthly_rate'),'Lãi suất %/tháng',maximum=Decimal('3')) if extended else None
    if extended and monthly not in (Decimal('3'),Decimal('2.5'),Decimal('2'),Decimal('1.5'),Decimal('1')):
        raise BusinessError('Chọn lãi suất tháng trong danh mục.')
    rate=monthly/30 if extended else decimal(data.get('daily_rate'),'Lãi suất %/ngày',maximum=Decimal('10'))
    if not extended and rate.as_tuple().exponent < -6:
        raise BusinessError('Lãi suất tối đa 6 chữ số thập phân.')
    start=parse_date(data.get('date1'),'Ngày cầm')
    if start != today():
        raise BusinessError('Phiếu mới ghi nhận trong ngày hiện tại để đối soát tiền thực tế.')
    golds=gold_options();allowed={str(g['id']) for g in golds}
    extra=desk.prepare(data,principal,golds) if extended else None
    photos=desk.prepare_photos(files or {}) if extended else {}
    if extra:
        for i in (1,2):
            row=extra['items'][i-1] if i<=len(extra['items']) else None
            for field,keyname in [('gold','gold'),('wgg','gross'),('whh','stone'),('mota','description')]:
                data[field+str(i)]=row[keyname] if row else ''
    items=[]
    for i in (1,2):
        gid=str(data.get(f'gold{i}',''))
        if i==2 and not gid:
            items.extend([None,None,None,None]);continue
        if gid not in allowed:
            raise BusinessError('Chỉ nhận vàng hoặc trang sức trong danh mục.')
        weight=decimal(data.get(f'wgg{i}'), 'Trọng lượng tổng',minimum=Decimal('0.0001'),maximum=Decimal('99999'))
        deduction=decimal(data.get(f'whh{i}','0') or '0','Trọng lượng trừ',maximum=weight)
        if deduction>=weight:
            raise BusinessError('Trọng lượng thực phải lớn hơn 0.')
        if weight.as_tuple().exponent < -4 or deduction.as_tuple().exponent < -4:
            raise BusinessError('Trọng lượng tối đa 4 chữ số thập phân.')
        desc=required(data,f'mota{i}','Mô tả tài sản')
        items.extend([gid,weight,deduction,desc])
    key=required(data,'request_key','Mã giao dịch',64)
    db.require_write();lock_writes()
    try:
        with db.transaction():
            existing=db.one('SELECT pawn_id,kind FROM khcd_event WHERE request_key=%s',(key,))
            if existing:
                if existing['kind']!='create': raise BusinessError('Mã giao dịch đã sử dụng.')
                return existing['pawn_id']
            c=master.get(cid)['customer'] if master.enabled() else db.one('SELECT id,phone FROM customer WHERE id=%s FOR UPDATE',(cid,))
            if not c or not c['phone'] or len(c['phone'])>11:
                raise BusinessError('Chọn khách hàng có số điện thoại hợp lệ trước khi lập phiếu.')
            if master.enabled() and str(c.get('Active'))!='1':
                raise BusinessError('Khách KK đã ngưng hoạt động; chọn hồ sơ đang hoạt động.')
            if not master.enabled() and db.one('SELECT customer_id FROM khcd_customer_meta WHERE customer_id=%s AND archived=1',(cid,)):
                raise BusinessError('Khách hàng này đã lưu trữ.')
            if not master.enabled() and db.one('SELECT COUNT(*) n FROM customer WHERE phone=%s',(c['phone'],))['n']!=1:
                raise BusinessError('SĐT trùng trong dữ liệu cũ. Cần xử lý trùng khách hàng trước khi lập phiếu.')
            timestamp=now();due=start+timedelta(days=term)
            sku='CD'+today().strftime('%y%m%d')+uuid.uuid4().hex[:8].upper()
            monthly=monthly if extended else rate*30
            pid=db.execute('''INSERT INTO pawn (sku,date1,date2,date3,phone,staff,safe,gold1,wgg1,whh1,mota1,gold2,wgg2,whh2,mota2,percent,value,status,note)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s)''',
                (sku,timestamp,timestamp,due,c['phone'],session['user'],optional(data,'safe'),*items,monthly,principal,optional(data,'note')))
            if master.enabled():
                db.execute('INSERT INTO khcd_pawn_customer (pawn_id,pmv_cust_id,source,linked_at) VALUES (%s,%s,%s,%s)',(pid,cid,'selected',now()))
            else:
                db.execute('INSERT INTO khcd_pawn_meta (pawn_id,customer_id) VALUES (%s,%s)',(pid,cid))
            if extra:desk.save(pid,extra,photos)
            bank=Decimal(extra['payment']['bank_amount']) if extra else Decimal(0)
            db.execute('''INSERT INTO pawn_log (pawn_id,status_id,date1,date2,date3,sotien,percent,days,tienlai,total,mbank)
                VALUES (%s,1,%s,%s,%s,%s,%s,%s,0,%s,%s)''',(pid,timestamp,timestamp,due,principal,monthly,term,-(principal-bank),-bank))
            event('create',pid,None if master.enabled() else cid,after=pawn(pid),principal=-principal,key=key,note=optional(data,'note'))
        return pid
    finally:
        unlock_writes()

def cancellation_state(p, lock=False):
    """Only a new, fully reconciled opening may be reversed within five minutes."""
    result=dict(allowed=False,remaining_seconds=0,reason='Chỉ hủy phiên Cầm mới chưa có nghiệp vụ tiếp theo.')
    if p['status']!=1:return result
    suffix=' FOR UPDATE' if lock else ''
    created=db.all("SELECT created_at FROM khcd_event WHERE pawn_id=%s AND kind='create'"+suffix,(p['id'],))
    if len(created)!=1:
        result['reason']='Phiếu nguồn cũ chưa có phiên lập được xác nhận; cần đối soát riêng.';return result
    elapsed=(now()-created[0]['created_at']).total_seconds()
    if not 0<=elapsed<300:
        result['reason']='Đã hết thời hạn hủy 5 phút hoặc thời điểm lập không hợp lệ.';return result
    logs=db.all('SELECT * FROM pawn_log WHERE pawn_id=%s ORDER BY id'+suffix,(p['id'],))
    if len(logs)!=1 or logs[0]['status_id']!=1:return result
    opening=logs[0];cash=Decimal(opening['total'] or 0);bank=Decimal(opening['mbank'] or 0)
    if cash>0 or bank>0 or cash+bank!=-p['value'] or opening['sotien']!=p['value'] or any(opening[k] for k in ('tienlai','tienthem','tienbot')):
        result['reason']='Tiền phiên mở đầu không khớp; cần đối soát, không tự hoàn tiền.';return result
    result.update(allowed=True,remaining_seconds=max(0,int(300-elapsed)),reason='Có thể hủy sau khi thu hồi đủ tiền đã giao khách.',
                  cash_return=str(-cash),bank_return=str(-bank))
    return result


def process_pawn(pid, data, action):
    from .live_loans import enabled
    if enabled():raise BusinessError('SQL cũ chỉ đọc. Mở biên nhận SQL mới để giao dịch.')
    if action not in ('renew','redeem','edit','cancel'):
        raise BusinessError('Thao tác không hợp lệ.')
    key=required(data,'request_key','Mã giao dịch',64)
    with db.transaction():
        old=db.one('SELECT * FROM pawn WHERE id=%s FOR UPDATE',(pid,))
        if not old:
            raise BusinessError('Không tìm thấy phiếu.')
        done=db.one('SELECT pawn_id,kind FROM khcd_event WHERE request_key=%s',(key,))
        if done:
            if done['pawn_id']!=pid or done['kind']!=action:
                raise BusinessError('Mã giao dịch đã sử dụng.')
            return
        if fingerprint(old)!=data.get('fingerprint'):
            raise BusinessError('Phiếu đã thay đổi ở phiên khác. Mở lại phiếu và kiểm tra số tiền trước khi xử lý.')
        if old['status'] not in ACTIVE:
            raise BusinessError('Phiếu đã đóng hoặc hủy, không thể xử lý tiếp.')
        if old['status']==7 and action in ('renew','redeem'):
            raise BusinessError('Phiếu báo mất cần được kiểm tra và xử lý riêng trước khi chuộc/gia hạn.')
        if action in ('renew','redeem') and not pawn(pid)['supported_asset']:
            raise BusinessError('Phiếu cũ thiếu loại vàng hoặc ngoài danh mục vàng/trang sức. Cần đối soát hồ sơ trước khi xử lý tiền.')
        note=optional(data,'note')
        if action=='edit':
            extra=desk.load(pid)
            if extra:
                for index,row in enumerate(extra['items'][:2],1):
                    row['description']=required(data,'mota'+str(index),'Mô tả tài sản '+str(index))
                db.execute('UPDATE khcd_pawn_desk SET items_json=%s,content=%s WHERE pawn_id=%s',
                    (json.dumps(extra['items'],ensure_ascii=False),desk.summary(extra['items']),pid))
            db.execute('UPDATE pawn SET safe=%s,note=%s,mota1=%s,mota2=%s WHERE id=%s',
                (optional(data,'safe'),note,required(data,'mota1','Mô tả tài sản'),optional(data,'mota2'),pid))
            event(action,pid,before=old,after=pawn(pid),note=note,key=key)
            return
        if action=='cancel':
            reason=required(data,'reason','Lý do hủy')
            eligibility=cancellation_state(old,lock=True)
            if not eligibility['allowed']:raise BusinessError(eligibility['reason'])
            db.execute('UPDATE pawn SET status=0 WHERE id=%s',(pid,))
            bank_return=Decimal(eligibility['bank_return'])
            db.execute('INSERT INTO pawn_log (pawn_id,status_id,date1,date2,sotien,tienlai,total,mbank) VALUES (%s,0,%s,%s,%s,0,%s,%s)',
                (pid,old['date2'],now(),old['value'],old['value']-bank_return,bank_return))
            event(action,pid,before=old,after=pawn(pid),principal=old['value'],note=reason,key=key)
            return
        end=parse_date(data.get('effective_date'),'Ngày xử lý')
        if end != today():
            raise BusinessError('Giao dịch tiền ghi nhận trong ngày hiện tại; không cho lùi hoặc đặt ngày tương lai.')
        paid_today=db.one('SELECT id FROM pawn_log WHERE pawn_id=%s AND status_id=4 AND date2>=%s AND date2<%s LIMIT 1',(pid,end,end+timedelta(days=1)))
        q=quote(old,end,0 if paid_today else current_app.config['MIN_INTEREST_DAYS'])
        amount=q['interest'] if action=='renew' else q['total']
        if decimal(data.get('confirmed_total'),'Số tiền xác nhận')!=amount:
            raise BusinessError('Số tiền xác nhận không khớp tính toán máy chủ. Tải lại báo giá.')
        if action=='renew':
            # A second same-day renewal must not charge the minimum day twice.
            if paid_today:
                raise BusinessError('Phiếu đã gia hạn hôm nay. Không thu lãi gia hạn lần nữa trong cùng ngày.')
            due=parse_date(data.get('new_due'),'Hẹn chuộc mới')
            if due<=max(end,parse_date(old['date3'] or end)) or (due-end).days>365:
                raise BusinessError('Hạn mới phải sau hôm nay và sau hạn hiện tại, tối đa 365 ngày.')
            status=4
        else:
            due=old['date3'];status=5
        db.execute('UPDATE pawn SET status=%s,date2=%s,date3=%s,staff=%s WHERE id=%s',(status,now(),due,session['user'],pid))
        db.execute('''INSERT INTO pawn_log (pawn_id,status_id,date1,date2,date3,sotien,percent,days,tienlai,total,mbank)
          VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0)''',
          (pid,status,old['date2'] or old['date1'],now(),due,q['principal'],old['percent'],q['days'],q['interest'],amount))
        event(action,pid,before=old,after=pawn(pid),interest=q['interest'],
            principal=q['principal'] if action=='redeem' else 0,note=note,key=key,effective=end)
