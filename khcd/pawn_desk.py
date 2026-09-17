"""Extra receipt data; old pawn columns remain readable by the legacy application."""
import base64
import json
from decimal import Decimal, ROUND_HALF_UP
from . import db, customer_master as master
from .domain import BusinessError, decimal, money

# ── LOẠI VÀNG HIỂN THỊ TRÊN BIÊN NHẬN CẦM ĐỒ — Giám đốc chốt 17/09/2026 ───────────────────────
# mã trong sổ (đã hạ chữ thường) → (nhãn in trong ngoặc vuông, hậu tố đơn vị sau con số)
# Sổ gom dữ liệu từ nhiều đời phần mềm nên CÙNG MỘT loại vàng có mấy cách viết; bảng này quy về
# một nhãn duy nhất để tờ giấy không nói hai kiểu cho cùng một thứ.
LOAI_VANG = {
    "61": ("61", "c"), "610": ("61", "c"), "18k": ("61", "c"),
    "98": ("98", "c"), "980": ("98", "c"), "24k": ("98", "c"),
    "99": ("99", "c"), "9999": ("99", "c"), "n9999": ("99", "c"), "99.99": ("99", "c"),
    "sjc": ("sjc", "c"), "pnj": ("sjc", "c"),
    "bk": ("bk", "g"),
}

DDL = [
'''CREATE TABLE IF NOT EXISTS khcd_pawn_desk (
 pawn_id INT NOT NULL PRIMARY KEY, items_json JSON NOT NULL,
 employee_id VARCHAR(30) NOT NULL, employee_name VARCHAR(255) NOT NULL,
 payment_json JSON NOT NULL, content TEXT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4''',
'''CREATE TABLE IF NOT EXISTS khcd_pawn_photo (
 pawn_id INT NOT NULL, kind VARCHAR(20) NOT NULL, data MEDIUMBLOB NOT NULL,
 PRIMARY KEY(pawn_id,kind)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4''']
PHOTO_NAMES = ('anh_truoc','anh_sau','anh_sp1','anh_sp2','anh_qr')


def items(data, golds):
    try:
        rows=json.loads(data.get('items_json','[]'))
    except (ValueError,TypeError): raise BusinessError('Danh sách món hàng không hợp lệ.')
    if not isinstance(rows,list) or not 1<=len(rows)<=30:
        raise BusinessError('Biên nhận cần từ 1 đến 30 dòng món hàng.')
    allowed={str(g['id']):g for g in golds};result=[]
    for row in rows:
        if not isinstance(row,dict):raise BusinessError('Dòng món hàng không hợp lệ.')
        gold=allowed.get(str(row.get('gold','')))
        if not gold:raise BusinessError('Loại vàng không nằm trong danh mục.')
        desc=str(row.get('description','')).strip()
        if not desc or len(desc)>255:raise BusinessError('Mô tả mỗi món bắt buộc, tối đa 255 ký tự.')
        if str(gold['id'])=='KHAC':
            price=decimal(row.get('price') or '0','Giá hiện tại',maximum=Decimal('999999999999'))
            if price!=money(price):raise BusinessError('Giá phải là số nguyên đồng.')
            result.append(dict(gold='KHAC',name=gold['name'],unit='món',description=desc,gross='0',stone='0',net='0',price=str(price),subtotal=str(price)))
            continue
        gross=decimal(row.get('gross'),'Tổng trọng lượng',Decimal('.0001'),Decimal('99999'))
        stone=decimal(row.get('stone','0'),'Trọng lượng hột',maximum=gross)
        if stone>=gross or min(gross.as_tuple().exponent,stone.as_tuple().exponent)<-4:
            raise BusinessError('TL vàng phải lớn hơn 0; trọng lượng tối đa 4 số thập phân.')
        price=decimal(gold.get('price') or 0,'Giá thâu',maximum=Decimal('999999999999'))
        if price<=0:raise BusinessError('Chưa có giá thâu hiện tại cho '+gold['name']+' trong khj_bl.gold_prices.')
        if decimal(row.get('price'),'Giá định giá')!=price:
            raise BusinessError('Giá thâu '+gold['name']+' đã thay đổi. Cập nhật giá và xác nhận lại phiếu.')
        if price!=money(price):raise BusinessError('Giá phải là số nguyên đồng.')
        result.append(dict(gold=str(gold['id']),name=gold['name'],unit=gold['unit'],description=desc,
            gross=str(gross),stone=str(stone),net=str(gross-stone),price=str(price),subtotal=str(money((gross-stone)*price))))
    return result


def loai_vang(ma_vang):
    """Mã vàng trong sổ → (NHÃN in trong ngoặc vuông, HẬU TỐ đơn vị). Giám đốc chốt 17/09/2026.

        610 · 18k · 61        → [61]  · chỉ  → 'c'
        980 · 24k · 98        → [98]  · chỉ  → 'c'
        9999 · N9999 · 99.99 · 99 → [99]  · chỉ  → 'c'
        sjc · pnj             → [sjc] · chỉ  → 'c'
        bk                    → [bk]  · gram → 'g'
        còn lại / không chắc  → giữ NGUYÊN mã, KHÔNG in đơn vị

    VÌ SAO QUY VỀ MỘT NHÃN: sổ gom dữ liệu từ nhiều đời phần mềm nên cùng một loại vàng có mấy cách
    viết (610 / 18k, 9999 / N9999 / 99.99…). Tờ biên nhận mà gọi cùng một thứ bằng hai tên thì lúc
    khách tới chuộc, đối chiếu với món trong tủ là cãi nhau.

    ⚠ ĐƠN VỊ: quyết theo MÃ VÀNG chứ KHÔNG theo cột `cd_loan_items.unit` — đo trên sổ thật có
    992/999 dòng để cột đó NULL (toàn bộ từ phiếu chuyển đổi hệ cũ).
    ⚠ KHÔNG ĐOÁN khi không chắc: trước 17/09 hàm này ép mọi đơn vị thiếu thành 'chỉ', tức ~99% biên
    nhận in ra khẳng định một đơn vị không có trong sổ. Đoán sai lệch 3,75 lần (1 chỉ = 3,75 gram)
    trên chứng từ cầm đồ — thà thiếu chữ còn hơn ghi sai.
    ⚠ Thêm cách viết mới thì thêm vào LOAI_VANG, đừng rải điều kiện ra chỗ khác.
    """
    ma = str(ma_vang or "").strip()
    return LOAI_VANG.get(ma.lower(), (ma, ""))


def _mot_mon(r):
    """Một dòng món → chuỗi in trên biên nhận. Nhãn và đơn vị do loai_vang() quyết (xem hàm đó)."""
    if r['gold'] == 'KHAC':
        return f"[KHÁC] {r['description']}"
    nhan, dv = loai_vang(r['gold'])
    so = Decimal(r['net']).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    return f"[{nhan}] {r['description']} {so:.2f}{dv}"


def summary(rows):
    return ' + '.join(_mot_mon(r) for r in rows)


def payment(data, principal):
    if 'payment_method' in data:
        method=data.get('payment_method')
        if method not in ('cash','bank'):raise BusinessError('Chọn phương thức thanh toán hợp lệ.')
        data=dict(data)
        cash=decimal(data.get('cash_amount'),'Tiền mặt',maximum=principal)
        bank=decimal(data.get('bank_amount'),'Tiền chuyển khoản',maximum=principal)
        if cash!=money(cash) or bank!=money(bank) or cash+bank!=principal:
            raise BusinessError('Tiền mặt + chuyển khoản phải bằng tiền cầm, tính bằng nguyên đồng.')
        if method=='cash' and bank!=0:raise BusinessError('Tiền mặt không kèm khoản chuyển ngân hàng.')
        data.update(pay_cash='1' if cash>0 else '',pay_bank='1' if method=='bank' else '')
    cash_on=data.get('pay_cash')=='1';bank_on=data.get('pay_bank')=='1'
    if not cash_on and not bank_on:raise BusinessError('Chọn phương thức chi tiền.')
    bank=decimal(data.get('bank_amount') or '0','Tiền chuyển khoản',maximum=principal) if bank_on else Decimal(0)
    if bank_on and (bank<=0 or bank!=money(bank)):raise BusinessError('Tiền chuyển khoản phải là số nguyên đồng, lớn hơn 0.')
    cash=principal-bank
    if not cash_on and cash!=0:raise BusinessError('Chuyển khoản toàn bộ phải bằng tiền cầm.')
    info=dict(cash=str(cash),bank_amount=str(bank))
    for field in ('bank_name','bank_account','bank_holder','bank_reference'):
        value=str(data.get(field,'')).strip() if bank_on else ''
        if len(value)>120:raise BusinessError('Thông tin chuyển khoản tối đa 120 ký tự mỗi ô.')
        if bank_on and field!='bank_reference' and not value:raise BusinessError('Điền ngân hàng, số tài khoản và tên người nhận.')
        info[field]=value
    return info


def prepare(data, principal, golds):
    tables=db.all("SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ('khcd_pawn_desk','khcd_pawn_photo')")
    if len(tables)!=2 or any(t['ENGINE']!='InnoDB' for t in tables):
        raise BusinessError('Chưa chuẩn bị dữ liệu bàn lập phiếu. Chạy scripts/migrate_desk.py trước khi lưu.')
    rows=items(data,golds)
    employees=master.call('employees')['rows']
    employee=next((e for e in employees if str(e['EmpID'])==data.get('employee_id')),None)
    if not employee:raise BusinessError('Chọn nhân viên đang hoạt động trong danh mục KK.')
    return dict(items=rows,employee_id=employee['EmpID'],employee_name=employee['EmpName'],
                payment=payment(data,principal),content=summary(rows))


def prepare_photos(files):
    uploads={}
    for name in PHOTO_NAMES:
        file=files.get(name)
        if not file or not file.filename:continue
        data=file.read(15*1024*1024+1)
        if len(data)>15*1024*1024:raise BusinessError('Mỗi ảnh tối đa 15 MB.')
        uploads[name]=base64.b64encode(data).decode('ascii')
    if not uploads:return {}
    result=master.call('pawn_images',files=uploads)
    return {k:base64.b64decode(v,validate=True) for k,v in result['images'].items() if k in PHOTO_NAMES}


def save(pid, desk, photos):
    db.execute('INSERT INTO khcd_pawn_desk (pawn_id,items_json,employee_id,employee_name,payment_json,content) VALUES (%s,%s,%s,%s,%s,%s)',
        (pid,json.dumps(desk['items'],ensure_ascii=False),desk['employee_id'],desk['employee_name'],json.dumps(desk['payment'],ensure_ascii=False),desk['content']))
    for kind,raw in photos.items():db.execute('INSERT INTO khcd_pawn_photo (pawn_id,kind,data) VALUES (%s,%s,%s)',(pid,kind,raw))


def load(pid):
    if not db.one("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='khcd_pawn_desk'"):
        return None
    row=db.one('SELECT * FROM khcd_pawn_desk WHERE pawn_id=%s',(pid,))
    if row:
        row['items']=json.loads(row.pop('items_json'));row['payment']=json.loads(row.pop('payment_json'))
        row['photos']=[r['kind'] for r in db.all('SELECT kind FROM khcd_pawn_photo WHERE pawn_id=%s',(pid,))]
    return row


def hydrate_summaries(rows):
    if not rows or not db.one("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='khcd_pawn_desk'"):return
    ids=[r['id'] for r in rows]
    extra=db.all('SELECT pawn_id,JSON_LENGTH(items_json) item_count,content FROM khcd_pawn_desk WHERE pawn_id IN ('+','.join(['%s']*len(ids))+')',ids)
    lookup={r['pawn_id']:r for r in extra}
    for row in rows:
        if row['id'] in lookup:row.update(lookup[row['id']])


def receipt_key(raw, host='localhost'):
    import re
    from urllib.parse import urlsplit, unquote
    text=str(raw or '').strip()
    if not text or len(text)>256 or any(ord(c)<32 for c in text):raise BusinessError('Nhập hoặc quét mã biên nhận hợp lệ.')
    if text.startswith(('/', 'https://','http://')):
        url=urlsplit(text)
        if url.netloc and url.hostname not in ('localhost','127.0.0.1','tiemvangkimhanh2',host):
            raise BusinessError('QR không thuộc hệ thống Cầm đồ.')
        match=re.fullmatch(r'/(?:camdo/)?(phieu-cam-do|bien-nhan)/(\d+)/?',url.path)
        if not match or url.query or url.fragment:raise BusinessError('QR không chứa đường dẫn biên nhận hợp lệ.')
        return ('new_id' if match.group(1)=='bien-nhan' else 'id'),int(match.group(2))
    return 'sku',text


def receipt_data(p, photo_url):
    from .domain import parse_date, STATUSES
    extra=p.get('desk')
    rows=extra['items'] if extra else []
    if not extra:
        for i in (1,2):
            gold=p.get('gold'+str(i))
            if not gold or gold=='0':continue
            gross=Decimal(str(p.get('wgg'+str(i)) or 0));stone=Decimal(str(p.get('whh'+str(i)) or 0))
            rows.append(dict(gold=gold,description=p.get('mota'+str(i)) or 'Tài sản cũ',gross=str(gross),stone=str(stone),
                net=str(gross-stone),unit=(p.get('gold_unit' if i==1 else 'gold2_unit') or 'chỉ'),price='0',subtotal='0'))
    first=db.one('SELECT total,mbank FROM pawn_log WHERE pawn_id=%s AND status_id=1 ORDER BY id LIMIT 1',(p['id'],))
    bank=abs(Decimal(str((first or {}).get('mbank') or 0)))
    payment=extra['payment'] if extra else dict(cash=str(Decimal(str(p['value']))-bank),bank_amount=str(bank))
    return dict(id=p['id'],sku=p['sku'],status=p['status'],status_name=STATUSES.get(p['status'],'Chưa xác định'),
        active=p['active'],valuation_known=bool(extra),items=rows,value=str(p['value']),monthly_rate=str(p['percent'] or 0),safe=p.get('safe') or '',
        date1=str(parse_date(p['date1'])),due=str(parse_date(p['date3'])) if p.get('date3') else '',
        employee_id=extra['employee_id'] if extra else '',employee_name=extra['employee_name'] if extra else ('Nhân viên cũ #'+str(p['staff']) if p.get('staff') else 'Chưa ghi nhận'),
        note=p.get('note') or '',payment=payment,content=extra['content'] if extra else ' + '.join(r['description'] for r in rows),
        customer=dict(id=p.get('pmv_cust_id') or '',name=p.get('customer_name') or '',phone=p.get('customer_phone') or p['phone'],cccd=p.get('cccd') or '',addr=p.get('addr') or ''),
        customer_error=p.get('customer_source_error'),photos={k:photo_url(p['id'],k) for k in extra['photos']} if extra else {})
