"""Staged, per-receipt legacy conversion. Never changes legacy or customer rows."""
import hashlib
import json
from calendar import monthrange
from datetime import datetime
from decimal import Decimal
from flask import session
from . import db, customer_master as master
from .domain import BusinessError, now, parse_date

STATE = {0:'CANCELLED',1:'ACTIVE',2:'ACTIVE',3:'ACTIVE',4:'ACTIVE',5:'REDEEMED',6:'LIQUIDATED',7:'ACTIVE'}
LABEL = {'CANCELLED':'Đã hủy','ACTIVE':'Đang cầm','REDEEMED':'Đã chuộc','LIQUIDATED':'Đã thanh lý'}
TABLES = ('cd_loans','cd_loan_items','cd_loan_logs','cd_payments')
EXCEPTION_CODES = frozenset(('CUSTOMER', 'CASHFLOW', 'ITEM_COUNT'))
EXCEPTION_RULE = 'approved-legacy-errors-six-months-v1'
DDL = [
'''CREATE TABLE IF NOT EXISTS cd_loans (
 id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY, legacy_pawn_id INT NOT NULL UNIQUE,
 sku VARCHAR(255) NOT NULL UNIQUE, phone VARCHAR(11) NOT NULL, cust_id VARCHAR(30) NOT NULL,
 loan_state VARCHAR(20) NOT NULL, last_operation_id INT NOT NULL, receipt_lost TINYINT NOT NULL DEFAULT 0,
 opened_at DATETIME NOT NULL, interest_from DATETIME NOT NULL, due_at DATETIME NOT NULL,
 original_principal DECIMAL(18,0) NOT NULL, principal_balance DECIMAL(18,0) NOT NULL,
 monthly_rate DECIMAL(12,8) NOT NULL, safe VARCHAR(255) NULL,
 employee_id VARCHAR(30) NULL, employee_name VARCHAR(255) NULL, note VARCHAR(255) NULL,
 customer_snapshot JSON NOT NULL, terms_json JSON NOT NULL, documents_json JSON NOT NULL,
 legacy_json JSON NOT NULL, source_hash CHAR(64) NOT NULL, target_hash CHAR(64) NOT NULL,
 migration_state VARCHAR(20) NOT NULL DEFAULT 'STAGED', converted_at DATETIME NOT NULL,
 converted_by INT NOT NULL, converted_username VARCHAR(150) NOT NULL,
 INDEX ix_cd_customer(cust_id), INDEX ix_cd_phone(phone), INDEX ix_cd_state_due(loan_state,due_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci''',
'''CREATE TABLE IF NOT EXISTS cd_loan_items (
 id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY, loan_id BIGINT NOT NULL, line_no INT NOT NULL,
 gold_code VARCHAR(255) NOT NULL, description VARCHAR(255) NOT NULL, unit VARCHAR(20) NULL,
 gross_weight DECIMAL(12,4) NOT NULL, stone_weight DECIMAL(12,4) NOT NULL, net_weight DECIMAL(12,4) NOT NULL,
 unit_price DECIMAL(18,0) NULL, valuation DECIMAL(18,0) NULL,
 UNIQUE KEY uq_cd_item(loan_id,line_no), FOREIGN KEY (loan_id) REFERENCES cd_loans(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci''',
'''CREATE TABLE IF NOT EXISTS cd_loan_logs (
 id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY, loan_id BIGINT NOT NULL, legacy_log_id INT NOT NULL UNIQUE,
 operation_id INT NOT NULL, happened_at DATETIME NOT NULL, interest_from DATETIME NOT NULL, due_at DATETIME NULL,
 principal_before DECIMAL(18,0) NOT NULL, principal_change DECIMAL(18,0) NOT NULL, principal_after DECIMAL(18,0) NOT NULL,
 interest DECIMAL(18,0) NOT NULL, extra_amount DECIMAL(18,0) NOT NULL, discount_amount DECIMAL(18,0) NOT NULL,
 monthly_rate DECIMAL(12,8) NULL, days INT NULL, actor_legacy VARCHAR(255) NULL,
 terms_json JSON NOT NULL, legacy_json JSON NOT NULL,
 FOREIGN KEY (loan_id) REFERENCES cd_loans(id), INDEX ix_cd_log_date(happened_at,operation_id), INDEX ix_cd_log_loan(loan_id,id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci''',
'''CREATE TABLE IF NOT EXISTS cd_payments (
 id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY, log_id BIGINT NOT NULL, channel VARCHAR(10) NOT NULL,
 direction VARCHAR(3) NOT NULL, amount DECIMAL(18,0) NOT NULL,
 bank_snapshot JSON NOT NULL, reconciliation_state VARCHAR(30) NOT NULL DEFAULT 'LEGACY_RECORDED',
 UNIQUE KEY uq_cd_payment(log_id,channel), FOREIGN KEY (log_id) REFERENCES cd_loan_logs(id),
 CHECK (amount>0), CHECK (direction IN ('IN','OUT')), CHECK (channel IN ('CASH','BANK'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci''']


def packed(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,default=str,separators=(',',':'))


def digest(value):
    return hashlib.sha256(packed(value).encode()).hexdigest()


def ready():
    rows=db.all('SELECT TABLE_NAME,ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN (%s,%s,%s,%s)',TABLES)
    return len(rows)==4 and all(r['ENGINE']=='InnoDB' for r in rows)


def source(pid, lock=False):
    suffix=' FOR UPDATE' if lock else ''
    p=db.one('SELECT * FROM pawn WHERE id=%s'+suffix,(pid,))
    if not p:raise BusinessError('Không tìm thấy phiếu nguồn.')
    logs=db.all('SELECT * FROM pawn_log WHERE pawn_id=%s ORDER BY id'+suffix,(pid,))
    link=db.one('SELECT * FROM khcd_pawn_customer WHERE pawn_id=%s'+suffix,(pid,))
    desk=db.one('SELECT * FROM khcd_pawn_desk WHERE pawn_id=%s'+suffix,(pid,))
    photos=db.all('SELECT kind,OCTET_LENGTH(data) size,SHA2(data,256) sha256 FROM khcd_pawn_photo WHERE pawn_id=%s ORDER BY kind'+suffix,(pid,))
    return dict(pawn=p,logs=logs,link=link,desk=desk,photos=photos)


def project(src, customer):
    p=src['pawn'];checks=[];items=[];logs=[];payments=[]
    def check(code,label,ok,old='',new='',detail='',warning=False):
        checks.append(dict(code=code,label=label,state='ok' if ok else ('warning' if warning else 'error'),source=str(old),target=str(new),detail=detail))
    def number(raw,label,nullable=False):
        if raw is None and nullable:return None
        try:
            n=Decimal(str(raw))
            if not n.is_finite():raise ValueError()
            return n
        except Exception:
            check('NUMBER',label,False,raw,'','Giá trị số thiếu hoặc không hợp lệ.');return Decimal(0)
    def date(raw,label):
        try:parse_date(raw);return raw
        except BusinessError:check('DATE',label,False,raw,'','Thiếu ngày hoặc ngày không hợp lệ.');return None
    state=STATE.get(p['status'])
    check('STATE','Trạng thái / nghiệp vụ',bool(state),p['status'],LABEL.get(state,'Không xác định'),'Trạng thái tách riêng; giữ nguyên mã nghiệp vụ gần nhất.')
    cid=(src['link'] or {}).get('pmv_cust_id') or ''
    check('CUSTOMER','CustID KK',bool(customer and str(customer.get('id'))==cid),cid,cid,'Chỉ dùng liên kết CustID đã xác định; không tự ghép theo SĐT.')
    check('PHONE','SĐT đối soát',bool(p['phone']),p['phone'],p['phone'],'Giữ nguyên SĐT trên phiếu cũ.')
    if customer and p['phone'] not in (customer.get('phone'),customer.get('phone2'),customer.get('phone3')):
        check('PHONE_CHANGED','SĐT hiện tại ở KK',False,p['phone'],customer.get('phone'),'SĐT khác nguồn KK; giữ SĐT cũ và liên kết CustID, không sửa khách.',True)
    for k,label in [('date1','Ngày lập'),('date2','Mốc lãi cũ'),('date3','Ngày hẹn')]:date(p[k],label)
    rate=number(p['percent'],'Lãi suất phiếu')
    check('RATE','Lãi suất %/tháng',rate>=0,p['percent'],rate,'Giữ nguyên; không tự đổi đơn vị hay tính lại lãi lịch sử.')
    desk=src['desk']
    try:extra=json.loads(desk['items_json']) if desk else None
    except (ValueError,TypeError):extra=[];check('ITEM_JSON','Dữ liệu món bổ sung',False,detail='JSON món hàng không đọc được.')
    if extra is not None:
        if not isinstance(extra,list):extra=[];check('ITEM_JSON','Dữ liệu món bổ sung',False,detail='Danh sách món không đúng định dạng.')
        for i,r in enumerate(extra,1):
            if not isinstance(r,dict) or any(k not in r for k in ('gold','description','unit','gross','stone','net','price','subtotal')):
                check('ITEM_JSON','Món '+str(i),False,detail='Thiếu trường bắt buộc trong dữ liệu món bổ sung.');continue
            items.append(dict(line_no=i,gold_code=r['gold'],description=r['description'],unit=r['unit'],gross_weight=number(r['gross'],'Tổng TL'),stone_weight=number(r['stone'],'TL hột'),net_weight=number(r['net'],'TL vàng'),unit_price=number(r['price'],'Đơn giá'),valuation=number(r['subtotal'],'Định giá')))
            if i<=2:
                same=str(p['gold'+str(i)])==str(r['gold']) and number(p['wgg'+str(i)],'TL nguồn')==items[-1]['gross_weight'] and number(p['whh'+str(i)] or 0,'TL hột nguồn')==items[-1]['stone_weight'] and (p['mota'+str(i)] or '')==r['description']
                check('ITEM_MIRROR','Món '+str(i)+' khớp hai nguồn',same,detail='pawn và dữ liệu món bổ sung phải khớp; không tự chọn bỏ một nguồn.')
    else:
        for i in (1,2):
            if not p['gold'+str(i)] or p['gold'+str(i)]=='0':continue
            gross=number(p['wgg'+str(i)],'Tổng TL món '+str(i));stone=number(p['whh'+str(i)] or 0,'TL hột')
            items.append(dict(line_no=i,gold_code=p['gold'+str(i)],description=p['mota'+str(i)] or '',unit=None,gross_weight=gross,stone_weight=stone,net_weight=gross-stone,unit_price=None,valuation=None))
        check('VALUATION','Định giá lịch sử',False,'Chưa lưu','NULL','Không lấy giá vàng hôm nay để điền vào phiếu cũ. Đơn vị cũ cần đối chiếu trước khi xử lý tài sản.',True)
    check('ITEM_COUNT','Số món tài sản',bool(items),len(items),len(items))
    for item in items:
        check('WEIGHT','Trọng lượng món '+str(item['line_no']),item['gross_weight']>0 and item['stone_weight']>=0 and item['net_weight']==item['gross_weight']-item['stone_weight'] and item['net_weight']>0,item['gross_weight'],item['net_weight'],'TL vàng = tổng TL − TL hột, phải lớn hơn 0.')
    balance=Decimal(0);original=Decimal(0);last_time=None;closed=False;cash=Decimal(0);bank=Decimal(0);interest=Decimal(0);last_book=Decimal(0)
    check('HISTORY','Lịch sử nguồn',bool(src['logs']),len(src['logs']),len(src['logs']),'Giữ đầy đủ từng dòng lịch sử.' if src['logs'] else 'Thiếu lịch sử: cần đối soát số dư chuyển tiếp, không tự tạo giao dịch.')
    for index,l in enumerate(src['logs']):
        op=l['status_id'];prefix='Log #'+str(l['id'])+' · '
        check('OPERATION',prefix+'nghiệp vụ',op in STATE,op,op)
        dt=date(l['date2'],prefix+'ngày xử lý');start=date(l['date1'],prefix+'mốc lãi')
        check('ORDER',prefix+'thứ tự',bool(dt and (last_time is None or dt>=last_time)),detail='Ngày xử lý phải theo thứ tự ID lịch sử.')
        if dt:last_time=dt
        if dt and start:check('INTERVAL',prefix+'khoảng ngày',start<=dt,start,dt)
        check('AFTER_CLOSE',prefix+'vòng đời',not closed,detail='Không tự diễn giải giao dịch sau khi phiếu đã đóng.')
        amount=number(l['sotien'],prefix+'số tiền');li=number(l['tienlai'] or 0,prefix+'lãi');add=number(l['tienthem'] or 0,prefix+'cộng thêm');discount=number(l['tienbot'] or 0,prefix+'giảm trừ')
        before=balance;delta=Decimal(0)
        if op==1:
            check('OPENING',prefix+'cầm mới',index==0 and amount>0,detail='Phải có đúng giao dịch mở đầu, số tiền > 0.')
            delta=amount;original=amount
        elif index==0:check('OPENING',prefix+'thiếu cầm mới',False,detail='Không đủ lịch sử để dựng dư gốc.')
        if op==2:delta=amount
        if op==3:delta=-amount
        last_book=before if op in (0,5,6) else before+delta
        if op in (0,5,6):delta=-before;closed=True
        balance=before+delta
        check('BALANCE',prefix+'dư gốc',balance>=0,before,balance,'Gốc sau = gốc trước + biến động gốc.')
        c=number(l['total'] or 0,prefix+'tiền mặt');b=number(l['mbank'] or 0,prefix+'chuyển khoản')
        expected=-delta+li+add-discount
        check('CASHFLOW',prefix+'tiền thu/chi',c+b==expected,c+b,expected,'Tiền mặt + chuyển khoản = − biến động gốc + lãi + cộng thêm − giảm trừ. Sai lệch cần đối soát, không tự sửa.')
        record=dict(legacy_log_id=l['id'],operation_id=op,happened_at=dt,interest_from=start,due_at=l['date3'],principal_before=before,principal_change=delta,principal_after=balance,interest=li,extra_amount=add,discount_amount=discount,monthly_rate=l['percent'],days=l['days'],actor_legacy=str(l['staff']) if l['staff'] is not None else None,terms_json=packed({'basis':'LEGACY_RECORDED','recalculated':False}),legacy_json=packed(l))
        logs.append(record)
        for channel,value in [('CASH',c),('BANK',b)]:
            if value:payments.append(dict(legacy_log_id=l['id'],channel=channel,direction='IN' if value>0 else 'OUT',amount=abs(value),bank_snapshot=packed({'legacy_nbank':l['nbank'],'legacy_gbank':l['gbank']}) if channel=='BANK' else '{}'))
        cash+=c;bank+=b;interest+=li
    value=number(p['value'],'Gốc phiếu')
    check('FINAL_BALANCE','Gốc phiếu khớp lịch sử',value==last_book,value,last_book,'Gốc đang cầm phải khớp số dư tính từ lịch sử.' if state=='ACTIVE' else 'Phiếu đóng giữ gốc cuối ở nguồn; cd_loans.principal_balance = 0.')
    if src['logs']:check('LAST_OPERATION','Nghiệp vụ gần nhất',src['logs'][-1]['status_id']==p['status'],p['status'],src['logs'][-1]['status_id'])
    check('ACTIVE_BALANCE','Dư gốc theo trạng thái',balance>0 if state=='ACTIVE' else balance==0,balance,LABEL.get(state,'?'),'Phiếu đang cầm phải còn gốc; phiếu đóng có dư gốc bằng 0.')
    if src['logs']:check('INTEREST_ANCHOR','Mốc lãi hiện tại khớp lịch sử',p['date2']==src['logs'][-1]['date2'],p['date2'],src['logs'][-1]['date2'],'Không tự chọn mốc tính lãi khi phiếu và lịch sử khác nhau.')
    if p['status']==6:check('LIQUIDATION','Thanh lý cũ',False,detail='Chỉ bảo toàn khoản ghi nhận cũ; chưa xác nhận giá bán thực tế hoặc phân bổ thu hồi.',warning=True)
    check('STAFF','Nhân viên / tài khoản cũ',bool(desk),p.get('staff'),desk['employee_name'] if desk else 'Giữ mã gốc','Không tự ghép ID người dùng PHP với EmpID hoặc auth_user.',True)
    loan=dict(legacy_pawn_id=p['id'],sku=p['sku'],phone=p['phone'],cust_id=cid,loan_state=state,last_operation_id=p['status'],receipt_lost=int(p['status']==7),opened_at=p['date1'],interest_from=p['date2'],due_at=p['date3'],original_principal=original,principal_balance=balance,monthly_rate=rate,safe=p['safe'],employee_id=desk['employee_id'] if desk else None,employee_name=desk['employee_name'] if desk else None,note=p['note'],customer_snapshot=packed(customer),terms_json=packed({'basis':'LEGACY_RECORDED','monthly_rate':rate,'recalculate_history':False}),documents_json=packed({'legacy_img1':p['img1'],'legacy_img2':p['img2'],'pawn_photo_refs':src['photos']}),legacy_json=packed({'pawn':p,'link':src['link'],'desk':desk}))
    return dict(loan=loan,items=items,logs=logs,payments=payments,checks=checks,summary=dict(sku=p['sku'],phone=p['phone'],cust_id=cid,customer_name=(customer or {}).get('name',''),state=LABEL.get(state,'?'),items=len(items),logs=len(logs),payments=len(payments),principal=str(balance),cash=str(cash),bank=str(bank),interest=str(interest)))


def target(pid):
    loan=db.one('SELECT * FROM cd_loans WHERE legacy_pawn_id=%s',(pid,))
    if not loan:return None
    fields=('id','source_hash','target_hash','migration_state','converted_at','converted_by','converted_username')
    data={k:v for k,v in loan.items() if k not in fields}
    result=dict(loan=data,items=[],logs=[],payments=[])
    for name,table,order in [('items','cd_loan_items','line_no'),('logs','cd_loan_logs','legacy_log_id')]:
        rows=db.all('SELECT * FROM '+table+' WHERE loan_id=%s ORDER BY '+order,(loan['id'],))
        result[name]=[{k:v for k,v in r.items() if k not in ('id','loan_id')} for r in rows]
    result['payments']=db.all('SELECT l.legacy_log_id,p.channel,p.direction,p.amount,p.bank_snapshot FROM cd_payments p JOIN cd_loan_logs l ON l.id=p.log_id WHERE l.loan_id=%s ORDER BY l.legacy_log_id,p.channel',(loan['id'],))
    return loan,result


def normalized(plan):
    """Canonical comparison across MySQL JSON whitespace and DECIMAL formatting."""
    if isinstance(plan,dict):
        return {k:normalized(json.loads(v) if k.endswith('_json') or k in ('customer_snapshot','bank_snapshot') else v) for k,v in plan.items()}
    if isinstance(plan,list):return [normalized(v) for v in plan]
    if isinstance(plan,Decimal):return format(plan.normalize(),'f')
    return plan


def plan_hash(plan):
    data={k:plan[k] for k in ('loan','items','logs','payments')}
    data['payments']=sorted(data['payments'],key=lambda p:(p['legacy_log_id'],p['channel']))
    return digest(normalized(data))


def exception_key(check):
    return tuple(check.get(k, '') for k in ('code', 'label', 'source', 'target'))


def acknowledge_checks(checks, accepted):
    keys={exception_key(c) for c in accepted if c.get('code') in EXCEPTION_CODES}
    for check in checks:
        if check['state']=='error' and exception_key(check) in keys:
            check.update(state='warning',accepted_exception=True,original_state='error')
            check['detail']='Đã chấp nhận ngoại lệ khi chuyển; giữ nguyên sai lệch để đối soát. '+check['detail']


def exception_policy(plan, src, enabled):
    policy={'enabled':bool(enabled)}
    if not enabled:return policy
    current=now()
    month_index=current.year*12+current.month-1-6
    year,month=divmod(month_index,12);month+=1
    start=datetime(year,month,min(current.day,monthrange(year,month)[1]))
    # Only an actual recorded transaction qualifies, never a receipt's due date.
    candidates=[]
    for row in src['logs']:
        value=row.get('date2')
        try:timestamp=value if isinstance(value,datetime) else datetime.fromisoformat(str(value))
        except (ValueError,TypeError):continue
        if timestamp.tzinfo is None and row.get('status_id') in STATE and start<=timestamp<=current:
            candidates.append((timestamp,row['id']))
    latest=max(candidates) if candidates else None
    accepted=[dict(c) for c in plan['checks'] if c['state']=='error' and c['code'] in EXCEPTION_CODES] if latest else []
    policy.update(rule=EXCEPTION_RULE,window_start=start.date().isoformat(),as_of_date=current.date().isoformat(),
                  eligible=bool(latest),qualifying_log_id=latest[1] if latest else None,
                  qualifying_transaction_at=latest[0].isoformat(sep=' ') if latest else None,accepted=accepted)
    plan['checks'].append(dict(code='RECENT_TRANSACTION',label='Giao dịch trong 6 tháng gần nhất',
        state='ok' if latest else 'error',source=policy['qualifying_transaction_at'] or 'Không có giao dịch hợp lệ trong kỳ',
        target=start.strftime('%d/%m/%Y')+' → '+current.strftime('%d/%m/%Y'),
        detail='Tính 6 tháng lịch theo giờ Việt Nam, gồm ngày đầu kỳ; dùng pawn_log.date2, loại ngày tương lai. Bật ngoại lệ thì mọi phiếu được chọn phải đạt điều kiện này.'))
    acknowledge_checks(plan['checks'],accepted)
    terms=json.loads(plan['loan']['terms_json']);terms['conversion_exceptions']=policy
    plan['loan']['terms_json']=packed(terms)
    return policy


def stored_exceptions(loan):
    terms=json.loads(loan['terms_json'])
    policy=terms.get('conversion_exceptions',{})
    return policy if policy.get('rule')==EXCEPTION_RULE and policy.get('eligible') else {}


def inspect(pid,lock=False,allow_exceptions=False):
    src=source(pid,lock);cid=(src['link'] or {}).get('pmv_cust_id');customer=None;service_error=None
    if cid:
        try:customer=master.get(cid)['customer']
        except BusinessError as exc:service_error=str(exc)
    plan=project(src,customer)
    count=db.one('SELECT COUNT(*) n FROM pawn WHERE sku=%s',(src['pawn']['sku'],))['n']
    if count!=1:plan['checks'].append(dict(code='DUPLICATE_SKU',label='Mã phiếu duy nhất',state='error',source=str(count),target='1',detail='Mã biên nhận bị trùng ở nguồn.'))
    if service_error:plan['checks'].append(dict(code='KK_UNAVAILABLE',label='Kết nối KK',state='error',source='',target='',detail=service_error))
    plan['exception_policy']=exception_policy(plan,src,allow_exceptions)
    # Stable phone/catalog snapshots are not guessed or written to KK.
    plan['source_hash']=digest(src);plan['review_hash']=digest({'source':src,'customer':customer,'rules':'cd-conversion-v2','exception_policy':plan['exception_policy']})
    plan['ready']=ready();existing=target(pid) if plan['ready'] else None
    plan['converted']=False;plan['loan_id']=None
    if existing:
        row,data=existing;plan['loan_id']=row['id'];same=row['source_hash']==plan['source_hash'];intact=row['target_hash']==plan_hash(data)
        plan['checks'].append(dict(code='EXISTING',label='Bản chuyển đã lưu',state='ok' if same and intact else 'error',source=row['source_hash'][:12],target=plan['source_hash'][:12],detail='Đã chuyển và dữ liệu đích còn nguyên.' if same and intact else 'Nguồn đã thay đổi hoặc dữ liệu đích khác bản chuyển. Không tự ghi đè; cần đối soát lại.'))
        plan['converted']=same and intact
        if same and intact:acknowledge_checks(plan['checks'],stored_exceptions(row).get('accepted',[]))
    if not plan['ready']:plan['checks'].append(dict(code='SCHEMA',label='Bộ bảng mới',state='error',source='',target='',detail='Chưa tạo đủ bốn bảng InnoDB.'))
    try:db.require_write()
    except BusinessError as exc:plan['checks'].append(dict(code='TRANSACTION_SCHEMA',label='Cấu trúc giao dịch an toàn',state='error',source='',target='InnoDB',detail=str(exc)))
    plan['can_convert']=not existing and not any(c['state']=='error' for c in plan['checks'])
    return plan


def insert(table,values):
    cols=list(values)
    return db.execute('INSERT INTO '+table+' ('+','.join(cols)+') VALUES ('+','.join(['%s']*len(cols))+')',list(values.values()))


def convert(pid,review_hash,active_only=False,allow_exceptions=False):
    with db.transaction():
        plan=inspect(pid,lock=True,allow_exceptions=allow_exceptions)
        if active_only and plan['loan']['loan_state']!='ACTIVE':raise BusinessError('Phiếu không còn đang cầm. Đã bỏ qua; cần tải lại danh sách.')
        if plan['review_hash']!=review_hash:raise BusinessError('Dữ liệu đã thay đổi sau đối soát. Bấm Đối soát lại trước khi chuyển.')
        if plan['converted']:return plan['loan_id']
        if not plan['can_convert']:raise BusinessError('Phiếu còn lỗi hoặc đã có bản chuyển khác. Đối soát lại để xem chi tiết.')
        loan_id=insert('cd_loans',dict(plan['loan'],source_hash=plan['source_hash'],target_hash=plan_hash(plan),converted_at=now(),converted_by=session['user_id'],converted_username=session['user']))
        for item in plan['items']:insert('cd_loan_items',dict(item,loan_id=loan_id))
        ids={}
        for log in plan['logs']:ids[log['legacy_log_id']]=insert('cd_loan_logs',dict(log,loan_id=loan_id))
        for pay in plan['payments']:insert('cd_payments',dict({k:v for k,v in pay.items() if k!='legacy_log_id'},log_id=ids[pay['legacy_log_id']]))
        saved=target(pid)
        if not saved or plan_hash(saved[1])!=plan_hash(plan):raise BusinessError('Đọc kiểm dữ liệu đích không khớp. Toàn bộ lần chuyển đã rollback.')
        from .services import event
        event('loan_convert',pid,after={'cd_loan_id':loan_id,'source_hash':plan['source_hash'],'summary':plan['summary'],'exception_policy':plan['exception_policy']},note='Chuyển dữ liệu STAGED; nguồn vận hành vẫn là pawn.',key='loan_convert:'+str(pid))
        return loan_id
