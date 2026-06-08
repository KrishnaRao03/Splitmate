from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from flask import Flask, flash, redirect, request, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user, logout_user
from flask_migrate import Migrate
from sqlalchemy import inspect, text
from config import Config

db = SQLAlchemy()
migrate = Migrate()
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

def ensure_expense_schema():
    inspector = inspect(db.engine)
    if not inspector.has_table('expense'):
        return

    columns = {column['name'] for column in inspector.get_columns('expense')}

    if 'receipt_url' not in columns:
        db.session.execute(text('ALTER TABLE expense ADD COLUMN receipt_url VARCHAR(500)'))

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

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
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

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(split_bp)
    app.register_blueprint(notes_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(admin_bp)

    with app.app_context():
        db.create_all()
        ensure_note_schema()
        ensure_user_email_schema()
        ensure_user_activity_schema()
        ensure_user_management_schema()
        ensure_stripe_schema()
        ensure_expense_schema()
        ensure_group_members_schema()

    return app
