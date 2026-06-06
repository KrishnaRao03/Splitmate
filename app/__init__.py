from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy import inspect, text
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'  # Redirect unauthorized users here
login_manager.login_message_category = 'info'

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
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN email_otp_expires_at DATETIME'))

    if 'email_otp_sent_at' not in columns:
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN email_otp_sent_at DATETIME'))

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

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.split import split_bp
    from app.routes.notes import notes_bp
    from app.routes.tasks import tasks_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(split_bp)
    app.register_blueprint(notes_bp)
    app.register_blueprint(tasks_bp)

    with app.app_context():
        db.create_all()
        ensure_note_schema()
        ensure_user_email_schema()
        ensure_stripe_schema()
        ensure_expense_schema()

    return app
