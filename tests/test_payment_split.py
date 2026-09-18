import datetime as dt
from decimal import Decimal
import pytest
from khcd.payment_split import split, reference


def test_reference():
    assert reference(dt.datetime(2026,9,17),977,3435)=='26090097703435'
    with pytest.raises(ValueError): reference(dt.datetime(2026,9,17),977,100000)


def test_old_and_new_rows():
    assert split(dict(amount=100,channel='CASH'))==(Decimal(100),Decimal(0))
    assert split(dict(amount=100,channel='BANK'))==(Decimal(0),Decimal(100))
    assert split(dict(amount=100,channel=None,cashPay=40,cardPay=60))==(Decimal(40),Decimal(60))
    for row in [dict(amount=100,channel=None),dict(amount=100,channel=None,cashPay=40,cardPay=70)]:
        with pytest.raises(ValueError):split(row)


def test_new_payment_is_one_cash_row(monkeypatch):
    from khcd import live_loans as L
    saved=[]
    monkeypatch.setattr(L.db,'one',lambda *a:dict(loan_id=977,happened_at=dt.datetime(2026,9,17)))
    monkeypatch.setattr(L,'insert',lambda table,row:saved.append(row))
    L.post_payments(3435,Decimal(100),Decimal(30),{})
    assert len(saved)==1
    assert (saved[0]['channel'],saved[0]['amount'],saved[0]['cashPay'],saved[0]['cardPay'])==(None,100,100,0)
    assert saved[0]['payment_ref']=='26090097703435'
