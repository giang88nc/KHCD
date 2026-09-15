import pytest
from khcd.customer_lookup import lookup_key
from khcd.domain import BusinessError


RAW='012345678901|123456789|Tr01980176ng Ng02250187c QA|07041988|Nam|Dia chi loi 0195|15092023'


def test_qr_uses_first_identifier_preserves_leading_zero():
    assert lookup_key(RAW)=='012345678901'
    assert lookup_key('  '+RAW+'\r\n')=='012345678901'


@pytest.mark.parametrize('query',['0900000001','012345678901','Nguyễn QA',''])
def test_plain_search_unchanged(query):
    assert lookup_key(query)==query


@pytest.mark.parametrize('raw',['123|abc',RAW[:-1],RAW.replace('012345678901','０12345678901'),'x'*8193])
def test_invalid_scan_does_not_guess_identifier(raw):
    with pytest.raises(BusinessError):lookup_key(raw)


def test_search_endpoint_passes_only_cccd_to_existing_lookup(client,monkeypatch):
    from khcd import views
    seen=[]
    def search(q='',selection=''):
        seen.append(q);return []
    monkeypatch.setattr(views,'entry_customers',search)
    response=client.get('/camdo/lap-phieu/khach-hang',query_string={'q':RAW})
    assert response.status_code==200 and seen==['012345678901']
    assert client.get('/camdo/lap-phieu/khach-hang',query_string={'q':'123|bad'}).status_code==400
    assert seen==['012345678901']


def test_changed_template_is_reloaded_without_process_restart(app,tmp_path):
    from jinja2 import FileSystemLoader
    file=tmp_path/'reload.html';file.write_text('old',encoding='utf-8')
    app.jinja_env.loader=FileSystemLoader(tmp_path)
    assert app.jinja_env.auto_reload
    assert app.jinja_env.get_template('reload.html').render()=='old'
    file.write_text('updated form',encoding='utf-8')
    import os
    os.utime(file,(file.stat().st_atime,file.stat().st_mtime+2))
    assert app.jinja_env.get_template('reload.html').render()=='updated form'
