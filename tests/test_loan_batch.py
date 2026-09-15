from khcd import db,loan_conversion as C
from khcd.domain import now
from test_loan_conversion import receipt,preview,save,BASE

def clone(app,pid,sku,status=1):
    with app.app_context():
        row=db.one('SELECT * FROM pawn WHERE id=%s',(pid,));row.pop('id');row.update(sku=sku,status=status)
        new=C.insert('pawn',row)
        db.execute("INSERT INTO khcd_pawn_customer (pawn_id,pmv_cust_id,source,linked_at) VALUES (%s,'CU_TEST','selected',%s)",(new,now()))
        log=db.one('SELECT * FROM pawn_log WHERE pawn_id=%s',(pid,));log.pop('id');log['pawn_id']=new;C.insert('pawn_log',log)
        return new

def batch(client,pid,plan,**extra):
    return client.post(BASE+'/hang-loat/luu-phieu',data=dict(csrf_token='token',pid=pid,review_hash=plan['review_hash'],confirmed='yes',**extra))

def test_lists_all_active_operations_excludes_closed_and_marks_existing(app,client,receipt):
    ids=[receipt]+[clone(app,receipt,'STATE_'+str(i),i) for i in range(2,8)]
    clone(app,receipt,'CANCELLED',0)
    assert save(client,receipt,preview(client,receipt)).status_code==200
    data=client.get(BASE+'/dang-cam').json
    assert data['total']==5
    assert {r['status'] for r in data['rows']}=={1,2,3,4,7}
    assert next(r for r in data['rows'] if r['id']==receipt)['loan_id']

def test_cursor_lists_more_than_one_page_without_duplicates_or_new_rows(app,client,receipt):
    for n in range(201):clone(app,receipt,'BATCH_'+str(n))
    first=client.get(BASE+'/dang-cam').json
    assert len(first['rows'])==200 and first['next_after']
    late=clone(app,receipt,'ADDED_AFTER_LIST')
    second=client.get(BASE+'/dang-cam',query_string={'after':first['next_after'],'ceiling':first['ceiling']}).json
    ids=[r['id'] for r in first['rows']+second['rows']]
    assert len(ids)==len(set(ids))==202 and late not in ids
    assert second['next_after'] is None

def test_batch_failures_do_not_rollback_completed_receipts_and_retry_is_safe(app,client,receipt):
    changed=clone(app,receipt,'CHANGED');valid=clone(app,receipt,'VALID')
    plans={pid:preview(client,pid) for pid in [receipt,changed,valid]}
    with app.app_context():db.execute("UPDATE pawn SET note='changed after preview' WHERE id=%s",(changed,))
    first=batch(client,receipt,plans[receipt]);assert first.status_code==200
    assert batch(client,changed,plans[changed]).status_code==409
    assert batch(client,valid,plans[valid]).status_code==200
    assert batch(client,receipt,plans[receipt]).json['loan_id']==first.json['loan_id']
    with app.app_context():
        assert db.one('SELECT COUNT(*) n FROM cd_loans')['n']==2
        assert db.one('SELECT COUNT(*) n FROM pawn')['n']==3

def test_closed_receipt_cannot_be_submitted_to_batch_even_with_fresh_hash(app,client,receipt):
    with app.app_context():
        timestamp=db.one('SELECT date2 FROM pawn WHERE id=%s',(receipt,))['date2']
        db.execute('UPDATE pawn SET status=5 WHERE id=%s',(receipt,))
        db.execute('INSERT INTO pawn_log (pawn_id,status_id,date1,date2,date3,sotien,tienlai,total,mbank,percent,days) VALUES (%s,5,%s,%s,%s,10000000,0,10000000,0,3,30)',(receipt,timestamp,timestamp,timestamp))
    plan=preview(client,receipt);assert plan['can_convert'],plan['checks']
    result=batch(client,receipt,plan);assert result.status_code==409 and 'không còn đang cầm' in result.json['error']
    with app.app_context():assert db.one('SELECT COUNT(*) n FROM cd_loans')['n']==0

def test_batch_auth_confirmation_csrf_and_readonly(app,client,receipt,monkeypatch):
    plan=preview(client,receipt)
    assert client.post(BASE+'/hang-loat/luu-phieu',data={'pid':receipt}).status_code==400
    assert client.post(BASE+'/hang-loat/luu-phieu',data={'csrf_token':'token','pid':receipt,'review_hash':plan['review_hash']}).status_code==409
    app.config['DB_READ_ONLY']=True
    assert batch(client,receipt,plan).status_code==409
    from khcd import auth
    monkeypatch.setattr(auth,'current_user',lambda:dict(is_superuser=False))
    assert client.get(BASE+'/dang-cam').status_code==403
    assert batch(client,receipt,plan).status_code==403
