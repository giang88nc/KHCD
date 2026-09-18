from . import live_loans as live
import secrets
import time
import threading
from datetime import timedelta
from decimal import Decimal
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, abort, current_app, Response
from . import db, services as svc, auth
from .domain import today, now, date_range, BusinessError, quote, parse_date, EVENTS
from . import pmv_customers as pmv, customer_compare as compare
from . import customer_master as master

bp=Blueprint('web',__name__)
attempts={}
attempt_lock=threading.Lock()

@bp.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        address=request.remote_addr
        stamp=time.monotonic()
        with attempt_lock:
            history=[t for t in attempts.get(address,[]) if stamp-t<300]
            if len(history)>=5:
                return render_template('login.html',error='Đã thử quá nhiều lần. Vui lòng đợi 5 phút.'),429
            attempts[address]=history+[stamp]
        username=request.form.get('username','').strip()
        password=request.form.get('password','')
        user=auth.authenticate(username,password) if 0<len(username)<=150 and 0<len(password)<=4096 else None
        if user:
            with attempt_lock: attempts.pop(address,None)
            auth.establish_session(user)
            return redirect(url_for('web.dashboard'))
        return render_template('login.html',error='Tài khoản hoặc mật khẩu không đúng.'),401
    return render_template('login.html')

@bp.post('/logout')
def logout():
    session.clear()
    return redirect(url_for('web.login'))

@bp.get('/health')
def health():
    service='ok'
    if master.enabled() and not current_app.testing:
        from urllib.request import urlopen
        import json
        try:
            with urlopen('http://127.0.0.1:18202/health',timeout=2) as reply:
                info=json.load(reply)
            if info.get('app')!='KHBL Customer Bridge' or info.get('target')!='kk':service='unavailable'
        except Exception:service='unavailable'
    return {'status':'ok','app':'KHCD','https':request.is_secure,'customer_service':service,'loan_store':'cd_loans' if live.enabled() else 'pawn'}

def paging():
    try: return max(1,min(100000,int(request.args.get('page','1'))))
    except ValueError: return 1

@bp.get('/')
@bp.get('/camdo')
def dashboard():
    if live.enabled():return live.dashboard()
    start,end,exclusive=date_range(request.args)
    metrics=db.one('''SELECT COUNT(*) count,COALESCE(SUM(value),0) principal,
        SUM(CASE WHEN date3 < %s THEN 1 ELSE 0 END) overdue,
        SUM(CASE WHEN date3 >= %s AND date3 < %s THEN 1 ELSE 0 END) due
        FROM pawn WHERE status IN (1,2,3,4,7)''',(today(),today(),today()+timedelta(days=4)))
    flow=db.one('''SELECT COUNT(*) count, COALESCE(SUM(CASE WHEN status_id IN (2,3,4,5,6) THEN tienlai ELSE 0 END),0) interest,
        COALESCE(SUM(GREATEST(-(COALESCE(total,0)+COALESCE(mbank,0)),0)),0) disbursed,
        COALESCE(SUM(GREATEST(COALESCE(total,0)+COALESCE(mbank,0),0)),0) received,
        SUM(status_id=1) new_count, SUM(status_id=5) redeemed_count, SUM(status_id=4) renew_count
        FROM pawn_log WHERE COALESCE(date2,date1)>=%s AND COALESCE(date2,date1)<%s''',(start,exclusive))
    urgent=db.all(svc.pawn_select()+' WHERE p.status IN (1,2,3,4,7) AND p.date3<%s ORDER BY p.date3 LIMIT 6',(today()+timedelta(days=4),))
    if master.enabled():
        master.hydrate(urgent)
        recent=db.all('SELECT l.*,p.sku,k.pmv_cust_id FROM pawn_log l LEFT JOIN pawn p ON p.id=l.pawn_id LEFT JOIN khcd_pawn_customer k ON k.pawn_id=p.id WHERE COALESCE(l.date2,l.date1)>=%s AND COALESCE(l.date2,l.date1)<%s ORDER BY COALESCE(l.date2,l.date1) DESC,l.id DESC LIMIT 6',(start,exclusive))
        master.hydrate(recent)
    else:
        recent=db.all('''SELECT l.*,p.sku,c.name customer_name FROM pawn_log l LEFT JOIN pawn p ON p.id=l.pawn_id
            LEFT JOIN (SELECT phone,MIN(id) id FROM customer GROUP BY phone) cm ON cm.phone=p.phone
            LEFT JOIN customer c ON c.id=cm.id
            WHERE COALESCE(l.date2,l.date1)>=%s AND COALESCE(l.date2,l.date1)<%s ORDER BY COALESCE(l.date2,l.date1) DESC,l.id DESC LIMIT 6''',(start,exclusive))
    chart_start=end-timedelta(days=13)
    chart_rows=db.all('''SELECT DATE(COALESCE(date2,date1)) day,
        SUM(GREATEST(COALESCE(total,0)+COALESCE(mbank,0),0)) income,
        SUM(GREATEST(-(COALESCE(total,0)+COALESCE(mbank,0)),0)) expense
        FROM pawn_log WHERE COALESCE(date2,date1)>=%s AND COALESCE(date2,date1)<%s GROUP BY day''',(chart_start,exclusive))
    values={r['day']:r for r in chart_rows}
    chart=[values.get(chart_start+timedelta(days=i),dict(day=chart_start+timedelta(days=i),income=0,expense=0)) for i in range(14)]
    peak=max([float(max(x['income'],x['expense'])) for x in chart]+[1])
    for row in chart:
        row['ih']=round(float(row['income'])/peak*125,2);row['eh']=round(float(row['expense'])/peak*125,2)
    portfolio=db.all('SELECT status,COUNT(*) count FROM pawn WHERE status IN (1,2,3,4,7) GROUP BY status')
    return render_template('dashboard.html',title='Tổng quan',metrics=metrics,flow=flow,urgent=urgent,recent=recent,chart=chart,portfolio=portfolio,start=start,end=end)

@bp.get('/camdo/phieu-cam-do')
def pawns():
    q=request.args.get('q','').strip()[:100];state=request.args.get('status','active');page=paging()
    where=[];params=[]
    if q:
        if master.enabled():
            ids=master.call('search_ids',q=q)['ids']
            where.append('(p.sku LIKE %s OR p.phone LIKE %s'+(' OR k.pmv_cust_id IN ('+','.join(['%s']*len(ids))+')' if ids else '')+')');params.extend(['%'+q+'%']*2+ids)
        else:
            where.append('(p.sku LIKE %s OR p.phone LIKE %s OR c.name LIKE %s)');params.extend(['%'+q+'%']*3)
    states={'active':'p.status IN (1,2,3,4,7)','overdue':'p.status IN (1,2,3,4,7) AND p.date3<CURDATE()',
        'due':'p.status IN (1,2,3,4,7) AND p.date3>=CURDATE() AND p.date3<DATE_ADD(CURDATE(),INTERVAL 4 DAY)',
        'redeemed':'p.status=5','cancelled':'p.status=0','liquidated':'p.status=6','all':'1=1'}
    if master.enabled():states['unlinked']='k.pmv_cust_id IS NULL'
    where.append(states.get(state,states['active']))
    sql=svc.pawn_select()+' WHERE '+' AND '.join(where)
    count=db.one('SELECT COUNT(*) n FROM ('+sql+') t',params)['n']
    rows=db.all(sql+' ORDER BY p.id DESC LIMIT 20 OFFSET %s',params+[(page-1)*20])
    if master.enabled():master.hydrate(rows)
    svc.desk.hydrate_summaries(rows)
    return render_template('pawns.html',title='Phiếu cầm đồ',rows=rows,q=q,state=state,total=count,page=page,pages=max(1,(count+19)//20))

def entry_customers(q='', selection=''):
    if master.enabled():
        if selection:
            row=master.get(selection)['customer'];return [row] if row else []
        return master.listing(q)['rows']
    where='(name LIKE %s OR phone LIKE %s OR cccd LIKE %s)' if q else '1=1'
    params=['%'+q+'%']*3 if q else []
    if str(selection).isdigit(): where='id=%s';params=[selection]
    if db.schema_ready(): where+=' AND NOT EXISTS (SELECT 1 FROM khcd_customer_meta m WHERE m.customer_id=customer.id AND m.archived=1)'
    return db.all('SELECT id,name,phone,cccd,addr FROM customer WHERE '+where+' ORDER BY id DESC LIMIT 30',params)


@bp.route('/camdo/lap-phieu/khach-hang',methods=['GET','POST'])
def entry_customer():
    from .customer_lookup import lookup_key
    try:q=lookup_key(request.args.get('q',''))
    except BusinessError as exc:return {'error':str(exc)},400
    if master.enabled():
        try:
            if request.method=='GET' and request.args.get('id'):
                cid=request.args['id'];result=master.get(cid)
                if not result['customer']:return {'error':'Không tìm thấy khách KK.'},404
                return {'customer':result['customer'],
                    'photos':{name:url_for('customer_popup.api',path=f'banle/khach-hang/{cid}/anh/{kind}/')
                              for name,kind in [('anh_truoc','mat-truoc'),('anh_sau','mat-sau')]}}
            if request.method=='POST':
                db.require_write()
                result=master.call('save',form=dict(request.form),token=request.form.get('save_token',''),version=request.form.get('version',''))
                if result.get('complete') is not True:
                    return {'error':'\n'.join(result.get('errors',[])),'cust_id':result.get('cust_id'),'uncertain':result.get('uncertain',False),'partial':result.get('partial',False)},409
                return {'customer':master.get(result['cust_id'])['customer'],'token':secrets.token_urlsafe(24)},201
            return {'customers':entry_customers(q)}
        except BusinessError as error:return {'error':str(error)},503
    if request.method=='POST':
        try:
            cid=svc.save_customer(request.form)
        except BusinessError as error:
            return {'error':str(error)},400
        return {'customer':entry_customers(selection=str(cid))[0]},201
    return {'customers':entry_customers(q)}


@bp.route('/camdo/lap-phieu',methods=['GET','POST'])
def pawn_new():
    error=None
    data=request.form if request.method=='POST' else {}
    if request.method=='POST':
        try:
            pid=live.create(request.form,request.files) if live.enabled() else svc.create_pawn(request.form,request.files)
        except BusinessError as exc:
            error=str(exc)
            if request.accept_mimetypes.best=='application/json':return {'error':error},400
        else:
            if live.enabled():
                result={'url':url_for('loans.detail',loan_id=pid),'sku':live.loan(pid)['sku']}
                return (result,201) if request.accept_mimetypes.best=='application/json' else redirect(result['url'])
            if request.accept_mimetypes.best=='application/json':return {'url':url_for('web.pawn_detail',pid=pid),'sku':db.one('SELECT sku FROM pawn WHERE id=%s',(pid,))['sku']},201
            flash('Đã lập phiếu và ghi nhận tiền giao khách.','success')
            return redirect(url_for('web.pawn_detail',pid=pid))
    q=request.args.get('customer_q','').strip()[:100]
    selection=data.get('customer_id',request.args.get('customer_id',''))
    try:customers=entry_customers(q,selection) if selection else []
    except master.Unavailable as exc:
        error=str(exc);customers=[dict(id=selection,name='Chưa đọc được hồ sơ KK',phone='',cccd='',addr='')] if selection else []
    if selection and customers:q=customers[0]['name']
    day_end=today()+timedelta(days=1)
    if live.enabled():
        daily=db.one('SELECT COUNT(*) count,COALESCE(SUM(principal_change),0) principal FROM cd_loan_logs WHERE operation_id=1 AND happened_at>=%s AND happened_at<%s',(today(),day_end))
        recent=[]
    else:
        daily=db.one('SELECT COUNT(*) count,COALESCE(SUM(sotien),0) principal FROM pawn_log WHERE status_id=1 AND date1>=%s AND date1<%s',(today(),day_end))
        recent=[]
    employees=[]
    if master.enabled():
        try:employees=master.employees()
        except master.Unavailable as exc:error=error or str(exc)
    actions=db.all('SELECT id,name,sort FROM pawn_status ORDER BY sort,id')
    safes=[]
    return render_template('pawn_form.html',title='Cầm đồ · Lập phiếu',customers=customers,golds=svc.gold_options(),customer_q=q,selected=selection,
        key=data.get('request_key') or secrets.token_urlsafe(24),form=data,error=error,daily=daily,recent=recent,master_kk=master.enabled(),employees=employees,actions=actions,safes=safes,customer_token=secrets.token_urlsafe(24)),400 if error else 200


@bp.get('/camdo/lap-phieu/phien-giao-dich')
def desk_sessions():
    if live.enabled():return live.sessions(request.args)
    from .desk_sessions import listing
    try:return listing(request.args)
    except master.Unavailable as exc:return {'error':str(exc)},503
    except BusinessError as exc:return {'error':str(exc)},400


@bp.get('/camdo/lap-phieu/tra-phieu')
def desk_receipt():
    if live.enabled():return live.receipt(request.args.get('q',''))
    try:
        field,value=svc.desk.receipt_key(request.args.get('q'),request.host.split(':')[0])
        matches=db.all('SELECT id FROM pawn WHERE '+field+'=%s LIMIT 2',(value,))
        if not matches:return {'error':'Không tìm thấy biên nhận khớp mã đã quét.'},404
        if len(matches)!=1:return {'error':'Mã biên nhận bị trùng; cần đối soát trước khi mở.'},409
        p=svc.pawn(matches[0]['id'])
        result=svc.desk.receipt_data(p,lambda pid,kind:url_for('web.pawn_photo',pid=pid,kind=kind))
        if p.get('pmv_cust_id'):
            for name,kind in [('anh_truoc','mat-truoc'),('anh_sau','mat-sau')]:
                result['photos'].setdefault(name,url_for('customer_popup.api',path=f"banle/khach-hang/{p['pmv_cust_id']}/anh/{kind}/"))
        result['detail_url']=url_for('web.pawn_detail',pid=p['id'])
        result['fingerprint']=p['fingerprint']
        result['cancellation']=svc.cancellation_state(p)
        return result
    except BusinessError as exc:return {'error':str(exc)},400


@bp.post('/camdo/lap-phieu/huy-phien')
def desk_cancel():
    try:
        pid=request.form.get('pid',type=int)
        if not pid:raise BusinessError('Thiếu mã phiếu.')
        if live.enabled():
            result=live.process(pid,0,request.form) or {}
            from . import sms;sms.sau_giao_dich(pid)   # hủy phiên cũng đổi mốc chu kỳ nhắc
            return dict(message='Đã xóa toàn bộ phiếu cầm mới.' if result.get('deleted_loan') else 'Đã xóa phiên, khôi phục phiếu trước giao dịch.',**result)
        if request.form.get('returned_funds')!='yes':raise BusinessError('Xác nhận đã thu hồi đủ tiền trước khi hủy phiên.')
        svc.process_pawn(pid,request.form,'cancel')
        return {'message':'Đã hủy phiên, ghi hoàn tiền và giữ lịch sử đối soát.'}
    except BusinessError as exc:return {'error':str(exc)},409


@bp.post('/camdo/lap-phieu/doc-qr')
def desk_qr():
    import base64
    try:
        kind=request.form.get('kind')
        if kind not in ('bank','receipt'):raise BusinessError('Loại mã quét không hợp lệ.')
        file=request.files.get('image');encoded=''
        if file:
            raw=file.read(15*1024*1024+1)
            if len(raw)>15*1024*1024:raise BusinessError('Ảnh QR tối đa 15 MB.')
            encoded=base64.b64encode(raw).decode('ascii')
        return master.call('pawn_qr',kind=kind,text=request.form.get('text',''),image=encoded)
    except BusinessError as exc:return {'error':str(exc)},400


@bp.get('/camdo/lap-phieu/tai-khoan-thu')
def desk_banks():
    try:return master.call('pawn_banks')
    except BusinessError as exc:return {'error':str(exc)},503


@bp.get('/camdo/phieu-cam-do/<int:pid>/anh/<kind>')
def pawn_photo(pid,kind):
    if kind not in svc.desk.PHOTO_NAMES:abort(404)
    row=db.one('SELECT data FROM khcd_pawn_photo WHERE pawn_id=%s AND kind=%s',(pid,kind))
    if not row:abort(404)
    return Response(row['data'],content_type='image/jpeg')

@bp.get('/camdo/phieu-cam-do/<int:pid>')
def pawn_detail(pid):
    p=svc.pawn(pid)
    if not p: abort(404)
    logs=db.all('SELECT l.*,s.name status_name FROM pawn_log l LEFT JOIN pawn_status s ON s.id=l.status_id WHERE pawn_id=%s ORDER BY l.id DESC',(pid,))
    calc=None;quote_error=None
    if p['active']:
        try:
            minimum=current_app.config['MIN_INTEREST_DAYS']
            paid_today=any(l['status_id']==4 and parse_date(l['date2'])==today() for l in logs if l['date2'])
            calc=quote(p,today(),0 if paid_today else minimum)
        except BusinessError as e: quote_error=str(e)
    audit=db.all('SELECT kind,actor,created_at,note FROM khcd_event WHERE pawn_id=%s ORDER BY id DESC',(pid,)) if db.schema_ready() else []
    new_due=max(today(),parse_date(p['date3'] or today()))+timedelta(days=30)
    return render_template('pawn_detail.html',title=p['sku'],p=p,logs=logs,calc=calc,quote_error=quote_error,new_due=new_due,audit=audit,key=secrets.token_urlsafe(24))

@bp.post('/camdo/phieu-cam-do/<int:pid>/<action>')
def pawn_action(pid,action):
    if live.enabled():raise BusinessError('Phiếu cũ chỉ để xem. Mở biên nhận SQL mới để giao dịch.')
    svc.process_pawn(pid,request.form,action)
    flash('Đã ghi nhận '+EVENTS.get(action,'thao tác').lower()+'.','success')
    return redirect(url_for('web.pawn_detail',pid=pid))

@bp.get('/camdo/khach-hang')
def customers():
    if master.enabled():
        q=request.args.get('q','').strip()[:100];page=paging();error=None
        try:result=master.listing(q,page)
        except master.Unavailable as exc:result={'rows':[],'total':None,'can_edit':False};error=str(exc)
        return render_template('customers_kk.html',title='Khách hàng KK',q=q,page=page,
            pages=max(1,((result['total'] or 0)+19)//20),error=error,**result)
    q=request.args.get('q','').strip()[:100];page=paging();archived=request.args.get('archived')=='1'
    source='pmv' if request.args.get('tab')=='pmv' else 'cd'
    source_error=None
    if source=='pmv':
        try: rows,total=pmv.listing(q,page)
        except pmv.Unavailable as error:rows=[];total=None;source_error=str(error)
        local=compare.local_directory() if rows else []
        for row in rows:
            matches=compare.candidates(row,local)
            row['match']=compare.status(row,matches)
        return render_template('customers.html',title='Khách PMV',source=source,source_error=source_error,
            rows=rows,q=q,total=total,page=page,pages=max(1,((total or 0)+19)//20),archived=False)
    where='(c.name LIKE %s OR c.phone LIKE %s OR c.cccd LIKE %s)';params=['%'+q+'%']*3
    if db.schema_ready():
        where+=(' AND ' if archived else ' AND NOT ')+'EXISTS (SELECT 1 FROM khcd_customer_meta m WHERE m.customer_id=c.id AND m.archived=1)'
    total=db.one('SELECT COUNT(*) n FROM customer c WHERE '+where,params)['n']
    rows=db.all('''SELECT c.id,c.name,c.phone,c.cccd,c.addr,c.created,
        (SELECT COUNT(*) FROM pawn p WHERE p.phone=c.phone AND p.status IN (1,2,3,4,7)) active_count,
        (SELECT COALESCE(SUM(value),0) FROM pawn p WHERE p.phone=c.phone AND p.status IN (1,2,3,4,7)) principal
        FROM customer c WHERE '''+where+' ORDER BY c.id DESC LIMIT 20 OFFSET %s',params+[(page-1)*20])
    try: counterparts=pmv.find_candidates(rows) if rows else []
    except pmv.Unavailable as error:counterparts=[];source_error=str(error)
    for row in rows:
        row['match']={'key':'unavailable','label':'Chưa đối chiếu','tone':'neutral','count':None} if source_error else compare.status(row,compare.candidates(row,counterparts))
    return render_template('customers.html',title='Khách hàng',rows=rows,q=q,total=total,page=page,pages=max(1,(total+19)//20),archived=archived,source=source,source_error=source_error)


@bp.get('/camdo/khach-hang/doi-chieu')
def customer_comparison():
    if master.enabled():return redirect(url_for('web.customers'))
    source='pmv' if request.args.get('tab')=='pmv' else 'cd'
    cd_id=request.args.get('cd_id','');pmv_id=request.args.get('pmv_id','').strip()[:100]
    cd=None;remote=None;matches=[];source_error=None
    if source=='cd':
        if not cd_id.isdigit():abort(404)
        cd=db.one('SELECT id,name,phone,cccd,addr FROM customer WHERE id=%s',(cd_id,))
        if not cd:abort(404)
        try:matches=compare.candidates(cd,pmv.find_candidates([cd]))
        except pmv.Unavailable as error:source_error=str(error)
        if pmv_id and not source_error:
            remote=next((row for row in matches if str(row['id'])==pmv_id),None)
            if not remote:abort(404)
        elif len(matches)==1:remote=matches[0]
        base=cd
    else:
        if not pmv_id:abort(404)
        try:remote=pmv.get(pmv_id)
        except pmv.Unavailable as error:source_error=str(error)
        if not remote and not source_error:abort(404)
        matches=compare.candidates(remote,compare.local_directory()) if remote else []
        if cd_id and not source_error:
            cd=next((row for row in matches if str(row['id'])==cd_id),None)
            if not cd:abort(404)
        elif len(matches)==1:cd=matches[0]
        base=remote
    result=compare.status(base,matches) if base and not source_error else {'key':'unavailable','label':'Chưa đối chiếu','tone':'neutral','count':None}
    affected=db.one('SELECT COUNT(*) total,SUM(status IN (1,2,3,4,7)) active FROM pawn WHERE phone=%s',(cd['phone'],)) if cd else None
    return render_template('customer_comparison.html',title='So sánh khách hàng',source=source,source_error=source_error,
        cd=cd,pmv=remote,base=base,matches=matches,result=result,affected=affected,
        fields=compare.comparison(cd,remote) if cd and remote else [],q=request.args.get('q','')[:100])

@bp.route('/camdo/khach-hang/moi',methods=['GET','POST'])
@bp.route('/camdo/khach-hang/<int:cid>',methods=['GET','POST'])
def customer_form(cid=None):
    if master.enabled():
        if cid:
            # An old numeric URL is a local customer ID, never a PMV CustID.
            linked=db.all('SELECT DISTINCT k.pmv_cust_id FROM khcd_pawn_customer k JOIN pawn p ON p.id=k.pawn_id JOIN customer c ON c.phone=p.phone WHERE c.id=%s',(cid,))
            if len(linked)!=1:raise BusinessError('Hồ sơ cũ chưa có một liên kết KK duy nhất. Tìm khách bằng mã KK trong danh sách.')
            return redirect(url_for('web.customer_kk_form',cust_id=linked[0]['pmv_cust_id']))
        return customer_kk_form()
    if request.method=='POST':
        cid=svc.save_customer(request.form,cid)
        flash('Đã lưu hồ sơ khách hàng.','success')
        return redirect(url_for('web.customer_form',cid=cid))
    c=db.one('SELECT id,name,phone,cccd,addr,note,bday,created FROM customer WHERE id=%s',(cid,)) if cid else {}
    if cid and not c: abort(404)
    history=db.all('SELECT id,sku,value,status,date1 FROM pawn WHERE phone=%s ORDER BY id DESC LIMIT 30',(c['phone'],)) if cid else []
    archived=db.one('SELECT archived FROM khcd_customer_meta WHERE customer_id=%s',(cid,)) if cid and db.schema_ready() else None
    return render_template('customer_form.html',title='Hồ sơ khách hàng' if cid else 'Thêm khách hàng',c=c,history=history,archived=bool(archived and archived['archived']))


@bp.route('/camdo/khach-hang/kk/<cust_id>',methods=['GET','POST'])
def customer_kk_form(cust_id=None):
    if not master.enabled():abort(404)
    error=None;pending=False;saved_id=None
    try:
        result=master.get(cust_id) if cust_id else {'customer':None,'form':{'NoiCap':'Cục Cảnh Sát QLHC về TTXH','Active':'1'},'version':'','can_edit':True}
    except master.Unavailable:
        if request.method!='POST':raise
        result={'customer':{'id':cust_id,'name':'Hồ sơ khách KK'},'form':{},'version':'','can_edit':False}
    if cust_id and not result['customer']:abort(404)
    values=result['form'];token=secrets.token_urlsafe(24);version=result['version']
    if request.method=='POST':
        values=dict(request.form);values['CustID']=cust_id or ''
        token=request.form.get('save_token','');version=request.form.get('version','')
        try:
            db.require_write()
            saved=master.call('save',form={k:v for k,v in values.items() if k not in ('csrf_token','save_token','version')},token=token,version=version)
            if saved.get('complete') is True:
                flash('Đã lưu khách vào KK và kiểm tra hoàn tất.','success')
                return redirect(url_for('web.customer_kk_form',cust_id=saved['cust_id']))
            error='\n'.join(saved.get('errors',[]));pending=bool(saved.get('uncertain') or saved.get('partial'));saved_id=saved.get('cust_id')
        except BusinessError as exc:error=str(exc);pending=True
    return render_template('customer_kk_form.html',title='Hồ sơ khách KK',c=result['customer'],values=values,
        can_edit=result['can_edit'],error=error,pending=pending,saved_id=saved_id,token=token,version=version,
        history=master.history(cust_id) if cust_id else [])


@bp.get('/camdo/khach-hang/ket-qua/<token>')
def customer_save_result(token):
    if not master.enabled() or len(token)>80:abort(404)
    result=master.call('receipt',token=token)
    if result.get('complete') is True:
        flash('Đã kiểm tra: yêu cầu lưu khách hoàn tất.','success')
        return redirect(url_for('web.customer_kk_form',cust_id=result['cust_id']))
    return render_template('customer_save_result.html',title='Kết quả lưu khách',result=result,token=token)

@bp.post('/camdo/khach-hang/<int:cid>/luu-tru')
def customer_archive(cid):
    svc.archive_customer(cid,svc.required(request.form,'reason','Lý do lưu trữ'))
    flash('Đã lưu trữ khách hàng; lịch sử phiếu được giữ lại.','success')
    return redirect(url_for('web.customers'))

@bp.post('/camdo/khach-hang/<int:cid>/khoi-phuc')
def customer_restore(cid):
    svc.restore_customer(cid)
    flash('Đã khôi phục khách hàng vào danh sách đang sử dụng.','success')
    return redirect(url_for('web.customer_form',cid=cid))

@bp.get('/camdo/thong-ke')
def reports():
    if live.enabled():return live.report()
    start,end,exclusive=date_range(request.args);page=paging();kind=request.args.get('kind','all')
    tab=request.args.get('tab','transactions')
    if tab=='audit':
        if db.schema_ready():
            sql='FROM khcd_event e LEFT JOIN pawn p ON p.id=e.pawn_id WHERE e.created_at>=%s AND e.created_at<%s';params=[start,exclusive]
            total=db.one('SELECT COUNT(*) n '+sql,params)['n']
            rows=db.all('SELECT e.*,p.sku '+sql+' ORDER BY e.id DESC LIMIT 30 OFFSET %s',params+[(page-1)*30])
        else: total=0;rows=[]
        sums={}
    else:
        sql='FROM pawn_log l LEFT JOIN pawn p ON p.id=l.pawn_id WHERE COALESCE(l.date2,l.date1)>=%s AND COALESCE(l.date2,l.date1)<%s';params=[start,exclusive]
        if kind in ('0','1','2','3','4','5','6','7'):
            sql+=' AND l.status_id=%s';params.append(int(kind))
        sums=db.one('''SELECT COUNT(*) n,COALESCE(SUM(COALESCE(l.total,0)+COALESCE(l.mbank,0)),0) net,
            COALESCE(SUM(CASE WHEN l.status_id IN (2,3,4,5,6) THEN l.tienlai ELSE 0 END),0) interest '''+sql,params)
        total=sums['n']
        rows=db.all('SELECT l.*,p.sku,COALESCE(l.date2,l.date1) happened '+sql+' ORDER BY happened DESC,l.id DESC LIMIT 30 OFFSET %s',params+[(page-1)*30])
    return render_template('reports.html',title='Thống kê',start=start,end=end,tab=tab,kind=kind,rows=rows,total=total,sums=sums,page=page,pages=max(1,(total+29)//30))
