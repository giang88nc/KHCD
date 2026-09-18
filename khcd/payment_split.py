"""Read both historical channel rows and consolidated native session payments."""
from decimal import Decimal


def split(row):
    amount = Decimal(str(row['amount']))
    cash, bank = row.get('cashPay'), row.get('cardPay')
    if cash is None and bank is None and row.get('channel') in ('CASH', 'BANK'):
        return (amount, Decimal(0)) if row['channel'] == 'CASH' else (Decimal(0), amount)
    if cash is None or bank is None:
        raise ValueError('Thiếu phân bổ tiền của phiên.')
    cash, bank = Decimal(str(cash)), Decimal(str(bank))
    if cash < 0 or bank < 0 or cash + bank != amount:
        raise ValueError('Phân bổ tiền không khớp tổng phiên.')
    return cash, bank


def reference(stamp, loan_id, log_id):
    if not 0 < int(loan_id) <= 99999 or not 0 < int(log_id) <= 99999:
        raise ValueError('Mã phiên vượt giới hạn 5 chữ số; cần nâng phiên bản mã đối soát.')
    return stamp.strftime('%y%m') + f'{int(loan_id):05d}{int(log_id):05d}'
