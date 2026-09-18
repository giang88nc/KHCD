"""Trang GIAO DỊCH (/camdo/giao-dich): danh sách + popup chi tiết, chỉ đọc."""
from test_native_loans import native,create,opdata

BASE='/camdo/giao-dich'

def test_listing_filters_and_popup(native,client):
    lid,_=create(client)
    r=client.post(f'/camdo/bien-nhan/{lid}/chot-phien',data=opdata(client,lid,4));assert r.status_code==200,r.get_data(as_text=True)
    html=client.get(BASE).get_data(as_text=True)
    assert 'KH2' in html and 'Gia hạn' in html and 'Cầm mới' in html and 'll-modal' in html
    assert 'Gia hạn</span>' in client.get(BASE+'?kind=4').get_data(as_text=True)
    assert 'data-loan=' not in client.get(BASE+'?d1=2020-01-01&d2=2020-01-31').get_data(as_text=True)
    assert client.get(BASE+'?d1=2020-01-01&d2=2026-01-01').status_code==400
    assert client.get('/giao-dich').status_code in (308,404)
    with native.app_context():
        from khcd import db
        logs=db.all('SELECT id,operation_id FROM cd_loan_logs WHERE loan_id=%s ORDER BY id',(lid,))
    popup=client.get(f'{BASE}/{logs[-1]["id"]}/xem');assert popup.status_code==200,popup.get_data(as_text=True)
    text=popup.get_data(as_text=True)
    assert 'Gia hạn' in text and 'Dòng tiền' in text and 'Biên nhận sau phiên' in text and 'Hẹn chuộc' in text and '<html' not in text
    first=client.get(f'{BASE}/{logs[0]["id"]}/xem').get_data(as_text=True)
    assert 'Cầm mới' in first and 'Tiệm chi' in first
    assert client.get(f'{BASE}/999999/xem').status_code==404

def test_listing_without_live_mode(app,client):
    r=client.get(BASE);assert r.status_code==200 and 'CD_LIVE' in r.get_data(as_text=True)
