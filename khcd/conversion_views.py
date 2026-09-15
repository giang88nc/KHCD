from flask import Blueprint, request, g
from . import db, loan_conversion as C
from .domain import BusinessError

bp=Blueprint('conversion',__name__,url_prefix='/camdo/phieu-cam-do/chuyen-doi')


@bp.get('/dang-cam')
def active_list():
    if not C.ready():return {'error':'Chưa có đủ bốn bảng SQL mới để chuyển đổi.'},409
    after=max(0,request.args.get('after',0,type=int) or 0)
    ceiling=request.args.get('ceiling',type=int)
    if ceiling is None:ceiling=db.one('SELECT COALESCE(MAX(id),0) n FROM pawn')['n']
    ceiling=max(0,ceiling)
    total=db.one('SELECT COUNT(*) n FROM pawn WHERE status IN (1,2,3,4,7) AND id<=%s',(ceiling,))['n']
    rows=db.all('''SELECT p.id,p.sku,p.phone,p.value,p.date1,p.date3,p.status,
        c.pmv_cust_id cust_id,l.id loan_id
        FROM pawn p LEFT JOIN khcd_pawn_customer c ON c.pawn_id=p.id
        LEFT JOIN cd_loans l ON l.legacy_pawn_id=p.id
        WHERE p.status IN (1,2,3,4,7) AND p.id>%s AND p.id<=%s ORDER BY p.id LIMIT 201''',(after,ceiling))
    more=len(rows)>200;rows=rows[:200]
    for row in rows:
        row['value']=str(row['value'])
        for field in ('date1','date3'):row[field]=row[field].isoformat() if row[field] else None
    return {'rows':rows,'total':total,'ceiling':ceiling,'next_after':rows[-1]['id'] if more else None}


@bp.post('/hang-loat/luu-phieu')
def batch_save():
    # One atomic receipt per request: failures never undo earlier completed receipts.
    # A browser queue limits load and may stop between receipts without a worker/table.
    try:
        pid=request.form.get('pid',type=int)
        if not pid or request.form.get('confirmed')!='yes':raise BusinessError('Cần xác nhận các phiếu đã chọn trước khi chuyển hàng loạt.')
        loan_id=C.convert(pid,request.form.get('review_hash',''),active_only=True,allow_exceptions=request.form.get('allow_exceptions')=='yes')
        return {'loan_id':loan_id,'message':'Đã chuyển và đọc kiểm thành công.'}
    except BusinessError as exc:return {'error':str(exc)},409


@bp.before_request
def admin_only():
    if not getattr(g,'auth_user',None) or not g.auth_user['is_superuser']:
        return {'error':'Chỉ quản trị viên được đối soát và chuyển dữ liệu.'},403


@bp.get('/doi-soat')
def preview():
    try:
        pid=request.args.get('pid',type=int)
        if not pid:
            q=request.args.get('q','').strip()
            if not q or len(q)>255:raise BusinessError('Nhập mã biên nhận chính xác.')
            rows=db.all('SELECT id FROM pawn WHERE sku=%s LIMIT 2',(q,))
            if len(rows)!=1:raise BusinessError('Không tìm thấy mã phiếu duy nhất. Kiểm tra mã hoặc dữ liệu trùng.')
            pid=rows[0]['id']
        p=C.inspect(pid,allow_exceptions=request.args.get('allow_exceptions')=='yes')
        return dict(pid=pid,loan_state=p['loan']['loan_state'],**{k:p[k] for k in ('summary','checks','source_hash','review_hash','converted','loan_id','can_convert','exception_policy')})
    except BusinessError as exc:return {'error':str(exc)},400


@bp.post('/luu')
def save():
    try:
        pid=request.form.get('pid',type=int)
        if not pid or request.form.get('confirmed')!='yes':raise BusinessError('Cần đối soát và xác nhận từng phiếu trước khi chuyển.')
        loan_id=C.convert(pid,request.form.get('review_hash',''),allow_exceptions=request.form.get('allow_exceptions')=='yes')
        return {'loan_id':loan_id,'message':'Đã chuyển và đọc kiểm thành công. Nguồn vận hành vẫn là pawn; cd_loans đang chờ tiếp quản.'}
    except BusinessError as exc:return {'error':str(exc)},409
