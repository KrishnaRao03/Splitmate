"""Protects members' payment details: password + alert on changes, and a verified Interac email."""
from datetime import datetime, timedelta
import secrets

from flask import current_app
from werkzeug.security import check_password_hash, generate_password_hash

from app.email_utils import send_interac_verification_code, send_payment_details_changed_email

MAX_INTERAC_OTP_ATTEMPTS = 5
HANDLE_LABELS = {
    'interac_email': 'Interac e-Transfer email',
    'paypal_username': 'PayPal.Me username',
    'upi_id': 'UPI ID',
}


def mask_email(email):
    """'krishna@gmail.com' -> 'k•••a@gmail.com'. Shown on screen instead of the full address."""
    if not email or '@' not in email:
        return email or ''
    local, domain = email.split('@', 1)
    if len(local) <= 2:
        return f'{local[0]}•••@{domain}'
    return f'{local[0]}•••{local[-1]}@{domain}'


def _alert(user, changes):
    if not changes:
        return
    try:
        send_payment_details_changed_email(user, changes)
    except Exception as exc:  # The change itself still stands; the alert is best effort.
        current_app.logger.exception('Failed to send payment details alert: %s', exc)


def send_interac_code(user):
    """Emails a fresh code to user.pending_interac_email. Returns True if it was sent."""
    otp = f'{secrets.randbelow(1000000):06d}'
    user.interac_otp_hash = generate_password_hash(otp)
    user.interac_otp_expires_at = datetime.utcnow() + timedelta(minutes=current_app.config['OTP_EXPIRY_MINUTES'])
    user.interac_otp_attempts = 0
    try:
        return bool(send_interac_verification_code(user, user.pending_interac_email, otp))
    except Exception as exc:
        current_app.logger.exception('Failed to send Interac verification code: %s', exc)
        return False


def apply_payment_handle_changes(user, handles, password):
    """Apply cleaned handles (from clean_payment_handles). Returns (result, error).

    Any change needs the current password and sends an alert to the account email. A new Interac
    email is held as pending and only replaces the old one once its emailed code is entered.
    """
    changed = {
        field: value for field, value in handles.items()
        if field != 'interac_email' and (getattr(user, field) or None) != value
    }
    new_interac = handles.get('interac_email', user.interac_email) if 'interac_email' in handles else user.interac_email
    interac_changed = 'interac_email' in handles and new_interac != (user.interac_email or None) \
        and new_interac != (user.pending_interac_email or None)

    if not changed and not interac_changed:
        return {'interac_code_sent': False}, None
    if not user.check_password(password or ''):
        return None, 'Enter your current password to change payment details.'

    changes = []
    for field, value in changed.items():
        setattr(user, field, value)
        changes.append(f'{HANDLE_LABELS[field]} {"removed" if not value else "updated"}')

    code_sent = False
    if interac_changed:
        if not new_interac:
            user.interac_email = None
            user.interac_email_verified = False
            user.pending_interac_email = None
            user.interac_otp_hash = None
            changes.append('Interac e-Transfer email removed')
        else:
            user.pending_interac_email = new_interac
            code_sent = send_interac_code(user)
            changes.append(f'New Interac e-Transfer email requested: {mask_email(new_interac)} (waiting for its code)')

    _alert(user, changes)
    return {'interac_code_sent': code_sent}, None


def verify_interac_code(user, otp):
    """Confirms the pending Interac email. Returns an error message, or None on success."""
    if not user.pending_interac_email or not user.interac_otp_hash:
        return 'There is no Interac email waiting for a code. Save one in your profile first.'
    if (user.interac_otp_attempts or 0) >= MAX_INTERAC_OTP_ATTEMPTS:
        return 'Too many wrong codes. Tap Resend code to get a new one.'
    if not user.interac_otp_expires_at or user.interac_otp_expires_at < datetime.utcnow():
        return 'That code has expired. Tap Resend code to get a new one.'
    if not check_password_hash(user.interac_otp_hash, (otp or '').strip()):
        user.interac_otp_attempts = (user.interac_otp_attempts or 0) + 1
        return 'That code is not right. Check the email and try again.'

    user.interac_email = user.pending_interac_email
    user.interac_email_verified = True
    user.pending_interac_email = None
    user.interac_otp_hash = None
    user.interac_otp_expires_at = None
    user.interac_otp_attempts = 0
    _alert(user, [f'Interac e-Transfer email confirmed: {mask_email(user.interac_email)}'])
    return None


def payment_status_payload(user):
    """What the owner sees about their own Interac setup."""
    return {
        'interac_email_verified': bool(user.interac_email and user.interac_email_verified),
        'pending_interac_email': user.pending_interac_email or '',
    }
