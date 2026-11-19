"""Account lockout against password guessing, shared by website, app and admin sign in.

Per-IP and per-email rate limits (Flask-Limiter) slow guessing down; this adds a lock stored on the
account itself, so it survives server restarts and applies however many IPs an attacker uses.
"""
from datetime import datetime, timedelta

from flask import current_app

from app import db
from app.models import lock_row

MAX_FAILED_ATTEMPTS = 5
LOCK_MINUTES = 15


def minutes_locked(user):
    """Minutes left on this account's lock, or 0 if it can sign in."""
    until = getattr(user, 'locked_until', None)
    if not until or until <= datetime.utcnow():
        return 0
    return max(1, int((until - datetime.utcnow()).total_seconds() // 60) + 1)


def locked_message(user):
    minutes = minutes_locked(user)
    return (f'Too many wrong passwords, so this account is locked for {minutes} more '
            f'{"minute" if minutes == 1 else "minutes"}. Reset your password to get in now.')


def record_failed_login(user):
    """Counts a wrong password; the fifth in a row locks the account and emails its owner."""
    lock_row(user)  # Parallel guesses each count, none get lost.
    user.failed_login_count = (user.failed_login_count or 0) + 1
    if user.failed_login_count >= MAX_FAILED_ATTEMPTS:
        user.failed_login_count = 0
        user.locked_until = datetime.utcnow() + timedelta(minutes=LOCK_MINUTES)
        db.session.commit()
        try:
            from app.email_utils import send_account_locked_email
            send_account_locked_email(user, LOCK_MINUTES)
        except Exception as exc:  # The lock matters more than the alert.
            current_app.logger.exception('Failed to send account locked email: %s', exc)
        return
    db.session.commit()


def clear_failed_logins(user):
    """After a correct password or a password reset."""
    if user.failed_login_count or user.locked_until:
        user.failed_login_count = 0
        user.locked_until = None
