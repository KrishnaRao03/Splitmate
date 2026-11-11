import os

from env_crypto import is_protected, unprotect_value


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
            # Real environment variables win, so servers and CI never need the .env file.
            if key in os.environ:
                continue
            if is_protected(value):
                # Encrypted on this machine with scripts/protect_env.py (Windows DPAPI).
                value = unprotect_value(value)
            os.environ[key] = value


_load_env_file(os.path.join(BASE_DIR, '.env'))


def _new_fernet_key():
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()


def _local_secret_key(filename='secret_key', make_key=None):
    # Without the variable set, use a random key kept in instance/ so it survives
    # restarts but can't be guessed from a known default.
    path = os.path.join(BASE_DIR, 'instance', filename)
    if os.path.exists(path):
        with open(path, encoding='utf-8') as key_file:
            key = key_file.read().strip()
        if key:
            return key

    import secrets
    key = make_key() if make_key else secrets.token_hex(32)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as key_file:
        key_file.write(key)
    return key


def _field_encryption_key():
    key = os.environ.get('FIELD_ENCRYPTION_KEY')
    if key:
        return key
    seed = os.environ.get('FIELD_ENCRYPTION_KEY_SEED')
    if seed:
        # Hosts like Render can generate a random secret but not a Fernet key, so derive one.
        import base64
        import hashlib
        return base64.urlsafe_b64encode(hashlib.sha256(seed.encode()).digest()).decode()
    return _local_secret_key('field_encryption_key', _new_fernet_key)


class Config:
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

    SECRET_KEY = os.environ.get('SECRET_KEY') or _local_secret_key()
    # Fernet key for payment handles stored in the database. Losing it makes them unreadable.
    FIELD_ENCRYPTION_KEY = _field_encryption_key()
    SQLALCHEMY_DATABASE_URI = DATABASE_URL or 'sqlite:///splitmate.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Uploads (receipts) are capped; bigger requests get a 413.
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    # Set SECURE_COOKIES=true once the site is served over HTTPS.
    SESSION_COOKIE_SECURE = os.environ.get('SECURE_COOKIES', 'false').lower() in ('1', 'true', 'yes')
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_HTTPONLY = True
    RATELIMIT_ENABLED = os.environ.get('RATELIMIT_ENABLED', 'true').lower() in ('1', 'true', 'yes')
    RATELIMIT_HEADERS_ENABLED = True
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ('1', 'true', 'yes')
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or None
    MAIL_PASSWORD = (os.environ.get('MAIL_PASSWORD') or '').replace(' ', '') or None
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or MAIL_USERNAME
    # When set, email goes through Brevo's HTTPS API instead of SMTP.
    BREVO_API_KEY = os.environ.get('BREVO_API_KEY') or None
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
    MOBILE_API_CORS_ORIGINS = {
        origin.strip()
        for origin in os.environ.get(
            'MOBILE_API_CORS_ORIGINS',
            'http://localhost:8082,http://127.0.0.1:8082'
        ).split(',')
        if origin.strip()
    }
    GROUP_INVITE_EXPIRY_DAYS = int(os.environ.get('GROUP_INVITE_EXPIRY_DAYS') or 7)
    # Display currency for the whole app (the name predates removing Stripe; kept so existing .env files still work).
    STRIPE_CURRENCY = (os.environ.get('STRIPE_CURRENCY') or 'cad').lower()
