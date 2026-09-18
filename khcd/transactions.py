"""Trang GIAO DỊCH: liệt kê phiên trong cd_loan_logs (mọi biên nhận) + popup chi tiết một phiên. Chỉ đọc.

Dữ liệu danh sách dùng chung live.sessions() với Tổng quan / Thống kê — một câu SQL (LOG_SQL), một cách tính
tiền mặt / chuyển khoản cho cả ba trang. Popup đọc lại đúng phiên đó kèm dòng tiền và biên nhận liên quan."""
import json
from decimal import Decimal
from flask import Blueprint,render_template,request,abort,url_for
from . import db,live_loans as live,loan_conversion as C
from .domain import BusinessError,today
from .loans import decoded,decorate,stamp

bp=Blueprint('giaodich',__name__,url_prefix='/camdo/giao-dich')

# Màu badge theo nghiệp vụ: tiền RA tiệm (cầm) = ruby, tiền VÀO (chuộc/trả bớt) = xanh, gia hạn = vàng, hủy/thanh lý = xám.
OP_CLASS={1:'op-out',2:'op-out',3:'op-in',5:'op-in',4:'op-renew',6:'op-neutral',7:'op-danger',8:'op-neutral',0:'op-cancel'}

def when(value):
    s=str(value or '')
    return s[8:10]+'/'+s[5:7]+'/'+s[0:4]+' '+s[11:16] if len(s)>=16 else (s or '—')

@bp.get('')
def listing():
    available=live.enabled() and C.ready()
    data=dict(rows=[],groups=[],totals=dict(received='0',paid='0',interest='0'),total=0,page=1,pages=1,
              d1=str(today()),d2=str(today()),q='')
    kind=request.args.get('kind','')
    if kind not in map(str,live.OPS):kind=''
    if available:
        args=dict(d1=request.args.get('d1') or str(today()),d2=request.args.get('d2') or str(today()),
                  q=request.args.get('q',''),kind=kind,page=request.args.get('page','1'))
        data=live.sessions(args)
        for r in data['rows']:
            r['when']=when(r['happened_at']);r['op_class']=OP_CLASS.get(r['operation_id'],'op-neutral')
            r['net_value']=Decimal(r['net'])
    counts={g['status_id']:g['count'] for g in data['groups']}
    chips=[(str(k),v,counts.get(k,0)) for k,v in live.OPS.items() if k!=8]
    filters=dict(q=data['q'],kind=kind,d1=data['d1'],d2=data['d2'])
    return render_template('transactions.html',title='Giao dịch',data=data,filters=filters,chips=chips,ops=live.OPS,
                           available=available,is_today=(data['d1']==data['d2']==str(today())))

def context(log_id):
    log=db.one(live.LOG_SQL+' WHERE l.id=%s',(log_id,))
    if not log:abort(404)
    loan=db.one('SELECT * FROM cd_loans WHERE id=%s',(log['loan_id'],));decorate(loan)
    customer=decoded(loan['customer_snapshot'],{});customer=customer if isinstance(customer,dict) else {}
    customer_live=False
    if loan['cust_id']:
        try:customer=live.master.get(loan['cust_id'])['customer'];customer_live=True
        except BusinessError:pass
    log['operation']=live.OPS.get(log['operation_id'],'Khác');log['op_class']=OP_CLASS.get(log['operation_id'],'op-neutral')
    log['when']=stamp(log['happened_at']);log['net']=log['cash']+log['bank']
    terms=decoded(log['terms_json'],{});terms=terms if isinstance(terms,dict) else {}
    before=terms.get('before') if isinstance(terms.get('before'),dict) else {}
    after=terms.get('after') if isinstance(terms.get('after'),dict) else {}
    # Chỉ hiện các mốc đổi trên biên nhận sau phiên (phiên nguồn cũ không có before/after → trống).
    changes=[]
    for key,label in [('principal_balance','Dư gốc'),('monthly_rate','Lãi suất %'),('interest_from','Mốc tính lãi'),('due_at','Hẹn chuộc'),('loan_state','Trạng thái'),('receipt_lost','Mất biên nhận')]:
        a,b=before.get(key),after.get(key)
        if a is None and b is None:continue
        if key=='loan_state':a,b=C.LABEL.get(a,a),C.LABEL.get(b,b)
        if key=='receipt_lost':a,b=('Có' if a else 'Không'),('Có' if b else 'Không')
        if key in ('principal_balance',):a,b=(f'{Decimal(str(a or 0)):,.0f}'.replace(',','.') if a is not None else '—'),(f'{Decimal(str(b or 0)):,.0f}'.replace(',','.') if b is not None else '—')
        if key=='monthly_rate':a,b=(format(Decimal(str(a)),'f').rstrip('0').rstrip('.') if a is not None else '—'),(format(Decimal(str(b)),'f').rstrip('0').rstrip('.') if b is not None else '—')
        if key in ('interest_from','due_at'):a,b=(str(a)[8:10]+'/'+str(a)[5:7]+'/'+str(a)[:4] if a else '—'),(str(b)[8:10]+'/'+str(b)[5:7]+'/'+str(b)[:4] if b else '—')
        changes.append(dict(label=label,before=a,after=b,changed=str(a)!=str(b)))
    payments=db.all('SELECT * FROM cd_payments WHERE log_id=%s ORDER BY id',(log_id,))
    for p in payments:
        cash,bank=live.split(p);p['cash'],p['bank']=cash,bank
        p['label']='Tiền mặt' if bank==0 else 'Chuyển khoản' if cash==0 else 'Tiền mặt + CK'
        info=decoded(p['bank_snapshot'],{});info=info if isinstance(info,dict) else {'Dữ liệu cần kiểm tra':str(info)}
        if info.pop('qr_image',None):p['qr_url']=url_for('live.session_qr',log_id=log_id)
        info.pop('qr_mime',None);p['info']=info
    reversed_by=db.one('SELECT id,happened_at FROM cd_loan_logs WHERE reverses_log_id=%s',(log_id,))
    if log['operation_id']==7 and terms.get('lost_photo'):log['lost_photo_url']=url_for('live.lost_photo',log_id=log_id)
    return dict(log=log,loan=loan,customer=customer,customer_live=customer_live,changes=changes,payments=payments,reversed_by=reversed_by,rule=terms.get('rule') or terms.get('basis') or '')

@bp.get('/<int:log_id>/xem')
def modal(log_id):
    return render_template('_transaction_modal.html',**context(log_id))
