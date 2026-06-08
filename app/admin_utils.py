from datetime import datetime

from app import db
from app.models import Expense, ExpenseSplit, Payment, Task, Note


def is_app_admin(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return False

    from flask import current_app

    admin_emails = current_app.config.get('ADMIN_EMAILS') or set()
    return user.email.lower() in admin_emails


def user_last_usage_at(user):
    return user.last_activity_at or user.last_login_at or user.created_at


def month_sequence(now=None, count=12):
    now = now or datetime.utcnow()
    months = []
    for offset in range(count - 1, -1, -1):
        month = now.month - offset
        year = now.year
        while month <= 0:
            month += 12
            year -= 1
        start = datetime(year, month, 1)
        end = datetime(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
        months.append({
            'start': start,
            'end': end,
            'label': start.strftime('%b %Y')
        })
    return months


def split_user_ids_since(since=None):
    paid_query = db.session.query(Expense.paid_by_id)
    owed_query = db.session.query(ExpenseSplit.user_id).join(Expense)

    if since:
        paid_query = paid_query.filter(Expense.date >= since)
        owed_query = owed_query.filter(Expense.date >= since)

    paid_ids = {row[0] for row in paid_query.all() if row[0]}
    owed_ids = {row[0] for row in owed_query.all() if row[0]}
    return paid_ids | owed_ids


def core_activity_user_ids():
    ids = split_user_ids_since()
    ids.update(row[0] for row in db.session.query(Payment.payer_id).all() if row[0])
    ids.update(row[0] for row in db.session.query(Payment.receiver_id).all() if row[0])
    ids.update(row[0] for row in db.session.query(Task.created_by_id).all() if row[0])
    ids.update(row[0] for row in db.session.query(Task.assigned_to_id).all() if row[0])
    ids.update(row[0] for row in db.session.query(Note.created_by_id).all() if row[0])
    return ids
