"""Read-only views of the new SQL and explicit live reconciliation."""
import json
from flask import Blueprint,render_template,request,abort,send_file,Response,url_for
from . import db,loan_conversion as C,loan_images as images
from .domain import BusinessError
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

@bp.get('')
def listing():
    q=request.args.get('q','').strip()[:255];state=request.args.get('state','all');page=max(1,request.args.get('page',1,type=int) or 1)
    rows=[];total=0;available=C.ready()
    if available:
        where=' WHERE 1=1';params=[]
        if q:
            where+=' AND (sku LIKE %s OR phone LIKE %s OR cust_id LIKE %s OR JSON_UNQUOTE(JSON_EXTRACT(customer_snapshot,\'$.name\')) LIKE %s)';params+=['%'+q+'%']*4
        if state in C.LABEL:where+=' AND loan_state=%s';params.append(state)
        total=db.one('SELECT COUNT(*) n FROM cd_loans'+where,params)['n']
        rows=db.all('SELECT l.*,(SELECT COUNT(*) FROM cd_loan_items i WHERE i.loan_id=l.id) item_count,(SELECT COUNT(*) FROM cd_loan_logs g WHERE g.loan_id=l.id) log_count FROM cd_loans l'+where+' ORDER BY id DESC LIMIT 20 OFFSET %s',params+[(page-1)*20])
        for r in rows:
            snapshot=decoded(r['customer_snapshot'],{});r['customer_name']=snapshot.get('name','') if isinstance(snapshot,dict) else ''
            r['missing']=[]
            if not r['cust_id']:r['missing'].append('Thiếu CustID')
            if not r['item_count']:r['missing'].append('Thiếu món')
            if not r['log_count']:r['missing'].append('Thiếu lịch sử')
            if not r['employee_id']:r['missing'].append('Chưa nối nhân viên')
            r['missing'] += [i['label']+': '+i['detail'] for i in images.inventory(r) if i['state']!='ok']
    if available and live.enabled() and rows:
        names={r['id']:r['customer_name'] for r in rows}
        for r in rows:r['pmv_cust_id']=r['cust_id']
        live.master.hydrate(rows)
        for r in rows:r['customer_name']=r.get('customer_name') or names[r['id']]
    return render_template('loans.html',title='Biên nhận · SQL mới',rows=rows,total=total,page=page,pages=max(1,(total+19)//20),q=q,state=state,labels=C.LABEL,available=available)

@bp.get('/<int:loan_id>')
def detail(loan_id):
    loan=get(loan_id)
    customer=decoded(loan['customer_snapshot'],{});customer=customer if isinstance(customer,dict) else {}
    if live.enabled() and loan['cust_id']:
        try:customer=live.master.get(loan['cust_id'])['customer']
        except BusinessError:pass
    items=db.all('SELECT * FROM cd_loan_items WHERE loan_id=%s ORDER BY line_no',(loan_id,))
    logs=db.all('SELECT l.*,s.name operation_name FROM cd_loan_logs l LEFT JOIN pawn_status s ON s.id=l.operation_id WHERE loan_id=%s ORDER BY l.id',(loan_id,))
    for log in logs:
        if log['operation_id']==7 and decoded(log['terms_json'],{}).get('lost_photo'):log['lost_photo_url']=url_for('live.lost_photo',log_id=log['id'])
    payments=db.all('SELECT p.*,l.legacy_log_id FROM cd_payments p JOIN cd_loan_logs l ON l.id=p.log_id WHERE l.loan_id=%s ORDER BY l.id,p.id',(loan_id,))
    for p in payments:
        p['bank']=decoded(p['bank_snapshot'],{})
        if isinstance(p['bank'],dict):
            if p['bank'].pop('qr_image',None):p['qr_url']=url_for('live.session_qr',log_id=p['log_id'])
            p['bank'].pop('qr_mime',None)
        if not isinstance(p['bank'],dict):p['bank']={'Dữ liệu cần kiểm tra':str(p['bank'])}
    exceptions=C.stored_exceptions(loan)
    legacy=decoded(loan['legacy_json'],{}).get('pawn',{})
    legacy_descriptions=[legacy.get('mota'+str(i)) for i in (1,2) if legacy.get('mota'+str(i))]
    return render_template('loan_detail.html',title=loan['sku']+' · Biên nhận',loan=loan,customer=customer,items=items,logs=logs,payments=payments,photos=images.inventory(loan),labels=C.LABEL,exceptions=exceptions,legacy_descriptions=legacy_descriptions)

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
