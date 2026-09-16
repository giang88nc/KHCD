"""Same-origin host for the canonical KHBL customer popup. No customer SQL here."""
import base64
import re
from pathlib import Path
from urllib.parse import quote
from flask import Blueprint, Response, abort, render_template, request, current_app, send_file, url_for
from . import customer_master as master, db
from .domain import BusinessError

bp = Blueprint('customer_popup', __name__, url_prefix='/camdo/khach-hang/popup')


def unpack(result):
    return base64.b64decode(result['body'], validate=True)


@bp.get('/photos')
def photos():
    if not master.enabled():abort(404)
    db.require_write()
    result=master.call('popup',path='/banle/khach-hang/them/',method='GET',query='pawn_photos=1&group='+({'front':'front','back':'back','products':'products','qr':'products'}.get(request.args.get('group'),'all')))
    return render_template('customer_popup_frame.html',popup_html=unpack(result).decode('utf-8'),pawn_photos=True,photo_group=request.args.get('group','all')),result['status']


@bp.get('/frame')
def frame():
    if not master.enabled():
        abort(404)
    db.require_write()
    cid = request.args.get('cust_id', '')
    if len(cid) > 60:
        abort(400)
    path = '/banle/khach-hang/' + (quote(cid, safe='') + '/sua/' if cid else 'them/')
    result = master.call('popup', path=path, method='GET')
    return render_template('customer_popup_frame.html', popup_html=unpack(result).decode('utf-8')), result['status']


@bp.route('/api/<path:path>', methods=['GET', 'POST'])
def api(path):
    if not master.enabled():
        abort(404)
    if request.method == 'POST':
        db.require_write()
    result = master.call('popup', path='/' + path, method=request.method,
        query=request.query_string.decode('ascii'), content_type=request.content_type or '',
        body=base64.b64encode(request.get_data()).decode('ascii'))
    return Response(unpack(result), status=result['status'], headers=result.get('headers', {}))


ASSETS={'css/fonts.css','css/khbl.css','js/vendor/htmx.min.js','js/vn_text.js','js/cccd.js','js/khbl.js'}

def asset_path(asset):
    if asset not in ASSETS and not re.fullmatch(r'fonts/(?:BeVietnamPro-(?:400|500|600|700)|Cormorant-600)-(?:vietnamese|latin)\.woff2',asset):
        abort(404)
    root=Path(current_app.config.get('KHBL_STATIC_ROOT','D:/PYTHON/KHBL/static')).resolve()
    path=(root/asset).resolve()
    if not path.is_relative_to(root):abort(404)
    return path

@bp.app_context_processor
def popup_asset_helpers():
    def popup_asset_url(asset):
        path=asset_path(asset)
        version=str(path.stat().st_mtime_ns) if path.is_file() else 'bridge'
        return url_for('customer_popup.asset',asset=asset,v=version)
    return dict(popup_asset_url=popup_asset_url)

@bp.get('/assets/<path:asset>')
def asset(asset):
    path=asset_path(asset)
    if path.is_file():
        version=str(path.stat().st_mtime_ns)
        response=send_file(path,conditional=True,max_age=86400 if request.args.get('v')==version else 0)
        response.cache_control.public=False
        response.cache_control.private=True
        return response
    # Remote installations can still use the original authenticated bridge.
    result=master.call('popup',asset=asset)
    response=Response(unpack(result),status=result['status'],headers=result.get('headers',{}))
    if response.status_code==200:
        import hashlib
        response.set_etag(hashlib.sha256(response.get_data()).hexdigest())
        response.headers['Cache-Control']='private, max-age=0, must-revalidate'
        response.make_conditional(request)
    return response


@bp.errorhandler(BusinessError)
def unavailable(error):
    if request.endpoint == 'customer_popup.frame':
        return render_template('customer_popup_frame.html', popup_error=str(error)), 503
    # The client keeps the form and its token; it never automatically resubmits.
    return Response('Chưa hoàn tất: ' + str(error), status=503, content_type='text/plain; charset=utf-8')
