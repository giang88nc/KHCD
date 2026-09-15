import pytest
from flask import request, url_for, render_template
from khcd import create_app, auth


@pytest.fixture
def routing(monkeypatch):
    app = create_app({'TESTING':True, 'SECRET_KEY':'routing-tests-only'})
    user = dict(id=1, username='routing-test', first_name='', last_name='', is_superuser=True)
    monkeypatch.setattr(auth, 'current_user', lambda: user)
    client = app.test_client()
    with client.session_transaction() as session:
        session['csrf'] = 'routing-token'; session['user'] = 'routing-test'
    return app, client


def test_canonical_url_generation_and_dashboard_alias(routing):
    app, client = routing
    targets = [('web.dashboard', {}, '/camdo'), ('web.pawn_new', {}, '/camdo/lap-phieu'),
               ('web.pawns', {}, '/camdo/phieu-cam-do'), ('web.reports', {}, '/camdo/thong-ke'),
               ('web.customers', {}, '/camdo/khach-hang'),
               ('web.pawn_detail', {'pid':42}, '/camdo/phieu-cam-do/42'),
               ('web.customer_form', {}, '/camdo/khach-hang/moi'),
               ('web.customer_kk_form', {'cust_id':'CU_TEST'}, '/camdo/khach-hang/kk/CU_TEST'),
               ('web.entry_customer', {}, '/camdo/lap-phieu/khach-hang'),
               ('customer_popup.frame', {}, '/camdo/khach-hang/popup/frame'),
               ('customer_popup.api', {'path':'banle/khach-hang/luu/'}, '/camdo/khach-hang/popup/api/banle/khach-hang/luu/')]
    with app.test_request_context():
        for endpoint, args, expected in targets:
            assert url_for(endpoint, **args) == expected
    app.view_functions['web.dashboard'] = lambda: 'dashboard'
    assert client.get('/').text == client.get('/camdo').text == 'dashboard'
    assert client.get('/camdo/').location == '/camdo'


@pytest.mark.parametrize('old,new', [
    ('/cam-do','/camdo/lap-phieu'), ('/phieu-cam-do/moi','/camdo/lap-phieu'),
    ('/phieu-cam-do/42','/camdo/phieu-cam-do/42'), ('/thong-ke','/camdo/thong-ke'),
    ('/khach-hang','/camdo/khach-hang'), ('/khach-hang/kk/CU_TEST','/camdo/khach-hang/kk/CU_TEST'),
    ('/cam-do/khach-hang','/camdo/lap-phieu/khach-hang'),
    ('/khach-hang/popup/api/banle/khach-hang/them/','/camdo/khach-hang/popup/api/banle/khach-hang/them/'),
])
def test_old_get_redirect_preserves_filters(routing, old, new):
    app, client = routing
    query = '?q=%C4%90%E1%BA%B7t&page=2&status=active&status=all'
    result = client.get(old + query)
    assert result.status_code == 308
    assert result.location == new + query


def test_open_old_form_post_keeps_body_and_csrf(routing):
    app, client = routing
    calls = []
    def save():
        calls.append(request.form.to_dict())
        return '', 204
    app.view_functions['web.pawn_new'] = save
    for path in ('/cam-do','/phieu-cam-do/moi','/camdo/lap-phieu'):
        assert client.post(path, data={'request_key':'do-not-repeat'}).status_code == 400
        assert client.post(path, data={'csrf_token':'routing-token','request_key':'do-not-repeat'}).status_code == 204
    assert len(calls) == 3
    assert all(call['request_key'] == 'do-not-repeat' for call in calls)


def test_navigation_builds_new_links(routing):
    app, client = routing
    app.view_functions['web.dashboard'] = lambda: render_template('base.html')
    html = client.get('/camdo').text
    for path in ('/camdo','/camdo/lap-phieu','/camdo/phieu-cam-do','/camdo/khach-hang','/camdo/thong-ke'):
        assert 'href="' + path + '"' in html
    assert 'href="/cam-do"' not in html
