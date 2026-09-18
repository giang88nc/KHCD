"""GỬI SMS (ZNS Zalo) — kiểm soát phiếu → lên lịch nhắc khách → CRUD thẳng lên sổ ``khj_bl.zalo_messages``.

GĐ chốt 18/09/2026:
  · Kênh ZBS/CARE360 (KHBL gửi theo ``scheduled_at``; Cầm đồ CHỈ tạo/sửa/hủy dòng của mình). Mẫu ZNS đã duyệt
    **635511 "Thông báo cầm đồ"**: pawn_code · customer_name · anh_chi · promise_date · days · notes.
  · LỊCH NHẮC theo d = hôm nay − ngày GIAO DỊCH GẦN NHẤT (không tính mở khóa báo mất):
        lần 1 = 15 · lần 2 = 30 · lần 3 = 45 (notes báo "thanh lý trong 15 ngày tới") ·
        lần 4 (CUỐI) = 60 (notes "THANH LÝ trong 7 ngày tới") · d ≥ 67 = hết hạn nhắc → nhóm CHỜ THANH LÝ.
    KHÔNG có tin "thanh lý" riêng gửi khách. Từ lần 3 tới hạn chót khách có ~3 tuần để đến tiệm.
  · CHU KỲ NHẮC: mỗi giao dịch mới (gia hạn, trả bớt, cầm thêm…) mở chu kỳ mới, nhắc lại từ lần 1. Mốc chu kỳ =
    id dòng cd_loan_logs gần nhất ⇒ khóa chống trùng = phiếu + mốc + mức.
  · ĐÃ NHẮC MỨC NÀO THÌ ẨN tới khi d chạm mức kế (mức tới hạn > mức đã xử lý). Nhảy cóc chỉ đề xuất MỘT tin ở
    mức hiện tại. Tin hủy / lỗi không tính là đã xử lý.
  · Tắt nhắc từng biên nhận: TẮT HẲN hoặc HOÃN ĐẾN NGÀY (kèm lý do). Có giao dịch mới / phiếu đóng ⇒ TỰ HỦY tin chờ.
  · Một SĐT nhiều phiếu cùng ngày: cứ xếp hàng bình thường, không giới hạn thêm.

HAI BẢNG RIÊNG trong khj_cd (không ghi vào cd_loans / cd_loan_logs — đó là sổ tiền có vân tay + đối soát):
    cd_sms_control  1 dòng/phiếu: tắt hẳn / hoãn đến ngày / lý do / ai đặt.
    cd_sms_log      1 dòng/tin: phiếu, mốc chu kỳ, mức, d, bản chụp biến, zalo id + tracking + dedupe, giờ hẹn,
                    trạng thái đọc được lần cuối, ai tạo/sửa/hủy → lọc nhanh + dấu vết + ĐỐI SOÁT hai chiều.

HỢP ĐỒNG DÒNG zalo_messages (chép công thức KHBL ``apps/oa/xep_hang.py`` — bản chép từ CARE360):
    source_type 'khcd_pawn' · channel 'phone' · status 'queued' · băm SĐT sha256("care360-zbs|84…") · masked 3***3 ·
    recipient_ciphertext 'khcd_no_cipher' · dedupe_key sha256("1|khcd_pawn|{loan}|{mốc}|{mức}") · send_rule_id NULL.
⚠ MỌI câu SQL đụng zalo_messages đều có ``source_type='khcd_pawn'``. Không có gọi mạng nào ở đây."""
import hashlib, json, re, uuid
from datetime import datetime, timedelta
from decimal import Decimal
from flask import Blueprint, current_app, flash, g, redirect, render_template, request, session, url_for
from . import db, live_loans as live
from .domain import BusinessError, now, today, parse_date

bp = Blueprint('sms', __name__, url_prefix='/camdo/gui-sms')

NGUON = 'khcd_pawn'
KHONG_MA_HOA = 'khcd_no_cipher'
TIEN_TO_BAM = 'care360-zbs|'
MAU_ZNS = '635511'
OA_ID = 1
HAN_CHOT = 67    # MẶC ĐỊNH khởi tạo — giá trị đang chạy nằm ở cd_sms_settings (xem quy_tac())
# MẶC ĐỊNH khởi tạo cd_sms_rules: (khóa, ngưỡng ngày, nhãn, màu, notes) — từ nặng → nhẹ
MUC = [('nhac4', 60, 'Nhắc lần 4 (cuối)', 'bad', 'Nhắc lần 4 (lần cuối): quá thời hạn này hàng sẽ được THANH LÝ trong 7 ngày tới.'),
       ('nhac3', 45, 'Nhắc lần 3', 'warn', 'Nhắc lần 3: nếu chưa gia hạn, hàng sẽ được thanh lý trong 15 ngày tới.'),
       ('nhac2', 30, 'Nhắc lần 2', 'warn', 'Nhắc lần 2: vui lòng đến tiệm gia hạn hoặc chuộc.'),
       ('nhac1', 15, 'Nhắc lần 1', 'ok', 'Nhắc lần 1: phiếu đã đến hạn gia hạn.')]
THU_TU = {'': 0, 'nhac1': 1, 'nhac2': 2, 'nhac3': 3, 'nhac4': 4}
MUC_MAU = {m[0]: m[3] for m in MUC}
BIEN_NOTES = ('lan', 'days', 'ngay_thanh_ly', 'so_ngay_con_lai')   # biến con dùng được trong câu notes
TRANG_THAI = {'cho': ('queued', 'sending', 'retry'), 'gui': ('sent', 'delivered', 'seen'),
              'loi': ('failed', 'failed_permanent'), 'huy': ('cancelled',)}
DA_XU_LY = TRANG_THAI['cho'] + TRANG_THAI['gui']
GIO_GUI_TU, GIO_GUI_DEN = 8, 20   # MẶC ĐỊNH khởi tạo
XUNG_HO_MAC_DINH = 'Anh/Chị'

DDL = ["""CREATE TABLE IF NOT EXISTS cd_sms_control (
  loan_id BIGINT NOT NULL PRIMARY KEY, muted TINYINT(1) NOT NULL DEFAULT 0, snooze_until DATE NULL,
  reason VARCHAR(255) NOT NULL DEFAULT '', updated_by BIGINT NULL, updated_username VARCHAR(150) NOT NULL DEFAULT '',
  updated_at DATETIME NOT NULL) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
       """CREATE TABLE IF NOT EXISTS cd_sms_log (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY, loan_id BIGINT NOT NULL, sku VARCHAR(255) NOT NULL,
  cycle_log_id BIGINT NOT NULL DEFAULT 0, level VARCHAR(10) NOT NULL, d_days INT NOT NULL DEFAULT 0,
  vars_json TEXT NOT NULL, zalo_message_id BIGINT NULL, tracking_id VARCHAR(48) NOT NULL, dedupe_key VARCHAR(64) NOT NULL,
  scheduled_at DATETIME NOT NULL, status VARCHAR(30) NOT NULL DEFAULT 'queued', sent_at DATETIME NULL,
  cancel_reason VARCHAR(100) NULL, synced_at DATETIME NULL, created_by BIGINT NULL, created_username VARCHAR(150) NOT NULL DEFAULT '',
  updated_username VARCHAR(150) NOT NULL DEFAULT '', created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL,
  UNIQUE KEY uq_cd_sms_dedupe (dedupe_key), KEY ix_cd_sms_loan (loan_id, cycle_log_id), KEY ix_cd_sms_status (status, scheduled_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"""]
DDL += ["""CREATE TABLE IF NOT EXISTS cd_sms_rules (
  level_no TINYINT NOT NULL PRIMARY KEY, days INT NOT NULL, label VARCHAR(60) NOT NULL, notes VARCHAR(200) NOT NULL,
  active TINYINT(1) NOT NULL DEFAULT 1, updated_username VARCHAR(150) NOT NULL DEFAULT '', updated_at DATETIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
        """CREATE TABLE IF NOT EXISTS cd_sms_settings (
  k VARCHAR(40) NOT NULL PRIMARY KEY, v VARCHAR(200) NOT NULL, updated_username VARCHAR(150) NOT NULL DEFAULT '', updated_at DATETIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
        """CREATE TABLE IF NOT EXISTS cd_sms_rules_history (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY, changed_at DATETIME NOT NULL, username VARCHAR(150) NOT NULL,
  target VARCHAR(40) NOT NULL, old_json TEXT NOT NULL, new_json TEXT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"""]
CAI_DAT_MAC_DINH = {'han_chot': str(HAN_CHOT), 'gio_tu': str(GIO_GUI_TU), 'gio_den': str(GIO_GUI_DEN), 'gio_mac_dinh': '9', 'xung_ho_mac_dinh': XUNG_HO_MAC_DINH,
                    # Xưng hô suy từ customer_name (GĐ chốt 18/09/2026) — sửa được trong ⚙ Quy tắc nhắc, ngăn bằng dấu phẩy
                    'tien_to_chi': 'Chị, Cô, Bà, Dì', 'tien_to_anh': 'Anh, Chú, Cậu, Bác, Ông', 'lot_chi': 'Thị, Mỹ', 'lot_anh': 'Văn, Tấn'}
KHOA_TU = ('tien_to_chi', 'tien_to_anh', 'lot_chi', 'lot_anh')
_schema_ok = set()


def ensure_schema():
    key = current_app.config['DB_NAME']
    if key in _schema_ok: return
    for ddl in DDL: db.execute(ddl)
    if not db.one('SELECT COUNT(*) n FROM cd_sms_rules')['n']:      # gieo 4 mức GĐ chốt 18/09/2026
        for key_, days, label, _, notes in MUC:
            db.execute('INSERT IGNORE INTO cd_sms_rules (level_no,days,label,notes,active,updated_username,updated_at) VALUES (%s,%s,%s,%s,1,%s,%s)', (THU_TU[key_], days, label, notes, 'khởi tạo', now()))
    for k, v in CAI_DAT_MAC_DINH.items():
        db.execute('INSERT IGNORE INTO cd_sms_settings (k,v,updated_username,updated_at) VALUES (%s,%s,%s,%s)', (k, v, 'khởi tạo', now()))
    _schema_ok.add(key)

def quy_tac():
    """Quy tắc ĐANG CHẠY đọc từ cd_sms_rules + cd_sms_settings (nhớ trong phạm vi 1 request)."""
    if 'sms_quy_tac' in g: return g.sms_quy_tac
    ensure_schema()
    rows = db.all('SELECT * FROM cd_sms_rules ORDER BY level_no')
    cd = dict(CAI_DAT_MAC_DINH); cd.update({r['k']: r['v'] for r in db.all('SELECT k,v FROM cd_sms_settings')})
    muc = [dict(key='nhac%d' % r['level_no'], no=int(r['level_no']), days=int(r['days']), label=r['label'], notes=r['notes'], active=bool(r['active']),
                mau=MUC_MAU.get('nhac%d' % r['level_no'], ''), updated_username=r['updated_username'], updated_at=r['updated_at']) for r in rows]
    g.sms_quy_tac = dict(muc=muc, dang_dung=sorted([m for m in muc if m['active']], key=lambda m: -m['days']), nhan={m['key']: m['label'] for m in muc},
                         han_chot=int(cd['han_chot']), gio_tu=int(cd['gio_tu']), gio_den=int(cd['gio_den']), gio_mac_dinh=int(cd['gio_mac_dinh']), xung_ho_mac_dinh=cd['xung_ho_mac_dinh'][:30],
                         **{k: [w.strip().casefold() for w in cd[k].split(',') if w.strip()] for k in KHOA_TU}, **{k + '_goc': cd[k] for k in KHOA_TU})
    return g.sms_quy_tac

def muc_cuoi():
    ds = quy_tac()['dang_dung']
    return ds[0]['key'] if ds else ''

def dung_notes(mau_cau, r, level):
    """Thay biến con trong câu notes: {lan} {days} {ngay_thanh_ly} {so_ngay_con_lai}. Biến lạ giữ nguyên văn."""
    qt = quy_tac(); han = parse_date(r['last_at']) + timedelta(days=qt['han_chot'])
    gia = dict(lan=THU_TU.get(level, 0), days=int(r['d']), ngay_thanh_ly=han.strftime('%d/%m/%Y'), so_ngay_con_lai=max(0, qt['han_chot'] - int(r['d'])))
    return re.sub(r'\{(\w+)\}', lambda m: str(gia[m.group(1)]) if m.group(1) in gia else m.group(0), str(mau_cau or ''))[:200]

def luu_quy_tac(form):
    """Lưu 4 mức + thiết lập chung. Ràng buộc: ngày tăng dần theo mức, hạn chót > mức cuối, notes ≤ 200, không link."""
    ensure_schema(); _, uname = nguoi(); bay_gio = now(); cu = quy_tac(); moi = []
    for m in cu['muc']:
        n = m['no']
        try: days = int(form.get('days_%d' % n, ''))
        except ValueError: raise BusinessError('Số ngày của lần %d không hợp lệ.' % n)
        notes = str(form.get('notes_%d' % n, '')).strip(); label = str(form.get('label_%d' % n, '') or m['label']).strip()[:60]
        if not 1 <= days <= 720: raise BusinessError('Số ngày của lần %d phải từ 1 đến 720.' % n)
        if not notes or len(notes) > 200: raise BusinessError('Câu nhắc lần %d phải có nội dung và tối đa 200 ký tự.' % n)
        if re.search(r'https?://|www\.', notes, re.I): raise BusinessError('Câu nhắc không được chứa đường link (Zalo sẽ từ chối tin).')
        la = [b for b in re.findall(r'\{(\w+)\}', notes) if b not in BIEN_NOTES]
        if la: raise BusinessError('Biến không hỗ trợ trong câu nhắc lần %d: %s. Dùng được: %s.' % (n, ', '.join(la), ', '.join('{%s}' % b for b in BIEN_NOTES)))
        moi.append(dict(no=n, days=days, label=label, notes=notes, active=form.get('active_%d' % n) == '1'))
    dung = [m for m in moi if m['active']]
    if not dung: raise BusinessError('Phải bật ít nhất một mức nhắc.')
    if any(a['days'] >= b['days'] for a, b in zip(dung, dung[1:])): raise BusinessError('Số ngày phải TĂNG DẦN theo thứ tự lần nhắc.')
    try: cd = dict(han_chot=int(form.get('han_chot', '')), gio_tu=int(form.get('gio_tu', '')), gio_den=int(form.get('gio_den', '')), gio_mac_dinh=int(form.get('gio_mac_dinh', '')))
    except ValueError: raise BusinessError('Thiết lập chung phải là số nguyên.')
    if cd['han_chot'] <= dung[-1]['days']: raise BusinessError('Hạn chót chờ thanh lý phải LỚN HƠN số ngày của lần nhắc cuối (%d).' % dung[-1]['days'])
    if not (0 <= cd['gio_tu'] < cd['gio_den'] <= 24) or not (cd['gio_tu'] <= cd['gio_mac_dinh'] < cd['gio_den']): raise BusinessError('Khung giờ gửi không hợp lệ (giờ mặc định phải nằm trong khung).')
    cd['xung_ho_mac_dinh'] = (str(form.get('xung_ho_mac_dinh', '')).strip() or XUNG_HO_MAC_DINH)[:30]
    for k in KHOA_TU:
        ds = [w.strip() for w in str(form.get(k, cu[k + '_goc'])).split(',') if w.strip()]
        if any(' ' in w or len(w) > 12 for w in ds): raise BusinessError('Danh sách tiền tố / chữ lót: mỗi mục là MỘT từ, ngăn bằng dấu phẩy.')
        cd[k] = ', '.join(dict.fromkeys(ds))[:200]
    trung = set(w.casefold() for w in cd['tien_to_chi'].split(', ') + cd['lot_chi'].split(', ')) & set(w.casefold() for w in cd['tien_to_anh'].split(', ') + cd['lot_anh'].split(', ')) - {''}
    if trung: raise BusinessError('Từ nằm ở cả hai phía Anh và Chị: ' + ', '.join(sorted(trung)))
    for m, c in zip(moi, cu['muc']):
        old = dict(days=c['days'], label=c['label'], notes=c['notes'], active=c['active']); new = dict(days=m['days'], label=m['label'], notes=m['notes'], active=m['active'])
        if old != new:
            db.execute('UPDATE cd_sms_rules SET days=%s,label=%s,notes=%s,active=%s,updated_username=%s,updated_at=%s WHERE level_no=%s', (m['days'], m['label'], m['notes'], 1 if m['active'] else 0, uname, bay_gio, m['no']))
            db.execute('INSERT INTO cd_sms_rules_history (changed_at,username,target,old_json,new_json) VALUES (%s,%s,%s,%s,%s)', (bay_gio, uname, 'nhac%d' % m['no'], json.dumps(old, ensure_ascii=False), json.dumps(new, ensure_ascii=False)))
    for k, v in cd.items():
        old = str(cu[k + '_goc']) if k in KHOA_TU else (str(cu[k]) if k in cu else '')
        if old != str(v):
            db.execute('INSERT INTO cd_sms_settings (k,v,updated_username,updated_at) VALUES (%s,%s,%s,%s) ON DUPLICATE KEY UPDATE v=VALUES(v),updated_username=VALUES(updated_username),updated_at=VALUES(updated_at)', (k, str(v), uname, bay_gio))
            db.execute('INSERT INTO cd_sms_rules_history (changed_at,username,target,old_json,new_json) VALUES (%s,%s,%s,%s,%s)', (bay_gio, uname, k, json.dumps(old), json.dumps(str(v))))
    g.pop('sms_quy_tac', None)

def so_bang():
    d = str(current_app.config.get('ZNS_DB', 'khj_bl'))
    if not re.fullmatch(r'[A-Za-z0-9_]+', d): raise BusinessError('Cấu hình ZNS_DB không hợp lệ.')
    return '`%s`.`zalo_messages`' % d

def bang_mau():
    return so_bang().replace('zalo_messages', 'zalo_templates')

def nguoi():
    return session.get('user_id'), str(session.get('user') or '')[:150]

def chuan_hoa_sdt(value):
    """Chép ``normalize_vn_phone`` CARE360: (digits '84…', local '0…', masked, hash) hoặc None."""
    digits = re.sub(r'\D', '', str(value or ''))
    if digits.startswith('0') and len(digits) == 10: digits = '84' + digits[1:]
    if not (digits.startswith('84') and len(digits) == 11): return None
    local = '0' + digits[2:]
    if local[1] not in '35789': return None
    return digits, local, local[:3] + '***' + local[-3:], hashlib.sha256((TIEN_TO_BAM + digits).encode()).hexdigest()

def _tu(ten):
    return ' '.join(str(ten or '').split()).split(' ') if str(ten or '').strip() else []

def anh_chi_cua(gioi_tinh, ten=None):
    """Xưng hô suy NGAY TỪ customer_name (GĐ chốt 18/09/2026), danh sách từ nằm ở cd_sms_settings:
      1. TIỀN TỐ đầu tên (phải còn ít nhất 1 từ phía sau): Chị/Cô/Bà/Dì → Chị · Anh/Chú/Cậu/Bác/Ông → Anh.
      2. CHỮ LÓT — chỉ xét tên từ 3 TỪ trở lên và chỉ các từ ở GIỮA (không phải họ, không phải tên gọi):
         Thị/Mỹ → Chị · Văn/Tấn → Anh. Từ khớp ĐẦU TIÊN tính từ trái sang quyết định.
      3. Không khớp gì ⇒ chỉ tin I_CUSTOMER.Gender = True → Anh (GĐ: ~99% đúng). Gender = False KHÔNG đủ tin (phần lớn là
         giá trị mặc định lúc nhập khách) ⇒ tên chưa xác nhận là nữ thì coi như None ⇒ xưng hô mặc định "Anh/Chị".
    So khớp không phân biệt HOA/thường nhưng PHẢI ĐÚNG DẤU ("Van" không phải "Văn", "Vân" là tên nữ)."""
    qt = quy_tac(); tu = [w.casefold() for w in _tu(ten)]
    if len(tu) >= 2:
        if tu[0] in qt['tien_to_chi']: return 'Chị'
        if tu[0] in qt['tien_to_anh']: return 'Anh'
    if len(tu) >= 3:
        for w in tu[1:-1]:
            if w in qt['lot_chi']: return 'Chị'
            if w in qt['lot_anh']: return 'Anh'
    if gioi_tinh is True: return 'Anh'
    return qt['xung_ho_mac_dinh']      # Gender False/None: không gọi 'Chị' khi tên chưa xác nhận là nữ

def ten_khong_tien_to(ten):
    """Bỏ tiền tố xưng hô ở ĐẦU tên (cả hai danh sách): 'Chị Quỳnh' → 'Quỳnh' · 'Chú Tư Hùng' → 'Tư Hùng'. Chỉ còn 1 từ thì giữ nguyên."""
    tu = _tu(ten); qt = quy_tac()
    if len(tu) >= 2 and tu[0].casefold() in qt['tien_to_chi'] + qt['tien_to_anh']: tu = tu[1:]
    return ' '.join(tu)

def che_ma(ma):
    """'KH22604018242' → 'KH******18242': giữ 2 ký tự đầu + 5 ký tự cuối, che phần giữa (GĐ chốt 18/09/2026).
    Tin có thể tới nhầm SĐT (khách khai sai số) ⇒ không lộ trọn mã phiếu; khách thật vẫn nhận ra phiếu của mình.
    Chạy lại trên chuỗi đã che vẫn ra y nguyên. Mã quá ngắn (≤ 7 ký tự) thì chỉ giữ 3 ký tự cuối."""
    ma = str(ma or '').strip()
    if len(ma) <= 7: return '*' * max(0, len(ma) - 3) + ma[-3:]
    return ma[:2] + '*' * (len(ma) - 7) + ma[-5:]

def phan_loai(d):
    """Mức TỚI HẠN theo số ngày: '' | nhac1..nhac4 (d ≥ 67 vẫn là nhac4 — tin cuối phải tới tay khách trước khi thanh lý)."""
    for m in quy_tac()['dang_dung']:
        if d >= m['days']: return m['key']
    return ''

def mau_zns():
    row = db.one('SELECT id,template_id,template_name,status,active,price_sdt,params_json FROM ' + bang_mau() + ' WHERE template_id=%s', (MAU_ZNS,))
    if not row: raise BusinessError('Chưa có mẫu ZNS %s trong khj_bl.zalo_templates.' % MAU_ZNS)
    return row

def gio_gui_mac_dinh():
    n = now(); muc = n.replace(hour=quy_tac()['gio_mac_dinh'], minute=0, second=0)
    return muc if n < muc - timedelta(minutes=30) else muc + timedelta(days=1)

def kiem_gio(dt):
    qt = quy_tac()
    if not (qt['gio_tu'] <= dt.hour < qt['gio_den']): raise BusinessError('Giờ gửi phải trong %d:00–%d:00.' % (qt['gio_tu'], qt['gio_den']))
    if dt < now() - timedelta(minutes=1): raise BusinessError('Giờ gửi đã qua.')

def dedupe(loan_id, cycle, level):
    return hashlib.sha256(('%s|%s|%s|%s|%s' % (OA_ID, NGUON, loan_id, cycle, level)).encode()).hexdigest()

# ── ĐỒNG BỘ + TỰ HỦY + ĐỐI SOÁT ────────────────────────────────────────────────────────────────
def dong_bo():
    """Kéo trạng thái từ sổ KHBL về cd_sms_log (theo zalo id, chỉ dòng khcd_pawn). Trả dict đối soát."""
    ensure_schema(); bay_gio = now()
    mo = db.all("SELECT id,zalo_message_id,status FROM cd_sms_log WHERE status NOT IN ('cancelled','failed_permanent','seen','missing')")
    mat = 0
    if mo:
        ids = [r['zalo_message_id'] for r in mo if r['zalo_message_id']]
        so = {}
        if ids:
            so = {r['id']: r for r in db.all('SELECT id,status,sent_at,scheduled_at,cancel_reason FROM ' + so_bang() + ' WHERE source_type=%s AND id IN (' + ','.join(['%s'] * len(ids)) + ')', [NGUON] + ids)}
        for r in mo:
            z = so.get(r['zalo_message_id'])
            if not z:
                db.execute("UPDATE cd_sms_log SET status='missing',synced_at=%s WHERE id=%s", (bay_gio, r['id'])); mat += 1
            elif z['status'] != r['status']:
                db.execute('UPDATE cd_sms_log SET status=%s,sent_at=%s,scheduled_at=COALESCE(%s,scheduled_at),cancel_reason=%s,synced_at=%s WHERE id=%s',
                           (z['status'], z['sent_at'], z['scheduled_at'], z['cancel_reason'], bay_gio, r['id']))
    # Tin ĐANG CHỜ lên lịch trước khi có quy tắc che mã phiếu → che lại ở cả hai sổ (tin đã gửi thì để nguyên làm dấu vết).
    for r in db.all("SELECT id,zalo_message_id,vars_json FROM cd_sms_log WHERE status IN ('queued','retry')"):
        try: bien = json.loads(r['vars_json']) or {}
        except Exception: continue
        ma = bien.get('pawn_code')
        if ma and che_ma(ma) != ma:
            bien['pawn_code'] = che_ma(ma); bj = json.dumps(bien, ensure_ascii=False)
            db.execute('UPDATE ' + so_bang() + " SET template_data_json=%s,updated_at=%s WHERE id=%s AND source_type=%s AND status IN ('queued','retry')", (bj, bay_gio, r['zalo_message_id'], NGUON))
            db.execute('UPDATE cd_sms_log SET vars_json=%s WHERE id=%s', (bj, r['id']))
    mo_coi = db.one('SELECT COUNT(*) n FROM ' + so_bang() + ' z WHERE z.source_type=%s AND NOT EXISTS (SELECT 1 FROM cd_sms_log g WHERE g.zalo_message_id=z.id)', (NGUON,))['n']
    thieu = db.one("SELECT COUNT(*) n FROM cd_sms_log WHERE status='missing'")['n']
    return dict(thieu_ben_so=int(thieu), khong_co_log=int(mo_coi), vua_mat=mat)

def huy_tin_cho(loan_id, ly_do, giu_cycle=None):
    """Hủy mọi tin ĐANG CHỜ của phiếu (trừ chu kỳ ``giu_cycle``). Dùng khi có giao dịch mới / phiếu đóng."""
    ensure_schema(); bay_gio = now(); n = 0
    sql = "SELECT id,zalo_message_id FROM cd_sms_log WHERE loan_id=%s AND status IN ('queued','retry')"; params = [loan_id]
    if giu_cycle is not None: sql += ' AND cycle_log_id<>%s'; params.append(giu_cycle)
    for r in db.all(sql, params):
        if r['zalo_message_id']:
            db.execute('UPDATE ' + so_bang() + " SET status='cancelled',cancelled_at=%s,cancel_reason=%s,updated_at=%s WHERE id=%s AND source_type=%s AND status IN ('queued','retry')",
                       (bay_gio, str(ly_do)[:100], bay_gio, r['zalo_message_id'], NGUON))
        db.execute("UPDATE cd_sms_log SET status='cancelled',cancel_reason=%s,updated_username='hệ thống',updated_at=%s WHERE id=%s", (str(ly_do)[:100], bay_gio, r['id'])); n += 1
    return n

def sau_giao_dich(loan_id):
    """Móc sau khi quầy chốt / hủy phiên: khách vừa giao dịch thì tin nhắc của chu kỳ cũ phải hủy NGAY
    (KHBL gửi "mù" theo giờ hẹn). KHÔNG BAO GIỜ ném lỗi ra luồng tiền."""
    try: return huy_tin_cho(loan_id, 'Phiếu có giao dịch mới — tự hủy tin nhắc')
    except Exception as exc:
        current_app.logger.warning('sms.sau_giao_dich(%s): %s', loan_id, exc); return 0

def ra_tin_cho():
    """Lưới an toàn khi mở trang: tin chờ mà phiếu đã đóng hoặc đã sang chu kỳ mới → hủy."""
    n = 0
    for r in db.all("SELECT g.loan_id,g.cycle_log_id,l.loan_state,(SELECT MAX(id) FROM cd_loan_logs x WHERE x.loan_id=g.loan_id AND x.operation_id<>8) cur "
                    "FROM cd_sms_log g LEFT JOIN cd_loans l ON l.id=g.loan_id WHERE g.status IN ('queued','retry') GROUP BY g.loan_id,g.cycle_log_id,l.loan_state"):
        if r['loan_state'] != 'ACTIVE': n += huy_tin_cho(r['loan_id'], 'Phiếu đã đóng — tự hủy tin nhắc')
        elif int(r['cur'] or 0) != int(r['cycle_log_id']): n += huy_tin_cho(r['loan_id'], 'Phiếu có giao dịch mới — tự hủy tin nhắc', giu_cycle=int(r['cur'] or 0))
    return n

# ── ỨNG VIÊN ──────────────────────────────────────────────────────────────────────────────────
def ung_vien(args):
    ensure_schema(); qt = quy_tac(); MUC_NHAN = qt['nhan']; cuoi = muc_cuoi()
    hom_nay = today(); q = (args.get('q') or '').strip()[:60]; loai = args.get('loai', 'can_nhac'); tu = args.get('tu', '')
    where = " WHERE l.loan_state='ACTIVE'"; params = []
    if q: where += " AND (l.sku LIKE %s OR l.phone LIKE %s OR JSON_UNQUOTE(JSON_EXTRACT(l.customer_snapshot,'$.name')) LIKE %s)"; params += ['%' + q + '%'] * 3
    if tu in ('1', '2', '3'): where += ' AND l.safe=%s'; params.append(tu)
    rows = db.all("SELECT l.id,l.sku,l.phone,l.cust_id,l.principal_balance,l.due_at,l.safe,l.receipt_lost,"
                  "JSON_UNQUOTE(JSON_EXTRACT(l.customer_snapshot,'$.name')) customer_name,"
                  "COALESCE(g.last_at,l.opened_at) last_at,COALESCE(g.last_id,0) cycle,"
                  "c.muted,c.snooze_until,c.reason mute_reason,c.updated_username mute_by FROM cd_loans l "
                  "LEFT JOIN (SELECT loan_id,MAX(happened_at) last_at,MAX(id) last_id FROM cd_loan_logs WHERE operation_id<>8 GROUP BY loan_id) g ON g.loan_id=l.id "
                  "LEFT JOIN cd_sms_control c ON c.loan_id=l.id" + where + " ORDER BY g.last_at,l.id", params)
    # Lịch sử tin CHU KỲ HIỆN TẠI + tổng đã gửi mọi chu kỳ
    lich = {}
    for m in db.all("SELECT loan_id,cycle_log_id,level,status,scheduled_at,sent_at FROM cd_sms_log"):
        h = lich.setdefault(m['loan_id'], dict(tong_gui=0, gui_gan_nhat=None, theo_cycle={}))
        if m['status'] in TRANG_THAI['gui']:
            h['tong_gui'] += 1
            if m['sent_at'] and (not h['gui_gan_nhat'] or m['sent_at'] > h['gui_gan_nhat']): h['gui_gan_nhat'] = m['sent_at']
        h['theo_cycle'].setdefault(int(m['cycle_log_id']), []).append(m)
    for r in rows: r['pmv_cust_id'] = r['cust_id']
    if live.master.enabled():
        ten = {r['id']: r['customer_name'] for r in rows}; live.master.hydrate(rows)
        for r in rows: r['customer_name'] = r.get('customer_name') or ten[r['id']]
    out = []; dem = dict(can_nhac=0, nhac1=0, nhac2=0, nhac3=0, nhac4=0, da_lich=0, cho_thanh_ly=0, khong_nhac=0, loi=0, tat_ca=len(rows))
    for r in rows:
        r['d'] = (hom_nay - parse_date(r['last_at'])).days; r['cycle'] = int(r['cycle'])
        r['toi_han'] = phan_loai(r['d'])
        h = lich.get(r['id'], dict(tong_gui=0, gui_gan_nhat=None, theo_cycle={})); tin = h['theo_cycle'].get(r['cycle'], [])
        r['da_xu_ly'] = max([m['level'] for m in tin if m['status'] in DA_XU_LY] or [''], key=lambda k: THU_TU.get(k, 0))
        cho = [m for m in tin if m['status'] in TRANG_THAI['cho']]
        r['cho'] = len(cho); r['cho_luc'] = cho[0]['scheduled_at'] if cho else None; r['cho_muc'] = cho[0]['level'] if cho else ''
        r['co_loi'] = any(m['status'] in TRANG_THAI['loi'] + ('missing',) for m in tin) and THU_TU[r['da_xu_ly']] < THU_TU[r['toi_han']]
        r['tong_gui'] = h['tong_gui']; r['gui_gan_nhat'] = h['gui_gan_nhat']
        r['hoan'] = bool(r['snooze_until'] and parse_date(r['snooze_until']) >= hom_nay)
        r['khong_nhac'] = bool(r['muted']) or r['hoan']
        r['can_nhac'] = THU_TU[r['toi_han']] > THU_TU[r['da_xu_ly']]
        r['cho_thanh_ly'] = r['d'] >= qt['han_chot'] and bool(cuoi) and r['da_xu_ly'] == cuoi and not r['cho']
        r['muc'] = r['toi_han'] if r['can_nhac'] else ''
        r['muc_nhan'] = MUC_NHAN.get(r['toi_han'], 'Chưa tới hạn nhắc') if r['can_nhac'] else ('Chờ thanh lý' if r['cho_thanh_ly'] else ('Đã nhắc ' + MUC_NHAN.get(r['da_xu_ly'], '').lower().replace('nhắc ', '') if r['da_xu_ly'] else 'Chưa tới hạn nhắc'))
        r['mau'] = 'bad' if r['cho_thanh_ly'] else (MUC_MAU.get(r['toi_han'], '') if r['can_nhac'] else '')
        r['sdt'] = chuan_hoa_sdt(r.get('customer_phone') or r['phone']); r['sdt_hien'] = r.get('customer_phone') or r['phone'] or ''
        r['qua_han'] = max(0, (hom_nay - parse_date(r['due_at'])).days); r['anh_chi'] = anh_chi_cua(r.get('customer_gender'), r['customer_name']); r['ten_goi'] = ten_khong_tien_to(r['customer_name'])
        r['co_the_gui'] = r['can_nhac'] and bool(r['sdt']) and not r['khong_nhac']
        r['ly_do'] = ('Đang tắt nhắc' if r['muted'] else 'Hoãn đến ' + parse_date(r['snooze_until']).strftime('%d/%m/%Y')) if r['khong_nhac'] else ('Không có SĐT di động hợp lệ' if not r['sdt'] else ('Đã xử lý mức này' if not r['can_nhac'] else ''))
        if r['khong_nhac']: dem['khong_nhac'] += 1
        elif r['can_nhac']: dem['can_nhac'] += 1; dem[r['toi_han']] += 1
        if r['cho']: dem['da_lich'] += 1
        if r['cho_thanh_ly']: dem['cho_thanh_ly'] += 1
        if r['co_loi']: dem['loi'] += 1
        giu = (loai == 'tat_ca' or (loai == 'can_nhac' and r['can_nhac'] and not r['khong_nhac']) or (loai in THU_TU and loai and r['can_nhac'] and not r['khong_nhac'] and r['toi_han'] == loai)
               or (loai == 'da_lich' and r['cho']) or (loai == 'cho_thanh_ly' and r['cho_thanh_ly']) or (loai == 'khong_nhac' and r['khong_nhac']) or (loai == 'loi' and r['co_loi']))
        if giu: out.append(r)
    return out, dem

# ── SỔ LỊCH (bên phải) — đọc từ cd_sms_log đã đồng bộ ───────────────────────────────────────────
def lich_gui(tab, muc=''):
    """DS tin của Cầm đồ (cd_sms_log đã đồng bộ). tab: cho · gui · loi · huy · tat_ca — muc: '' | nhac1..nhac4."""
    if tab == 'tat_ca': st = sum(TRANG_THAI.values(), ()) + ('missing',)
    else: st = TRANG_THAI.get(tab, TRANG_THAI['cho']) + (('missing',) if tab == 'loi' else ())
    where = ' WHERE status IN (' + ','.join(['%s'] * len(st)) + ')'; params = list(st)
    if muc in THU_TU and muc: where += ' AND level=%s'; params.append(muc)
    rows = db.all('SELECT * FROM cd_sms_log' + where + ' ORDER BY ' + ('scheduled_at,id' if tab == 'cho' else 'updated_at DESC,id DESC') + ' LIMIT 500', params)
    nhan = quy_tac()['nhan']
    for m in rows:
        try: m['bien'] = json.loads(m['vars_json']) or {}
        except Exception: m['bien'] = {}
        if m['bien'].get('pawn_code'): m['bien']['pawn_code'] = che_ma(m['bien']['pawn_code'])   # tin cũ chưa che vẫn hiện dạng che
        m['scheduled_local'] = m['scheduled_at'].strftime('%Y-%m-%dT%H:%M') if m['scheduled_at'] else ''
        m['sua_duoc'] = m['status'] in ('queued', 'retry'); m['xoa_duoc'] = m['status'] not in TRANG_THAI['gui'] + ('sending',)
        m['muc_nhan'] = nhan.get(m['level'], m['level']); m['mau'] = MUC_MAU.get(m['level'], '')
        m['nhom'] = next((k for k, v in TRANG_THAI.items() if m['status'] in v), 'loi')
    tong = {k: 0 for k in TRANG_THAI}; theo_muc = {}
    for r in db.all('SELECT status,level,COUNT(*) n FROM cd_sms_log GROUP BY status,level'):
        nhom = next((k for k, v in TRANG_THAI.items() if r['status'] in v), 'loi'); tong[nhom] += int(r['n'])
        if tab == 'tat_ca' or nhom == tab: theo_muc[r['level']] = theo_muc.get(r['level'], 0) + int(r['n'])
    tong['tat_ca'] = sum(tong.values())
    return rows, tong, theo_muc

def xem_truoc(bien):
    return ('CẦM ĐỒ KIM HẠNH 2\n\nKính gửi {anh_chi} {customer_name},\n\nBộ phận Cầm đồ – Tiệm Vàng Kim Hạnh 2 xin thông báo: Mã phiếu cầm {pawn_code} '
            'đã quá hạn gia hạn kể từ ngày {promise_date}.\n\n– Số ngày quá hạn: {days}; Nhắc hẹn: {notes}\n\nKính đề nghị {anh_chi} thu xếp đến '
            'Tiệm Vàng Kim Hạnh 2 trong thời gian sớm nhất để thực hiện gia hạn hoặc hoàn tất giao dịch liên quan. Trân trọng!').format(
        **{k: bien.get(k, '…') for k in ('anh_chi', 'customer_name', 'pawn_code', 'promise_date', 'days', 'notes')})

def lich_su_phieu(loan_id):
    """Cho popup XEM biên nhận. Không ném lỗi."""
    try:
        ensure_schema()
        rows = db.all('SELECT level,status,scheduled_at,sent_at,d_days,vars_json,created_username,cancel_reason FROM cd_sms_log WHERE loan_id=%s ORDER BY id DESC LIMIT 20', (loan_id,))
        for m in rows:
            m['muc_nhan'] = quy_tac()['nhan'].get(m['level'], m['level'])
            try: m['notes'] = (json.loads(m['vars_json']) or {}).get('notes', '')
            except Exception: m['notes'] = ''
        ctl = db.one('SELECT muted,snooze_until,reason FROM cd_sms_control WHERE loan_id=%s', (loan_id,))
        return dict(rows=rows, control=ctl)
    except Exception: return dict(rows=[], control=None)

# ── GHI SỔ ────────────────────────────────────────────────────────────────────────────────────
def dung_bien(r, level, ghi_chu=None, anh_chi=None):
    cau = ghi_chu or next((m['notes'] for m in quy_tac()['muc'] if m['key'] == level), 'Nhắc hẹn')
    # GĐ chốt: d = số ngày quá hạn = hôm nay − ngày giao dịch gần nhất ⇒ promise_date là CHÍNH ngày giao dịch đó,
    # để câu "quá hạn kể từ ngày X – số ngày quá hạn: d" tự khớp nhau.
    return {'pawn_code': che_ma(r['sku'])[:30], 'customer_name': str(r.get('ten_goi') or ten_khong_tien_to(r['customer_name']) or 'Khách hàng')[:30],
            'anh_chi': str(anh_chi or r.get('anh_chi') or quy_tac()['xung_ho_mac_dinh'])[:30], 'promise_date': parse_date(r['last_at']).strftime('%d/%m/%Y'),
            'days': str(int(r['d'])), 'notes': dung_notes(cau, r, level)}

def len_lich(loan_ids, muc_chon, gio, ghi_chu):
    """Upsert: mỗi phiếu tối đa MỘT tin chờ trong chu kỳ. Có tin chờ → cập nhật; chưa có → INSERT cả sổ KHBL lẫn cd_sms_log."""
    if not loan_ids: raise BusinessError('Chưa chọn phiếu nào.')
    kiem_gio(gio); mau = mau_zns(); bay_gio = now(); uid, uname = nguoi(); ket = dict(them=0, sua=0, bo=[])
    ung, _ = ung_vien({'loai': 'tat_ca'}); theo_id = {str(r['id']): r for r in ung}
    for lid in loan_ids:
        r = theo_id.get(str(lid))
        if not r: ket['bo'].append('#%s không còn đang cầm' % lid); continue
        if r['khong_nhac']: ket['bo'].append(r['sku'] + ': ' + r['ly_do'].lower()); continue
        if not r['sdt']: ket['bo'].append(r['sku'] + ': không có SĐT di động'); continue
        level = muc_chon if muc_chon in THU_TU and muc_chon else r['toi_han']
        if not level: ket['bo'].append(r['sku'] + ': chưa tới hạn nhắc (%d ngày)' % r['d']); continue
        digits, local, masked, ph = r['sdt']; bien = dung_bien(r, level, ghi_chu); bien_json = json.dumps(bien, ensure_ascii=False)
        cho = db.one("SELECT id,zalo_message_id FROM cd_sms_log WHERE loan_id=%s AND cycle_log_id=%s AND status IN ('queued','retry') ORDER BY id DESC LIMIT 1", (r['id'], r['cycle']))
        if cho:
            db.execute('UPDATE ' + so_bang() + " SET scheduled_at=%s,template_data_json=%s,customer_name=%s,customer_phone=%s,recipient_masked=%s,recipient_hash=%s,updated_at=%s WHERE id=%s AND source_type=%s AND status IN ('queued','retry')",
                       (gio, bien_json, bien['customer_name'], local, masked, ph, bay_gio, cho['zalo_message_id'], NGUON))
            db.execute('UPDATE cd_sms_log SET scheduled_at=%s,vars_json=%s,d_days=%s,updated_username=%s,updated_at=%s WHERE id=%s', (gio, bien_json, r['d'], uname, bay_gio, cho['id'])); ket['sua'] += 1; continue
        if THU_TU[level] <= THU_TU[r['da_xu_ly']]: ket['bo'].append('%s: %s đã xử lý trong chu kỳ này' % (r['sku'], quy_tac()['nhan'].get(level, level))); continue
        khoa = dedupe(r['id'], r['cycle'], level); tracking = uuid.uuid4().hex[:32]
        cu = db.one('SELECT id,zalo_message_id,status FROM cd_sms_log WHERE dedupe_key=%s', (khoa,))
        if cu:   # tin cùng mức đã hủy/lỗi → mở lại chính dòng cũ (dedupe_key là UNIQUE ở cả hai sổ)
            db.execute('UPDATE ' + so_bang() + " SET status='queued',scheduled_at=%s,template_data_json=%s,attempt_count=0,next_retry_at=NULL,error_code=NULL,error_message=NULL,cancelled_at=NULL,cancel_reason=NULL,updated_at=%s WHERE id=%s AND source_type=%s",
                       (gio, bien_json, bay_gio, cu['zalo_message_id'], NGUON))
            db.execute("UPDATE cd_sms_log SET status='queued',scheduled_at=%s,vars_json=%s,d_days=%s,cancel_reason=NULL,sent_at=NULL,updated_username=%s,updated_at=%s WHERE id=%s", (gio, bien_json, r['d'], uname, bay_gio, cu['id'])); ket['them'] += 1; continue
        zid = db.execute('INSERT INTO ' + so_bang() + ' (oa_account_id,template_id,send_rule_id,external_template_id,channel,source_type,source_ref,trn_id,bill_code,cust_id,customer_name,customer_phone,'
                         'transaction_at,eligible_at,source_status,source_eligible,pay_amount,recipient_ciphertext,recipient_masked,recipient_hash,template_data_json,tracking_id,dedupe_key,status,scheduled_at,'
                         'attempt_count,estimated_cost,rule_snapshot_json,created_by,created_at,updated_at) VALUES (%s,%s,NULL,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s,%s,%s,%s,%s,%s,%s,%s,%s,0,%s,%s,%s,%s,%s)',
                         (OA_ID, mau['id'], mau['template_id'], 'phone', NGUON, str(r['id']), str(r['sku'])[:30], str(r['sku'])[:100], str(r['cust_id'] or '')[:50], bien['customer_name'], local,
                          r['last_at'], bay_gio, level, Decimal(r['principal_balance'] or 0), KHONG_MA_HOA, masked, ph, bien_json, tracking, khoa, 'queued', gio, mau['price_sdt'],
                          json.dumps({'rule_name': 'khcd_pawn_' + level, 'template_id': mau['id'], 'external_template_id': mau['template_id'], 'd': r['d'], 'cycle_log_id': r['cycle']}, ensure_ascii=False), uid, bay_gio, bay_gio))
        db.execute('INSERT INTO cd_sms_log (loan_id,sku,cycle_log_id,level,d_days,vars_json,zalo_message_id,tracking_id,dedupe_key,scheduled_at,status,created_by,created_username,updated_username,created_at,updated_at) '
                   "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'queued',%s,%s,%s,%s,%s)", (r['id'], r['sku'], r['cycle'], level, r['d'], bien_json, zid, tracking, khoa, gio, uid, uname, uname, bay_gio, bay_gio))
        ket['them'] += 1
    return ket

def _dong(mid):
    m = db.one('SELECT * FROM cd_sms_log WHERE id=%s', (mid,))
    if not m: raise BusinessError('Không thấy dòng lịch của Cầm đồ.')
    if m['status'] not in ('queued', 'retry'): raise BusinessError('Chỉ sửa / hủy được tin đang chờ gửi.')
    return m

def sua_dong(mid, gio, notes, anh_chi, level=None):
    """Sửa tin đang chờ: giờ gửi, (tuỳ chọn) xưng hô / câu nhắc, và RULE. Đổi rule ⇒ câu nhắc lấy lại theo rule mới,
    khóa chống trùng tính lại (phiếu + mốc + mức) ở CẢ HAI sổ; mức đó đã có tin khác trong chu kỳ thì từ chối."""
    m = _dong(mid); kiem_gio(gio); bien = json.loads(m['vars_json'] or '{}'); _, uname = nguoi(); bay_gio = now()
    if notes is not None and str(notes).strip(): bien['notes'] = str(notes)[:200]
    if anh_chi: bien['anh_chi'] = str(anh_chi)[:30]
    if bien.get('pawn_code'): bien['pawn_code'] = che_ma(bien['pawn_code'])
    level = level if level in THU_TU and level else m['level']; khoa = m['dedupe_key']
    if level != m['level']:
        if not any(x['key'] == level and x['active'] for x in quy_tac()['muc']): raise BusinessError('Rule này đang tắt trong ⚙ Quy tắc nhắc.')
        khoa = dedupe(m['loan_id'], m['cycle_log_id'], level)
        trung = db.one('SELECT id,status FROM cd_sms_log WHERE dedupe_key=%s AND id<>%s', (khoa, mid))
        if trung:
            if not xoa_dong(trung['id']): raise BusinessError('%s đã có tin ĐÃ GỬI trong chu kỳ này — không đổi sang rule đó được.' % quy_tac()['nhan'].get(level, level))
        try: moc = datetime.strptime(bien.get('promise_date', ''), '%d/%m/%Y')
        except ValueError: moc = bay_gio - timedelta(days=int(m['d_days']))
        cau = next(x['notes'] for x in quy_tac()['muc'] if x['key'] == level)
        bien['notes'] = dung_notes(cau, dict(last_at=moc, d=int(bien.get('days') or m['d_days'])), level)
    bj = json.dumps(bien, ensure_ascii=False)
    # KHÔNG dựa vào rowcount: MySQL chỉ đếm dòng THAY ĐỔI — lưu lại y nguyên trong cùng một giây sẽ ra 0 và báo lỗi oan.
    if not db.one('SELECT id FROM ' + so_bang() + " WHERE id=%s AND source_type=%s AND status IN ('queued','retry')", (m['zalo_message_id'], NGUON)):
        raise BusinessError('Tin không còn ở trạng thái chờ bên sổ KHBL — tải lại trang để đồng bộ.')
    db.execute('UPDATE ' + so_bang() + " SET scheduled_at=%s,template_data_json=%s,dedupe_key=%s,source_status=%s,updated_at=%s WHERE id=%s AND source_type=%s AND status IN ('queued','retry')",
               (gio, bj, khoa, level, bay_gio, m['zalo_message_id'], NGUON))
    db.execute('UPDATE cd_sms_log SET scheduled_at=%s,vars_json=%s,level=%s,dedupe_key=%s,updated_username=%s,updated_at=%s WHERE id=%s', (gio, bj, level, khoa, uname, bay_gio, mid))

def huy_dong(mid, ly_do):
    m = _dong(mid); _, uname = nguoi(); ly = str(ly_do or 'Cầm đồ hủy')[:100]
    db.execute('UPDATE ' + so_bang() + " SET status='cancelled',cancelled_at=%s,cancel_reason=%s,updated_at=%s WHERE id=%s AND source_type=%s AND status IN ('queued','retry')", (now(), ly, now(), m['zalo_message_id'], NGUON))
    db.execute("UPDATE cd_sms_log SET status='cancelled',cancel_reason=%s,updated_username=%s,updated_at=%s WHERE id=%s", (ly, uname, now(), mid))

def xoa_dong(mid):
    """XÓA HẲN một tin khỏi cả sổ KHBL lẫn cd_sms_log. Tin ĐÃ GỬI / đang gửi thì KHÔNG xóa (giữ dấu vết đối soát).
    Xóa xong, mức đó coi như chưa xử lý ⇒ phiếu hiện lại ở cột trái."""
    m = db.one('SELECT id,zalo_message_id,status FROM cd_sms_log WHERE id=%s', (mid,))
    if not m or m['status'] in TRANG_THAI['gui'] + ('sending',): return False
    if m['zalo_message_id']:
        db.execute('DELETE FROM ' + so_bang() + " WHERE id=%s AND source_type=%s AND status NOT IN ('sent','delivered','seen','sending')", (m['zalo_message_id'], NGUON))
        if db.one('SELECT id FROM ' + so_bang() + ' WHERE id=%s AND source_type=%s', (m['zalo_message_id'], NGUON)): return False   # bên sổ đã gửi mất rồi → giữ log
    db.execute('DELETE FROM cd_sms_log WHERE id=%s', (mid,)); return True

def db_rowcount(sql, params):
    with db.db().cursor() as cur:
        cur.execute(sql, params); return cur.rowcount

def dat_nhac(loan_id, che_do, den_ngay, ly_do):
    """che_do: 'tat' (tắt hẳn) · 'hoan' (hoãn đến ngày) · 'bat' (nhắc lại bình thường)."""
    ensure_schema(); uid, uname = nguoi()
    if not db.one('SELECT id FROM cd_loans WHERE id=%s', (loan_id,)): raise BusinessError('Không thấy biên nhận.')
    if che_do == 'bat':
        db.execute('DELETE FROM cd_sms_control WHERE loan_id=%s', (loan_id,)); return 0
    if not str(ly_do or '').strip(): raise BusinessError('Cần ghi lý do tắt / hoãn nhắc.')
    snooze = None
    if che_do == 'hoan':
        snooze = parse_date(den_ngay, 'Hoãn đến ngày')
        if snooze < today(): raise BusinessError('Ngày hoãn phải từ hôm nay trở đi.')
    elif che_do != 'tat': raise BusinessError('Chế độ không hợp lệ.')
    db.execute('INSERT INTO cd_sms_control (loan_id,muted,snooze_until,reason,updated_by,updated_username,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s) '
               'ON DUPLICATE KEY UPDATE muted=VALUES(muted),snooze_until=VALUES(snooze_until),reason=VALUES(reason),updated_by=VALUES(updated_by),updated_username=VALUES(updated_username),updated_at=VALUES(updated_at)',
               (loan_id, 1 if che_do == 'tat' else 0, snooze, str(ly_do)[:255], uid, uname, now()))
    return huy_tin_cho(loan_id, 'Tắt / hoãn nhắc: ' + str(ly_do)[:60])

# ── ROUTES ────────────────────────────────────────────────────────────────────────────────────
def _an_toan(fn, mac_dinh):
    try: return fn(), None
    except BusinessError as exc: return mac_dinh, str(exc)
    except Exception as exc:
        current_app.logger.warning('gui-sms: %s', exc)
        return mac_dinh, 'Chưa đọc được sổ tin ZNS (khj_bl.zalo_messages): ' + str(exc)[:160]

@bp.get('')
def trang():
    tab = request.args.get('tab', 'cho'); tab = tab if tab in TRANG_THAI or tab == 'tat_ca' else 'cho'
    muc_loc = request.args.get('muc', ''); muc_loc = muc_loc if muc_loc in THU_TU else ''
    doi_soat, loi0 = _an_toan(lambda: (ra_tin_cho(), dong_bo())[1] if not current_app.config['DB_READ_ONLY'] else dict(thieu_ben_so=0, khong_co_log=0, vua_mat=0), dict(thieu_ben_so=0, khong_co_log=0, vua_mat=0))
    (ung, dem), loi1 = _an_toan(lambda: ung_vien(request.args), ([], {}))
    (lich, tong, theo_muc), loi2 = _an_toan(lambda: lich_gui(tab, muc_loc), ([], dict({k: 0 for k in TRANG_THAI}, tat_ca=0), {}))
    mau, loi3 = _an_toan(mau_zns, None)
    filters = dict(q=request.args.get('q', ''), loai=request.args.get('loai', 'can_nhac'), tu=request.args.get('tu', ''), muc=muc_loc)
    canh_bao = list(dict.fromkeys(x for x in (loi0, loi1, loi2, loi3) if x))
    if mau and (mau['status'] != 'ENABLE' or not mau['active']): canh_bao.append('Mẫu ZNS %s "%s" đang %s trên Zalo OA — tin sẽ nằm chờ tới khi KHBL/CARE360 bật mẫu và bộ gửi.' % (mau['template_id'], mau['template_name'], mau['status']))
    if doi_soat['thieu_ben_so'] or doi_soat['khong_co_log']: canh_bao.append('ĐỐI SOÁT: %d tin có trong sổ Cầm đồ nhưng KHÔNG còn bên khj_bl.zalo_messages (xem tab Lỗi) · %d dòng khcd_pawn bên sổ KHBL không có log Cầm đồ.' % (doi_soat['thieu_ben_so'], doi_soat['khong_co_log']))
    return render_template('sms.html', title='Gửi SMS', ung=ung, dem=dem, lich=lich, tong=tong, theo_muc=theo_muc, tab=tab, filters=filters, mau=mau, canh_bao=canh_bao,
                           qt=quy_tac(), muc_nhan=quy_tac()['nhan'], han_chot=quy_tac()['han_chot'], bien_notes=BIEN_NOTES, duoc_sua_quy_tac=bool(getattr(g, 'auth_user', None) and g.auth_user.get('is_superuser')),
                           lich_su_qt=db.all('SELECT changed_at,username,target,old_json,new_json FROM cd_sms_rules_history ORDER BY id DESC LIMIT 12'), gio_mac_dinh=gio_gui_mac_dinh().strftime('%Y-%m-%dT%H:%M'), xem_truoc=xem_truoc, today_iso=str(today()))

def _ve():
    return redirect(url_for('sms.trang', **{k: v for k, v in request.form.items() if k in ('q', 'loai', 'tu', 'tab', 'muc') and v}))

def _gio():
    try: return datetime.strptime(request.form.get('gio', ''), '%Y-%m-%dT%H:%M')
    except ValueError: raise BusinessError('Giờ gửi không hợp lệ.')

@bp.post('/len-lich')
def len_lich_route():
    db.require_write()
    ket = len_lich(request.form.getlist('loan'), request.form.get('muc_chon') or '', _gio(), request.form.get('ghi_chu') or None)
    flash('Đã lên lịch %d tin mới, cập nhật %d tin đang chờ.' % (ket['them'], ket['sua']) + (' Bỏ qua: ' + '; '.join(ket['bo'][:6]) if ket['bo'] else ''), 'success' if not ket['bo'] else 'warning')
    return _ve()

@bp.post('/<int:mid>/sua')
def sua_route(mid):
    db.require_write(); sua_dong(mid, _gio(), request.form.get('notes'), request.form.get('anh_chi'), request.form.get('level')); flash('Đã cập nhật tin #%d.' % mid, 'success'); return _ve()

@bp.post('/<int:mid>/huy')
def huy_route(mid):
    db.require_write(); huy_dong(mid, request.form.get('ly_do')); flash('Đã hủy tin #%d.' % mid, 'success'); return _ve()

@bp.post('/doi-gio')
def doi_gio_route():
    db.require_write(); gio = _gio(); kiem_gio(gio); n = 0
    for mid in [int(x) for x in request.form.getlist('msg') if str(x).isdigit()]:
        try: m = _dong(mid)
        except BusinessError: continue
        if db.one('SELECT id FROM ' + so_bang() + " WHERE id=%s AND source_type=%s AND status IN ('queued','retry')", (m['zalo_message_id'], NGUON)):
            db.execute('UPDATE ' + so_bang() + " SET scheduled_at=%s,updated_at=%s WHERE id=%s AND source_type=%s AND status IN ('queued','retry')", (gio, now(), m['zalo_message_id'], NGUON))
            db.execute('UPDATE cd_sms_log SET scheduled_at=%s,updated_username=%s,updated_at=%s WHERE id=%s', (gio, nguoi()[1], now(), mid)); n += 1
    if not n: raise BusinessError('Chưa chọn tin nào đang chờ.')
    flash('Đã dời %d tin sang %s.' % (n, gio.strftime('%d/%m/%Y %H:%M')), 'success'); return _ve()

@bp.post('/phieu/<int:loan_id>/nhac')
def dat_nhac_route(loan_id):
    db.require_write(); che_do = request.form.get('che_do', '')
    n = dat_nhac(loan_id, che_do, request.form.get('den_ngay'), request.form.get('ly_do'))
    flash({'tat': 'Đã TẮT nhắc biên nhận này', 'hoan': 'Đã HOÃN nhắc biên nhận này', 'bat': 'Đã bật nhắc lại biên nhận này'}.get(che_do, 'Đã lưu') + ('; hủy %d tin đang chờ.' % n if n else '.'), 'success')
    return _ve()

@bp.post('/quy-tac')
def quy_tac_route():
    """Sửa quy tắc nhắc: chỉ tài khoản quản trị (lên lịch thì mọi tài khoản đều được)."""
    db.require_write()
    if not (getattr(g, 'auth_user', None) and g.auth_user.get('is_superuser')): raise BusinessError('Chỉ tài khoản quản trị được sửa quy tắc nhắc.')
    luu_quy_tac(request.form); flash('Đã lưu quy tắc nhắc. Tin đã lên lịch giữ nguyên nội dung cũ; quy tắc mới áp dụng từ lượt lên lịch kế tiếp.', 'success'); return _ve()

def _ids():
    ids = [int(x) for x in request.form.getlist('msg') if str(x).isdigit()]
    if not ids: raise BusinessError('Chưa tick tin nào.')
    return ids

@bp.post('/huy-nhom')
def huy_nhom_route():
    db.require_write(); n = 0
    for mid in _ids():
        try: huy_dong(mid, 'Cầm đồ hủy (nhóm) tại trang Gửi SMS'); n += 1
        except BusinessError: continue
    flash('Đã hủy %d tin đang chờ.' % n, 'success' if n else 'warning'); return _ve()

@bp.post('/xoa')
def xoa_route():
    db.require_write(); ids = _ids(); n = sum(1 for mid in ids if xoa_dong(mid))
    flash('Đã XÓA %d tin khỏi sổ.' % n + (' %d tin đã gửi / đang gửi được giữ lại làm dấu vết.' % (len(ids) - n) if len(ids) - n else ''), 'success' if n else 'warning'); return _ve()
