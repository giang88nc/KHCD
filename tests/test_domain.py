from datetime import date,datetime
from decimal import Decimal
import pytest
from khcd.domain import quote,decimal,BusinessError,parse_date,date_range

def pawn(**extra):
    return dict(value='10000000',percent='3',date1=datetime(2026,1,1),date2=None,**extra)

def test_legacy_monthly_rate_is_divided_by_30():
    q=quote(pawn(),date(2026,1,31))
    assert q['daily_rate']==Decimal('0.1')
    assert q['interest']==300000 and q['total']==10300000

def test_same_day_minimum_and_paid_same_day_exception():
    assert quote(pawn(),date(2026,1,1))['interest']==10000
    assert quote(pawn(),date(2026,1,1),0)['interest']==0

def test_calendar_days_across_leap_year():
    p=pawn();p['date1']=datetime(2024,2,28,23,59)
    assert quote(p,date(2024,3,1))['days']==2

def test_renewal_uses_latest_cycle_not_original_date():
    p=pawn();p['date2']=datetime(2026,1,20)
    assert quote(p,date(2026,1,31))['interest']==110000

def test_round_half_up_to_vnd_without_daily_rounding():
    p=pawn();p.update(value='1001',percent='1.5')
    assert quote(p,date(2026,1,2))['interest']==1
    assert quote(p,date(2026,1,4))['interest']==2

@pytest.mark.parametrize('value',['NaN','Infinity','-1','abc','1000000000000'])
def test_invalid_numbers_rejected(value):
    with pytest.raises(BusinessError):decimal(value)

def test_backwards_date_rejected():
    with pytest.raises(BusinessError):quote(pawn(),date(2025,12,31))

def test_bad_date_range():
    with pytest.raises(BusinessError):date_range({'start':'2026-02-01','end':'2026-01-01'})
    with pytest.raises(BusinessError):date_range({'start':'2020-01-01','end':'2026-01-01'})
