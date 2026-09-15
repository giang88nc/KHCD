"""Money rules. Legacy percent is monthly / 30; never reinterpret it as daily."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

VN = timezone(timedelta(hours=7))
ACTIVE = (1, 2, 3, 4, 7)
STATUSES = {0: 'Đã hủy', 1: 'Đang cầm', 2: 'Cầm thêm', 3: 'Trả bớt',
            4: 'Đã gia hạn', 5: 'Đã chuộc', 6: 'Đã thanh lý', 7: 'Báo mất'}
EVENTS = {'loan_convert':'Chuyển dữ liệu phiếu', 'create': 'Lập phiếu', 'renew': 'Gia hạn', 'redeem': 'Chuộc vàng',
          'edit': 'Sửa phiếu', 'cancel': 'Hủy phiếu', 'customer_create': 'Thêm khách hàng',
          'customer_edit': 'Sửa khách hàng', 'customer_delete': 'Lưu trữ khách hàng', 'customer_restore':'Khôi phục khách hàng'}

class BusinessError(ValueError):
    pass

def now():
    return datetime.now(VN).replace(tzinfo=None, microsecond=0)

def today():
    return now().date()

def decimal(value, label='Giá trị', minimum=Decimal('0'), maximum=Decimal('999999999999')):
    try:
        result = Decimal(str(value).strip().replace(',', '.'))
    except (InvalidOperation, ValueError):
        raise BusinessError(f'{label} phải là số hợp lệ.')
    if not result.is_finite() or result < minimum or result > maximum:
        raise BusinessError(f'{label} nằm ngoài khoảng cho phép ({minimum} – {maximum}).')
    return result

def money(value):
    return Decimal(str(value or 0)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)

def parse_date(value, label='Ngày'):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        raise BusinessError(f'{label} không hợp lệ.')

def quote(pawn, end, minimum_days=1):
    end = parse_date(end)
    start = parse_date(pawn.get('date2') or pawn['date1'])
    if end < start:
        raise BusinessError('Ngày xử lý không được trước ngày bắt đầu kỳ lãi.')
    days = max(minimum_days, (end-start).days)
    principal = decimal(pawn['value'], 'Tiền gốc', minimum=Decimal('1'))
    monthly = decimal(pawn['percent'], 'Lãi suất cũ', maximum=Decimal('300'))
    daily = monthly / Decimal('30')
    interest = money(principal * monthly * days / Decimal('3000'))
    return dict(start=start, end=end, days=days, principal=money(principal),
                daily_rate=daily, interest=interest, total=money(principal)+interest)

def date_range(args):
    mode = args.get('period', 'day')
    end = today()
    start = end.replace(day=1) if mode == 'month' else end
    if args.get('start'):
        start = parse_date(args['start'], 'Từ ngày')
    if args.get('end'):
        end = parse_date(args['end'], 'Đến ngày')
    if start > end or (end-start).days > 366:
        raise BusinessError('Chọn khoảng thời gian hợp lệ, tối đa 366 ngày.')
    return start, end, end+timedelta(days=1)
