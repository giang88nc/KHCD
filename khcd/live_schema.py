"""Additive upgrade for native loans. Never modify legacy business rows."""
def upgrade(conn):
    with conn.cursor() as c:
        c.execute('ALTER TABLE cd_loans MODIFY legacy_pawn_id INT NULL')
        c.execute('ALTER TABLE cd_loan_logs MODIFY legacy_log_id INT NULL')
        changes={'cd_loans':{'version':'INT NOT NULL DEFAULT 0','count_print':'INT UNSIGNED NOT NULL DEFAULT 0'},'cd_loan_logs':{
          'request_key':'VARCHAR(64) NULL','note':'VARCHAR(255) NULL','actor_id':'BIGINT NULL',
          'employee_id':'VARCHAR(30) NULL','reverses_log_id':'BIGINT NULL'}}
        for table,cols in changes.items():
            c.execute('SHOW COLUMNS FROM '+table);names={r[0] if not isinstance(r,dict) else r['Field'] for r in c.fetchall()}
            for name,typ in cols.items():
                if name not in names:c.execute('ALTER TABLE '+table+' ADD COLUMN '+name+' '+typ)
        c.execute('SHOW INDEX FROM cd_loan_logs');indexes={r[2] if not isinstance(r,dict) else r['Key_name'] for r in c.fetchall()}
        if 'uq_cd_request' not in indexes:c.execute('ALTER TABLE cd_loan_logs ADD UNIQUE KEY uq_cd_request(request_key)')
        if 'uq_cd_reverse' not in indexes:c.execute('ALTER TABLE cd_loan_logs ADD UNIQUE KEY uq_cd_reverse(reverses_log_id)')
    upgrade_payments(conn)


def upgrade_payments(conn):
    """Additive only: historical IDs/channel rows and amounts remain untouched."""
    with conn.cursor() as c:
        c.execute('SHOW COLUMNS FROM cd_payments')
        names={r[0] if not isinstance(r,dict) else r['Field'] for r in c.fetchall()}
        for name,typ in {'cashPay':'DECIMAL(18,0) NULL','cardPay':'DECIMAL(18,0) NULL',
                         'payment_ref':'VARCHAR(14) NULL',
                         'session_slot':'BIGINT GENERATED ALWAYS AS (CASE WHEN channel IS NULL THEN log_id ELSE NULL END) STORED'}.items():
            if name not in names:c.execute('ALTER TABLE cd_payments ADD COLUMN '+name+' '+typ)
        c.execute('ALTER TABLE cd_payments MODIFY channel VARCHAR(10) NULL')
        c.execute('SHOW INDEX FROM cd_payments')
        indexes={r[2] if not isinstance(r,dict) else r['Key_name'] for r in c.fetchall()}
        if 'uq_cd_session_payment' not in indexes:c.execute('ALTER TABLE cd_payments ADD UNIQUE KEY uq_cd_session_payment(session_slot)')
        if 'uq_cd_payment_ref' not in indexes:c.execute('ALTER TABLE cd_payments ADD UNIQUE KEY uq_cd_payment_ref(payment_ref)')
        c.execute("SELECT CONSTRAINT_NAME FROM information_schema.TABLE_CONSTRAINTS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='cd_payments' AND CONSTRAINT_NAME='ck_cd_payment_split'")
        if not c.fetchone():
            c.execute('ALTER TABLE cd_payments ADD CONSTRAINT ck_cd_payment_split CHECK '
                      '((channel IS NOT NULL AND cashPay IS NULL AND cardPay IS NULL) OR '
                      '(cashPay IS NOT NULL AND cardPay IS NOT NULL AND cashPay>=0 AND cardPay>=0 AND cashPay+cardPay=amount))')
