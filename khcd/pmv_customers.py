"""Narrow SELECT-only adapter for the primary KK I_CUSTOMER, SQL Server 2005 compatible.

No arbitrary SQL input, stored procedure calls, DML, DDL, or fallback to a sandbox.
The connection is always rolled back and closed, including on query failure.
"""
from contextlib import contextmanager
import pyodbc
from flask import current_app
from .customer_compare import phone_key,identity_key


class Unavailable(Exception):
    pass


COLUMNS='CustID AS id,CustCode AS code,CustName AS name,Phone AS phone,CMND AS cccd,Address AS addr,Active AS active'


@contextmanager
def connection():
    config=current_app.config
    if config.get('TESTING'):
        raise Unavailable('Kết nối PMV thật bị tắt trong môi trường kiểm thử.')
    keys={'DRIVER':'PMV_MSSQL_ODBC_DRIVER','SERVER':'PMV_MSSQL_HOST','DATABASE':'PMV_MSSQL_DB',
          'UID':'PMV_MSSQL_USER','PWD':'PMV_MSSQL_PASSWORD','Encrypt':'PMV_MSSQL_ENCRYPT','TrustServerCertificate':'PMV_MSSQL_TRUST_CERT'}
    if not all(config.get(keys[k]) for k in ('DRIVER','SERVER','DATABASE','UID','PWD')):
        raise Unavailable('Chưa cấu hình nguồn khách PMV trên máy KK.')
    # ODBC brace quoting also protects passwords containing semicolons/braces.
    connection_string=';'.join(k+'={'+str(config[v]).replace('}','}}')+'}' for k,v in keys.items())+';APP=KHCD Customer Read;'
    conn=None
    try:
        conn=pyodbc.connect(connection_string,timeout=4,autocommit=False)
        conn.timeout=5
        yield conn
    except pyodbc.Error as error:
        current_app.logger.warning('PMV customer read unavailable: %s',type(error).__name__)
        raise Unavailable('Chưa đọc được khách PMV từ máy KK. Vui lòng thử lại; khách CĐ vẫn sử dụng bình thường.') from None
    finally:
        if conn is not None:
            try:conn.rollback()
            except pyodbc.Error:pass
            conn.close()


def _rows(cursor):
    names=[column[0] for column in cursor.description]
    return [dict(zip(names,row)) for row in cursor.fetchall()]


def _like(value):
    for char in ('\\','%','_','['):value=value.replace(char,'\\'+char)
    return '%'+value+'%'


def _matching_ids(conn,phones,identities):
    # Old SQL Server 2005: nested SQL REPLACE/CASE scans are too expensive.
    # Read only identity keys once per request, normalize locally, fetch matched
    # profiles by their indexed CustID. No stale cache or persistent customer copy.
    cursor=conn.cursor().execute('SELECT CustID,Phone,CMND FROM dbo.I_CUSTOMER')
    result=[]
    while True:
        rows=cursor.fetchmany(2000)
        if not rows:break
        for key,phone,identity in rows:
            if (phones and phone_key(phone) in phones) or (identities and identity_key(identity) in identities):
                result.append(str(key))
                if len(result)>1000:raise Unavailable('Có quá nhiều hồ sơ trùng thông tin. Cần đối soát riêng trước khi kết luận.')
    return result


def listing(q='',page=1):
    where='1=1';params=[]
    if q:
        where="(CustName LIKE ? ESCAPE '\\' OR Phone LIKE ? ESCAPE '\\' OR CMND LIKE ? ESCAPE '\\' OR CustCode LIKE ? ESCAPE '\\' OR CustID LIKE ? ESCAPE '\\')"
        params=[_like(q)]*5
    with connection() as conn:
        normalized=phone_key(q)
        if normalized:
            ids=_matching_ids(conn,{normalized},set())
            if ids:where='('+where+' OR CustID IN ('+','.join('?' for _ in ids)+'))';params.extend(ids)
        cursor=conn.cursor()
        total=cursor.execute('SELECT COUNT(*) FROM dbo.I_CUSTOMER WHERE '+where,params).fetchone()[0]
        cursor.execute('SELECT * FROM (SELECT '+COLUMNS+',ROW_NUMBER() OVER (ORDER BY CustName,CustID) AS rn FROM dbo.I_CUSTOMER WHERE '+where+') numbered WHERE rn>? AND rn<=? ORDER BY rn',params+[(page-1)*20,page*20])
        return _rows(cursor),total


def get(customer_id):
    with connection() as conn:
        rows=_rows(conn.cursor().execute('SELECT '+COLUMNS+' FROM dbo.I_CUSTOMER WHERE CustID=?',(customer_id,)))
        return rows[0] if rows else None


def find_candidates(records):
    phones=sorted({phone_key(r.get('phone')) for r in records}-{''})
    identities=sorted({identity_key(r.get('cccd')) for r in records}-{''})
    if not phones and not identities:return []
    with connection() as conn:
        ids=_matching_ids(conn,set(phones),set(identities))
        if not ids:return []
        return _rows(conn.cursor().execute('SELECT '+COLUMNS+' FROM dbo.I_CUSTOMER WHERE CustID IN ('+','.join('?' for _ in ids)+') ORDER BY CustID',ids))
