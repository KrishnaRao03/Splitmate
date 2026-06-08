from datetime import datetime, timedelta

from flask import current_app

from app import db
from app.admin_utils import user_last_usage_at
from app.email_utils import send_inactivity_reminder_email
from app.models import User


def inactive_reminder_candidates(now=None):
    now = now or datetime.utcnow()
    inactive_cutoff = now - timedelta(days=current_app.config['INACTIVITY_REMINDER_DAYS'])
    cooldown_cutoff = now - timedelta(days=current_app.config['INACTIVITY_EMAIL_COOLDOWN_DAYS'])
    users = User.query.filter_by(is_email_verified=True).order_by(User.created_at.asc()).all()
    candidates = []

    for user in users:
        last_usage_at = user_last_usage_at(user)
        if last_usage_at and last_usage_at > inactive_cutoff:
            continue

        if user.last_inactivity_email_sent_at and user.last_inactivity_email_sent_at > cooldown_cutoff:
            continue

        candidates.append(user)

    return candidates


def send_inactivity_reminders(now=None, limit=None):
    now = now or datetime.utcnow()
    result = {
        'sent': 0,
        'failed': 0,
        'skipped': 0,
        'candidates': 0
    }

    if not current_app.config.get('MAIL_PASSWORD'):
        result['skipped'] = len(inactive_reminder_candidates(now))
        return result

    candidates = inactive_reminder_candidates(now)
    if limit:
        candidates = candidates[:limit]

    result['candidates'] = len(candidates)

    for user in candidates:
        last_usage_at = user_last_usage_at(user)
        days_idle = (now - last_usage_at).days if last_usage_at else current_app.config['INACTIVITY_REMINDER_DAYS']

        try:
            sent = send_inactivity_reminder_email(user, days_idle)
        except Exception as exc:
            current_app.logger.exception('Failed to send inactivity reminder to %s: %s', user.email, exc)
            sent = False

        if sent:
            user.last_inactivity_email_sent_at = now
            db.session.commit()
            result['sent'] += 1
        else:
            db.session.rollback()
            result['failed'] += 1

    return result
