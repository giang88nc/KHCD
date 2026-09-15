"""Read recorded transactions without creating or recalculating entries."""
from datetime import timedelta
from decimal import Decimal
from . import db, customer_master as master
from .domain import today, parse_date, BusinessError


def listing(args):
    start=parse_date(args.get('d1') or today(),'Từ ngày')
    end=parse_date(args.get('d2') or today(),'Đến ngày')
    if start>end or (end-start).days>366:
        raise BusinessError('Khoảng ngày phải đúng thứ tự và không quá 366 ngày.')
    q=args.get('q','').strip()
    if len(q)>100:raise BusinessError('Từ khóa tối đa 100 ký tự.')
    try:page=max(1,int(args.get('page',1)))
    except (ValueError,TypeError):raise BusinessError('Số trang không hợp lệ.')
    joins=''' FROM pawn_log l LEFT JOIN pawn p ON p.id=l.pawn_id
        LEFT JOIN pawn_status s ON s.id=l.status_id
        LEFT JOIN khcd_pawn_customer k ON k.pawn_id=p.id'''
    customer_field="'' customer_name"
    if not master.enabled():
        joins+=''' LEFT JOIN (SELECT phone,MIN(id) id FROM customer GROUP BY phone) cm ON cm.phone=p.phone
            LEFT JOIN customer c ON c.id=cm.id'''
        customer_field='c.name customer_name'
    where=' WHERE COALESCE(l.date2,l.date1)>=%s AND COALESCE(l.date2,l.date1)<%s'
    params=[start,end+timedelta(days=1)]
    if q:
        pattern='%'+q.replace('!','!!').replace('%','!%').replace('_','!_')+'%'
        if master.enabled():
            ids=master.call('search_ids',q=q)['ids']
            where+=" AND (p.phone LIKE %s ESCAPE '!'"+(' OR k.pmv_cust_id IN ('+','.join(['%s']*len(ids))+')' if ids else '')+')'
            params.extend([pattern]+ids)
        else:
            where+=" AND (p.phone LIKE %s ESCAPE '!' OR c.name LIKE %s ESCAPE '!' OR c.cccd LIKE %s ESCAPE '!')"
            params.extend([pattern]*3)
    flow='(COALESCE(l.total,0)+COALESCE(l.mbank,0))'
    groups=db.all('''SELECT l.status_id,COALESCE(s.name,'Không xác định') operation,COUNT(*) count,
        COALESCE(SUM(l.sotien),0) amount,COALESCE(SUM(l.tienlai),0) interest,
        COALESCE(SUM(l.total),0) cash,COALESCE(SUM(l.mbank),0) bank,
        COALESCE(SUM(GREATEST('''+flow+''',0)),0) received,
        COALESCE(SUM(GREATEST(-'''+flow+''',0)),0) paid'''+joins+where+
        ' GROUP BY l.status_id,s.name,s.sort ORDER BY s.sort,l.status_id',params)
    total=sum(r['count'] for r in groups);pages=max(1,(total+49)//50);page=min(page,pages)
    rows=db.all('''SELECT l.id,l.pawn_id,p.id existing_pawn_id,p.sku,p.phone,k.pmv_cust_id,
        COALESCE(l.date2,l.date1) happened_at,l.date2 IS NULL date_fallback,
        l.status_id,COALESCE(s.name,'Không xác định') operation,
        l.sotien amount,COALESCE(l.tienlai,0) interest,COALESCE(l.tienthem,0) extra,
        COALESCE(l.tienbot,0) discount,COALESCE(l.total,0) cash,COALESCE(l.mbank,0) bank,
        '''+flow+' net,'+customer_field+joins+where+
        ' ORDER BY COALESCE(l.date2,l.date1) DESC,l.id DESC LIMIT 50 OFFSET %s',params+[(page-1)*50])
    warnings=[]
    if master.enabled():
        master.hydrate(rows)
        if any(r.get('customer_source_error') for r in rows):
            warnings.append('Một số phiên chưa đọc được khách KK hoặc chưa nối CustID; SĐT trên phiếu cũ vẫn được hiển thị.')
    money_fields=('amount','interest','cash','bank','received','paid')
    totals={field:str(sum((r[field] for r in groups),Decimal(0))) for field in money_fields}
    for row in rows:
        row['happened_at']=row['happened_at'].isoformat(sep=' ')
        for field in ('amount','interest','extra','discount','cash','bank','net'):
            row[field]=str(row[field]) if row[field] is not None else None
        row['can_open']=bool(row['existing_pawn_id'] and row['sku'])
        for field in ('cccd','addr','customer_phone','customer_id'):row.pop(field,None)
    for row in groups:
        for field in money_fields:row[field]=str(row[field])
    return dict(rows=rows,total=total,page=page,pages=pages,d1=start.isoformat(),d2=end.isoformat(),q=q,
                totals=totals,groups=groups,warnings=warnings)
