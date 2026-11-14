import re
import secrets
from io import BytesIO
from datetime import datetime, timedelta

import qrcode
from qrcode.image.svg import SvgPathImage

from flask import Blueprint, Response, abort, current_app, jsonify, render_template, request, flash, redirect, send_from_directory, url_for
from flask_login import login_required, current_user, login_user
from sqlalchemy import func, or_
from app import db, limiter
from app.regions import countries_payload, normalize_country, payment_fields_for
from app.email_validation import normalize_email
from app.email_utils import send_group_invite_email, send_splitmate_invite_email
from app.models import User, Group, GroupInvite, Expense, ExpenseSplit, ExpenseHistory, Note, Payment, RewardTransaction, Task
from app.routes.auth import send_user_otp, set_pending_verification
from app.group_utils import group_member_payload, group_pending_invite_payload, set_member_nickname
from app import billing
from app.rewards import REWARD_TIERS, reward_progress
from app.routes import split as split_routes
from app.payment_security import apply_payment_handle_changes, send_interac_code, verify_interac_code
from app.security import clean_payment_handles, display_name_error, password_error

main_bp = Blueprint('main', __name__)
RECEIPT_FILENAME = re.compile(r'^[0-9a-f]{32}\.(png|jpg|jpeg|gif|webp|pdf)$')
# Wording used whether or not the address already has an account, so it can't be used to look people up.
SPLITMATE_INVITE_MESSAGE = 'If {email} is not on Splitmate yet, we sent them an invite.'


@main_bp.route('/receipts/<filename>')
def receipt_file(filename):
    """Receipts are private: open to members of the expense's group, or with a fresh signed link from the app."""
    if not RECEIPT_FILENAME.match(filename):
        abort(404)
    stored_url = f'{split_routes.RECEIPT_URL_PREFIX}{filename}'
    expense = Expense.query.filter_by(receipt_url=stored_url).first()
    if not expense:
        abort(404)

    signed_ok = split_routes.receipt_signature_valid(filename, request.args.get('sig'))
    member_ok = current_user.is_authenticated and current_user in expense.group.members
    if not (signed_ok or member_ok):
        abort(404)

    response = send_from_directory(split_routes.receipt_upload_dir(), filename)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cache-Control'] = 'private, no-store'
    return response


def invite_to_group(group, inviter, email):
    """Creates (or reuses) a pending invite and emails it. Returns (invite, created_new, email_sent)."""
    invite = GroupInvite.query.filter(
        GroupInvite.group_id == group.id,
        GroupInvite.email == email,
        GroupInvite.accepted_at.is_(None),
        GroupInvite.revoked_at.is_(None),
        GroupInvite.expires_at > datetime.utcnow()
    ).order_by(GroupInvite.created_at.desc()).first()

    created_new = False
    if not invite:
        invite = GroupInvite(
            group_id=group.id,
            email=email,
            token=generate_invite_token(),
            invited_by_id=inviter.id,
            expires_at=datetime.utcnow() + timedelta(days=current_app.config['GROUP_INVITE_EXPIRY_DAYS'])
        )
        db.session.add(invite)
        db.session.flush()
        created_new = True

    email_sent = False
    try:
        email_sent = send_group_invite_email(email, group, inviter, group_invite_url(invite))
    except Exception as exc:
        current_app.logger.exception('Failed to send group invite email to %s: %s', email, exc)
    return invite, created_new, email_sent

def safe_redirect_target(default_endpoint='main.home'):
    target = request.form.get('next', '').strip()
    if target.startswith('/') and not target.startswith('//'):
        return target
    return url_for(default_endpoint)


def wants_json_response():
    return (
        request.headers.get('X-Requested-With') == 'fetch'
        or 'application/json' in request.headers.get('Accept', '')
    )


def group_invite_url(invite):
    return url_for('main.accept_group_invite', token=invite.token, _external=True)


def generate_invite_token():
    while True:
        token = secrets.token_urlsafe(32)
        if not GroupInvite.query.filter_by(token=token).first():
            return token


def vcard_escape(value):
    return (
        str(value or '')
        .replace('\\', '\\\\')
        .replace('\r', '')
        .replace('\n', '\\n')
        .replace(';', '\\;')
        .replace(',', '\\,')
    )


def profile_qr_payload(user):
    profile_url = url_for('main.profile', _external=True)
    return '\n'.join([
        'BEGIN:VCARD',
        'VERSION:3.0',
        f'FN:{vcard_escape(user.name)}',
        f'EMAIL:{vcard_escape(user.email)}',
        'ORG:Splitmate',
        f'URL:{vcard_escape(profile_url)}',
        'NOTE:Splitmate profile contact',
        'END:VCARD',
    ])


def invite_response(payload, status=200, redirect_target=None, category='success'):
    if wants_json_response():
        return jsonify(payload), status

    flash(payload.get('message', 'Invite updated.'), category)
    if payload.get('invite_url'):
        flash(f'Invite link: {payload["invite_url"]}', 'info')
    return redirect(redirect_target or url_for('main.home'))


@main_bp.route('/join')
def join_splitmate():
    if current_user.is_authenticated:
        flash('You are already using Splitmate.', 'info')
        return redirect(url_for('main.home'))

    email = normalize_email(request.args.get('email'))
    register_kwargs = {'email': email} if email else {}
    return render_template(
        'join_splitmate.html',
        email=email,
        login_url=url_for('auth.login'),
        register_url=url_for('auth.register', **register_kwargs)
    )

@main_bp.route('/')
@login_required
def home():
    groups = current_user.groups.all()

    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)

    monthly_spending = {}
    recent_expenses = []

    # Build monthly totals and recent items. ExpenseHistory already holds a copy
    # of every active expense, so summing Expense too would double count.
    for group in groups:
        history_sum = db.session.query(func.coalesce(func.sum(ExpenseHistory.amount), 0.0)).filter(
            ExpenseHistory.group_id == group.id,
            ExpenseHistory.date >= month_start
        ).scalar()

        monthly_spending[group.name] = float(history_sum)

        recent = Expense.query.filter_by(group_id=group.id) \
            .order_by(Expense.date.desc()) \
            .limit(5).all()
        recent_expenses.extend(recent)

    recent_expenses.sort(key=lambda x: x.date, reverse=True)
    recent_expenses = recent_expenses[:10]

    # Totals owed/owes for current user (unchanged)
    total_owed_to_user = 0
    total_user_owes = 0

    for expense in Expense.query.filter_by(paid_by_id=current_user.id).all():
        for split in expense.splits:
            if split.user_id != current_user.id and not split.is_settled:
                total_owed_to_user += split.amount_owed

    for split in ExpenseSplit.query.filter_by(user_id=current_user.id, is_settled=False).all():
        if split.expense.paid_by_id != current_user.id:
            total_user_owes += split.amount_owed

    # Build last 6 months series for charts. ExpenseHistory has a copy of every
    # expense ever added, so it alone is the source of truth for totals.
    def month_sequence(n=6):
        y, m = now.year, now.month
        seq = []
        for i in range(n - 1, -1, -1):
            mm = m - i
            yy = y
            while mm <= 0:
                mm += 12
                yy -= 1
            seq.append((yy, mm))
        return seq

    months = month_sequence(6)
    group_ids = [group.id for group in groups]
    history_items = ExpenseHistory.query.filter(
        ExpenseHistory.group_id.in_(group_ids)
    ).all() if group_ids else []

    category_totals = {}
    payer_totals = {}
    group_totals = {}
    group_names = {group.id: group.name for group in groups}
    insight_months = {
        f'{yy}-{str(mm).zfill(2)}': {
            'label': datetime(yy, mm, 1).strftime("%b '%y"),
            'total': 0.0,
            'percent': 0
        }
        for yy, mm in months
    }
    payer_ids = {item.paid_by_id for item in history_items if item.paid_by_id}
    payer_names = {
        user.id: user.name
        for user in User.query.filter(User.id.in_(payer_ids)).all()
    } if payer_ids else {}
    insight_total = 0.0

    for item in history_items:
        amount = float(item.amount or 0)
        insight_total += amount

        category = (getattr(item, 'category', None) or 'General').strip() or 'General'
        category_totals[category] = category_totals.get(category, 0.0) + amount

        if item.date:
            month_key = item.date.strftime('%Y-%m')
            if month_key in insight_months:
                insight_months[month_key]['total'] += amount

        payer_name = payer_names.get(item.paid_by_id, 'Unknown')
        payer_totals[payer_name] = payer_totals.get(payer_name, 0.0) + amount

        group_name = group_names.get(item.group_id, 'Unknown')
        group_totals[group_name] = group_totals.get(group_name, 0.0) + amount

    def insight_rows(totals, label_key):
        rows = [
            {label_key: label, 'total': total, 'percent': 0}
            for label, total in totals.items()
        ]
        rows.sort(key=lambda row: row['total'], reverse=True)
        max_total = max((row['total'] for row in rows), default=0)
        if max_total:
            for row in rows:
                row['percent'] = max(4, round(row['total'] / max_total * 100))
        return rows

    category_rows = insight_rows(category_totals, 'category')
    payer_rows = insight_rows(payer_totals, 'name')[:5]
    max_month_total = max((row['total'] for row in insight_months.values()), default=0)
    if max_month_total:
        for row in insight_months.values():
            # Keep a sliver visible for small months, but show empty months as empty.
            row['percent'] = max(6, round(row['total'] / max_month_total * 100)) if row['total'] else 0

    spending_insights = {
        'total': insight_total,
        'count': len(history_items),
        'top_category': category_rows[0]['category'] if category_rows else 'None',
        'category_totals': category_rows,
        'payer_totals': payer_rows,
        'group_totals': insight_rows(group_totals, 'name'),
        'average': insight_total / len(history_items) if history_items else 0.0,
        'monthly_totals': list(insight_months.values())
    }


    # JSON-safe group data for Manage modal (prevents "User is not JSON serializable")
    groups_json = [
        {
            'id': g.id,
            'name': g.name,
            'admin_id': g.admin_id,
            'members': group_member_payload(g),
            'pending_invites': group_pending_invite_payload(g) if g.admin_id == current_user.id else []
        }
        for g in groups
    ]

    return render_template(
        'home.html',
        groups=groups,
        groups_json=groups_json,
        monthly_spending=monthly_spending,
        recent_expenses=recent_expenses,
        total_owed_to_user=total_owed_to_user,
        total_user_owes=total_user_owes,
        spending_insights=spending_insights
    )

@main_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        form_type = request.form.get('form_type', '').strip()

        if form_type == 'details':
            name = request.form.get('name', '').strip()
            email = normalize_email(request.form.get('email'))
            errors = []

            name_error = display_name_error(name, 'Full name')
            if name_error:
                errors.append(name_error)
            if not email:
                errors.append('Valid email is required.')

            existing_user = User.query.filter(
                User.email == email,
                User.id != current_user.id
            ).first() if email else None
            if existing_user:
                errors.append('That email is already used by another account.')

            email_changed = bool(email) and email != current_user.email
            # Changing the sign-in email is a takeover risk, so it needs the current password.
            if email_changed and not current_user.check_password(request.form.get('current_password', '')):
                errors.append('Enter your current password to change your email.')

            # Country decides currency and payment apps, so changing it needs the password too.
            country = normalize_country(request.form.get('country')) if request.form.get('country') else current_user.country
            if not country:
                errors.append('Choose a country from the list.')
            elif country != current_user.country and not current_user.check_password(request.form.get('current_password', '')):
                errors.append('Enter your current password to change your country.')

            handles, handle_error = clean_payment_handles(request.form)
            if handle_error:
                errors.append(handle_error)

            if errors:
                for error in errors:
                    flash(error, 'error')
                return redirect(url_for('main.profile'))

            # Payment details need the password too, and the owner is emailed about any change.
            payment_result, payment_error = apply_payment_handle_changes(
                current_user, handles, request.form.get('current_password', '')
            )
            if payment_error:
                db.session.rollback()
                flash(payment_error, 'error')
                return redirect(url_for('main.profile'))
            if payment_result['interac_code_sent']:
                flash('We emailed a 6-digit code to your new Interac email. Enter it below to start using it.', 'info')
            current_user.name = name
            current_user.country = country

            if email_changed:
                current_user.email = email
                current_user.is_email_verified = False
                current_user.clear_email_otp()
                set_pending_verification(current_user)

                try:
                    otp_sent = send_user_otp(current_user)
                except Exception as exc:
                    current_app.logger.exception('Failed to send profile email verification OTP: %s', exc)
                    otp_sent = False

                if otp_sent:
                    flash('Profile updated. Verify your new email with the OTP we sent.', 'success')
                    return redirect(url_for('auth.verify_email'))

                flash('Profile updated, but the verification email could not be sent. Use Resend OTP to try again.', 'info')
                return redirect(url_for('auth.verify_email'))

            db.session.commit()
            flash('Profile details updated.', 'success')
            return redirect(url_for('main.profile'))

        if form_type == 'interac_verify':
            error = verify_interac_code(current_user, request.form.get('otp'))
            db.session.commit()
            flash(error or 'Interac email confirmed. Members who owe you can now see it.', 'error' if error else 'success')
            return redirect(url_for('main.profile'))

        if form_type == 'interac_resend':
            if not current_user.pending_interac_email:
                flash('There is no Interac email waiting for a code.', 'error')
            elif send_interac_code(current_user):
                flash('A new code is on its way.', 'success')
            else:
                flash('The code email could not be sent. Try again in a minute.', 'error')
            db.session.commit()
            return redirect(url_for('main.profile'))

        if form_type == 'password':
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')
            errors = []

            if not current_user.check_password(current_password):
                errors.append('Current password is incorrect.')
            new_password_error = password_error(new_password)
            if new_password_error:
                errors.append(new_password_error)
            if new_password != confirm_password:
                errors.append('New password and confirmation do not match.')

            if errors:
                for error in errors:
                    flash(error, 'error')
                return redirect(url_for('main.profile'))

            user = current_user._get_current_object()
            user.set_password(new_password)
            db.session.commit()
            # set_password signs out every other browser; keep this one signed in.
            login_user(user, remember=True)
            flash('Password updated. Other devices were signed out.', 'success')
            return redirect(url_for('main.profile'))

        flash('Choose a valid profile action.', 'error')
        return redirect(url_for('main.profile'))

    recent_reward_transactions = (
        current_user.reward_transactions
        .order_by(db.desc('created_at'))
        .limit(5)
        .all()
    )

    return render_template(
        'profile.html',
        reward_progress=reward_progress(current_user.reward_points),
        reward_tiers=REWARD_TIERS,
        membership=billing.membership_payload(current_user),
        recent_reward_transactions=recent_reward_transactions,
        countries=countries_payload(),
        payment_fields=payment_fields_for(current_user.country),
    )


@main_bp.route('/profile/qr.svg')
@login_required
def profile_qr():
    qr_image = qrcode.make(
        profile_qr_payload(current_user),
        image_factory=SvgPathImage,
        box_size=10,
        border=2,
    )
    output = BytesIO()
    qr_image.save(output)

    response = Response(output.getvalue(), mimetype='image/svg+xml')
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['Content-Disposition'] = 'inline; filename=splitmate-profile-qr.svg'
    return response


def iso_datetime(value):
    return value.isoformat() if value else None


@main_bp.route('/profile/export.json')
@login_required
def export_profile_data():
    group_ids = [group.id for group in current_user.groups.all()]
    data = {
        'profile': {
            'id': current_user.id,
            'name': current_user.name,
            'email': current_user.email,
            'created_at': iso_datetime(current_user.created_at),
            'reward_points': int(current_user.reward_points or 0),
            'membership_plan': current_user.membership_plan or 'free',
            'membership_status': current_user.membership_status or 'active',
        },
        'groups': [{
            'id': group.id,
            'name': group.name,
            'admin_id': group.admin_id,
            'created_at': iso_datetime(group.created_at),
            'members': group_member_payload(group),
        } for group in current_user.groups.all()],
        'expenses': [{
            'id': expense.id,
            'description': expense.description,
            'amount': round(expense.amount, 2),
            'category': expense.category,
            'date': iso_datetime(expense.date),
            'group_id': expense.group_id,
            'paid_by_id': expense.paid_by_id,
        } for expense in Expense.query.filter(Expense.group_id.in_(group_ids)).order_by(Expense.date.desc()).all()] if group_ids else [],
        'payments': [{
            'id': payment.id,
            'amount': round(payment.amount, 2),
            'date': iso_datetime(payment.date),
            'group_id': payment.group_id,
            'payer_id': payment.payer_id,
            'receiver_id': payment.receiver_id,
            'method': payment.method,
            'status': payment.status,
            'reward_points_awarded': int(payment.reward_points_awarded or 0),
        } for payment in Payment.query.filter(
            or_(Payment.payer_id == current_user.id, Payment.receiver_id == current_user.id)
        ).order_by(Payment.date.desc()).all()],
        'tasks': [{
            'id': task.id,
            'title': task.title,
            'description': task.description or '',
            'due_date': iso_datetime(task.due_date),
            'reminder_time': iso_datetime(task.reminder_time),
            'priority': task.priority,
            'recurrence': task.recurrence,
            'is_completed': bool(task.is_completed),
            'group_id': task.group_id,
            'assigned_to_id': task.assigned_to_id,
            'created_by_id': task.created_by_id,
        } for task in Task.query.filter(Task.group_id.in_(group_ids)).order_by(Task.due_date.desc()).all()] if group_ids else [],
        'notes': [{
            'id': note.id,
            'title': note.title or note.content,
            'description': note.description or '',
            'content': note.content,
            'is_completed': bool(note.is_completed),
            'created_at': iso_datetime(note.created_at),
            'group_id': note.group_id,
            'created_by_id': note.created_by_id,
        } for note in Note.query.filter(Note.group_id.in_(group_ids)).order_by(Note.created_at.desc()).all()] if group_ids else [],
        'rewards': [{
            'id': transaction.id,
            'points': transaction.points,
            'type': transaction.type,
            'note': transaction.note,
            'payment_id': transaction.payment_id,
            'created_at': iso_datetime(transaction.created_at),
        } for transaction in RewardTransaction.query.filter_by(user_id=current_user.id).order_by(RewardTransaction.created_at.desc()).all()],
    }
    response = jsonify(data)
    response.headers['Content-Disposition'] = 'attachment; filename=splitmate-account-data.json'
    return response


@main_bp.route('/privacy')
def privacy_policy():
    return render_template('legal.html', page_title='Privacy Policy', legal_kind='privacy')


@main_bp.route('/terms')
def terms():
    return render_template('legal.html', page_title='Terms', legal_kind='terms')

@main_bp.route('/group/create', methods=['POST'])
@login_required
def create_group():
    name = request.form.get('name', '').strip()
    redirect_target = safe_redirect_target()
    name_error = display_name_error(name, 'Group name')
    if name_error:
        flash(name_error, 'error')
        return redirect(redirect_target)

    from app.regions import currency_for_country, normalize_currency
    currency = normalize_currency(request.form.get('currency')) or currency_for_country(current_user.country)
    group = Group(name=name, admin_id=current_user.id, currency=currency)
    group.members.append(current_user)
    db.session.add(group)
    db.session.flush()
    set_member_nickname(group.id, current_user)
    db.session.commit()

    flash(f'Group "{name}" created!', 'success')
    return redirect(redirect_target)

@main_bp.route('/group/<int:group_id>/members/add', methods=['POST'])
@login_required
@limiter.limit('30 per hour')
def add_group_member(group_id):
    """People join a group by accepting an invite, never by being added without asking."""
    group = Group.query.get_or_404(group_id)
    if group.admin_id != current_user.id:
        flash('Only the group admin can add members.', 'error')
        return redirect(url_for('main.home'))

    email = normalize_email(request.form.get('email'))
    if not email:
        flash('Enter a valid member email.', 'error')
        return redirect(url_for('main.home'))

    existing_user = User.query.filter_by(email=email).first()
    if existing_user and existing_user in group.members:
        flash(f'{existing_user.name} is already in this group.', 'info')
        return redirect(url_for('main.home'))

    invite_to_group(group, current_user, email)
    db.session.commit()
    flash(f'Invite sent to {email}. They join "{group.name}" once they accept it.', 'success')
    return redirect(url_for('main.home'))


@main_bp.route('/group/<int:group_id>/invites', methods=['POST'])
@login_required
@limiter.limit('30 per hour')
def create_group_invite(group_id):
    group = Group.query.get_or_404(group_id)
    redirect_target = safe_redirect_target()
    if group.admin_id != current_user.id:
        return invite_response(
            {'error': 'Only the group admin can invite members.', 'message': 'Only the group admin can invite members.'},
            status=403,
            redirect_target=redirect_target,
            category='error'
        )

    email = normalize_email(request.form.get('email'))
    if not email:
        return invite_response(
            {'error': 'Enter a valid email address.', 'message': 'Enter a valid email address.'},
            status=400,
            redirect_target=redirect_target,
            category='error'
        )

    existing_user = User.query.filter_by(email=email).first()
    if existing_user and existing_user in group.members:
        return invite_response(
            {
                'already_member': True,
                'message': f'{existing_user.name} is already in "{group.name}".'
            },
            redirect_target=redirect_target,
            category='info'
        )

    invite, created_new, email_sent = invite_to_group(group, current_user, email)
    invite_url = group_invite_url(invite)
    db.session.commit()
    if email_sent:
        message = f'Invite sent to {email}.'
    else:
        message = f'Invite link created for {email}. Copy and share it manually.'

    return invite_response(
        {
            'message': message,
            'email': email,
            'email_sent': email_sent,
            'created_new': created_new,
            'invite_url': invite_url,
            'expires_at': invite.expires_at.isoformat()
        },
        status=201 if created_new else 200,
        redirect_target=redirect_target,
        category='success' if email_sent else 'info'
    )


@main_bp.route('/invite-splitmate', methods=['POST'])
@login_required
@limiter.limit('10 per hour')
def invite_splitmate():
    redirect_target = safe_redirect_target()
    email = normalize_email(request.form.get('email'))
    if not email:
        return invite_response(
            {'error': 'Enter a valid email address.', 'message': 'Enter a valid email address.'},
            status=400,
            redirect_target=redirect_target,
            category='error'
        )

    if email == normalize_email(current_user.email):
        return invite_response(
            {
                'already_user': True,
                'message': 'You are already using Splitmate.'
            },
            redirect_target=redirect_target,
            category='info'
        )

    join_url = url_for('main.join_splitmate', _external=True)
    # Existing accounts get no email and the same reply, so this can't reveal who uses Splitmate.
    if not User.query.filter_by(email=email).first():
        try:
            send_splitmate_invite_email(email, current_user, join_url)
        except Exception as exc:
            current_app.logger.exception('Failed to send Splitmate invite email to %s: %s', email, exc)

    return invite_response(
        {
            'message': SPLITMATE_INVITE_MESSAGE.format(email=email),
            'email': email,
            'invite_url': join_url
        },
        redirect_target=redirect_target,
        category='success'
    )


@main_bp.route('/group/<int:group_id>/invites/<int:invite_id>/revoke', methods=['POST'])
@login_required
def revoke_group_invite(group_id, invite_id):
    group = Group.query.get_or_404(group_id)
    redirect_target = safe_redirect_target()
    if group.admin_id != current_user.id:
        flash('Only the group admin can revoke invites.', 'error')
        return redirect(redirect_target)

    invite = GroupInvite.query.filter_by(id=invite_id, group_id=group.id).first_or_404()
    if invite.accepted_at:
        flash('That invite was already accepted.', 'info')
        return redirect(redirect_target)

    invite.revoked_at = datetime.utcnow()
    db.session.commit()
    flash(f'Invite for {invite.email} revoked.', 'success')
    return redirect(redirect_target)


@main_bp.route('/invite/<token>')
def accept_group_invite(token):
    invite = GroupInvite.query.filter_by(token=token).first()
    if not invite or invite.revoked_at:
        flash('That invite link is invalid or was revoked.', 'error')
        return redirect(url_for('main.home' if current_user.is_authenticated else 'auth.login'))

    if invite.accepted_at:
        flash('That invite was already accepted.', 'info')
        return redirect(url_for('main.home' if current_user.is_authenticated else 'auth.login'))

    if invite.expires_at <= datetime.utcnow():
        flash('That invite link has expired. Ask the group admin for a new invite.', 'error')
        return redirect(url_for('main.home' if current_user.is_authenticated else 'auth.login'))

    if not current_user.is_authenticated:
        return render_template(
            'invite.html',
            invite=invite,
            login_url=url_for('auth.login', next=request.path),
            register_url=url_for('auth.register', next=request.path)
        )

    if normalize_email(current_user.email) != invite.email:
        flash(f'This invite was sent to {invite.email}. Sign in with that email to accept it.', 'error')
        return redirect(url_for('main.home'))

    if current_user not in invite.group.members:
        invite.group.members.append(current_user)
        db.session.flush()
        set_member_nickname(invite.group.id, current_user)

    invite.accepted_at = datetime.utcnow()
    invite.accepted_by_id = current_user.id
    db.session.commit()
    flash(f'You joined "{invite.group.name}".', 'success')
    return redirect(url_for('main.home'))

@main_bp.route('/group/<int:group_id>/members/<int:user_id>/nickname', methods=['POST'])
@login_required
def update_group_member_nickname(group_id, user_id):
    group = Group.query.get_or_404(group_id)
    if group.admin_id != current_user.id:
        flash('Only the group admin can edit nicknames.', 'error')
        return redirect(url_for('main.home'))

    user = User.query.get_or_404(user_id)
    if user not in group.members:
        flash('That user is not in this group.', 'error')
        return redirect(url_for('main.home'))

    nickname = request.form.get('nickname', '').strip()
    nickname_error = display_name_error(nickname, 'Nickname') if nickname else None
    if nickname_error:
        flash(nickname_error, 'error')
        return redirect(url_for('main.home'))
    display_name = set_member_nickname(group.id, user, nickname)
    db.session.commit()
    flash(f'Nickname updated to "{display_name}".', 'success')
    return redirect(url_for('main.home'))

@main_bp.route('/group/<int:group_id>/members/<int:user_id>/remove', methods=['POST'])
@login_required
def remove_group_member(group_id, user_id):
    group = Group.query.get_or_404(group_id)
    if group.admin_id != current_user.id:
        flash('Only the group admin can remove members.', 'error')
        return redirect(url_for('main.home'))

    if user_id == group.admin_id:
        flash('The group admin cannot be removed.', 'error')
        return redirect(url_for('main.home'))

    user = User.query.get_or_404(user_id)
    if user not in group.members:
        flash('That user is not in this group.', 'error')
        return redirect(url_for('main.home'))

    if split_routes.member_has_open_balance(group, user):
        flash(f'{user.name} still has unsettled balances in "{group.name}". Settle up before removing them.', 'error')
        return redirect(url_for('main.home'))

    group.members.remove(user)
    db.session.commit()
    flash(f'{user.name} removed from "{group.name}".', 'success')
    return redirect(url_for('main.home'))
