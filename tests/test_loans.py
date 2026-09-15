import io
import json
from PIL import Image
from khcd import db, loan_conversion as C
from khcd.loan_images import legacy_path
from test_loan_conversion import receipt,preview,save

BASE='/camdo/bien-nhan'

def migrated(client,pid):
    plan=preview(client,pid);assert plan['can_convert'],plan['checks']
    response=save(client,pid,plan)
    assert response.status_code==200,response.text
    return response.json['loan_id']

def test_new_list_detail_reconcile_are_read_only(app,client,receipt):
    assert 'CONVERT_TEST' not in client.get(BASE).text
    lid=migrated(client,receipt)
    with app.app_context():before=C.target(receipt);source=C.source(receipt)
    listing=client.get(BASE);assert listing.status_code==200 and 'CONVERT_TEST' in listing.text
    detail=client.get(f'{BASE}/{lid}');assert detail.status_code==200,detail.text
    assert 'CU_TEST' in detail.text and '6.000.000' in detail.text and 'Chưa xác định' in detail.text
    result=client.get(f'{BASE}/{lid}/doi-soat');assert result.status_code==200,result.text
    assert result.json['errors']==0,result.json
    assert any(c['label'].startswith('Dòng tiền') for c in result.json['checks'])
    with app.app_context():assert C.target(receipt)==before and C.source(receipt)==source
    assert 'CONVERT_TEST' in client.get(BASE+'?q=CU_TEST').text
    assert 'CONVERT_TEST' in client.get(BASE+'?q=Khách').text
    assert 'CONVERT_TEST' not in client.get(BASE+'?state=REDEEMED').text
    assert client.get('/bien-nhan').status_code==308

def test_reconcile_shows_each_changed_field_and_missing_row(app,client,receipt):
    lid=migrated(client,receipt)
    with app.app_context():
        db.execute("UPDATE cd_loan_items SET description='Sai mô tả'")
        db.execute('UPDATE cd_loan_logs SET interest=123')
        db.execute("DELETE FROM cd_payments WHERE channel='BANK'")
        db.execute("UPDATE pawn SET note='Nguồn đã thay đổi' WHERE id=%s",(receipt,))
    checks=client.get(f'{BASE}/{lid}/doi-soat').json['checks']
    errors=[c for c in checks if c['state']=='error']
    assert any(c['label'].endswith('Mô tả') and c['target']=='Sai mô tả' for c in errors)
    assert any(c['label'].endswith('Lãi') and c['target']=='123' for c in errors)
    assert any(c['label'].endswith('BANK') and c['target']=='Thiếu' for c in errors)
    assert any(c['label'].endswith('Ghi chú') and c['source']=='Nguồn đã thay đổi' for c in errors)

def test_source_missing_does_not_hide_saved_receipt(app,client,receipt):
    lid=migrated(client,receipt)
    with app.app_context():db.execute('DELETE FROM pawn WHERE id=%s',(receipt,))
    assert client.get(f'{BASE}/{lid}').status_code==200
    result=client.get(f'{BASE}/{lid}/doi-soat').json
    assert result['errors'] and any(c['label']=='Đối soát nguồn' for c in result['checks'])

def test_legacy_image_reuse_missing_corrupt_and_path_guard(app,client,receipt,tmp_path):
    root=tmp_path/'photos';root.mkdir();app.config['LEGACY_PAWN_IMAGE_ROOT']=str(root)
    Image.new('RGB',(12,12),'red').save(root/'old.jpg')
    with app.app_context():db.execute("UPDATE pawn SET img1='old.jpg',img2='missing.jpg' WHERE id=%s",(receipt,))
    lid=migrated(client,receipt)
    url=f'{BASE}/{lid}/anh/legacy1'
    photo=client.get(url);assert photo.status_code==200 and photo.mimetype=='image/jpeg'
    assert photo.data==(root/'old.jpg').read_bytes() and photo.headers['Cache-Control']=='no-store'
    assert client.get(f'{BASE}/{lid}/anh/legacy2').status_code==404
    result=client.get(f'{BASE}/{lid}/doi-soat').json
    assert any(c['label']=='Ảnh phiếu cũ 2' and 'Thiếu tệp' in c['detail'] for c in result['checks'])
    (root/'old.jpg').write_bytes(b'not an image')
    assert client.get(url).status_code==404
    with app.app_context():
        for path in ('../old.jpg','C:/secret.jpg','file.jpg:stream','..\\old.jpg'):
            assert legacy_path(path)[0] is None
    with client.session_transaction() as session:session.clear()
    for path in (BASE,f'{BASE}/{lid}',url,f'{BASE}/{lid}/doi-soat'):
        assert client.get(path).status_code==302

def test_mysql_photo_reuse_detects_changed_bytes(app,client,receipt):
    output=io.BytesIO();Image.new('RGB',(12,12),'blue').save(output,format='JPEG');raw=output.getvalue()
    with app.app_context():db.execute("INSERT INTO khcd_pawn_photo (pawn_id,kind,data) VALUES (%s,'anh_sp1',%s)",(receipt,raw))
    lid=migrated(client,receipt);url=f'{BASE}/{lid}/anh/anh_sp1'
    assert client.get(url).data==raw
    with app.app_context():db.execute("UPDATE khcd_pawn_photo SET data=%s WHERE pawn_id=%s",(b'changed',receipt))
    assert client.get(url).status_code==404
    checks=client.get(f'{BASE}/{lid}/doi-soat').json['checks']
    assert any(c['label']=='Ảnh vàng 1' and c['state']=='error' for c in checks)

def test_staff_can_read_and_malformed_optional_data_is_reported(app,client,receipt):
    lid=migrated(client,receipt)
    with app.app_context():
        from khcd import auth
        db.execute('UPDATE '+auth.source_table()+' SET is_superuser=0 WHERE id=1')
        db.execute('UPDATE cd_loans SET documents_json=%s',(json.dumps({'pawn_photo_refs':'invalid'}),))
        db.execute("UPDATE cd_payments SET bank_snapshot='[]'")
    # Auth signature is refreshed after changing the source role.
    with app.app_context():
        user=auth.sync_user(username='khj_admin');signature=auth.session_signature(user)
    with client.session_transaction() as session:session['auth_signature']=signature
    assert client.get(BASE).status_code==200
    assert client.get(f'{BASE}/{lid}').status_code==200
    checks=client.get(f'{BASE}/{lid}/doi-soat').json['checks']
    assert any(c['label']=='Tham chiếu ảnh MySQL' and c['state']=='error' for c in checks)
