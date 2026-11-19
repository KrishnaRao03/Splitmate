"""Protects members' payment details: changes need the password and send an alert."""
from flask import current_app

from app.email_utils import send_payment_details_changed_email

HANDLE_LABELS = {
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


def apply_payment_handle_changes(user, handles, password):
    """Apply cleaned handles (from clean_payment_handles). Returns (result, error).

    Any change needs the current password and sends an alert to the account email.
    """
    changed = {field: value for field, value in handles.items() if (getattr(user, field) or None) != value}
    if not changed:
        return {'interac_code_sent': False}, None
    if not user.check_password(password or ''):
        return None, 'Enter your current password to change payment details.'

    changes = []
    for field, value in changed.items():
        setattr(user, field, value)
        changes.append(f'{HANDLE_LABELS[field]} {"removed" if not value else "updated"}')
    _alert(user, changes)
    return {'interac_code_sent': False}, None


def payment_status_payload(user):
    """What the owner sees about their own Interac setup."""
    return {
        'interac_email_verified': bool(user.interac_email and user.interac_email_verified),
        'pending_interac_email': user.pending_interac_email or '',
    }
