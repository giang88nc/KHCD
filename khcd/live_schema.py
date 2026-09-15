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
