"""Read-only KHBL buy prices; no legacy price fallback."""
import re
import pymysql
from flask import current_app
from . import db
from .domain import BusinessError

TYPES=[('61','610','VÀNG 610','chỉ'),('99','9999','VÀNG 9999','chỉ'),('bk','BK','BẠCH KIM','gram'),('vt','VT','VÀNG TRẮNG','gram'),('sjc','SJC','SJC','chỉ'),('98','980','VÀNG 980','chỉ')]

def options():
    database=current_app.config.get('GOLD_PRICE_DB','khj_bl')
    if not re.fullmatch(r'[A-Za-z0-9_]+',database):raise BusinessError('Cấu hình nguồn giá vàng không hợp lệ.')
    try:rows=db.all('SELECT id,gold_type,buy,effective_at FROM `'+database+'`.gold_prices WHERE is_current=1 ORDER BY id DESC')
    except pymysql.MySQLError as exc:raise BusinessError('Không đọc được giá vàng từ khj_bl.gold_prices. Chưa thể định giá hoặc thanh lý theo giá thực tế.') from exc
    prices={}
    for row in rows:prices.setdefault(str(row['gold_type']).upper(),row)
    result=[]
    for code,kind,name,unit in TYPES:
        price=prices.get(kind)
        result.append(dict(id=code,name=name,unit=unit,price=price['buy'] if price else 0,price_id=price['id'] if price else None,effective_at=str(price['effective_at']) if price else None,price_source='khj_bl.gold_prices.buy'))
    return result+[dict(id='KHAC',name='KHÁC',unit='món',price=0)]
