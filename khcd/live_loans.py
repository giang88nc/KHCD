"""Native loan ledger with a five-minute deletion window for the latest session."""
import json, uuid, hashlib, secrets, base64
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal
from flask import Blueprint, current_app, request, session, url_for, render_template, abort, Response, send_file
from . import db, pawn_desk as desk, customer_master as master, loan_conversion as C
from .domain import BusinessError, now, today, parse_date, decimal, money, date_range
from .payment_split import split, reference

bp=Blueprint('live',__name__,url_prefix='/camdo')
OPS={0:'Hủy phiên',1:'Cầm mới',2:'Cầm thêm',3:'Trả bớt',4:'Gia hạn',5:'Chuộc đồ',6:'Thanh lý',7:'Báo mất',8:'Mở khóa báo mất'}

def enabled():return str(current_app.config.get('CD_LIVE','0'))=='1'
def unpack(raw):return json.loads(raw) if isinstance(raw,str) else (raw or {})
def insert(table,values):return C.insert(table,values)
def integer(value,label,minimum=0):
    n=decimal(value,label,Decimal(minimum))
    if n!=money(n):raise BusinessError(label+' phải là nguyên đồng.')
    return n

def require_live():
    if not enabled():raise BusinessError('Chưa bật vận hành SQL mới.')
    db.require_write()
    if not db.one("SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='cd_loan_logs' AND COLUMN_NAME='request_key'"):
        raise BusinessError('Cần nâng cấp cấu trúc SQL mới trước khi ghi.')
    if not db.one("SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='cd_payments' AND COLUMN_NAME='payment_ref'"):
        raise BusinessError('Cần nâng cấp payment split trước khi tạo phiên mới.')

def loan(lid,lock=False):
    p=db.one('SELECT * FROM cd_loans WHERE id=%s'+(' FOR UPDATE' if lock else ''),(lid,))
    if not p:raise BusinessError('Không tìm thấy biên nhận trong SQL mới. Phiếu nguồn cũ cần chuyển đổi trước.')
    return p

def fingerprint(p):return C.digest({k:str(p[k]) for k in ('id','version','principal_balance','loan_state','interest_from','monthly_rate','due_at','receipt_lost','terms_json')})
def snapshot(p):
    result={k:p[k] for k in ('loan_state','last_operation_id','receipt_lost','principal_balance','interest_from','due_at','terms_json','note','employee_id','employee_name')}
    for k in ('interest_from','due_at'):result[k]=str(parse_date(result[k]))
    return result

def latest(lid):return db.one('SELECT * FROM cd_loan_logs WHERE loan_id=%s ORDER BY id DESC LIMIT 1',(lid,))
def lost_locked(p):return bool(p['receipt_lost'] and not unpack(p['terms_json']).get('lost_unlocked'))

def cancellation(p):
    l=latest(p['id']);reason='Chỉ xóa phiên mới nhất trong 5 phút; phiên nhập từ nguồn cũ không được xóa.'
    out=dict(allowed=False,remaining_seconds=0,reason=reason,cash_return='0',bank_return='0')
    if not l or not l.get('request_key') or l['operation_id']==0:return out
    age=(now()-l['happened_at']).total_seconds()
    if not 0<=age<300:return dict(out,reason='Đã hết thời hạn xóa 5 phút.')
    terms=unpack(l['terms_json'])
    if 'before' not in terms or 'after' not in terms:return out
    if C.digest(C.normalized(snapshot(p)))!=C.digest(C.normalized(terms['after'])):return dict(out,reason='Phiếu đã thay đổi sau phiên; cần đối soát.')
    pays=db.all('SELECT * FROM cd_payments WHERE log_id=%s',(l['id'],))
    if any(r['reconciliation_state'] in ('MATCHED','PARTIAL','RECONCILED') for r in pays):
        return dict(out,reason='Phiên đã có chứng từ ngân hàng; không được xóa dòng tiền đã đối soát.')
    for pay in pays:
        cash,bank=split(pay)
        out['cash_return']=str(Decimal(out['cash_return'])+cash)
        out['bank_return']=str(Decimal(out['bank_return'])+bank)
    return dict(out,allowed=True,remaining_seconds=int(300-age),reason='Hoàn lại đúng dòng tiền phiên trước khi hủy.',log_id=l['id'],operation=OPS[l['operation_id']])

def photos_save(raw):
    root=Path(current_app.config.get('LOAN_MEDIA_ROOT',str(Path(current_app.root_path).parent/'media'/'loans'))).resolve();root.mkdir(parents=True,exist_ok=True)
    docs={};paths=[]
    try:
        for kind,data in raw.items():
            name=uuid.uuid4().hex+'.jpg';path=root/name
            with path.open('xb') as f:f.write(data)
            paths.append(path);docs[kind]=dict(file=name,sha256=hashlib.sha256(data).hexdigest(),size=len(data))
        return docs,paths
    except Exception:
        for p in paths:p.unlink(missing_ok=True)
        raise

def post_log(p,operation,before,change,interest,extra,discount,days,key,note,employee='',reverses=None,applied_rate=None):
    return insert('cd_loan_logs',dict(loan_id=p['id'],legacy_log_id=None,operation_id=operation,happened_at=now(),interest_from=parse_date(before['interest_from']),due_at=p['due_at'],
      principal_before=Decimal(str(before['principal_balance'])),principal_change=change,principal_after=p['principal_balance'],interest=interest,extra_amount=extra,discount_amount=discount,
      monthly_rate=applied_rate if applied_rate is not None else before.get('monthly_rate',p['monthly_rate']),days=days,actor_legacy=session['user'],actor_id=session['user_id'],employee_id=employee or p['employee_id'],note=note,request_key=key,reverses_log_id=reverses,
      terms_json=C.packed(dict(before=before,after=snapshot(p),rule='daily-monthly-div30-v1')),legacy_json='{}'))

def post_payments(log_id,net,bank,info):
    if not net:return
    log=db.one('SELECT loan_id,happened_at FROM cd_loan_logs WHERE id=%s',(log_id,))
    # A prepared QR is not bank evidence. New sessions stay cash until reconciled.
    details=dict(info or {})
    if bank:details.update(requested_bank_amount=str(bank),transfer_status='PREPARED')
    insert('cd_payments',dict(log_id=log_id,channel=None,direction='IN' if net>0 else 'OUT',
      amount=abs(net),cashPay=abs(net),cardPay=0,payment_ref=reference(log['happened_at'],log['loan_id'],log_id),
      bank_snapshot=C.packed(details),reconciliation_state='RECORDED'))

def next_receipt_code(stamp):
    """Caller holds the year allocation lock until the INSERT transaction commits."""
    prefix='KH2'+stamp.strftime('%y')
    pattern='^'+prefix+'(0[1-9]|1[0-2])[0-9]{6}$'
    row=db.one("SELECT COALESCE(MAX(CAST(RIGHT(sku,6) AS UNSIGNED)),0) seq FROM cd_loans WHERE sku LIKE %s AND CHAR_LENGTH(sku)=13 AND REGEXP_LIKE(sku,%s,'c')",(prefix+'%',pattern))
    seq=int(row['seq'])+1
    if seq>999999:raise BusinessError('Đã hết số thứ tự 999999 trong năm. Không thể cấp thêm mã phiếu.')
    return 'KH2'+stamp.strftime('%y%m')+f'{seq:06d}'


def create(data,files):
    require_live();data=dict(data);key=str(data.get('request_key','')).strip()
    if not key or len(key)>64:raise BusinessError('Thiếu mã chống ghi trùng.')
    old=db.one('SELECT loan_id,operation_id FROM cd_loan_logs WHERE request_key=%s',(key,))
    if old:
        if old['operation_id']!=1:raise BusinessError('Mã yêu cầu đã dùng cho nghiệp vụ khác.')
        return old['loan_id']
    legacy_request=db.one('SELECT pawn_id,kind FROM khcd_event WHERE request_key=%s',(key,))
    if legacy_request:
        mapped=db.one('SELECT id FROM cd_loans WHERE legacy_pawn_id=%s',(legacy_request['pawn_id'],))
        if legacy_request['kind']=='create' and mapped:return mapped['id']
        raise BusinessError('Yêu cầu này đã ghi ở nguồn cũ. Đối soát/chuyển phiếu đó trước; không lập lại để tránh chi trùng.')
    if parse_date(data.get('date1'))!=today():raise BusinessError('Ngày lập phải là hôm nay.')
    if data.get('safe') not in ('1','2','3'):raise BusinessError('Vui lòng chọn Tủ đồ hợp lệ.')
    principal=integer(data.get('value'),'Tiền cầm',1);rate=decimal(data.get('monthly_rate'),'Lãi suất')
    if rate not in map(Decimal,['3','2.5','2','1.5','1']):raise BusinessError('Lãi suất ngoài danh mục.')
    try:term=int(data.get('term','30'))
    except (ValueError,TypeError):raise BusinessError('Số ngày không hợp lệ.')
    if not 1<=term<=365:raise BusinessError('Kỳ hạn từ 1 đến 365 ngày.')
    cid=str(data.get('customer_id','')).strip();c=master.get(cid)['customer'] if cid else None
    if not c or str(c.get('Active'))!='1' or not c.get('phone') or len(c['phone'])>11:raise BusinessError('Chọn khách KK đang hoạt động, có SĐT hợp lệ.')
    from .services import gold_options
    rows=desk.items(data,gold_options());pay=desk.payment(data,principal)
    employee=next((e for e in master.employees() if str(e['EmpID'])==data.get('employee_id')),None)
    if employee is None:employee=next((e for e in master.employees(refresh=True) if str(e['EmpID'])==data.get('employee_id')),None)   # NV mới thêm bên KK trong 10 phút
    if not employee:raise BusinessError('Chọn nhân viên KK đang hoạt động.')
    note=str(data.get('note','')).strip()
    if len(note)>255:raise BusinessError('Ghi chú tối đa 255 ký tự.')
    raw=desk.prepare_photos(files);qr=raw.pop('anh_qr',None)
    if qr and Decimal(pay['bank_amount'])<=0:raise BusinessError('QR phiên chỉ lưu khi có tiền chuyển khoản.')
    bank_info=dict(pay)
    if qr:bank_info.update(qr_image=base64.b64encode(qr).decode('ascii'),qr_mime='image/jpeg')
    docs,paths=photos_save(raw)
    lock_name='cd-create:'+hashlib.sha256(key.encode()).hexdigest()[:40]
    if db.one('SELECT GET_LOCK(%s,10) ok',(lock_name,))['ok']!=1:raise BusinessError('Quầy đang bận. Thử lại cùng phiếu.')
    year_lock=None
    try:
        stamp=now()
        allocation_lock='cd-sku:'+hashlib.sha256(str(current_app.config['DB_NAME']).encode()).hexdigest()[:32]+':'+str(stamp.year)
        if db.one('SELECT GET_LOCK(%s,10) ok',(allocation_lock,))['ok']!=1:raise BusinessError('Đang cấp mã phiếu. Thử lại cùng yêu cầu.')
        year_lock=allocation_lock
        with db.transaction():
            old=db.one('SELECT loan_id,operation_id FROM cd_loan_logs WHERE request_key=%s',(key,))
            if old:
                for path in paths:path.unlink(missing_ok=True)
                if old['operation_id']!=1:raise BusinessError('Mã yêu cầu đã sử dụng.')
                return old['loan_id']
            p=dict(legacy_pawn_id=None,sku=next_receipt_code(stamp),phone=c['phone'],cust_id=cid,loan_state='ACTIVE',last_operation_id=1,receipt_lost=0,
              opened_at=stamp,interest_from=stamp,due_at=stamp.date()+timedelta(days=term),original_principal=principal,principal_balance=principal,monthly_rate=rate,safe=data['safe'],employee_id=employee['EmpID'],employee_name=employee['EmpName'],note=note,
              customer_snapshot=C.packed(c),terms_json=C.packed(dict(payment=pay,interest_carry='0',rule='daily-monthly-div30-v1')),documents_json=C.packed(dict(native=docs)),legacy_json='{}',source_hash='',target_hash='',migration_state='LIVE',converted_at=stamp,converted_by=session['user_id'],converted_username=session['user'])
            lid=insert('cd_loans',p);p=loan(lid)
            for i,r in enumerate(rows,1):insert('cd_loan_items',dict(loan_id=lid,line_no=i,gold_code=r['gold'],description=r['description'],unit=r['unit'],gross_weight=r['gross'],stone_weight=r['stone'],net_weight=r['net'],unit_price=r['price'],valuation=r['subtotal']))
            before=dict(snapshot(p),principal_balance=Decimal(0),loan_state='CANCELLED',last_operation_id=0)
            terms=unpack(p['terms_json']);terms['assets_hash']=assets_hash(lid);p['terms_json']=C.packed(terms);db.execute('UPDATE cd_loans SET terms_json=%s WHERE id=%s',(p['terms_json'],lid));before['terms_json']=p['terms_json']
            log=post_log(p,1,before,principal,0,0,0,0,key,note)
            post_payments(log,-principal,Decimal(pay['bank_amount']),bank_info)
        return lid
    finally:
        # Keep unreferenced immutable images if a commit outcome is uncertain.
        # Never remove an image that a committed receipt may already reference.
        try:
            if year_lock:db.one('SELECT RELEASE_LOCK(%s)',(year_lock,))
        finally:db.one('SELECT RELEASE_LOCK(%s)',(lock_name,))

def liquidation_values(p,accrued):
    from .services import gold_options
    prices={str(g['id']):g for g in gold_options()};lines=[];total=Decimal(0);errors=[]
    items=db.all('SELECT line_no,gold_code,description,net_weight,unit FROM cd_loan_items WHERE loan_id=%s ORDER BY line_no',(p['id'],))
    if not items:errors.append('Phiếu chưa có chi tiết món hàng.')
    for item in items:
        gold=prices.get(str(item['gold_code']));weight=Decimal(str(item['net_weight'] or 0))
        if not gold or str(item['gold_code'])=='KHAC' or not gold.get('price') or weight<=0:
            errors.append('Món '+str(item['line_no'])+': thiếu loại vàng, trọng lượng hoặc giá thâu.');continue
        if item['unit']!=gold['unit']:
            errors.append('Món '+str(item['line_no'])+': đơn vị trọng lượng khác đơn vị giá thâu.');continue
        price=decimal(gold['price'],'Giá thâu');value=money(weight*price);total+=value
        lines.append(dict(line=item['line_no'],gold=item['gold_code'],description=item['description'],weight=str(weight),unit=item['unit'],price=str(price),value=str(value),price_id=gold.get('price_id'),effective_at=gold.get('effective_at')))
    return dict(principal=str(p['principal_balance']),principal_interest=str(p['principal_balance']+max(Decimal(5000),accrued)),actual=str(total) if not errors else None,lines=lines,errors=errors,price_source='khj_bl.gold_prices.buy')

def estimate(p,operation,data):
    if p['loan_state']!='ACTIVE':raise BusinessError('Phiếu đã đóng; chỉ xem hoặc hủy phiên cuối còn thời hạn.')
    op=int(operation)
    if op not in (2,3,4,5,6,7):raise BusinessError('Nghiệp vụ không hợp lệ.')
    if lost_locked(p):raise BusinessError('Phiếu báo mất đang KHÓA. Cần PassCode mở lại trước khi giao dịch.')
    balance=p['principal_balance'];start=parse_date(p['interest_from']);effective=parse_date(data.get('transaction_date') or today()) if op in (2,3,4) else today()
    if effective<start:raise BusinessError('Ngày giao dịch không được trước mốc lãi đã chốt.')
    if effective>today()+timedelta(days=365):raise BusinessError('Ngày tính lãi tối đa 365 ngày từ hôm nay.')
    days=(effective-start).days
    if days<0:raise BusinessError('Mốc tính lãi ở tương lai; cần đối soát.')
    terms=unpack(p['terms_json']);carry=Decimal(str(terms.get('interest_carry','0')))
    days=max(1,days)
    applied_rate=decimal(data.get('current_monthly_rate') or p['monthly_rate'],'Lãi suất hiện tại')
    if data.get('current_monthly_rate') and applied_rate not in map(Decimal,['3','2.5','2','1.5','1']):raise BusinessError('Lãi suất hiện tại ngoài danh mục.')
    accrued=money(balance*applied_rate*days/Decimal(3000)+carry)
    change=Decimal(0);interest=Decimal(0);due=p['due_at'];reset=False
    if op==2:change=integer(data.get('amount'),'Tiền cầm thêm',1)
    if op==3:
        change=-integer(data.get('amount'),'Tiền trả bớt',1)
        if -change>=balance:raise BusinessError('Trả bớt phải nhỏ hơn dư gốc; tất toán dùng Chuộc đồ.')
    if op in (2,3,4,5,6,7):interest=max(Decimal(5000),accrued);reset=True
    if op in (5,6):change=-balance
    next_rate=p['monthly_rate']
    if op in (2,3,4):
        next_rate=decimal(data.get('next_monthly_rate') or p['monthly_rate'],'Lãi suất kỳ tiếp')
        if next_rate not in map(Decimal,['3','2.5','2','1.5','1']):raise BusinessError('Lãi suất kỳ tiếp ngoài danh mục.')
        due=parse_date(data.get('due') or effective+timedelta(days=30),'Ngày hẹn mới')
        if not effective<due<=effective+timedelta(days=365):raise BusinessError('Ngày hẹn mới phải sau ngày tính lãi, tối đa 365 ngày.')
    extra=integer(data.get('extra','0') or '0','Thu thêm');discount=integer(data.get('discount','0') or '0','Giảm trừ')
    liquidation=None
    if op==6:
        mode=str(data.get('liquidation_mode') or 'principal')
        if mode not in ('principal','principal_interest','actual'):raise BusinessError('Chọn cách tính thanh lý hợp lệ.')
        liquidation=liquidation_values(p,accrued);liquidation['mode']=mode
        if mode=='actual' and liquidation['errors']:raise BusinessError(' '.join(liquidation['errors']))
        target=integer(liquidation[mode],'Giá trị thanh lý')
        interest=max(Decimal(5000),accrued) if mode=='principal_interest' else Decimal(0)
        extra=max(Decimal(0),target-balance-interest);discount=max(Decimal(0),balance+interest-target)
    net=-change+interest+extra-discount
    if op!=2 and net<0:raise BusinessError('Giảm trừ không được lớn hơn số tiền phải thu.')
    if balance+change>Decimal('999999999999'):raise BusinessError('Dư gốc vượt giới hạn.')
    return dict(liquidation_json=C.packed(liquidation) if liquidation else '',applied_rate=applied_rate,transaction_date=effective,next_monthly_rate=next_rate,operation=op,change=change,interest=interest,extra=extra,discount=discount,net=net,days=days,accrued=accrued,due=due,reset=reset,principal_after=balance+change)

def process(lid,op,data,files=None):
    require_live();key=str(data.get('request_key','')).strip()
    if not key or len(key)>64:raise BusinessError('Thiếu mã chống ghi trùng.')
    qr=None
    if files and files.get('anh_qr') and files['anh_qr'].filename:
        qr=desk.prepare_photos({'anh_qr':files['anh_qr']}).get('anh_qr')
    with db.transaction():
        p=loan(lid,True);old=db.one('SELECT loan_id,operation_id FROM cd_loan_logs WHERE request_key=%s',(key,))
        if old:
            if old['loan_id']!=lid or old['operation_id']!=op:raise BusinessError('Mã yêu cầu đã sử dụng.')
            return
        if op==7 and (not files or not files.get('lost_photo') or not files['lost_photo'].filename):
            raise BusinessError('Vui lòng chụp hoặc chọn ảnh giấy cam kết báo mất trước khi xác nhận.')
        if fingerprint(p)!=data.get('fingerprint'):raise BusinessError('Phiếu đã thay đổi. Mở lại và đối chiếu trước khi xác nhận.')
        before=snapshot(p)
        for date_field in ('interest_from','due_at'):before[date_field]=str(p[date_field])
        note=str(data.get('reason' if op==0 else 'note','')).strip()
        if len(note)>255:raise BusinessError('Ghi chú tối đa 255 ký tự.')
        if op==0:
            state=cancellation(p)
            if not state['allowed']:raise BusinessError(state['reason'])
            if data.get('confirmed')!='yes' and data.get('returned_funds')!='yes':raise BusinessError('Cần xác nhận xóa phiên.')
            last=latest(lid)
            if last['operation_id']==1:
                if p['legacy_pawn_id'] or db.one('SELECT COUNT(*) n FROM cd_loan_logs WHERE loan_id=%s',(lid,))['n']!=1:
                    raise BusinessError('Chỉ xóa toàn bộ phiếu cầm mới chưa có phiên tiếp theo.')
                db.execute('DELETE FROM cd_payments WHERE log_id=%s',(last['id'],))
                db.execute('DELETE FROM cd_loan_logs WHERE id=%s AND loan_id=%s',(last['id'],lid))
                db.execute('DELETE FROM cd_loan_items WHERE loan_id=%s',(lid,))
                db.execute('DELETE FROM cd_loans WHERE id=%s',(lid,))
                return dict(deleted_loan=True)
            restore=unpack(last['terms_json'])['before']
            for k in before:p[k]=restore[k]
            if 'monthly_rate' in restore:p['monthly_rate']=Decimal(str(restore['monthly_rate']))
            p['principal_balance']=Decimal(str(p['principal_balance']));p['interest_from']=datetime.fromisoformat(str(p['interest_from']));p['due_at']=datetime.fromisoformat(str(p['due_at']))
            update(p)
            db.execute('DELETE FROM cd_payments WHERE log_id=%s',(last['id'],))
            db.execute('DELETE FROM cd_loan_logs WHERE id=%s AND loan_id=%s',(last['id'],lid))
            return
        if not db.one('SELECT id FROM cd_loan_logs WHERE loan_id=%s AND request_key IS NOT NULL LIMIT 1',(lid,)):
            original=C.target(p['legacy_pawn_id']) if p['legacy_pawn_id'] else None
            if original and C.plan_hash(original[1])!=p['target_hash']:raise BusinessError('Bản chuyển đã thay đổi ngoài nghiệp vụ; cần đối soát trước khi ghi.')
        expected_assets=unpack(p['terms_json']).get('assets_hash')
        if expected_assets and expected_assets!=assets_hash(lid):raise BusinessError('Tài sản/ảnh đã thay đổi; cần đối soát trước khi giao dịch.')
        e=estimate(p,op,data)
        if integer(data.get('confirmed_total'),'Tổng tiền xác nhận')!=abs(e['net']):raise BusinessError('Số tiền đã thay đổi. Tính lại trước khi xác nhận.')
        bank=integer(data.get('bank_amount','0') or '0','Chuyển khoản')
        if qr and bank<=0:raise BusinessError('QR phiên chỉ lưu khi có tiền chuyển khoản.')
        if bank>abs(e['net']):raise BusinessError('Chuyển khoản vượt số tiền phiên.')
        info={}
        if bank:
            if e['net']>0:
                banks=master.call('pawn_banks')['rows'];info=next((b for b in banks if str(b['id'])==str(data.get('bank_id'))),None)
                if not info:raise BusinessError('Chọn tài khoản nhận tiền đang bật của tiệm.')
            else:
                for k in ('bank_name','bank_account','bank_holder'):
                    info[k]=str(data.get(k,'')).strip()
                    if not info[k] or len(info[k])>120:raise BusinessError('Điền đủ tài khoản nhận của khách.')
        if qr:info.update(qr_image=base64.b64encode(qr).decode('ascii'),qr_mime='image/jpeg')
        terms=unpack(p['terms_json']);terms['assets_hash']=assets_hash(lid)
        if e['reset']:terms.update(interest_carry='0',settled_on=str(e['transaction_date']));p['interest_from']=e['transaction_date']
        if op in (2,3,4):
            before['monthly_rate']=str(p['monthly_rate'])
            p['monthly_rate']=e['next_monthly_rate']
            terms['renewal']=dict(transaction_date=str(e['transaction_date']),previous_rate=before['monthly_rate'],next_rate=str(e['next_monthly_rate']))
        p.update(principal_balance=e['principal_after'],last_operation_id=op,due_at=e['due'],terms_json=C.packed(terms))
        if op in (5,6):p['loan_state']='REDEEMED' if op==5 else 'LIQUIDATED'
        if op==7:
            p['receipt_lost']=1
            terms['lost_unlocked']=False
            p['terms_json']=C.packed(terms)
        update(p);log=post_log(p,op,before,e['change'],e['interest'],e['extra'],e['discount'],e['days'],key,note,applied_rate=e['applied_rate'])
        if op==6:
            log_terms=unpack(db.one('SELECT terms_json FROM cd_loan_logs WHERE id=%s',(log,))['terms_json'])
            log_terms['liquidation']=unpack(e['liquidation_json'])
            db.execute('UPDATE cd_loan_logs SET terms_json=%s WHERE id=%s',(C.packed(log_terms),log))
        if op==7 and files and files.get('lost_photo') and files['lost_photo'].filename:
            attachment=save_lost_photo(files['lost_photo'])
            log_terms=unpack(db.one('SELECT terms_json FROM cd_loan_logs WHERE id=%s',(log,))['terms_json'])
            log_terms['lost_photo']=attachment
            db.execute('UPDATE cd_loan_logs SET terms_json=%s WHERE id=%s',(C.packed(log_terms),log))
        post_payments(log,e['net'],bank,info)

def update(p):
    values=snapshot(p);values['monthly_rate']=p['monthly_rate']
    for date_field in ('interest_from','due_at'):values[date_field]=p[date_field]
    cols=list(values)
    db.execute('UPDATE cd_loans SET '+','.join(k+'=%s' for k in cols)+",version=version+1,migration_state='LIVE' WHERE id=%s",[values[k] for k in cols]+[p['id']])

@bp.post('/bien-nhan/<int:lid>/tinh-phien')
def preview(lid):
    try:
        p=loan(lid);e=estimate(p,request.form.get('operation'),request.form)
        return dict(**{k:str(v) for k,v in e.items()},fingerprint=fingerprint(p))
    except (BusinessError,ValueError) as exc:return {'error':str(exc)},409

@bp.post('/bien-nhan/<int:lid>/chot-phien')
def commit(lid):
    try:
        op=int(request.form.get('operation','0'));process(lid,op,request.form,request.files)
        return {'message':'Đã ghi nhận phiên vào SQL mới.','sku':loan(lid)['sku']}
    except (BusinessError,ValueError) as exc:return {'error':str(exc)},409


def checkout_summary(p):
    last=db.one('SELECT * FROM cd_loan_logs WHERE loan_id=%s AND operation_id<>8 ORDER BY id DESC LIMIT 1',(p['id'],));terms=unpack(p['terms_json'])
    start=parse_date(p['interest_from']);due=parse_date(p['due_at']);days=(due-start).days
    forecast=None
    if p['loan_state']=='ACTIVE' and days>=0:
        minimum=1
        forecast=str(max(Decimal(5000),money(p['principal_balance']*p['monthly_rate']*max(minimum,days)/Decimal(3000)+Decimal(str(terms.get('interest_carry','0'))))))
    payment={'cash':'0','bank_amount':'0'};net=Decimal(0);qr_url=None
    if last:
        for row in db.all('SELECT * FROM cd_payments WHERE log_id=%s',(last['id'],)):
            cash,bank_amount=split(row)
            payment['cash']=str(Decimal(payment['cash'])+cash)
            payment['bank_amount']=str(Decimal(payment['bank_amount'])+bank_amount)
            net+=row['amount']*(1 if row['direction']=='IN' else -1)
            if row.get('bank_snapshot'):
                bank=unpack(row['bank_snapshot'])
                if bank.get('qr_image'):qr_url='/camdo/phien/'+str(last['id'])+'/qr'
                payment.update(bank_name=bank.get('bank_name') or bank.get('bank_bin',''),bank_account=bank.get('bank_account') or bank.get('bank_number',''),bank_holder=bank.get('bank_holder') or bank.get('bank_user',''),bank_reference=bank.get('bank_reference',''))
    return dict(operation=OPS.get(last['operation_id'],'Giao dịch') if last else '',at=str(last['happened_at']) if last else '',
      log_id=last['id'] if last else None,total=str(abs(net)),payment_edit=payment_edit_state(p,last),qr_url=qr_url,note=(last.get('note') or '') if last and last.get('request_key') else p.get('note') or '',payment=payment,
      direction='THU TỪ KHÁCH' if net>0 else 'CHI CHO KHÁCH' if net<0 else 'KHÔNG THU / CHI',
      interest_from=str(start),forecast_interest=forecast,forecast_days=max(0,days),closed=p['loan_state']!='ACTIVE')


def receipt(raw):
    key=desk.receipt_key(raw,request.host.split(':')[0])
    field='id' if key[0]=='new_id' else 'legacy_pawn_id' if key[0]=='id' else 'sku'
    found=db.all('SELECT id FROM cd_loans WHERE '+field+'=%s LIMIT 2',(key[1],))
    if len(found)!=1:raise BusinessError('Không tìm thấy mã duy nhất trong SQL mới. Phiếu cũ chưa chuyển: mở Phiếu cũ để đối soát/chuyển đổi.')
    p=loan(found[0]['id']);items=db.all('SELECT * FROM cd_loan_items WHERE loan_id=%s ORDER BY line_no',(p['id'],))
    customer=unpack(p['customer_snapshot']);err=None
    if p['cust_id']:
        try:customer=master.get(p['cust_id'])['customer']
        except BusinessError as exc:err=str(exc)+' · đang hiển thị hồ sơ lưu trên phiếu.'
    else:err='Chưa có CustID đã xác định; giữ SĐT nguồn để đối soát.'
    rows=[dict(gold=i['gold_code'],description=i['description'],unit=i['unit'] or 'chỉ',gross=str(i['gross_weight']),stone=str(i['stone_weight']),net=str(i['net_weight']),price=str(i['unit_price'] or 0),subtotal=str(i['valuation'] or 0)) for i in items]
    terms=unpack(p['terms_json']);pay={}
    if not pay:
        first=db.one('SELECT id FROM cd_loan_logs WHERE loan_id=%s AND operation_id=1 ORDER BY id LIMIT 1',(p['id'],))
        pays=db.all('SELECT * FROM cd_payments WHERE log_id=%s',(first['id'],)) if first else []
        pay={'cash':'0','bank_amount':'0'}
        for r in pays:
            cash,bank_amount=split(r)
            pay['cash']=str(Decimal(pay['cash'])+cash)
            pay['bank_amount']=str(Decimal(pay['bank_amount'])+bank_amount)
    from .loan_images import inventory
    photos={i['slot']:url_for('loans.photo',loan_id=p['id'],slot=i['slot']) for i in inventory(p) if i['available'] and i['slot'] in desk.PHOTO_NAMES and i['slot']!='anh_qr'}
    if p['cust_id']:
        for kind,part in [('anh_truoc','mat-truoc'),('anh_sau','mat-sau')]:photos.setdefault(kind,url_for('customer_popup.api',path=f"banle/khach-hang/{p['cust_id']}/anh/{part}/"))
    checkout=checkout_summary(p)
    if checkout['qr_url']:photos['anh_qr']=checkout['qr_url']
    elif latest(p['id']) and latest(p['id'])['operation_id']==1:
        # Historic receipt QR is only attributable to the opening, never a later session.
        old_qr=next((i for i in inventory(p) if i['slot']=='anh_qr' and i['available']),None)
        if old_qr:photos['anh_qr']=url_for('loans.photo',loan_id=p['id'],slot='anh_qr')
    lost_papers=[]
    for report in db.all('SELECT id,happened_at,note,terms_json FROM cd_loan_logs WHERE loan_id=%s AND operation_id=7 ORDER BY happened_at DESC,id DESC',(p['id'],)):
        has_photo=bool(unpack(report['terms_json']).get('lost_photo'))
        lost_papers.append(dict(id=report['id'],at=str(report['happened_at']),note=report['note'] or '',photo_url=url_for('live.lost_photo',log_id=report['id']) if has_photo else None))
    session_count=db.one('SELECT COUNT(*) total FROM cd_loan_logs WHERE loan_id=%s AND operation_id<>8',(p['id'],))['total']
    return dict(session_count=session_count,loan_state=p['loan_state'],lost_papers=lost_papers,count_print=p.get('count_print',0),print_count_url=url_for('live.print_count',lid=p['id']),id=p['id'],sku=p['sku'],status=p['last_operation_id'],status_name=C.LABEL[p['loan_state']],active=p['loan_state']=='ACTIVE',valuation_known=bool(items and all(i['valuation'] is not None for i in items)),items=rows,
      value=str(p['principal_balance']),monthly_rate=str(p['monthly_rate']),safe=p['safe'] or '',date1=str(parse_date(p['opened_at'])),due=str(parse_date(p['due_at'])),employee_id=p['employee_id'] or '',employee_name=p['employee_name'] or '',note=p['note'] or '',payment=pay,content=desk.summary(rows),
      customer=dict(id=p['cust_id'],name=customer.get('name',''),phone=customer.get('phone') or p['phone'],cccd=customer.get('cccd',''),addr=customer.get('addr','')),customer_error=err,photos=photos,detail_url=url_for('live.print_receipt',lid=p['id']),giay_url=url_for('gcd.giay',lid=p['id']),may_url=url_for('gcd.in_may_chu',lid=p['id']),fingerprint=fingerprint(p),cancellation=cancellation(p),
      checkout=checkout,preview_url=url_for('live.preview',lid=p['id']),commit_url=url_for('live.commit',lid=p['id']),receipt_lost=bool(p['receipt_lost']),lost_locked=lost_locked(p),unlock_url=url_for('live.unlock_lost',lid=p['id']))

# Each log is joined to pre-aggregated payments: never multiply interest by channels.
LOG_SQL="""SELECT l.*,p.sku,p.phone,p.cust_id pmv_cust_id,
 JSON_UNQUOTE(JSON_EXTRACT(p.customer_snapshot,'$.name')) customer_name,
 JSON_UNQUOTE(JSON_EXTRACT(p.customer_snapshot,'$.cccd')) cccd,
 COALESCE(f.cash,0) cash,COALESCE(f.bank,0) bank,
 COALESCE(f.received,0) received,COALESCE(f.paid,0) paid
 FROM cd_loan_logs l JOIN cd_loans p ON p.id=l.loan_id
 LEFT JOIN (SELECT log_id,SUM(IF(direction='IN',1,-1)*COALESCE(cashPay,IF(channel='CASH',amount,0))) cash,
 SUM(IF(direction='IN',1,-1)*COALESCE(cardPay,IF(channel='BANK',amount,0))) bank,
 SUM(IF(direction='IN',amount,0)) received,SUM(IF(direction='OUT',amount,0)) paid FROM cd_payments GROUP BY log_id) f ON f.log_id=l.id"""

def sessions(args):
    start=parse_date(args.get('d1') or today());end=parse_date(args.get('d2') or today())
    if start>end or (end-start).days>366:raise BusinessError('Khoảng ngày tối đa 366 ngày.')
    q=args.get('q','').strip()[:100];where=' WHERE happened_at>=%s AND happened_at<%s';params=[start,end+timedelta(days=1)]
    if args.get('loan_id'):
        try:lid=int(args['loan_id'])
        except (ValueError,TypeError):raise BusinessError('Mã phiếu không hợp lệ.')
        p=loan(lid)
        where=' WHERE loan_id=%s';params=[lid];q=''
        bounds=db.one('SELECT MIN(happened_at) first_at,MAX(happened_at) last_at FROM cd_loan_logs WHERE loan_id=%s',(lid,))
        start=parse_date(bounds['first_at'] or p['opened_at']);end=parse_date(bounds['last_at'] or today())
    if not args.get('loan_id'):where+=' AND operation_id<>8'
    if q:
        ids=[]
        try:ids=master.call('search_ids',q=q)['ids']
        except BusinessError:pass
        where+=' AND (phone LIKE %s OR customer_name LIKE %s OR cccd LIKE %s OR sku LIKE %s'+(' OR pmv_cust_id IN ('+','.join(['%s']*len(ids))+')' if ids else '')+')';params+=['%'+q+'%']*4+ids
    if str(args.get('kind','')) in map(str,OPS):where+=' AND operation_id=%s';params.append(int(args['kind']))
    source=' FROM ('+LOG_SQL+') t'+where
    groups=db.all('SELECT operation_id status_id,COUNT(*) count,SUM(ABS(principal_change)) amount,SUM(interest) interest,SUM(cash) cash,SUM(bank) bank,SUM(received) received,SUM(paid) paid'+source+' GROUP BY operation_id',params)
    total=sum(g['count'] for g in groups);pages=max(1,(total+49)//50)
    try:page=min(pages,max(1,int(args.get('page',1))))
    except ValueError:raise BusinessError('Số trang không hợp lệ.')
    rows=db.all('SELECT *'+source+' ORDER BY happened_at DESC,id DESC LIMIT 50 OFFSET %s',params+[(page-1)*50])
    fields=('amount','interest','cash','bank','received','paid');totals={k:str(sum((g[k] or 0 for g in groups),Decimal(0))) for k in fields}
    for g in groups:
        g['operation']=OPS.get(g['status_id'],'Khác')
        for k in fields:g[k]=str(g[k] or 0)
    if rows:
        names={r['id']:r['customer_name'] for r in rows}
        master.hydrate(rows)
        for r in rows:r['customer_name']=r.get('customer_name') or names[r['id']]
    for r in rows:
        r.update(pawn_id=r['loan_id'],status_id=r['operation_id'],operation=OPS.get(r['operation_id'],'Khác'),date_fallback=False,can_open=True,
          amount=str(abs(r['principal_change'])),extra=str(r['extra_amount']),discount=str(r['discount_amount']),net=str(r['cash']+r['bank']))
        for k in ('interest','cash','bank'):r[k]=str(r[k])
        r['happened_at']=str(r['happened_at'])
        if r['operation_id']==7 and unpack(r['terms_json']).get('lost_photo'):r['lost_photo_url']='/camdo/phien/'+str(r['id'])+'/cam-ket'
    return dict(rows=rows,groups=groups,totals=totals,total=total,page=page,pages=pages,d1=str(start),d2=str(end),q=q,warnings=[])

def dashboard():
    """Tổng quan trên sổ SQL mới — số liệu, tuổi nợ, tài sản, cảnh báo: xem khcd/overview.py."""
    from . import overview
    start,end,_=date_range(request.args)
    return render_template('live_dashboard.html',title='Tổng quan',ov=overview.stats(start,end),start=start,end=end)

def report():
    start,end,_=date_range(request.args);args=dict(request.args,d1=str(start),d2=str(end));data=sessions(args)
    return render_template('live_reports.html',title='Thống kê',data=data,start=start,end=end,ops=OPS)

def check(lid):
    p=loan(lid);logs=db.all('SELECT * FROM cd_loan_logs WHERE loan_id=%s ORDER BY id',(lid,));checks=[]
    def add(label,valid,detail):checks.append(dict(label=label,state='ok' if valid else 'error',detail=detail,source='',target=''))
    native=[r for r in logs if r['request_key']]
    if not native and p['legacy_pawn_id']:
        original=C.target(p['legacy_pawn_id'])
        add('Bản chuyển trước khi phát sinh',bool(original and C.plan_hash(original[1])==p['target_hash']),'Kiểm tra checksum bản chuyển đã xác nhận.')
    balance=None
    for r in logs:
        # Accepted legacy discrepancies remain visible, but do not rewrite history.
        if r['request_key']:
            add('Phiên #'+str(r['id'])+' · dư gốc',r['principal_before']+r['principal_change']==r['principal_after'],'Gốc trước + biến động = gốc sau.')
            if balance is not None:add('Phiên #'+str(r['id'])+' · nối số dư',balance==r['principal_before'],'Khớp số dư phiên trước.')
            pays=db.one("SELECT COALESCE(SUM(IF(direction='IN',amount,-amount)),0) n FROM cd_payments WHERE log_id=%s",(r['id'],))['n']
            add('Phiên #'+str(r['id'])+' · dòng tiền',pays==-r['principal_change']+r['interest']+r['extra_amount']-r['discount_amount'],'Thu − chi = − biến động gốc + lãi + thu thêm − giảm trừ.')
        balance=r['principal_after']
    if native:
        add('Dư gốc hiện tại',balance==p['principal_balance'],'Đối chiếu phiên mới nhất với biên nhận.')
        add('Trạng thái phiên mới nhất',C.digest(C.normalized(snapshot(p)))==C.digest(C.normalized(unpack(native[-1]['terms_json']).get('after',{}))),'Đối chiếu biên nhận với bản ghi cuối.')
    add('Dư gốc theo trạng thái',(p['principal_balance']>0 if p['loan_state']=='ACTIVE' else p['principal_balance']==0),'Đang cầm còn dư gốc; phiếu đóng dư gốc bằng 0.')
    if p['legacy_pawn_id']:
        try:add('Nguồn lưu trữ',C.digest(C.source(p['legacy_pawn_id']))==p['source_hash'],'Nguồn cũ giữ nguyên so với thời điểm chuyển. SQL mới phát sinh tiếp độc lập.')
        except BusinessError as exc:add('Nguồn lưu trữ',False,str(exc))
    asset_digest=unpack(p['terms_json']).get('assets_hash')
    if asset_digest:add('Danh sách tài sản / tham chiếu ảnh',asset_digest==assets_hash(lid),'Đối chiếu checksum nội dung tài sản.')
    if not p['cust_id']:checks.append(dict(label='CustID',state='warning',detail='Chưa có liên kết đã xác định; không tự ghép SĐT.',source='',target=''))
    for c in C.stored_exceptions(p).get('accepted',[]):checks.append(dict(label=c['label'],state='warning',detail=c['detail'],source='',target=''))
    return dict(checks=checks,errors=sum(c['state']=='error' for c in checks),warnings=sum(c['state']=='warning' for c in checks))


def receipt_context(lid):
    """Dữ liệu một biên nhận để in — dùng chung cho trang in cũ và trang GIẤY IN SẴN (GCD).

    Một nguồn duy nhất: hai đường in KHÔNG BAO GIỜ được hiện số khác nhau cho cùng một phiếu.
    Đọc phiếu → khách → món; bên gọi đọc bố cục SAU CÙNG (khj_bl có thể hụt — xem gcd_layout)."""
    p=loan(lid);customer=unpack(p['customer_snapshot']);warning=None
    if p['cust_id']:
        try:customer=master.get(p['cust_id'])['customer']
        except BusinessError:warning='Khách KK tạm mất kết nối; thông tin khách là bản lưu trên biên nhận.'
    items=db.all('SELECT * FROM cd_loan_items WHERE loan_id=%s ORDER BY line_no',(lid,))
    return dict(loan=p,customer=customer,items=items,warning=warning)


@bp.get('/bien-nhan/<int:lid>/in')
def print_receipt(lid):
    ctx=receipt_context(lid)
    return render_template('loan_print.html',title=ctx['loan']['sku'],labels=C.LABEL,**ctx)


def assets_hash(lid):
    rows=db.all('SELECT line_no,gold_code,description,unit,gross_weight,stone_weight,net_weight,unit_price,valuation FROM cd_loan_items WHERE loan_id=%s ORDER BY line_no',(lid,))
    docs=unpack(loan(lid)['documents_json'])
    return C.digest(C.normalized({'items':rows,'documents':docs}))


@bp.get('/phien/<int:log_id>/qr')
def session_qr(log_id):
    row=db.one("SELECT bank_snapshot FROM cd_payments WHERE log_id=%s AND (channel='BANK' OR channel IS NULL)",(log_id,))
    if not row:abort(404)
    info=unpack(row['bank_snapshot']);encoded=info.get('qr_image','')
    if not isinstance(encoded,str) or not encoded or len(encoded)>21*1024*1024:abort(404)
    try:raw=base64.b64decode(encoded,validate=True)
    except (ValueError,TypeError):abort(404)
    return Response(raw,content_type=info.get('qr_mime','image/jpeg'),headers={'Cache-Control':'private, no-store'})


@bp.route('/bien-nhan/<int:lid>/luot-in',methods=['GET','POST'])
def print_count(lid):
    loan(lid)
    if request.method=='POST':
        require_live()
        with db.transaction():
            db.execute('UPDATE cd_loans SET count_print=count_print+1 WHERE id=%s',(lid,))
    return dict(count_print=db.one('SELECT count_print FROM cd_loans WHERE id=%s',(lid,))['count_print'])


@bp.get('/lap-phieu/ket-qua-luu')
def create_result():
    key=request.args.get('request_key','')
    if not key or len(key)>64:raise BusinessError('Mã yêu cầu không hợp lệ.')
    found=db.one('SELECT p.id,p.sku FROM cd_loan_logs l JOIN cd_loans p ON p.id=l.loan_id WHERE l.request_key=%s AND l.operation_id=1 AND l.actor_id=%s',(key,session['user_id']))
    if not found:return {'error':'Chưa tìm thấy phiếu đã lưu theo yêu cầu này.'},404
    return dict(url=url_for('loans.detail',loan_id=found['id']),sku=found['sku'])


def payment_edit_state(p,last=None):
    last=last or latest(p['id'])
    if not last:return dict(allowed=False,remaining_seconds=0)
    rows=db.all('SELECT * FROM cd_payments WHERE log_id=%s ORDER BY id',(last['id'],))
    net=sum((r['amount']*(1 if r['direction']=='IN' else -1) for r in rows),Decimal(0))
    age=(now()-last['happened_at']).total_seconds()
    allowed=bool(last.get('request_key') and last['operation_id'] in (1,2) and net<0 and 0<=age<1800
                 and not any(r['reconciliation_state'] in ('MATCHED','PARTIAL','RECONCILED') for r in rows))
    return dict(allowed=allowed,remaining_seconds=max(0,int(1800-age)) if allowed else 0,
      version=C.digest(C.normalized(rows)),url='/camdo/bien-nhan/'+str(p['id'])+'/chi-chuyen-khoan',log_id=last['id'])


def outgoing_details(p,last,data):
    state=payment_edit_state(p,last)
    if not state['allowed']:raise BusinessError('Chỉ đổi thanh toán cho phiên CHI mới nhất, số tiền lớn hơn 0, trong 30 phút.')
    if str(last['id'])!=str(data.get('log_id')):raise BusinessError('Phiên đã thay đổi. Mở lại biên nhận.')
    if data.get('payment_version')!=state['version']:raise BusinessError('Thanh toán đã thay đổi. Mở lại biên nhận trước khi lưu.')
    pays=db.all('SELECT * FROM cd_payments WHERE log_id=%s ORDER BY id',(last['id'],))
    total=sum((r['amount'] for r in pays),Decimal(0))
    if any(r['direction']!='OUT' for r in pays):raise BusinessError('Phiên không phải chi tiền cho khách.')
    from . import banking_qr as QR
    bank=integer(data.get('bank_amount'),'Tiền chuyển khoản',1)
    if bank>total:raise BusinessError('Chuyển khoản không được vượt tiền CHI của phiên.')
    code=str(data.get('bank_code') or data.get('bank_name') or '').strip()
    if not QR.bank_bin(code):
        code=next((c for c,b,n in QR.BANKS if n.casefold()==code.casefold()),'')
    if not QR.bank_bin(code):raise BusinessError('Ngân hàng chưa hợp lệ. Quét QR khách hoặc nhập mã ngân hàng/BIN.')
    account=str(data.get('bank_account','')).strip();holder=str(data.get('bank_holder','')).strip()
    if not account or len(account)>34 or not account.isascii() or not account.isalnum():raise BusinessError('Số tài khoản không hợp lệ.')
    if not holder or len(holder)>120:raise BusinessError('Nhập và đối chiếu tên tài khoản khách.')
    transfer_ref=reference(last['happened_at'],p['id'],last['id'])
    payload=QR.payload(code,account,int(bank),transfer_ref,holder)
    import io,segno
    output=io.BytesIO();segno.make(payload,micro=False,error='m').save(output,kind='png',scale=7,border=4)
    info=dict(bank_name=QR.bank_ten(code),bank_code=code,bank_account=account,bank_holder=holder,bank_reference=transfer_ref,
      qr_image=base64.b64encode(output.getvalue()).decode('ascii'),qr_mime='image/png',qr_payload=payload,transfer_status='PREPARED')
    return total,bank,info,pays


@bp.post('/bien-nhan/<int:lid>/chi-chuyen-khoan')
def outgoing_payment(lid):
    data=request.form
    if data.get('mode')!='save':
        p=loan(lid);last=latest(lid)
        total,bank,info,_=outgoing_details(p,last,data)
        return dict(**info,total=str(total),bank_amount=str(bank),cash=str(total-bank))
    require_live()
    with db.transaction():
        p=loan(lid,True);last=latest(lid)
        key=str(data.get('request_key',''))
        if not key or len(key)>64:raise BusinessError('Thiếu mã chống lưu trùng.')
        terms=unpack(last['terms_json']) if last else {}
        history=terms.get('payment_changes',[])
        # Read-back after a lost response is idempotent; it does not change funds twice.
        if any(h.get('request_key')==key and h.get('actor_id')==session['user_id'] for h in history):return dict(sku=p['sku'],saved=True)
        total,bank,info,pays=outgoing_details(p,last,data)
        history.append(dict(request_key=key,actor_id=session['user_id'],at=str(now()),before=C.normalized(pays),
          after=dict(cash=str(total-bank),bank_amount=str(bank),bank_name=info['bank_name'],bank_account=info['bank_account'],bank_holder=info['bank_holder'],bank_reference=info['bank_reference'])))
        terms['payment_changes']=history
        db.execute('DELETE FROM cd_payments WHERE log_id=%s',(last['id'],))
        post_payments(last['id'],-total,bank,info)
        db.execute('UPDATE cd_loan_logs SET terms_json=%s WHERE id=%s',(C.packed(terms),last['id']))
    return dict(sku=p['sku'],saved=True)


def save_lost_photo(upload):
    import io
    from PIL import Image,ImageOps,UnidentifiedImageError
    raw=upload.read(15*1024*1024+1)
    if len(raw)>15*1024*1024:raise BusinessError('Ảnh cam kết tối đa 15 MB.')
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.width*image.height>25000000:raise BusinessError('Ảnh cam kết tối đa 25 megapixel.')
            image=ImageOps.exif_transpose(image).convert('RGB');image.thumbnail((2400,2400))
            output=io.BytesIO();image.save(output,format='JPEG',quality=90)
    except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError) as exc:raise BusinessError('Không đọc được ảnh cam kết.') from exc
    docs,_=photos_save({'lost_commitment':output.getvalue()})
    return docs['lost_commitment']


@bp.get('/phien/<int:log_id>/cam-ket')
def lost_photo(log_id):
    row=db.one('SELECT terms_json FROM cd_loan_logs WHERE id=%s AND operation_id=7',(log_id,))
    info=unpack(row['terms_json']).get('lost_photo') if row else None
    if not info:abort(404)
    root=Path(current_app.config.get('LOAN_MEDIA_ROOT',str(Path(current_app.root_path).parent/'media'/'loans'))).resolve()
    path=(root/str(info.get('file',''))).resolve()
    if path.parent!=root or not path.is_file():abort(404)
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=info.get('sha256'):abort(404)
    return Response(raw,content_type='image/jpeg',headers={'Cache-Control':'private, no-store'})



@bp.post('/bien-nhan/<int:lid>/mo-khoa-bao-mat')
def unlock_lost(lid):
    from . import auth
    from flask import g
    require_live();key=str(request.form.get('request_key',''));reason=str(request.form.get('reason','')).strip()
    if not key or len(key)>64 or not reason or len(reason)>255:raise BusinessError('Nhập lý do mở khóa hợp lệ.')
    failed=False
    with db.transaction():
        p=loan(lid,True)
        duplicate=db.one('SELECT loan_id,operation_id FROM cd_loan_logs WHERE request_key=%s',(key,))
        if duplicate:
            if duplicate['loan_id']==lid and duplicate['operation_id']==8:return dict(sku=p['sku'])
            raise BusinessError('Mã yêu cầu đã sử dụng.')
        if not lost_locked(p):raise BusinessError('Phiếu không còn bị khóa báo mất.')
        last=latest(lid);lt=unpack(last['terms_json']);uid=str(session['user_id'])
        attempts=lt.get('unlock_attempts',{});stamps=[t for t in attempts.get(uid,[]) if now().timestamp()-t<300]
        if len(stamps)>=5:raise BusinessError('Sai PassCode nhiều lần. Thử lại sau 5 phút.')
        user=g.auth_user;code=request.form.get('passcode','')
        valid=bool(code and len(code)<=128 and user.get('passcode') and auth.verify_password(code,user['passcode']))
        if not valid:
            attempts[uid]=stamps+[now().timestamp()];lt['unlock_attempts']=attempts
            db.execute('UPDATE cd_loan_logs SET terms_json=%s WHERE id=%s',(C.packed(lt),last['id']))
            failed=True
        else:
            before=snapshot(p)
            for date_field in ('interest_from','due_at'):before[date_field]=str(p[date_field])
            terms=unpack(p['terms_json']);terms['lost_unlocked']=True
            terms['lost_unlock']=dict(actor=session['user_id'],at=str(now()),reason=reason)
            p['terms_json']=C.packed(terms);update(p)
            post_log(p,8,before,0,0,0,0,0,key,reason)
    if failed:raise BusinessError('PassCode không đúng hoặc tài khoản chưa thiết lập PassCode.')
    return dict(sku=p['sku'])


@bp.get('/mau/giay-cam-ket-bao-mat')
def lost_commitment_template():
    return send_file(Path(current_app.root_path)/'resources'/'giay-cam-ket-bao-mat-kim-hanh-2.docx',as_attachment=True,download_name='Giay_cam_ket_bao_mat_Kim_Hanh_2.docx',mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')


@bp.get('/gia-vang')
def current_gold_prices():
    from .services import gold_options
    try:return dict(rows=[dict(g,price=str(g['price'])) for g in gold_options()]),200,{'Cache-Control':'no-store'}
    except BusinessError as exc:return dict(error=str(exc)),503,{'Cache-Control':'no-store'}
