"""Encryption for sensitive database columns (payment handles).

Values are stored as ``enc:<Fernet token>`` using FIELD_ENCRYPTION_KEY. Rows written
before encryption was added are plain text; they are still readable and get
encrypted at start-up by encrypt_existing_payment_handles().
"""
from cryptography.fernet import Fernet, InvalidToken
from flask import current_app
from sqlalchemy import String, inspect, text
from sqlalchemy.types import TypeDecorator

PREFIX = 'enc:'
ENCRYPTED_COLUMN_LENGTH = 512
PAYMENT_HANDLE_COLUMNS = ('interac_email', 'paypal_username', 'upi_id')

_fernets = {}


def fernet():
    key = current_app.config['FIELD_ENCRYPTION_KEY']
    if key not in _fernets:
        _fernets[key] = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernets[key]


def is_encrypted(value):
    return isinstance(value, str) and value.startswith(PREFIX)


def encrypt_value(value):
    if not value or is_encrypted(value):
        return value
    return PREFIX + fernet().encrypt(value.encode('utf-8')).decode('ascii')


def decrypt_value(value):
    if not is_encrypted(value):
        return value
    try:
        return fernet().decrypt(value[len(PREFIX):].encode('ascii')).decode('utf-8')
    except InvalidToken:
        # Wrong or lost FIELD_ENCRYPTION_KEY. Hide the value rather than break every page that loads the user.
        current_app.logger.warning('Could not decrypt a stored payment handle; check FIELD_ENCRYPTION_KEY.')
        return None


class EncryptedString(TypeDecorator):
    """A string column that is encrypted in the database and plain text in Python."""

    impl = String(ENCRYPTED_COLUMN_LENGTH)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return encrypt_value(value)

    def process_result_value(self, value, dialect):
        return decrypt_value(value)


def encrypt_existing_payment_handles(db):
    """Widen the columns (PostgreSQL) and encrypt any plain-text payment handles. Safe to run every start-up."""
    inspector = inspect(db.engine)
    if not inspector.has_table('user'):
        return

    columns = {column['name']: column for column in inspector.get_columns('user')}
    present = [name for name in PAYMENT_HANDLE_COLUMNS if name in columns]
    if not present:
        return

    if db.engine.dialect.name == 'postgresql':
        for name in present:
            length = getattr(columns[name]['type'], 'length', None)
            if length is not None and length < ENCRYPTED_COLUMN_LENGTH:
                db.session.execute(text(f'ALTER TABLE "user" ALTER COLUMN {name} TYPE VARCHAR({ENCRYPTED_COLUMN_LENGTH})'))

    rows = db.session.execute(text(f'SELECT id, {", ".join(present)} FROM "user"')).all()
    for row in rows:
        updates = {
            name: encrypt_value(value)
            for name, value in zip(present, row[1:])
            if value and not is_encrypted(value)
        }
        if updates:
            assignments = ', '.join(f'{name} = :{name}' for name in updates)
            db.session.execute(text(f'UPDATE "user" SET {assignments} WHERE id = :id'), {**updates, 'id': row[0]})

    db.session.commit()
