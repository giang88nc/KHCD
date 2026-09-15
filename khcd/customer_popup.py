"""Same-origin host for the canonical KHBL customer popup. No customer SQL here."""
import base64
from urllib.parse import quote
from flask import Blueprint, Response, abort, render_template, request
from . import customer_master as master, db
from .domain import BusinessError

bp = Blueprint('customer_popup', __name__, url_prefix='/camdo/khach-hang/popup')


def unpack(result):
    return base64.b64decode(result['body'], validate=True)


@bp.get('/photos')
def photos():
    if not master.enabled():abort(404)
    db.require_write()
    result=master.call('popup',path='/banle/khach-hang/them/',method='GET',query='pawn_photos=1&group='+({'front':'front','back':'back','products':'products'}.get(request.args.get('group'),'all')))
    return render_template('customer_popup_frame.html',popup_html=unpack(result).decode('utf-8'),pawn_photos=True),result['status']


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


@bp.get('/assets/<path:asset>')
def asset(asset):
    result = master.call('popup', asset=asset)
    return Response(unpack(result), status=result['status'], headers=result.get('headers', {}))


@bp.errorhandler(BusinessError)
def unavailable(error):
    if request.endpoint == 'customer_popup.frame':
        return render_template('customer_popup_frame.html', popup_error=str(error)), 503
    # The client keeps the form and its token; it never automatically resubmits.
    return Response('Chưa hoàn tất: ' + str(error), status=503, content_type='text/plain; charset=utf-8')
