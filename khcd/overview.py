"""TỔNG QUAN cầm đồ — số liệu, nhận định và cảnh báo tính trên sổ SQL mới (cd_loans + bảng liên quan).

Nguồn cũ (pawn/pawn_log) chỉ còn là dữ liệu chuyển đổi: trang này KHÔNG đọc nó, trừ một dòng đếm
"phiếu nguồn cũ chưa chuyển" để nhắc việc. Mọi con số là CHỈ ĐỌC; không có truy vấn nào ghi.

Bố cục số liệu (GĐ chốt 18/09/2026 — trang Tổng quan phải đúng chức năng cầm đồ):
    · DƯ NỢ: số phiếu đang cầm, dư gốc, giá trị tài sản theo giá vàng KHBL, tỷ lệ cho vay/giá trị (LTV)
    · TUỔI NỢ: chưa đến hạn · sắp hạn 7 ngày · quá hạn 1–30 · 31–90 · >90 ngày (số phiếu + dư gốc)
    · DÒNG TIỀN kỳ đang xem (sessions() dùng chung Thống kê/Giao dịch): thu · chi · lãi ròng · số phiên
    · TÀI SẢN theo loại vàng · DƯ GỐC theo tủ
    · CẢNH BÁO & ĐỀ XUẤT sinh tự động từ chính các số trên (ngưỡng ở NGUONG bên dưới)."""
from datetime import timedelta
from decimal import Decimal
from flask import current_app
from . import db, live_loans as live
from .domain import BusinessError, today, parse_date

# Ngưỡng cảnh báo — chỉnh ở đây, không rải trong template.
NGUONG = dict(sap_han_ngay=7, qua_han_thanh_ly=90, ltv_cao=0.9, lai_chua_thu_ngay=60, gia_vang_cu_ngay=7)
NHAN_VANG = {'61': 'Vàng 610', '99': 'Vàng 9999', '98': 'Vàng 980', 'bk': 'Bạch kim', 'vt': 'Vàng trắng',
             'sjc': 'SJC', '18k': 'Vàng 18K', '24k': 'Vàng 24K', '#': 'Khác'}

def _d(v):return Decimal(str(v or 0))

def gia_vang():
    """{'61': (giá/chỉ, effective_at)} từ khj_bl.gold_prices; lỗi → {} (trang vẫn lên, LTV bỏ trống)."""
    try:
        from .gold_prices import options
        return {g['id']: (_d(g.get('price')), g.get('effective_at')) for g in options() if _d(g.get('price')) > 0}
    except BusinessError:return {}

def stats(d1, d2):
    hom_nay = today(); ky = dict(d1=str(d1), d2=str(d2))
    # ── 1. Dư nợ đang cầm + tuổi nợ ────────────────────────────────────────────────────────────
    a = db.one("""SELECT COUNT(*) n,COALESCE(SUM(principal_balance),0) goc,
        SUM(due_at>=%(t7)s) chua_han,COALESCE(SUM(IF(due_at>=%(t7)s,principal_balance,0)),0) chua_han_goc,
        SUM(due_at>=%(t)s AND due_at<%(t7)s) sap_han,COALESCE(SUM(IF(due_at>=%(t)s AND due_at<%(t7)s,principal_balance,0)),0) sap_han_goc,
        SUM(due_at<%(t)s) qua_han,COALESCE(SUM(IF(due_at<%(t)s,principal_balance,0)),0) qua_han_goc,
        SUM(due_at<%(t)s AND due_at>=%(t30)s) qh1,COALESCE(SUM(IF(due_at<%(t)s AND due_at>=%(t30)s,principal_balance,0)),0) qh1_goc,
        SUM(due_at<%(t30)s AND due_at>=%(t90)s) qh2,COALESCE(SUM(IF(due_at<%(t30)s AND due_at>=%(t90)s,principal_balance,0)),0) qh2_goc,
        SUM(due_at<%(t90)s) qh3,COALESCE(SUM(IF(due_at<%(t90)s,principal_balance,0)),0) qh3_goc,
        SUM(interest_from<%(t60)s) lai_lau,COALESCE(SUM(IF(interest_from<%(t60)s,principal_balance,0)),0) lai_lau_goc,
        SUM(cust_id IS NULL OR cust_id='') chua_kk,SUM(receipt_lost) mat_bn,
        COALESCE(SUM(monthly_rate<3),0) lai_thap
        FROM cd_loans WHERE loan_state='ACTIVE'""",
        dict(t=hom_nay, t7=hom_nay + timedelta(days=NGUONG['sap_han_ngay']), t30=hom_nay - timedelta(days=30),
             t90=hom_nay - timedelta(days=NGUONG['qua_han_thanh_ly']), t60=hom_nay - timedelta(days=NGUONG['lai_chua_thu_ngay'])))
    a = {k: (int(v or 0) if k in ('n','chua_han','sap_han','qua_han','qh1','qh2','qh3','lai_lau','chua_kk','mat_bn','lai_thap') else _d(v)) for k, v in a.items()}
    tuoi_no = [dict(nhan='Chưa đến hạn', n=a['chua_han'], goc=a['chua_han_goc'], mau='ok'),
               dict(nhan='Đến hạn ≤ %d ngày' % NGUONG['sap_han_ngay'], n=a['sap_han'], goc=a['sap_han_goc'], mau='warn'),
               dict(nhan='Quá hạn 1–30 ngày', n=a['qh1'], goc=a['qh1_goc'], mau='warn'),
               dict(nhan='Quá hạn 31–90 ngày', n=a['qh2'], goc=a['qh2_goc'], mau='bad'),
               dict(nhan='Quá hạn > 90 ngày', n=a['qh3'], goc=a['qh3_goc'], mau='bad')]
    for t in tuoi_no:t['pct'] = float(t['goc'] / a['goc'] * 100) if a['goc'] else 0.0
    # ── 2. Tài sản đang giữ theo loại vàng + định giá theo giá KHBL ────────────────────────────
    gia = gia_vang()
    vang = db.all("""SELECT i.gold_code ma,COUNT(*) mon,COUNT(DISTINCT i.loan_id) phieu,COALESCE(SUM(i.net_weight),0) tl,
        COALESCE(SUM(i.valuation),0) dinh_gia FROM cd_loan_items i JOIN cd_loans l ON l.id=i.loan_id
        WHERE l.loan_state='ACTIVE' GROUP BY i.gold_code ORDER BY mon DESC""")
    tong_gt = Decimal(0); co_gia = False
    for v in vang:
        v['nhan'] = NHAN_VANG.get(str(v['ma']), str(v['ma'])); v['tl'] = _d(v['tl']); v['mon'] = int(v['mon']); v['phieu'] = int(v['phieu'])
        p = gia.get(str(v['ma']))
        v['gia'] = p[0] if p else None; v['gia_tri'] = (v['tl'] * p[0]).quantize(Decimal(1)) if p else None
        if v['gia_tri'] is not None:tong_gt += v['gia_tri']; co_gia = True
    # Gốc của riêng các phiếu CÓ định giá được (để LTV không so gốc toàn sổ với giá trị một phần).
    ma_co_gia = [m for m in gia if any(str(v['ma']) == m for v in vang)]
    goc_co_gia = _d(db.one("SELECT COALESCE(SUM(l.principal_balance),0) s FROM cd_loans l WHERE l.loan_state='ACTIVE' AND NOT EXISTS "
                           "(SELECT 1 FROM cd_loan_items i WHERE i.loan_id=l.id AND i.gold_code NOT IN (" + ','.join(['%s'] * len(ma_co_gia)) + "))",
                           ma_co_gia)['s']) if ma_co_gia else Decimal(0)
    # Giá trị thị trường của riêng các phiếu đó
    gt_co_gia = Decimal(0)
    if ma_co_gia:
        for r in db.all("SELECT i.gold_code ma,COALESCE(SUM(i.net_weight),0) tl FROM cd_loan_items i JOIN cd_loans l ON l.id=i.loan_id WHERE l.loan_state='ACTIVE' AND NOT EXISTS "
                        "(SELECT 1 FROM cd_loan_items j WHERE j.loan_id=l.id AND j.gold_code NOT IN (" + ','.join(['%s'] * len(ma_co_gia)) + ")) GROUP BY i.gold_code", ma_co_gia):
            if str(r['ma']) in gia:gt_co_gia += _d(r['tl']) * gia[str(r['ma'])][0]
    ltv = float(goc_co_gia / gt_co_gia) if gt_co_gia else None
    gia_ngay = max((p[1] for p in gia.values() if p[1]), default=None)
    gia_cu = bool(gia_ngay) and (hom_nay - parse_date(str(gia_ngay)[:10])).days > NGUONG['gia_vang_cu_ngay']
    # Phiếu LTV cao (gốc > 90% giá trị vàng) — chỉ xét phiếu định giá được trọn
    ltv_cao = []
    if ma_co_gia:
        rows = db.all("SELECT l.id,l.sku,l.principal_balance goc,l.due_at,i.gold_code ma,i.net_weight tl FROM cd_loans l JOIN cd_loan_items i ON i.loan_id=l.id "
                      "WHERE l.loan_state='ACTIVE' AND NOT EXISTS (SELECT 1 FROM cd_loan_items j WHERE j.loan_id=l.id AND j.gold_code NOT IN (" + ','.join(['%s'] * len(ma_co_gia)) + "))", ma_co_gia)
        gom = {}
        for r in rows:
            g = gom.setdefault(r['id'], dict(id=r['id'], sku=r['sku'], goc=_d(r['goc']), gt=Decimal(0), due_at=r['due_at']))
            g['gt'] += _d(r['tl']) * gia[str(r['ma'])][0]
        for g in gom.values():
            if g['gt'] > 0 and g['goc'] / g['gt'] > Decimal(str(NGUONG['ltv_cao'])):
                g['ltv'] = float(g['goc'] / g['gt']); ltv_cao.append(g)
        ltv_cao.sort(key=lambda g: -g['ltv'])
    # ── 3. Theo tủ ────────────────────────────────────────────────────────────────────────────
    tu = db.all("SELECT COALESCE(NULLIF(safe,''),'—') tu,COUNT(*) n,COALESCE(SUM(principal_balance),0) goc FROM cd_loans WHERE loan_state='ACTIVE' GROUP BY tu ORDER BY tu")
    for t in tu:t['n'] = int(t['n']); t['goc'] = _d(t['goc']); t['pct'] = float(t['goc'] / a['goc'] * 100) if a['goc'] else 0.0
    # ── 4. Dòng tiền kỳ đang xem — cùng nguồn với Thống kê / Giao dịch ─────────────────────────
    ky_data = live.sessions(dict(d1=str(d1), d2=str(d2)))
    ops = {g['status_id']: g for g in ky_data['groups']}
    hoat_dong = [dict(nhan=live.OPS[k], n=int(ops[k]['count']) if k in ops else 0, tien=_d(ops[k]['amount']) if k in ops else Decimal(0),
                      lai=_d(ops[k]['interest']) if k in ops else Decimal(0), kind=k) for k in (1, 2, 3, 4, 5, 6, 7)]
    # Lãi thu ròng tháng này + 30 ngày trước (so sánh xu hướng)
    dau_thang = hom_nay.replace(day=1)
    thang = db.one("SELECT COALESCE(SUM(interest),0) lai,COUNT(*) n FROM cd_loan_logs WHERE happened_at>=%s AND happened_at<%s AND operation_id<>8", (dau_thang, hom_nay + timedelta(days=1)))
    thang_truoc_dau = (dau_thang - timedelta(days=1)).replace(day=1)
    thang_truoc = db.one("SELECT COALESCE(SUM(interest),0) lai,COUNT(*) n FROM cd_loan_logs WHERE happened_at>=%s AND happened_at<%s AND operation_id<>8", (thang_truoc_dau, dau_thang))
    # Cầm mới 30 ngày qua vs chuộc 30 ngày qua (sổ đang phình hay co)
    dong = db.one("SELECT COALESCE(SUM(IF(operation_id=1,1,0)),0) moi,COALESCE(SUM(IF(operation_id=1,principal_change,0)),0) moi_tien,"
                  "COALESCE(SUM(IF(operation_id IN (5,6),1,0)),0) dong,COALESCE(SUM(IF(operation_id IN (5,6),-principal_change,0)),0) dong_tien "
                  "FROM cd_loan_logs WHERE happened_at>=%s AND happened_at<%s AND operation_id<>8", (hom_nay - timedelta(days=30), hom_nay + timedelta(days=1)))
    # ── 5. Danh sách cần xử lý ────────────────────────────────────────────────────────────────
    def ds(sql, params):
        rows = db.all(sql, params)
        for r in rows:
            r['pmv_cust_id'] = r['cust_id']; r['customer_name'] = r.get('customer_name') or ''
        if rows and live.master.enabled():
            ten = {r['id']: r['customer_name'] for r in rows}; live.master.hydrate(rows)
            for r in rows:r['customer_name'] = r.get('customer_name') or ten[r['id']]
        for r in rows:
            r['qua'] = (hom_nay - parse_date(r['due_at'])).days if r.get('due_at') else 0; r['goc'] = _d(r['principal_balance'])
        return rows
    cot = "SELECT id,sku,cust_id,phone,principal_balance,due_at,interest_from,monthly_rate,JSON_UNQUOTE(JSON_EXTRACT(customer_snapshot,'$.name')) customer_name FROM cd_loans WHERE loan_state='ACTIVE'"
    sap_han = ds(cot + " AND due_at>=%s AND due_at<%s ORDER BY due_at,id LIMIT 8", (hom_nay, hom_nay + timedelta(days=NGUONG['sap_han_ngay'])))
    qua_han = ds(cot + " AND due_at<%s ORDER BY due_at,id LIMIT 8", (hom_nay - timedelta(days=NGUONG['qua_han_thanh_ly']),))
    # ── 6. Nhận định & cảnh báo tự sinh ─────────────────────────────────────────────────────────
    canh_bao = []
    if a['qh3']:canh_bao.append(dict(muc='bad', tieu_de='%d phiếu quá hạn trên %d ngày · dư gốc %s' % (a['qh3'], NGUONG['qua_han_thanh_ly'], _vnd(a['qh3_goc'])),
                                     de_xuat='Rà từng phiếu: gọi khách lần cuối, chốt gia hạn hoặc lập thủ tục thanh lý — để lâu lãi dồn vượt giá trị vàng.', link=('OVERDUE', None)))
    if a['sap_han']:canh_bao.append(dict(muc='warn', tieu_de='%d phiếu đến hạn trong %d ngày tới · %s' % (a['sap_han'], NGUONG['sap_han_ngay'], _vnd(a['sap_han_goc'])),
                                         de_xuat='Nhắn/gọi khách trước ngày hẹn (danh sách bên dưới) — chủ động gia hạn giữ được lãi đều và tránh phát sinh quá hạn.'))
    if ltv is not None and ltv > NGUONG['ltv_cao']:canh_bao.append(dict(muc='bad', tieu_de='Tỷ lệ cho vay / giá trị vàng toàn sổ %.0f%%' % (ltv * 100),
                                                                          de_xuat='Đang cho vay sát giá vàng thu vào — giá giảm là lỗ khi thanh lý. Siết mức cầm với phiếu mới.'))
    if ltv_cao:canh_bao.append(dict(muc='warn', tieu_de='%d phiếu có dư gốc > %.0f%% giá trị vàng theo giá hôm nay' % (len(ltv_cao), NGUONG['ltv_cao'] * 100),
                                    de_xuat='Ưu tiên thu lãi/gia hạn các phiếu này; không cho cầm thêm trên cùng tài sản.'))
    if a['lai_lau']:canh_bao.append(dict(muc='warn', tieu_de='%d phiếu chưa thu lãi quá %d ngày · dư gốc %s' % (a['lai_lau'], NGUONG['lai_chua_thu_ngay'], _vnd(a['lai_lau_goc'])),
                                         de_xuat='Lãi dồn nhiều kỳ làm khách khó chuộc — đề xuất thu lãi từng kỳ, gia hạn ngắn.'))
    if gia_cu or not gia:canh_bao.append(dict(muc='warn', tieu_de='Giá vàng KHBL %s' % ('chưa đọc được' if not gia else 'cập nhật lần cuối %s' % str(gia_ngay)[:10]),
                                              de_xuat='Cập nhật giá thu vào ở Bán lẻ để định giá tài sản và LTV trên trang này đúng thực tế.'))
    if a['chua_kk']:canh_bao.append(dict(muc='info', tieu_de='%d phiếu đang cầm chưa nối khách KK' % a['chua_kk'],
                                         de_xuat='Vào Phiếu cũ → "Chưa nối khách KK" để gán đúng CustID; hồ sơ khách trên giấy in đang lấy từ bản lưu.'))
    if a['mat_bn']:canh_bao.append(dict(muc='info', tieu_de='%d phiếu đang báo mất biên nhận' % a['mat_bn'],
                                        de_xuat='Chỉ giao hàng khi có cam kết báo mất + CCCD khớp; mở khóa tại quầy bằng PassCode.'))
    pending = db.one("SELECT COUNT(*) n,COALESCE(SUM(p.value),0) goc FROM pawn p LEFT JOIN cd_loans l ON l.legacy_pawn_id=p.id WHERE p.status IN (1,2,3,4,7) AND l.id IS NULL")
    if pending and int(pending['n']):canh_bao.append(dict(muc='info', tieu_de='%d phiếu nguồn cũ chưa chuyển sang sổ mới · %s' % (int(pending['n']), _vnd(pending['goc'])),
                                                          de_xuat='Chưa tính vào số liệu trang này. Chuyển đổi có đối soát tại Phiếu cũ.'))
    nhan_dinh = []
    if a['goc']:
        nhan_dinh.append('Quá hạn chiếm <b>%.0f%%</b> dư gốc (%d/%d phiếu)%s.' % (float(a['qua_han_goc'] / a['goc'] * 100), a['qua_han'], a['n'],
                         ' — cao, cần lịch nhắc khách theo tuần' if a['qua_han'] > a['n'] * 0.25 else ''))
    if thang and thang_truoc and _d(thang_truoc['lai']):
        ch = float((_d(thang['lai']) - _d(thang_truoc['lai'])) / _d(thang_truoc['lai']) * 100)
        nhan_dinh.append('Lãi thu tháng này <b>%s</b> (%+.0f%% so với cả tháng trước %s).' % (_vnd(thang['lai']), ch, _vnd(thang_truoc['lai'])))
    if dong:
        nhan_dinh.append('30 ngày qua: cầm mới <b>%d</b> phiếu (%s) · chuộc/thanh lý <b>%d</b> (%s) → sổ %s.' % (
            int(dong['moi']), _vnd(dong['moi_tien']), int(dong['dong']), _vnd(dong['dong_tien']),
            'đang phình' if _d(dong['moi_tien']) > _d(dong['dong_tien']) else 'đang co lại'))
    if ltv is not None:nhan_dinh.append('Cho vay bằng <b>%.0f%%</b> giá trị vàng thu vào (giá KHBL), tính trên %s dư gốc định giá được.' % (ltv * 100, _vnd(goc_co_gia)))
    if a['lai_thap']:nhan_dinh.append('%d phiếu áp lãi dưới 3%%/tháng.' % a['lai_thap'])
    return dict(ky=ky, d366=str(hom_nay - timedelta(days=366)), a=a, tuoi_no=tuoi_no, vang=vang, tong_gt=tong_gt, co_gia=co_gia, ltv=ltv, gia_ngay=str(gia_ngay)[:10] if gia_ngay else None,
                ltv_cao=ltv_cao[:6], tu=tu, ky_data=ky_data, hoat_dong=hoat_dong, thang=thang, thang_truoc=thang_truoc, dong=dong,
                sap_han=sap_han, qua_han=qua_han, canh_bao=canh_bao, nhan_dinh=nhan_dinh, nguong=NGUONG)

def _vnd(v):return f'{_d(v):,.0f}'.replace(',', '.') + ' đ'
