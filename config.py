import os


BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _load_env_file(path):
    if not os.path.exists(path):
        return

    with open(path, encoding='utf-8') as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue

            key, value = line.split('=', 1)
            key = key.strip().lstrip('\ufeff')
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


_load_env_file(os.path.join(BASE_DIR, '.env'))


class Config:
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = DATABASE_URL or 'sqlite:///splitmate.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ('1', 'true', 'yes')
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'krishna.rao.0302@gmail.com'
    MAIL_PASSWORD = (os.environ.get('MAIL_PASSWORD') or '').replace(' ', '') or None
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or MAIL_USERNAME
    ADMIN_EMAILS = {
        email.strip().lower()
        for email in (os.environ.get('ADMIN_EMAILS') or MAIL_USERNAME or '').split(',')
        if email.strip()
    }
    OTP_EXPIRY_MINUTES = int(os.environ.get('OTP_EXPIRY_MINUTES') or 10)
    OTP_RESEND_COOLDOWN_SECONDS = int(os.environ.get('OTP_RESEND_COOLDOWN_SECONDS') or 60)
    PASSWORD_RESET_EXPIRY_MINUTES = int(os.environ.get('PASSWORD_RESET_EXPIRY_MINUTES') or 30)
    ACTIVITY_UPDATE_INTERVAL_MINUTES = int(os.environ.get('ACTIVITY_UPDATE_INTERVAL_MINUTES') or 5)
    INACTIVITY_REMINDER_DAYS = int(os.environ.get('INACTIVITY_REMINDER_DAYS') or 30)
    INACTIVITY_EMAIL_COOLDOWN_DAYS = int(os.environ.get('INACTIVITY_EMAIL_COOLDOWN_DAYS') or 14)
    INACTIVITY_EMAILS_ENABLED = os.environ.get('INACTIVITY_EMAILS_ENABLED', 'true').lower() in ('1', 'true', 'yes')
    INACTIVITY_EMAIL_HOUR_UTC = int(os.environ.get('INACTIVITY_EMAIL_HOUR_UTC') or 14)
    MOBILE_TOKEN_EXPIRY_DAYS = int(os.environ.get('MOBILE_TOKEN_EXPIRY_DAYS') or 30)
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
    STRIPE_CURRENCY = (os.environ.get('STRIPE_CURRENCY') or 'cad').lower()
