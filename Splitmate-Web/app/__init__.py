from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from flask import Flask, flash, jsonify, redirect, request, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager, current_user, logout_user
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import inspect, text
from config import Config
from app import field_encryption

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
# Per-IP limits on sign-in, codes and anything that sends email; see the @limiter.limit decorators.
limiter = Limiter(key_func=get_remote_address, storage_uri='memory://')
login_manager = LoginManager()
login_manager.login_view = 'auth.login'  # Redirect unauthorized users here
login_manager.login_message_category = 'info'

def datetime_column_type():
    return 'TIMESTAMP' if db.engine.dialect.name == 'postgresql' else 'DATETIME'

def false_boolean_default():
    return 'BOOLEAN DEFAULT false NOT NULL' if db.engine.dialect.name == 'postgresql' else 'BOOLEAN DEFAULT 0 NOT NULL'

def ensure_note_schema():
    inspector = inspect(db.engine)
    if not inspector.has_table('note'):
        return

    columns = {column['name'] for column in inspector.get_columns('note')}

    if 'title' not in columns:
        db.session.execute(text('ALTER TABLE note ADD COLUMN title VARCHAR(200)'))
        db.session.execute(text("UPDATE note SET title = content WHERE title IS NULL OR title = ''"))

    if 'description' not in columns:
        db.session.execute(text('ALTER TABLE note ADD COLUMN description TEXT'))

    db.session.commit()

def ensure_user_email_schema():
    inspector = inspect(db.engine)
    if not inspector.has_table('user'):
        return

    columns = {column['name'] for column in inspector.get_columns('user')}

    if 'is_email_verified' not in columns:
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN is_email_verified BOOLEAN DEFAULT 1'))
        db.session.execute(text('UPDATE "user" SET is_email_verified = 1 WHERE is_email_verified IS NULL'))

    if 'email_otp_hash' not in columns:
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN email_otp_hash VARCHAR(256)'))

    if 'email_otp_expires_at' not in columns:
        db.session.execute(text(f'ALTER TABLE "user" ADD COLUMN email_otp_expires_at {datetime_column_type()}'))

    if 'email_otp_sent_at' not in columns:
        db.session.execute(text(f'ALTER TABLE "user" ADD COLUMN email_otp_sent_at {datetime_column_type()}'))

    if 'email_otp_attempts' not in columns:
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN email_otp_attempts INTEGER DEFAULT 0 NOT NULL'))

    if 'token_version' not in columns:
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN token_version INTEGER DEFAULT 0 NOT NULL'))

    for column in ('interac_email', 'paypal_username', 'upi_id'):
        if column not in columns:
            db.session.execute(text(f'ALTER TABLE "user" ADD COLUMN {column} VARCHAR(120)'))

    db.session.commit()

def ensure_user_activity_schema():
    inspector = inspect(db.engine)
    if not inspector.has_table('user'):
        return

    columns = {column['name'] for column in inspector.get_columns('user')}

    if 'last_login_at' not in columns:
        db.session.execute(text(f'ALTER TABLE "user" ADD COLUMN last_login_at {datetime_column_type()}'))

    if 'last_activity_at' not in columns:
        db.session.execute(text(f'ALTER TABLE "user" ADD COLUMN last_activity_at {datetime_column_type()}'))

    if 'last_inactivity_email_sent_at' not in columns:
        db.session.execute(text(f'ALTER TABLE "user" ADD COLUMN last_inactivity_email_sent_at {datetime_column_type()}'))

    db.session.commit()

def ensure_user_management_schema():
    inspector = inspect(db.engine)
    if not inspector.has_table('user'):
        return

    columns = {column['name'] for column in inspector.get_columns('user')}

    if 'is_suspended' not in columns:
        db.session.execute(text(f'ALTER TABLE "user" ADD COLUMN is_suspended {false_boolean_default()}'))

    db.session.commit()

def ensure_stripe_schema():
    inspector = inspect(db.engine)

    if inspector.has_table('user'):
        user_columns = {column['name'] for column in inspector.get_columns('user')}

        if 'stripe_account_id' not in user_columns:
            db.session.execute(text('ALTER TABLE "user" ADD COLUMN stripe_account_id VARCHAR(255)'))

        if 'stripe_charges_enabled' not in user_columns:
            db.session.execute(text('ALTER TABLE "user" ADD COLUMN stripe_charges_enabled BOOLEAN DEFAULT 0 NOT NULL'))

        if 'stripe_payouts_enabled' not in user_columns:
            db.session.execute(text('ALTER TABLE "user" ADD COLUMN stripe_payouts_enabled BOOLEAN DEFAULT 0 NOT NULL'))

    if inspector.has_table('payment'):
        payment_columns = {column['name'] for column in inspector.get_columns('payment')}

        if 'method' not in payment_columns:
            db.session.execute(text("ALTER TABLE payment ADD COLUMN method VARCHAR(30) DEFAULT 'manual' NOT NULL"))

        if 'stripe_checkout_session_id' not in payment_columns:
            db.session.execute(text('ALTER TABLE payment ADD COLUMN stripe_checkout_session_id VARCHAR(255)'))
            db.session.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS ix_payment_stripe_checkout_session_id ON payment (stripe_checkout_session_id)'))

        if 'status' not in payment_columns:
            db.session.execute(text("ALTER TABLE payment ADD COLUMN status VARCHAR(30) DEFAULT 'recorded' NOT NULL"))

    db.session.commit()

def ensure_rewards_schema():
    inspector = inspect(db.engine)

    if inspector.has_table('user'):
        user_columns = {column['name'] for column in inspector.get_columns('user')}

        if 'reward_points' not in user_columns:
            db.session.execute(text('ALTER TABLE "user" ADD COLUMN reward_points INTEGER DEFAULT 0 NOT NULL'))

        if 'membership_plan' not in user_columns:
            db.session.execute(text("ALTER TABLE \"user\" ADD COLUMN membership_plan VARCHAR(30) DEFAULT 'free' NOT NULL"))

        if 'membership_status' not in user_columns:
            db.session.execute(text("ALTER TABLE \"user\" ADD COLUMN membership_status VARCHAR(30) DEFAULT 'active' NOT NULL"))

    if inspector.has_table('payment'):
        payment_columns = {column['name'] for column in inspector.get_columns('payment')}

        if 'reward_points_awarded' not in payment_columns:
            db.session.execute(text('ALTER TABLE payment ADD COLUMN reward_points_awarded INTEGER DEFAULT 0 NOT NULL'))

    if not inspector.has_table('reward_transaction'):
        db.create_all()

    db.session.commit()

def ensure_expense_schema():
    inspector = inspect(db.engine)
    if inspector.has_table('expense'):
        columns = {column['name'] for column in inspector.get_columns('expense')}

        if 'receipt_url' not in columns:
            db.session.execute(text('ALTER TABLE expense ADD COLUMN receipt_url VARCHAR(500)'))

        if 'category' not in columns:
            db.session.execute(text("ALTER TABLE expense ADD COLUMN category VARCHAR(40) DEFAULT 'General' NOT NULL"))

    if inspector.has_table('expense_history'):
        history_columns = {column['name'] for column in inspector.get_columns('expense_history')}

        if 'category' not in history_columns:
            db.session.execute(text("ALTER TABLE expense_history ADD COLUMN category VARCHAR(40) DEFAULT 'General' NOT NULL"))

    db.session.commit()

def ensure_group_default_split_schema():
    inspector = inspect(db.engine)
    if not inspector.has_table('group'):
        return

    columns = {column['name'] for column in inspector.get_columns('group')}

    if 'default_split_type' not in columns:
        db.session.execute(text("ALTER TABLE \"group\" ADD COLUMN default_split_type VARCHAR(20) DEFAULT 'equal' NOT NULL"))

    if 'default_split_config' not in columns:
        db.session.execute(text('ALTER TABLE "group" ADD COLUMN default_split_config TEXT'))

    db.session.commit()

def ensure_task_schema():
    inspector = inspect(db.engine)
    if not inspector.has_table('task'):
        return

    columns = {column['name'] for column in inspector.get_columns('task')}

    if 'priority' not in columns:
        db.session.execute(text("ALTER TABLE task ADD COLUMN priority VARCHAR(20) DEFAULT 'medium' NOT NULL"))

    if 'recurrence' not in columns:
        db.session.execute(text("ALTER TABLE task ADD COLUMN recurrence VARCHAR(20) DEFAULT 'none' NOT NULL"))

    db.session.commit()

def ensure_group_members_schema():
    inspector = inspect(db.engine)
    if not inspector.has_table('group_members'):
        return

    columns = {column['name'] for column in inspector.get_columns('group_members')}

    if 'nickname' not in columns:
        db.session.execute(text('ALTER TABLE group_members ADD COLUMN nickname VARCHAR(100)'))

    db.session.execute(text(
        'UPDATE group_members '
        'SET nickname = (SELECT "user".name FROM "user" WHERE "user".id = group_members.user_id) '
        "WHERE group_members.nickname IS NULL OR group_members.nickname = ''"
    ))

    db.session.commit()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    def configured_currency_code():
        return (app.config.get('STRIPE_CURRENCY') or 'cad').upper()

    def configured_currency_symbol():
        symbols = {
            'CAD': '$',
            'USD': '$',
            'INR': '\u20b9',
            'EUR': '\u20ac',
            'GBP': '\u00a3'
        }
        return symbols.get(configured_currency_code(), configured_currency_code())

    @app.template_filter('money')
    def money_filter(value, decimals=2):
        try:
            amount = Decimal(str(value if value is not None else 0))
        except (InvalidOperation, ValueError):
            amount = Decimal('0')

        precision = int(decimals)
        return f'{configured_currency_symbol()}{amount:,.{precision}f}'

    @app.context_processor
    def inject_currency_context():
        from app.admin_utils import is_app_admin

        return {
            'currency_code': configured_currency_code(),
            'currency_symbol': configured_currency_symbol(),
            'is_app_admin': is_app_admin(current_user)
        }

    def mobile_cors_origin_allowed(origin):
        if not origin:
            return False

        if origin in app.config['MOBILE_API_CORS_ORIGINS']:
            return True

        parsed_origin = urlparse(origin)
        return (
            app.debug
            and parsed_origin.scheme in ('http', 'https')
            and parsed_origin.hostname in ('localhost', '127.0.0.1')
        )

    @app.before_request
    def handle_mobile_cors_preflight():
        if request.method == 'OPTIONS' and request.path.startswith('/api/mobile'):
            return '', 204

    @app.after_request
    def add_mobile_cors_headers(response):
        if not request.path.startswith('/api/mobile'):
            return response

        origin = request.headers.get('Origin')
        if mobile_cors_origin_allowed(origin):
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers.add('Vary', 'Origin')

        response.headers['Access-Control-Allow-Headers'] = 'Authorization, Content-Type'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        return response

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    limiter.init_app(app)

    @app.errorhandler(429)
    def too_many_requests(error):
        message = 'Too many attempts. Please wait a few minutes and try again.'
        if request.path.startswith('/api/mobile'):
            return jsonify({'error': message}), 429
        return message, 429

    @app.errorhandler(413)
    def upload_too_large(error):
        message = 'That file is too large. Upload something under 10 MB.'
        if request.path.startswith('/api/mobile'):
            return jsonify({'error': message}), 413
        return message, 413
    scheduler_started = {'value': False}

    @app.before_request
    def ensure_scheduler_started():
        if scheduler_started['value']:
            return

        from app.scheduler import start_inactivity_scheduler
        start_inactivity_scheduler(app)
        scheduler_started['value'] = True

    @app.before_request
    def record_authenticated_activity():
        endpoint = request.endpoint or ''
        if endpoint == 'static' or endpoint.startswith('auth.') or endpoint.startswith('admin.'):
            return

        if not current_user.is_authenticated:
            return

        if getattr(current_user, 'is_suspended', False):
            logout_user()
            flash('Your Splitmate account is suspended. Contact an administrator.', 'error')
            return redirect(url_for('auth.login'))

        now = datetime.utcnow()
        interval = timedelta(minutes=app.config['ACTIVITY_UPDATE_INTERVAL_MINUTES'])
        if not current_user.last_activity_at or now - current_user.last_activity_at >= interval:
            current_user.last_activity_at = now
            db.session.commit()

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.split import split_bp
    from app.routes.notes import notes_bp
    from app.routes.tasks import tasks_bp
    from app.routes.admin import admin_bp
    from app.routes.mobile_api import mobile_api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(split_bp)
    app.register_blueprint(notes_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(mobile_api_bp)

    # The mobile API authenticates with Bearer tokens, not cookies, so CSRF doesn't apply.
    csrf.init_app(app)
    csrf.exempt(mobile_api_bp)

    with app.app_context():
        db.create_all()
        ensure_note_schema()
        ensure_user_email_schema()
        ensure_user_activity_schema()
        ensure_user_management_schema()
        ensure_stripe_schema()
        ensure_rewards_schema()
        ensure_expense_schema()
        ensure_group_default_split_schema()
        ensure_task_schema()
        ensure_group_members_schema()
        # Fails fast on a malformed FIELD_ENCRYPTION_KEY, then encrypts any plain-text payment handles.
        field_encryption.fernet()
        field_encryption.encrypt_existing_payment_handles(db)

    return app
