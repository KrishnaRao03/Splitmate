from datetime import datetime, timedelta
from functools import wraps
import secrets

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from sqlalchemy import func

from app import db
from app.admin_utils import core_activity_user_ids, is_app_admin, month_sequence, split_user_ids_since, user_last_usage_at
from app.email_utils import send_password_reset_email
from app.inactivity_reminders import inactive_reminder_candidates, send_inactivity_reminders
from app.models import Expense, ExpenseSplit, Group, Payment, User, group_members
from app.routes.auth import generate_password_reset_token

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_user():
    user_id = session.get('admin_user_id')
    if not user_id:
        return None

    user = User.query.get(user_id)
    if not user or not is_app_admin(user) or getattr(user, 'is_suspended', False):
        session.pop('admin_user_id', None)
        return None

    return user


def render_admin_template(template_name, active_page, **context):
    return render_template(
        template_name,
        admin_user=admin_user(),
        active_admin_page=active_page,
        **context
    )


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not admin_user():
            return redirect(url_for('admin.login', next=request.path))
        return view(*args, **kwargs)

    return wrapped


@admin_bp.before_request
def protect_admin_area():
    if request.endpoint in ('admin.login', 'admin.logout'):
        return None

    if not admin_user():
        return redirect(url_for('admin.login', next=request.path))

    return None


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
        admin_emails = current_app.config.get('ADMIN_EMAILS') or set()
        user = User.query.filter_by(email=email).first() if email in admin_emails else None

        if user and user.check_password(password) and is_app_admin(user):
            if getattr(user, 'is_suspended', False):
                flash('This admin account is suspended.', 'error')
                return render_admin_template('admin_login.html', 'login')

            if not user.is_email_verified:
                flash('Verify this account email before using the admin dashboard.', 'error')
                return render_admin_template('admin_login.html', 'login')

            session['admin_user_id'] = user.id
            flash('Admin sign in successful.', 'success')
            return redirect(safe_admin_redirect())

        flash('Invalid admin email or password.', 'error')

    return render_admin_template('admin_login.html', 'login')


@admin_bp.route('/logout')
def logout():
    session.pop('admin_user_id', None)
    flash('Signed out of admin.', 'info')
    return redirect(url_for('admin.login'))


def count_users_created_between(users, start, end):
    return sum(1 for user in users if user.created_at and start <= user.created_at < end)


def admin_users_redirect(user_id=None, tab='all'):
    anchor = f'{tab}-user-{user_id}' if user_id else None
    return redirect(url_for('admin.users', tab=tab, _anchor=anchor))


def count_map(query):
    return {row[0]: row[1] for row in query.all() if row[0]}


def max_date_map(query):
    return {row[0]: row[1] for row in query.all() if row[0] and row[1]}


def timestamp_value(value):
    return int(value.timestamp()) if value else 0


def admin_metric_maps():
    return {
        'member_groups': count_map(
            db.session.query(group_members.c.user_id, func.count(group_members.c.group_id))
            .group_by(group_members.c.user_id)
        ),
        'admin_groups': count_map(
            db.session.query(Group.admin_id, func.count(Group.id))
            .group_by(Group.admin_id)
        ),
        'expenses_paid': count_map(
            db.session.query(Expense.paid_by_id, func.count(Expense.id))
            .group_by(Expense.paid_by_id)
        ),
        'splits_owed': count_map(
            db.session.query(ExpenseSplit.user_id, func.count(ExpenseSplit.id))
            .group_by(ExpenseSplit.user_id)
        ),
        'payments_sent': count_map(
            db.session.query(Payment.payer_id, func.count(Payment.id))
            .group_by(Payment.payer_id)
        ),
        'payments_received': count_map(
            db.session.query(Payment.receiver_id, func.count(Payment.id))
            .group_by(Payment.receiver_id)
        ),
        'last_paid_expense': max_date_map(
            db.session.query(Expense.paid_by_id, func.max(Expense.date))
            .group_by(Expense.paid_by_id)
        ),
        'last_owed_expense': max_date_map(
            db.session.query(ExpenseSplit.user_id, func.max(Expense.date))
            .join(Expense)
            .group_by(ExpenseSplit.user_id)
        )
    }


def user_row(user, now, metrics=None, month_start=None, inactive_cutoff=None,
             split_users_this_month=None, core_users=None, reminder_candidate_ids=None):
    metrics = metrics or {}
    split_users_this_month = split_users_this_month or set()
    core_users = core_users or set()
    reminder_candidate_ids = reminder_candidate_ids or set()

    last_usage_at = user_last_usage_at(user)
    last_paid_expense_at = metrics.get('last_paid_expense', {}).get(user.id)
    last_owed_expense_at = metrics.get('last_owed_expense', {}).get(user.id)
    split_dates = [value for value in (last_paid_expense_at, last_owed_expense_at) if value]
    last_split_at = max(split_dates) if split_dates else None
    payments_sent = metrics.get('payments_sent', {}).get(user.id, 0)
    payments_received = metrics.get('payments_received', {}).get(user.id, 0)

    return {
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'created_at': user.created_at,
        'created_sort': timestamp_value(user.created_at),
        'last_login_at': user.last_login_at,
        'last_login_sort': timestamp_value(user.last_login_at),
        'last_activity_at': user.last_activity_at,
        'last_usage_at': last_usage_at,
        'last_usage_sort': timestamp_value(last_usage_at),
        'last_split_at': last_split_at,
        'last_split_sort': timestamp_value(last_split_at),
        'days_idle': (now - last_usage_at).days if last_usage_at else None,
        'days_idle_sort': (now - last_usage_at).days if last_usage_at else 999999,
        'last_inactivity_email_sent_at': user.last_inactivity_email_sent_at,
        'last_inactivity_email_sent_sort': timestamp_value(user.last_inactivity_email_sent_at),
        'is_suspended': getattr(user, 'is_suspended', False),
        'is_email_verified': user.is_email_verified,
        'is_admin': is_app_admin(user),
        'member_group_count': metrics.get('member_groups', {}).get(user.id, 0),
        'admin_group_count': metrics.get('admin_groups', {}).get(user.id, 0),
        'expense_count': metrics.get('expenses_paid', {}).get(user.id, 0),
        'split_count': metrics.get('splits_owed', {}).get(user.id, 0),
        'payments_sent_count': payments_sent,
        'payments_received_count': payments_received,
        'payment_count': payments_sent + payments_received,
        'has_split_this_month': user.id in split_users_this_month,
        'has_core_activity': user.id in core_users,
        'created_this_month': bool(month_start and user.created_at and month_start <= user.created_at <= now),
        'is_long_inactive': bool(inactive_cutoff and last_usage_at and last_usage_at < inactive_cutoff),
        'is_reminder_candidate': user.id in reminder_candidate_ids
    }


def admin_report_snapshot():
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
    metrics = admin_metric_maps()
    split_users_this_month = split_user_ids_since(month_start)
    core_users = core_activity_user_ids()
    reminder_candidates = inactive_reminder_candidates(now)
    reminder_candidate_ids = {user.id for user in reminder_candidates}

    user_rows = [
        user_row(
            user,
            now,
            metrics=metrics,
            month_start=month_start,
            inactive_cutoff=inactive_cutoff,
            split_users_this_month=split_users_this_month,
            core_users=core_users,
            reminder_candidate_ids=reminder_candidate_ids
        )
        for user in users
    ]

    total_users = len(users)
    verified_users = sum(1 for user in users if user.is_email_verified)
    suspended_users = sum(1 for user in users if getattr(user, 'is_suspended', False))
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

    no_split_this_month = [
        row for row in user_rows if not row['has_split_this_month']
    ]
    never_used_core_feature = [
        row for row in user_rows if not row['has_core_activity']
    ]
    long_inactive_users = [
        row for row in user_rows if row['is_long_inactive']
    ]
    new_user_rows = [
        row for row in user_rows if row['created_this_month']
    ]
    reminder_candidate_rows = [
        row for row in user_rows if row['is_reminder_candidate']
    ]
    suspended_user_rows = [
        row for row in user_rows if row['is_suspended']
    ]

    stats = {
        'total_users': total_users,
        'verified_users': verified_users,
        'suspended_users': suspended_users,
        'new_users_this_month': new_users_this_month,
        'new_user_delta': new_user_delta,
        'no_split_this_month': len(no_split_this_month),
        'never_used_core_feature': len(never_used_core_feature),
        'long_inactive_users': len(long_inactive_users),
        'reminder_candidates': len(reminder_candidates)
    }

    return {
        'now': now,
        'stats': stats,
        'growth_data': growth_data,
        'users': user_rows,
        'new_users_this_month': new_user_rows,
        'no_split_this_month': no_split_this_month,
        'never_used_core_feature': never_used_core_feature,
        'long_inactive_users': long_inactive_users,
        'suspended_users_list': suspended_user_rows,
        'reminder_candidates': reminder_candidate_rows,
        'inactivity_days': current_app.config['INACTIVITY_REMINDER_DAYS'],
        'email_cooldown_days': current_app.config['INACTIVITY_EMAIL_COOLDOWN_DAYS'],
        'emails_enabled': current_app.config['INACTIVITY_EMAILS_ENABLED'],
        'email_hour_utc': current_app.config['INACTIVITY_EMAIL_HOUR_UTC']
    }


def user_report_tabs(snapshot):
    return [
        {
            'id': 'all',
            'label': 'All Users',
            'users': snapshot['users'],
            'empty': 'No users have signed up yet.'
        },
        {
            'id': 'new',
            'label': 'New This Month',
            'users': snapshot['new_users_this_month'],
            'empty': 'No new users joined this month.'
        },
        {
            'id': 'no_split',
            'label': 'No Split This Month',
            'users': snapshot['no_split_this_month'],
            'empty': 'Every user has split activity this month.'
        },
        {
            'id': 'never_used',
            'label': 'Never Used Core',
            'users': snapshot['never_used_core_feature'],
            'empty': 'Every user has used at least one core feature.'
        },
        {
            'id': 'inactive',
            'label': 'Long Inactive',
            'users': snapshot['long_inactive_users'],
            'empty': 'No users are past the inactivity threshold.'
        },
        {
            'id': 'suspended',
            'label': 'Suspended',
            'users': snapshot['suspended_users_list'],
            'empty': 'No user accounts are suspended.'
        },
        {
            'id': 'reminder_ready',
            'label': 'Reminder Ready',
            'users': snapshot['reminder_candidates'],
            'empty': 'No verified inactive users are ready for a reminder.'
        }
    ]


@admin_bp.route('/')
@admin_required
def dashboard():
    snapshot = admin_report_snapshot()

    return render_template(
        'admin_dashboard.html',
        admin_user=admin_user(),
        active_admin_page='dashboard',
        stats=snapshot['stats'],
        growth_data=snapshot['growth_data'],
        inactivity_days=snapshot['inactivity_days'],
        emails_enabled=snapshot['emails_enabled'],
        email_hour_utc=snapshot['email_hour_utc']
    )


@admin_bp.route('/users')
@admin_required
def users():
    snapshot = admin_report_snapshot()
    tabs = user_report_tabs(snapshot)
    active_tab = request.args.get('tab', 'all')
    valid_tabs = {tab['id'] for tab in tabs}
    if active_tab not in valid_tabs:
        active_tab = 'all'

    return render_admin_template(
        'admin_users.html',
        'users',
        stats=snapshot['stats'],
        tabs=tabs,
        active_tab=active_tab,
        inactivity_days=snapshot['inactivity_days']
    )


@admin_bp.route('/users/create', methods=['POST'])
@admin_required
def create_user():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()
    is_email_verified = request.form.get('is_email_verified') == 'on'
    should_send_reset = request.form.get('send_password_reset') == 'on'

    if not name:
        flash('User name is required.', 'error')
        return admin_users_redirect(tab='all')

    if not email or '@' not in email:
        flash('A valid user email is required.', 'error')
        return admin_users_redirect(tab='all')

    admin_emails = current_app.config.get('ADMIN_EMAILS') or set()
    if email in admin_emails:
        flash('Admin emails are controlled by ADMIN_EMAILS and cannot be created here.', 'error')
        return admin_users_redirect(tab='all')

    if User.query.filter_by(email=email).first():
        flash('A user with that email already exists.', 'error')
        return admin_users_redirect(tab='all')

    user = User(email=email, name=name, is_email_verified=is_email_verified)
    user.set_password(secrets.token_urlsafe(24))
    db.session.add(user)
    db.session.commit()

    if should_send_reset:
        token = generate_password_reset_token(user)
        reset_url = url_for('auth.reset_password', token=token, _external=True)
        try:
            sent = send_password_reset_email(user, reset_url)
        except Exception as exc:
            current_app.logger.exception('Failed to send new-user password setup to %s: %s', user.email, exc)
            sent = False

        if sent:
            flash(f'Created {user.name} and sent a password setup email.', 'success')
        else:
            flash(f'Created {user.name}, but the password setup email could not be sent.', 'error')
    else:
        flash(f'Created {user.name}. Send a password reset when they are ready to sign in.', 'success')

    return admin_users_redirect(user.id, 'all')


@admin_bp.route('/emails')
@admin_required
def emails():
    snapshot = admin_report_snapshot()

    return render_admin_template(
        'admin_emails.html',
        'emails',
        stats=snapshot['stats'],
        reminder_candidates=snapshot['reminder_candidates'],
        long_inactive_users=snapshot['long_inactive_users'],
        inactivity_days=snapshot['inactivity_days'],
        email_cooldown_days=snapshot['email_cooldown_days'],
        emails_enabled=snapshot['emails_enabled'],
        email_hour_utc=snapshot['email_hour_utc']
    )


@admin_bp.route('/users/<int:user_id>/profile', methods=['POST'])
@admin_required
def update_user_profile(user_id):
    user = User.query.get_or_404(user_id)
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()
    tab = request.form.get('tab') or 'all'

    if not name:
        flash('User name is required.', 'error')
        return admin_users_redirect(user.id, tab)

    if not email or '@' not in email:
        flash('A valid user email is required.', 'error')
        return admin_users_redirect(user.id, tab)

    admin_emails = current_app.config.get('ADMIN_EMAILS') or set()
    if email in admin_emails and not is_app_admin(user):
        flash('Admin emails are controlled by ADMIN_EMAILS and cannot be assigned here.', 'error')
        return admin_users_redirect(user.id, tab)

    if is_app_admin(user) and email != user.email:
        flash('Admin account emails must be changed in ADMIN_EMAILS and cannot be edited here.', 'error')
        return admin_users_redirect(user.id, tab)

    existing = User.query.filter(User.email == email, User.id != user.id).first()
    if existing:
        flash('Another user already has that email.', 'error')
        return admin_users_redirect(user.id, tab)

    user.name = name
    user.email = email
    db.session.commit()
    flash(f'Updated {user.name}.', 'success')
    return admin_users_redirect(user.id, tab)


@admin_bp.route('/users/<int:user_id>/status', methods=['POST'])
@admin_required
def update_user_status(user_id):
    user = User.query.get_or_404(user_id)
    tab = request.form.get('tab') or 'all'

    if is_app_admin(user):
        user.is_email_verified = True
        user.is_suspended = False
        db.session.commit()
        flash('Admin accounts must stay verified and active.', 'info')
        return admin_users_redirect(user.id, tab)

    user.is_email_verified = request.form.get('is_email_verified') == 'on'
    user.is_suspended = request.form.get('is_suspended') == 'on'
    if not user.is_email_verified:
        user.clear_email_otp()

    db.session.commit()
    flash(f'Updated account status for {user.name}.', 'success')
    return admin_users_redirect(user.id, tab)


@admin_bp.route('/users/<int:user_id>/password-reset', methods=['POST'])
@admin_required
def send_user_password_reset(user_id):
    user = User.query.get_or_404(user_id)
    tab = request.form.get('tab') or 'all'
    token = generate_password_reset_token(user)
    reset_url = url_for('auth.reset_password', token=token, _external=True)

    try:
        sent = send_password_reset_email(user, reset_url)
    except Exception as exc:
        current_app.logger.exception('Failed to send admin password reset to %s: %s', user.email, exc)
        sent = False

    if sent:
        flash(f'Sent password reset email to {user.email}.', 'success')
    else:
        flash('Could not send the password reset email. Check MAIL_PASSWORD.', 'error')

    return admin_users_redirect(user.id, tab)


@admin_bp.route('/send-inactivity-reminders', methods=['POST'])
@admin_required
def send_inactivity_reminders_now():
    result = send_inactivity_reminders()
    redirect_target = request.form.get('next') or url_for('admin.emails')
    if not redirect_target.startswith('/admin') or redirect_target.startswith('//'):
        redirect_target = url_for('admin.emails')

    if result['sent']:
        flash(f'Sent {result["sent"]} inactivity reminder email(s).', 'success')
    elif result['skipped']:
        flash('No reminders were sent because MAIL_PASSWORD is not configured.', 'info')
    else:
        flash('No eligible inactive users needed a reminder right now.', 'info')

    if result['failed']:
        flash(f'{result["failed"]} reminder email(s) failed. Check the app logs.', 'error')

    return redirect(redirect_target)
