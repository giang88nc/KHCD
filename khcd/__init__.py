import os
import secrets
import hmac
from pathlib import Path
from datetime import timedelta
from flask import Flask, session, request, redirect, url_for, render_template, g
from dotenv import load_dotenv
import pymysql
from . import db
from .domain import BusinessError, money, today, STATUSES, EVENTS

def create_app(test_config=None):
    load_dotenv(os.environ.get('KHCD_ENV_FILE', '.env'), override=False)
    app = Flask(__name__)
    # Reload changed templates even in Waitress; F5 must not keep an old form.
    app.config['TEMPLATES_AUTO_RELOAD']=True
    app.config.update({k: os.getenv(k, default) for k, default in {
        'DB_HOST':'127.0.0.1','DB_PORT':'3308','DB_NAME':'khj_cd',
        'DB_USER':'khj_admin','DB_PASSWORD':'','SECRET_KEY':'',
        'AUTH_SOURCE_DB':'khj_bl','RETAIL_URL':'https://tiemvangkimhanh2:8100',
        'CD_LIVE':'1','CUSTOMER_MASTER':'kk','CUSTOMER_BRIDGE_KEY_FILE':'instance/customer-bridge.key',
        'LEGACY_PAWN_IMAGE_ROOT':'D:/PYTHON/KHCD/media/pawn',
        'PMV_MSSQL_HOST':'','PMV_MSSQL_DB':'','PMV_MSSQL_USER':'','PMV_MSSQL_PASSWORD':'',
        'PMV_MSSQL_ODBC_DRIVER':'SQL Server Native Client 10.0',
        'PMV_MSSQL_ENCRYPT':'no','PMV_MSSQL_TRUST_CERT':'yes'}.items()})
    app.config.update(DB_READ_ONLY=os.getenv('DB_READ_ONLY','0')=='1',
        MIN_INTEREST_DAYS=int(os.getenv('MIN_INTEREST_DAYS','1')),
        SESSION_COOKIE_NAME='khcd_session',
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE','0')=='1',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8), MAX_CONTENT_LENGTH=128*1024)
    if test_config:
        app.config.update(test_config)
    app.config['MIN_INTEREST_DAYS']=int(app.config['MIN_INTEREST_DAYS'])
    if not app.config['SECRET_KEY']:
        raise RuntimeError('Thiếu SECRET_KEY. Chạy scripts/setup.py để tạo cấu hình.')
    from .views import bp
    app.register_blueprint(bp)
    from .customer_popup import bp as customer_popup_bp
    app.register_blueprint(customer_popup_bp)
    from .conversion_views import bp as conversion_bp
    app.register_blueprint(conversion_bp)
    from .loans import bp as loans_bp
    app.register_blueprint(loans_bp)
    from .transactions import bp as transactions_bp
    app.register_blueprint(transactions_bp)
    from .sms import bp as sms_bp
    app.register_blueprint(sms_bp)
    from .live_loans import bp as live_bp
    app.register_blueprint(live_bp)
    # In bien nhan len GIAY CAM DO A5 ngang da in san; bo cuc doc tu khj_bl.pmv_state['gcd_layout'].
    from .gcd_print import bp as gcd_bp
    app.register_blueprint(gcd_bp)
    app.teardown_appcontext(db.close)

    @app.before_request
    def security():
        from . import auth
        if request.endpoint == 'customer_popup.api':
            request.max_content_length = 48 * 1024 * 1024
        if request.endpoint == 'web.pawn_new':
            request.max_content_length = 80 * 1024 * 1024
        if request.endpoint == 'live.commit':request.max_content_length=16*1024*1024
        if request.endpoint == 'web.desk_qr':request.max_content_length = 16 * 1024 * 1024
        g.auth_user=None
        if request.endpoint not in ('static','web.health'):
            g.auth_user=auth.current_user()
            if not g.auth_user and (session.get('user') or session.get('user_id')):
                session.clear()
        session.setdefault('csrf', secrets.token_urlsafe(32))
        if request.endpoint not in ('web.login', 'static', 'web.health') and not g.auth_user:
            return redirect(url_for('web.login'))
        if request.method == 'POST':
            token = (request.headers.get('X-CSRFToken', '') if request.endpoint == 'customer_popup.api'
                     else request.form.get('csrf_token', ''))
            if not hmac.compare_digest(token, session['csrf']):
                return render_template('error.html', message='Phiên thao tác đã hết hạn. Tải lại trang rồi thử lại.'), 400

    from .urls import install_legacy_urls
    install_legacy_urls(app)

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='same-origin'
        response.headers['Content-Security-Policy']="default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data: blob:; form-action 'self'; frame-ancestors 'none'; base-uri 'self'"
        if request.endpoint=='web.pawn_new':
            response.headers['Content-Security-Policy']+="; media-src 'self' blob:"
        if request.endpoint in ('customer_popup.frame', 'customer_popup.api','customer_popup.photos'):
            # The canonical KHBL modal uses inline HTMX handlers and crop scripts.
            # Confine that policy to its same-origin iframe; the main app stays strict.
            response.headers['X-Frame-Options']='SAMEORIGIN'
            response.headers['Content-Security-Policy']="default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; img-src 'self' data: blob:; media-src 'self' blob:; form-action 'self'; frame-ancestors 'self'; base-uri 'self'"
        if request.endpoint != 'static' and not (request.endpoint=='customer_popup.asset' and response.status_code in (200,304)):
            response.headers['Cache-Control']='no-store'
        return response

    @app.context_processor
    def context():
        user=getattr(g,'auth_user',None)
        display_name=(' '.join([user['first_name'],user['last_name']]).strip() or user['username']) if user else ''
        return dict(today=today(), statuses=STATUSES, event_names=EVENTS,
            cd_live=str(app.config.get('CD_LIVE','0'))=='1',readonly=app.config['DB_READ_ONLY'], auth_user=user,display_name=display_name,
            retail_url=app.config['RETAIL_URL'],
            role_label='Quản trị viên' if user and user['is_superuser'] else 'Nhân viên')

    app.jinja_env.filters['vnd'] = lambda x: f'{money(x):,.0f}'.replace(',', '.')
    app.jinja_env.filters['num'] = lambda x: f'{x or 0:,}'.replace(',', '.')
    app.jinja_env.filters['datevn'] = lambda x: x.strftime('%d/%m/%Y') if hasattr(x,'strftime') else (str(x)[:10] if x else '—')
    app.jinja_env.filters['rate'] = lambda x: format(x, '.6f').rstrip('0').rstrip('.') if x is not None else '—'

    @app.errorhandler(BusinessError)
    def invalid(error):
        if request.accept_mimetypes.best=='application/json':return {'error':str(error)},400
        return render_template('error.html', message=str(error)), 400

    @app.errorhandler(pymysql.MySQLError)
    def db_error(error):
        app.logger.error('Database operation failed: code=%s', error.args[0])
        if request.accept_mimetypes.best=='application/json':return {'error':'Chưa xác định kết quả MySQL. Giữ mã yêu cầu và kiểm tra lịch sử trước khi tiếp tục.','uncertain':True},503
        return render_template('error.html', message='Chưa thể hoàn tất thao tác với MySQL. Kiểm tra cấu hình kết nối; không gửi lại giao dịch trước khi kiểm tra lịch sử.'), 503

    @app.errorhandler(404)
    def missing(error):
        return render_template('error.html', message='Không tìm thấy hồ sơ này.'), 404
    return app
