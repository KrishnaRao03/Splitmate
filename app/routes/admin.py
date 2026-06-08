from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from app.admin_utils import core_activity_user_ids, is_app_admin, month_sequence, split_user_ids_since, user_last_usage_at
from app.inactivity_reminders import inactive_reminder_candidates, send_inactivity_reminders
from app.models import User

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_user():
    user_id = session.get('admin_user_id')
    if not user_id:
        return None

    user = User.query.get(user_id)
    if not user or not is_app_admin(user):
        session.pop('admin_user_id', None)
        return None

    return user


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not admin_user():
            return redirect(url_for('admin.login', next=request.path))
        return view(*args, **kwargs)

    return wrapped


def safe_admin_redirect(default_endpoint='admin.dashboard'):
    target = request.args.get('next', '').strip()
    if target.startswith('/admin') and not target.startswith('//'):
        return target
    return url_for(default_endpoint)


@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if admin_user():
        return redirect(safe_admin_redirect())

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first() if email else None

        if user and user.check_password(password) and is_app_admin(user):
            if not user.is_email_verified:
                flash('Verify this account email before using the admin dashboard.', 'error')
                return render_template('admin_login.html')

            session['admin_user_id'] = user.id
            flash('Admin sign in successful.', 'success')
            return redirect(safe_admin_redirect())

        flash('Invalid admin email or password.', 'error')

    return render_template('admin_login.html')


@admin_bp.route('/logout')
def logout():
    session.pop('admin_user_id', None)
    flash('Signed out of admin.', 'info')
    return redirect(url_for('admin.login'))


def count_users_created_between(users, start, end):
    return sum(1 for user in users if user.created_at and start <= user.created_at < end)


def user_row(user, now):
    last_usage_at = user_last_usage_at(user)
    return {
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'created_at': user.created_at,
        'last_login_at': user.last_login_at,
        'last_activity_at': user.last_activity_at,
        'last_usage_at': last_usage_at,
        'days_idle': (now - last_usage_at).days if last_usage_at else None,
        'last_inactivity_email_sent_at': user.last_inactivity_email_sent_at,
        'is_email_verified': user.is_email_verified
    }


@admin_bp.route('/')
@admin_required
def dashboard():
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    previous_month_end = month_start
    previous_month_start = datetime(
        month_start.year - (1 if month_start.month == 1 else 0),
        12 if month_start.month == 1 else month_start.month - 1,
        1
    )
    inactive_cutoff = now - timedelta(days=current_app.config['INACTIVITY_REMINDER_DAYS'])

    users = User.query.order_by(User.created_at.desc()).all()
    total_users = len(users)
    verified_users = sum(1 for user in users if user.is_email_verified)
    new_users_this_month = count_users_created_between(users, month_start, now + timedelta(seconds=1))
    new_users_previous_month = count_users_created_between(users, previous_month_start, previous_month_end)
    new_user_delta = new_users_this_month - new_users_previous_month

    growth_months = month_sequence(now, 12)
    growth_data = [
        {
            'label': month['start'].strftime('%b'),
            'year': month['start'].strftime('%Y'),
            'count': count_users_created_between(users, month['start'], month['end'])
        }
        for month in growth_months
    ]

    split_users_this_month = split_user_ids_since(month_start)
    core_users = core_activity_user_ids()
    no_split_this_month = [
        user_row(user, now)
        for user in users
        if user.id not in split_users_this_month
    ]
    never_used_core_feature = [
        user_row(user, now)
        for user in users
        if user.id not in core_users
    ]
    long_inactive_users = [
        user_row(user, now)
        for user in users
        if user_last_usage_at(user) and user_last_usage_at(user) < inactive_cutoff
    ]
    reminder_candidates = inactive_reminder_candidates(now)

    stats = {
        'total_users': total_users,
        'verified_users': verified_users,
        'new_users_this_month': new_users_this_month,
        'new_user_delta': new_user_delta,
        'no_split_this_month': len(no_split_this_month),
        'never_used_core_feature': len(never_used_core_feature),
        'long_inactive_users': len(long_inactive_users),
        'reminder_candidates': len(reminder_candidates)
    }

    return render_template(
        'admin_dashboard.html',
        admin_user=admin_user(),
        stats=stats,
        growth_data=growth_data,
        no_split_this_month=no_split_this_month[:12],
        never_used_core_feature=never_used_core_feature[:12],
        long_inactive_users=long_inactive_users[:12],
        inactivity_days=current_app.config['INACTIVITY_REMINDER_DAYS'],
        emails_enabled=current_app.config['INACTIVITY_EMAILS_ENABLED'],
        email_hour_utc=current_app.config['INACTIVITY_EMAIL_HOUR_UTC']
    )


@admin_bp.route('/send-inactivity-reminders', methods=['POST'])
@admin_required
def send_inactivity_reminders_now():
    result = send_inactivity_reminders()

    if result['sent']:
        flash(f'Sent {result["sent"]} inactivity reminder email(s).', 'success')
    elif result['skipped']:
        flash('No reminders were sent because MAIL_PASSWORD is not configured.', 'info')
    else:
        flash('No eligible inactive users needed a reminder right now.', 'info')

    if result['failed']:
        flash(f'{result["failed"]} reminder email(s) failed. Check the app logs.', 'error')

    return redirect(url_for('admin.dashboard'))
