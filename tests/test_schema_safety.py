from khcd import db,loan_conversion as C
from scripts.migrate import upgrade
from test_loan_conversion import receipt,preview,save


def test_reimported_myisam_is_blocked_at_preview_and_fixed_by_upgrade(app,client,receipt):
    with app.app_context():
        db.execute('ALTER TABLE pawn ENGINE=MyISAM')
        db.execute('ALTER TABLE pawn_log ENGINE=MyISAM')
        before=C.source(receipt)
    p=preview(client,receipt)
    assert not p['can_convert']
    problem=next(c for c in p['checks'] if c['code']=='TRANSACTION_SCHEMA')
    assert 'pawn=MyISAM' in problem['detail'] and 'pawn_log=MyISAM' in problem['detail']
    assert save(client,receipt,p).status_code==409
    with app.app_context():
        # Migration uses a normal tuple cursor, while the app uses DictCursor.
        import pymysql
        cfg=app.config
        connection=pymysql.connect(host=cfg['DB_HOST'],port=int(cfg['DB_PORT']),user=cfg['DB_USER'],password=cfg['DB_PASSWORD'],database=cfg['DB_NAME'],autocommit=True)
        try:upgrade(connection)
        finally:connection.close()
        db.require_write()
        assert C.source(receipt)==before
    p=preview(client,receipt);assert p['can_convert'],p['checks']
    assert save(client,receipt,p).status_code==200
