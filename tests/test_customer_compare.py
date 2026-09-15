import pytest
from khcd import customer_compare as compare,pmv_customers as pmv,db


@pytest.mark.parametrize('value,expected',[
    ('0901234567','0901234567'),('+84 901.234.567','0901234567'),('0084901234567','0901234567'),
    ('84901234567','0901234567'),('090\u00a0123 4567','0901234567'),('0901234567 / 0902222222',''),
    ('abc0901234567',''),('',''),('123',''),('0901234567x','')])
def test_normalize_for_comparison_only(value,expected):
    assert compare.phone_key(value)==expected


def test_candidates_do_not_merge_and_conflicting_identity():
    customer={'phone':'0901234567','cccd':'000000000001'}
    one={'id':'PMV-A','phone':'+84901234567','cccd':'000000000002'}
    two={'id':'PMV-B','phone':'0901234567','cccd':'000000000001'}
    assert compare.status(customer,compare.candidates(customer,[one]))['key']=='conflict'
    assert compare.status(customer,compare.candidates(customer,[one,two]))['key']=='multiple'
    assert compare.status(customer,compare.candidates(customer,[two]))['key']=='candidate'
    assert compare.status({'phone':'','cccd':''},[])['key']=='insufficient'
    assert one['phone']=='+84901234567'


def test_field_comparison_keeps_raw_values():
    left={'name':' Nguyễn An ','phone':'+84 901234567','cccd':'000000000001','addr':'Địa chỉ cũ'}
    right={'name':'nguyễn an','phone':'0901234567','cccd':'000000000002','addr':''}
    rows={r['field']:r for r in compare.comparison(left,right)}
    assert rows['phone']['state']=='same' and rows['phone']['cd']=='+84 901234567'
    assert rows['cccd']['state']=='different'
    assert rows['addr']['state']=='missing'
    assert left['addr']=='Địa chỉ cũ'


def create_local(client):
    response=client.post('/camdo/lap-phieu/khach-hang',data=dict(csrf_token='token',name='Khách CĐ thử',phone='0901234567',cccd='000000000001',addr='Địa chỉ CĐ'))
    return response.json['customer']['id']


def test_both_tabs_comparison_and_no_customer_changes(app,client,monkeypatch):
    cid=create_local(client)
    remote={'id':'001-PMV','code':'KH001','name':'<script>alert(1)</script>','phone':'+84901234567','cccd':'000000000001','addr':'Địa chỉ PMV','active':'1'}
    monkeypatch.setattr(pmv,'listing',lambda q,page:([remote.copy()],1))
    monkeypatch.setattr(pmv,'find_candidates',lambda rows:[remote.copy()])
    monkeypatch.setattr(pmv,'get',lambda key:remote.copy() if key==remote['id'] else None)
    with app.app_context():before=db.one('SELECT * FROM customer WHERE id=%s',(cid,))
    for path in ['/camdo/khach-hang','/camdo/khach-hang?tab=pmv',f'/camdo/khach-hang/doi-chieu?cd_id={cid}', '/camdo/khach-hang/doi-chieu?tab=pmv&pmv_id=001-PMV']:
        response=client.get(path)
        assert response.status_code==200,response.text
        assert '<script>alert(1)</script>' not in response.text
    detail=client.get(f'/camdo/khach-hang/doi-chieu?cd_id={cid}')
    assert '001-PMV' in detail.text and 'Địa chỉ CĐ' in detail.text and 'Địa chỉ PMV' in detail.text
    assert '&lt;script&gt;' in detail.text
    assert client.get(f'/camdo/khach-hang/doi-chieu?cd_id={cid}&pmv_id=non-candidate').status_code==404
    assert client.post(f'/camdo/khach-hang/doi-chieu?cd_id={cid}',data={'csrf_token':'token'}).status_code==405
    with app.app_context():
        assert db.one('SELECT * FROM customer WHERE id=%s',(cid,))==before
        assert db.one('SELECT COUNT(*) n FROM pawn')['n']==0
    assert app.test_client().get('/camdo/khach-hang?tab=pmv').status_code==302


def test_source_failure_is_not_missing_and_cd_stays_usable(app,client,monkeypatch):
    cid=create_local(client)
    def failed(*a,**kw):raise pmv.Unavailable('Nguồn thử đang lỗi')
    monkeypatch.setattr(pmv,'listing',failed);monkeypatch.setattr(pmv,'find_candidates',failed)
    local=client.get('/camdo/khach-hang')
    assert local.status_code==200 and 'Khách CĐ thử' in local.text and 'Chưa đối chiếu' in local.text
    assert 'Chưa tìm thấy đối ứng' not in local.text
    remote=client.get('/camdo/khach-hang?tab=pmv')
    assert remote.status_code==200 and 'không khả dụng' in remote.text
    assert 'Không tìm thấy khách hàng.' not in remote.text
    detail=client.get(f'/camdo/khach-hang/doi-chieu?cd_id={cid}')
    assert 'Nguồn thử đang lỗi' in detail.text and 'Chưa có hồ sơ đối ứng' not in detail.text


def test_multiple_candidates_require_selection(client,monkeypatch):
    cid=create_local(client)
    rows=[{'id':f'PMV-{i}','name':f'Ứng viên {i}','phone':'0901234567','cccd':'000000000001','addr':'','code':''} for i in (1,2)]
    monkeypatch.setattr(pmv,'find_candidates',lambda _:rows)
    page=client.get(f'/camdo/khach-hang/doi-chieu?cd_id={cid}')
    assert 'Nhiều ứng viên' in page.text and 'Chưa chọn hồ sơ PMV' in page.text
    chosen=client.get(f'/camdo/khach-hang/doi-chieu?cd_id={cid}&pmv_id=PMV-2')
    assert 'Thông tin đặt cạnh nhau' in chosen.text


def test_test_environment_cannot_connect_to_live_pmv(app):
    with app.app_context(),pytest.raises(pmv.Unavailable):
        pmv.listing()
