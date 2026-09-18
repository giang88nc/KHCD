"""Read-only views of the new SQL and explicit live reconciliation."""
import json
from datetime import timedelta
from decimal import Decimal
from flask import Blueprint,render_template,request,abort,send_file,Response,url_for
from . import db,loan_conversion as C,loan_images as images
from .domain import BusinessError,today,parse_date
from . import live_loans as live

bp=Blueprint('loans',__name__,url_prefix='/camdo/bien-nhan')

def decoded(value,default):
    try:return json.loads(value)
    except (ValueError,TypeError):return default

def get(loan_id):
    if not C.ready():abort(404)
    loan=db.one('SELECT * FROM cd_loans WHERE id=%s',(loan_id,))
    if not loan:abort(404)
    return loan

STATE_FILTERS=[('all','Tất cả'),('ACTIVE','Đang cầm'),('OVERDUE','Quá hạn'),('REDEEMED','Đã chuộc'),('LIQUIDATED','Đã thanh lý'),('CANCELLED','Đã hủy')]
PAGE_SIZE=30

def stamp(value):
    """dd/mm/yyyy HH:MM cho datetime; chuỗi/None giữ nguyên dạng đọc được."""
    return value.strftime('%d/%m/%Y %H:%M') if hasattr(value,'strftime') else (str(value)[:16] if value else '—')

def overdue_days(loan):
    if loan.get('loan_state')!='ACTIVE' or not loan.get('due_at'):return 0
    return max(0,(today()-parse_date(loan['due_at'])).days)

def decorate(r):
    """Thông tin hiển thị dùng chung cho bảng danh sách và popup."""
    snapshot=decoded(r.get('customer_snapshot'),{});snapshot=snapshot if isinstance(snapshot,dict) else {}
    r['snapshot_name']=snapshot.get('name','') or '';r['snapshot_phone']=snapshot.get('phone','') or ''
    r['customer_name']=r.get('customer_name') or r['snapshot_name']
    r['state_label']=C.LABEL.get(r['loan_state'],r['loan_state'])
    r['overdue_days']=overdue_days(r)
    r['state_class']=('danger' if r['overdue_days'] else 'success') if r['loan_state']=='ACTIVE' else 'neutral' if r['loan_state'] in ('REDEEMED','LIQUIDATED') else 'warning'
    r['last_op_label']=live.OPS.get(r.get('last_op'),'Chưa có giao dịch') if r.get('last_id') else 'Chưa có giao dịch'
    r['last_at_label']=stamp(r.get('last_at') or r.get('opened_at'))
    return r

def search_ids(q):
    """CustID KK khớp tên/SĐT — chỉ khi dịch vụ khách sẵn sàng; lỗi thì bỏ qua, không chặn tìm nội bộ."""
    if not (q and live.enabled() and live.master.enabled()):return []
    try:return [str(i) for i in live.master.call('search_ids',q=q).get('ids',[])][:1000]
    except BusinessError:return []

@bp.get('')
def listing():
    q=request.args.get('q','').strip()[:100];state=request.args.get('state','all');page=max(1,request.args.get('page',1,type=int) or 1)
    if state not in dict(STATE_FILTERS):state='all'
    d1=parse_date(request.args.get('d1') or today(),'Từ ngày');d2=parse_date(request.args.get('d2') or today(),'Đến ngày')
    if d1>d2:d1,d2=d2,d1
    if (d2-d1).days>366:raise BusinessError('Khoảng ngày tối đa 366 ngày.')
    rows=[];total=0;summary=dict(n=0,principal=0,active=0,overdue=0);available=C.ready()
    if available:
        # Nhóm log theo phiếu: mốc giao dịch gần nhất (sắp xếp) + có giao dịch trong khoảng ngày (lọc).
        source=(' FROM cd_loans l LEFT JOIN (SELECT loan_id,MAX(happened_at) last_at,MAX(id) last_id,COUNT(*) log_count,'
                'SUM(happened_at>=%s AND happened_at<%s) in_range FROM cd_loan_logs GROUP BY loan_id) g ON g.loan_id=l.id'
                ' LEFT JOIN cd_loan_logs lg ON lg.id=g.last_id WHERE 1=1')
        params=[d1,d2+timedelta(days=1)]
        if q:
            # Tìm theo mã/SĐT/tên bỏ qua khoảng ngày: người dùng đã chỉ đích danh phiếu.
            ids=search_ids(q)
            source+=(" AND (l.sku LIKE %s OR l.phone LIKE %s OR l.cust_id LIKE %s OR JSON_UNQUOTE(JSON_EXTRACT(l.customer_snapshot,'$.name')) LIKE %s"
                     +(' OR l.cust_id IN ('+','.join(['%s']*len(ids))+')' if ids else '')+')')
            params+=['%'+q+'%']*4+ids
        else:
            source+=' AND (g.in_range>0 OR (g.loan_id IS NULL AND l.opened_at>=%s AND l.opened_at<%s))';params+=[d1,d2+timedelta(days=1)]
        if state=='OVERDUE':source+=" AND l.loan_state='ACTIVE' AND l.due_at<%s";params.append(today())
        elif state!='all':source+=' AND l.loan_state=%s';params.append(state)
        summary=db.one("SELECT COUNT(*) n,COALESCE(SUM(l.principal_balance),0) principal,COALESCE(SUM(l.loan_state='ACTIVE'),0) active,"
                       "COALESCE(SUM(l.loan_state='ACTIVE' AND l.due_at<%s),0) overdue"+source,[today()]+params)
        total=int(summary['n'])
        rows=db.all('SELECT l.id,l.sku,l.phone,l.cust_id,l.loan_state,l.principal_balance,l.monthly_rate,l.opened_at,l.due_at,l.receipt_lost,'
                    'l.employee_name,l.safe,l.customer_snapshot,l.legacy_pawn_id,g.last_at,g.last_id,COALESCE(g.log_count,0) log_count,'
                    'lg.operation_id last_op,lg.principal_change last_change,lg.interest last_interest,'
                    '(SELECT COUNT(*) FROM cd_loan_items i WHERE i.loan_id=l.id) item_count,'
                    '(SELECT i.description FROM cd_loan_items i WHERE i.loan_id=l.id ORDER BY i.line_no LIMIT 1) first_item'
                    +source+' ORDER BY COALESCE(g.last_at,l.opened_at) DESC,l.id DESC LIMIT %s OFFSET %s',params+[PAGE_SIZE,(page-1)*PAGE_SIZE])
        for r in rows:decorate(r)
        if live.enabled() and rows:
            names={r['id']:r['customer_name'] for r in rows}
            for r in rows:r['pmv_cust_id']=r['cust_id']
            live.master.hydrate(rows)
            for r in rows:r['customer_name']=r.get('customer_name') or names[r['id']]
    filters=dict(q=q,state=state,d1=str(d1),d2=str(d2))
    return render_template('loans.html',title='Biên nhận',rows=rows,total=total,page=page,pages=max(1,(total+PAGE_SIZE-1)//PAGE_SIZE),
                           summary=summary,filters=filters,state_filters=STATE_FILTERS,available=available,is_today=(d1==d2==today()))

def context(loan_id):
    """Dữ liệu chi tiết một biên nhận — dùng chung trang đối soát và popup XEM."""
    loan=get(loan_id)
    customer=decoded(loan['customer_snapshot'],{});customer=customer if isinstance(customer,dict) else {}
    customer_live=False
    if live.enabled() and loan['cust_id']:
        try:customer=live.master.get(loan['cust_id'])['customer'];customer_live=True
        except BusinessError:pass
    items=db.all('SELECT * FROM cd_loan_items WHERE loan_id=%s ORDER BY line_no',(loan_id,))
    logs=db.all('SELECT l.*,s.name operation_name FROM cd_loan_logs l LEFT JOIN pawn_status s ON s.id=l.operation_id WHERE loan_id=%s ORDER BY l.id',(loan_id,))
    for log in logs:
        if log['operation_id']==7 and decoded(log['terms_json'],{}).get('lost_photo'):log['lost_photo_url']=url_for('live.lost_photo',log_id=log['id'])
        log['operation_label']=log['operation_name'] or live.OPS.get(log['operation_id'],str(log['operation_id']))
        log['when']=stamp(log['happened_at']);log['cash']=Decimal(0);log['bank']=Decimal(0)
    by_id={l['id']:l for l in logs}
    payments=db.all('SELECT p.*,l.legacy_log_id FROM cd_payments p JOIN cd_loan_logs l ON l.id=p.log_id WHERE l.loan_id=%s ORDER BY l.id,p.id',(loan_id,))
    for p in payments:
        # Display the two components without mislabelling a NULL channel as BANK.
        cash,bank=live.split(p)
        p['payment_label']=('Tiền mặt' if bank==0 else 'Chuyển khoản' if cash==0 else 'Tiền mặt + CK')
        p['cashPay'],p['cardPay']=cash,bank
        sign=1 if p['direction']=='IN' else -1
        if p['log_id'] in by_id:by_id[p['log_id']]['cash']+=sign*cash;by_id[p['log_id']]['bank']+=sign*bank
        p['bank']=decoded(p['bank_snapshot'],{})
        if isinstance(p['bank'],dict):
            if p['bank'].pop('qr_image',None):p['qr_url']=url_for('live.session_qr',log_id=p['log_id'])
            p['bank'].pop('qr_mime',None)
        if not isinstance(p['bank'],dict):p['bank']={'Dữ liệu cần kiểm tra':str(p['bank'])}
    exceptions=C.stored_exceptions(loan)
    legacy=decoded(loan['legacy_json'],{}).get('pawn',{})
    legacy_descriptions=[legacy.get('mota'+str(i)) for i in (1,2) if legacy.get('mota'+str(i))]
    decorate(loan)
    return dict(loan=loan,customer=customer,customer_live=customer_live,items=items,logs=logs,payments=payments,photos=images.inventory(loan),
                labels=C.LABEL,exceptions=exceptions,legacy_descriptions=legacy_descriptions)

@bp.get('/<int:loan_id>/xem')
def modal(loan_id):
    """Popup XEM trên danh sách: mảnh HTML (không extend base), gồm hồ sơ + lịch sử giao dịch."""
    return render_template('_loan_modal.html',**context(loan_id))

@bp.get('/<int:loan_id>')
def detail(loan_id):
    ctx=context(loan_id)
    return render_template('loan_detail.html',title=ctx['loan']['sku']+' · Biên nhận',**ctx)

@bp.get('/<int:loan_id>/doi-soat')
def reconcile(loan_id):
    if live.enabled():return live.check(loan_id)
    loan=get(loan_id);checks=[];saved=None
    def add(label,state,detail,source='',target=''):
        checks.append(dict(label=label,state=state,detail=detail,source='Chưa có' if source is None else str(source),target='Chưa có' if target is None else str(target)))
    try:
        saved=C.target(loan['legacy_pawn_id'])
        intact=saved and C.plan_hash(saved[1])==loan['target_hash']
        add('Toàn vẹn SQL mới','ok' if intact else 'error','So checksum dữ liệu đích với bản đã xác nhận khi chuyển.')
    except (ValueError,TypeError,KeyError):add('Dữ liệu SQL mới','error','Không đọc được cấu trúc JSON của bản chuyển.')
    try:
        p=C.inspect(loan['legacy_pawn_id']);checks.extend(p['checks'])
        for key,label in [('sku','Mã biên nhận'),('phone','SĐT cũ'),('cust_id','CustID'),('loan_state','Trạng thái'),('last_operation_id','Nghiệp vụ cuối'),('receipt_lost','Mất biên nhận'),('original_principal','Gốc ban đầu'),('principal_balance','Dư gốc'),('monthly_rate','Lãi suất tháng'),('safe','Tủ'),('opened_at','Ngày lập'),('interest_from','Mốc lãi'),('due_at','Hẹn chuộc'),('employee_id','EmpID'),('note','Ghi chú')]:
            expected=p['loan'][key];actual=loan[key]
            add('Nguồn / bản chuyển: '+label,'ok' if expected==actual else 'error','Nguồn hiện tại so với dữ liệu đã chuyển; không tự ghi đè.',expected,actual)
        for name,table in [('items','cd_loan_items'),('logs','cd_loan_logs')]:
            n=db.one('SELECT COUNT(*) n FROM '+table+' WHERE loan_id=%s',(loan_id,))['n']
            add('Số '+('món' if name=='items' else 'dòng lịch sử'),'ok' if n==len(p[name]) else 'error','Đối chiếu số dòng nguồn và SQL mới.',len(p[name]),n)
        if saved:
            names={'gold_code':'Loại vàng','description':'Mô tả','unit':'Đơn vị','gross_weight':'Tổng TL','stone_weight':'TL hột','net_weight':'TL vàng','unit_price':'Đơn giá','valuation':'Định giá','principal_before':'Gốc trước','principal_change':'Thay đổi gốc','principal_after':'Gốc sau','interest':'Lãi','extra_amount':'Thu thêm','discount_amount':'Giảm trừ','operation_id':'Nghiệp vụ','amount':'Số tiền','direction':'Thu / chi','happened_at':'Ngày giao dịch','bank_snapshot':'Thông tin ngân hàng'}
            for group,keys,label in [('items',('line_no',),'Món'),('logs',('legacy_log_id',),'Log'),('payments',('legacy_log_id','channel'),'Dòng tiền')]:
                expected={tuple(r[k] for k in keys):r for r in p[group]};actual={tuple(r[k] for k in keys):r for r in saved[1][group]}
                for key in sorted(expected.keys()|actual.keys()):
                    left=expected.get(key);right=actual.get(key);prefix=label+' '+ '/'.join(map(str,key))
                    if left is None or right is None:
                        add(prefix,'error','Thiếu dòng ở nguồn hoặc bản chuyển.','Có' if left else 'Thiếu','Có' if right else 'Thiếu');continue
                    differences=0
                    for field in left:
                        if field in keys:continue
                        if C.digest(C.normalized({field:left[field]}))!=C.digest(C.normalized({field:right.get(field)})):
                            differences+=1
                            # JSON source snapshots may contain large payloads; show their mismatch explicitly.
                            a,b=('Khác bản lưu','Cần kiểm tra bản gốc') if field=='legacy_json' else (left[field],right.get(field))
                            add(prefix+' · '+names.get(field,field),'error','Giá trị nguồn hiện tại khác SQL mới.',a,b)
                    if not differences:add(prefix,'ok','Các trường của dòng khớp nguồn hiện tại.')
    except (BusinessError,ValueError,TypeError,KeyError) as exc:
        add('Đối soát nguồn','error',str(exc) if isinstance(exc,BusinessError) else 'Cấu trúc nguồn thiếu/sai; cần đối soát dữ liệu gốc.')
    for photo in images.inventory(loan):add(photo['label'],photo['state'],photo['detail'],photo['filename'],'Có ảnh' if photo['available'] else 'Chưa đọc được ảnh')
    if not loan['employee_id']:add('Nhân viên nghiệp vụ','warning','Chưa có EmpID KK; mã người thao tác PHP được giữ để đối soát, không tự ghép.')
    add('Nguồn vận hành','warning','Bản chuyển đang chờ tiếp quản. Giao dịch vẫn dùng pawn; trang này chỉ đọc SQL mới.')
    return {'checks':checks,'errors':sum(c['state']=='error' for c in checks),'warnings':sum(c['state']=='warning' for c in checks)}

@bp.get('/<int:loan_id>/anh/<slot>')
def photo(loan_id,slot):
    loan=get(loan_id)
    if slot in ('legacy1','legacy2'):
        docs=images.documents(loan);path,mime=images.legacy_path(docs.get('legacy_img'+slot[-1]))
        if not path:abort(404)
        return send_file(path,mimetype=mime,conditional=False)
    if slot not in images.LABELS:abort(404)
    raw=images.blob(loan,slot)
    if not raw:abort(404)
    return Response(raw,content_type='image/jpeg')
