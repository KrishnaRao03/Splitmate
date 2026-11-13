import csv
import io
import json
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import wraps

from flask import Blueprint, Response, current_app, jsonify, request, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
import qrcode
from sqlalchemy import func, or_

from app import db, limiter
from app.email_validation import email_error_message, normalize_email
from app.grocery_compare import (
    compare_grocery_list, compare_grocery_note, note_allows_grocery_comparison, parse_grocery_items_from_text,
)
from app.group_utils import group_member_payload, group_pending_invite_payload, member_nickname_rows, set_member_nickname
from app.models import (
    MoneyRequest,
    PendingRegistration,
    Expense,
    ExpenseHistory,
    ExpenseSplit,
    Group,
    GroupInvite,
    MobileDevice,
    Note,
    Payment,
    RewardTransaction,
    Task,
    User,
)
from app.rewards import MEMBERSHIP_PLANS, POINTS_EARNING_PAUSED, REWARD_TIERS, reward_progress
from app.email_utils import send_money_request_email, send_password_reset_email, send_splitmate_invite_email
from app.payment_security import (
    apply_payment_handle_changes, payment_status_payload, send_interac_code, verify_interac_code,
)
from app.routes.auth import (
    OTP_LOCKED_MESSAGE, complete_pending_registration, generate_password_reset_token, registered_account,
    send_user_otp, start_pending_registration,
)
from app.routes.main import SPLITMATE_INVITE_MESSAGE, invite_to_group, profile_qr_payload
from app.receipt_scan import ReceiptScanError, scan_receipt_image
from app.routes import split as split_routes
from app.security import clean_payment_handles, csv_safe, display_name_error, is_safe_link, normalize_phone, password_error
from app.task_utils import (
    normalize_task_priority,
    normalize_task_recurrence,
    task_is_overdue,
    toggle_task_completion,
)


mobile_api_bp = Blueprint('mobile_api', __name__, url_prefix='/api/mobile')
CENT = Decimal('0.01')
TOKEN_SALT = 'mobile-api-token'


def money_decimal(value):
    try:
        return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('Enter a valid amount.')


def token_serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


def mobile_token_for(user):
    # 'v' ties the token to the user's token_version, so password changes and "log out everywhere" revoke it.
    return token_serializer().dumps(
        {'user_id': user.id, 'email': user.email, 'v': user.token_version or 0},
        salt=TOKEN_SALT,
    )


def json_email_key():
    """Rate-limit key for sign-in and email-sending routes: the target address, falling back to the IP."""
    return normalize_email(json_body().get('email')) or request.remote_addr or 'unknown'


def mobile_token_max_age():
    days = int(current_app.config.get('MOBILE_TOKEN_EXPIRY_DAYS') or 30)
    return days * 24 * 60 * 60


def user_payload(user):
    return {
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'phone': user.phone or '',
        'is_email_verified': bool(user.is_email_verified),
        'reward_points': int(user.reward_points or 0),
        'membership_plan': user.membership_plan or 'free',
        'membership_status': user.membership_status or 'active',
        'created_at': user.created_at.isoformat() if user.created_at else None,
        'interac_email': user.interac_email or '',
        'paypal_username': user.paypal_username or '',
        'upi_id': user.upi_id or '',
        **payment_status_payload(user),
    }


def auth_payload(user):
    return {
        'token': mobile_token_for(user),
        'user': user_payload(user),
        'currency_code': (current_app.config.get('STRIPE_CURRENCY') or 'cad').upper(),
    }


def json_body():
    return request.get_json(silent=True) or {}


def json_or_form_body():
    if request.is_json:
        return json_body()

    raw_payload = request.form.get('payload', '{}')
    try:
        payload = json.loads(raw_payload)
    except (TypeError, ValueError):
        raise ValueError('The request payload is invalid.')

    if not isinstance(payload, dict):
        raise ValueError('The request payload is invalid.')
    return payload


def json_error(message, status=400):
    return jsonify({'error': message}), status


def iso_datetime(value):
    return value.isoformat() if value else None


def mobile_user_from_request():
    auth_header = request.headers.get('Authorization', '')
    prefix = 'Bearer '
    if not auth_header.startswith(prefix):
        return None

    token = auth_header[len(prefix):].strip()
    if not token:
        return None

    try:
        data = token_serializer().loads(token, salt=TOKEN_SALT, max_age=mobile_token_max_age())
    except (BadSignature, SignatureExpired):
        return None

    user = db.session.get(User, data.get('user_id'))
    if not user or user.email != data.get('email') or getattr(user, 'is_suspended', False):
        return None
    if data.get('v', 0) != (user.token_version or 0):
        return None

    return user


def mobile_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = mobile_user_from_request()
        if not user:
            return json_error('Authentication required.', 401)

        request.mobile_user = user
        now = datetime.utcnow()
        interval = timedelta(minutes=current_app.config['ACTIVITY_UPDATE_INTERVAL_MINUTES'])
        if not user.last_activity_at or now - user.last_activity_at >= interval:
            user.last_activity_at = now
            db.session.commit()

        return view(*args, **kwargs)

    return wrapped


def require_group_member(group_id):
    group = Group.query.get_or_404(group_id)
    if request.mobile_user not in group.members:
        return None, json_error('Unauthorized group access.', 403)
    return group, None


def group_payload(group):
    return {
        'id': group.id,
        'name': group.name,
        'admin_id': group.admin_id,
        'members': group_member_payload(group),
    }


def expense_payload(expense, nicknames=None):
    nicknames = nicknames or member_nickname_rows(expense.group_id)
    return {
        'id': expense.id,
        'description': expense.description,
        'amount': round(expense.amount, 2),
        'category': split_routes.normalize_expense_category(expense.category),
        'date': expense.date.isoformat() if expense.date else None,
        'paid_by_id': expense.paid_by_id,
        'paid_by': nicknames.get(expense.paid_by_id) or expense.added_by.name,
        'receipt_url': split_routes.signed_receipt_url(expense.receipt_url),
        'splits': [{
            'id': split.id,
            'user_id': split.user_id,
            'user': nicknames.get(split.user_id) or split.user.name,
            'amount': round(split.amount_owed, 2),
            'is_settled': bool(split.is_settled),
        } for split in expense.splits],
    }


def task_payload(task, nicknames=None):
    nicknames = nicknames or member_nickname_rows(task.group_id)
    return {
        'id': task.id,
        'title': task.title,
        'description': task.description or '',
        'due_date': task.due_date.isoformat() if task.due_date else None,
        'reminder_time': task.reminder_time.isoformat() if task.reminder_time else None,
        'priority': task.priority or 'medium',
        'recurrence': task.recurrence or 'none',
        'is_completed': bool(task.is_completed),
        'is_overdue': task_is_overdue(task),
        'assigned_to_id': task.assigned_to_id,
        'assigned_to': (nicknames.get(task.assigned_to_id) or task.assigned_to.name) if task.assigned_to else None,
        'created_by': nicknames.get(task.created_by_id) or task.created_by.name,
        'created_by_id': task.created_by_id,
        # Same rule as the delete endpoints: only the creator or the group admin.
        'can_delete': request.mobile_user.id in (task.created_by_id, task.group.admin_id),
        'group_id': task.group_id,
        'group_name': task.group.name,
    }


def note_payload(note, nicknames=None):
    nicknames = nicknames or member_nickname_rows(note.group_id)
    return {
        'id': note.id,
        'title': note.title or note.content,
        'description': note.description or '',
        'content': note.content,
        'is_completed': bool(note.is_completed),
        'created_at': note.created_at.isoformat() if note.created_at else None,
        'created_by': nicknames.get(note.created_by_id) or note.created_by.name,
        'created_by_id': note.created_by_id,
        # Same rule as the delete endpoints: only the writer or the group admin.
        'can_delete': request.mobile_user.id in (note.created_by_id, note.group.admin_id),
        'group_id': note.group_id,
        'group_name': note.group.name,
        'can_compare_prices': note_allows_grocery_comparison(note),
    }


def summaries_for(group):
    nicknames = member_nickname_rows(group.id)
    summaries = []
    expenses = Expense.query.filter_by(group_id=group.id).order_by(Expense.date.desc()).all()
    for expense in expenses:
        payer = nicknames.get(expense.paid_by_id) or expense.added_by.name
        for split in expense.splits:
            if split.user_id == expense.paid_by_id:
                continue
            is_settled = bool(split.is_settled)
            summaries.append({
                'split_id': split.id,
                'expense': expense.description,
                'expense_amount': round(expense.amount, 2),
                'date': expense.date.isoformat() if expense.date else None,
                'payer_id': expense.paid_by_id,
                'payer': payer,
                'owed_by_id': split.user_id,
                'owed_by': nicknames.get(split.user_id) or split.user.name,
                'amount_owed': round(split.amount_owed, 2),
                'is_settled': is_settled,
                'status': 'settled' if is_settled else 'outstanding',
                'status_label': 'Settled' if is_settled else 'Outstanding',
            })
    return summaries


def analytics_for(group):
    history_items = ExpenseHistory.query.filter_by(group_id=group.id).all()
    now = datetime.utcnow()
    months = []
    for offset in range(5, -1, -1):
        month = now.month - offset
        year = now.year
        while month <= 0:
            month += 12
            year -= 1
        months.append((year, month))

    monthly_totals = {
        f'{year}-{month:02d}': {
            'label': datetime(year, month, 1).strftime('%b'),
            'total': Decimal('0.00'),
        }
        for year, month in months
    }
    category_totals = {}
    payer_totals = {}
    total = Decimal('0.00')
    nicknames = member_nickname_rows(group.id)

    for item in history_items:
        amount = money_decimal(item.amount)
        total += amount
        category = split_routes.normalize_expense_category(item.category)
        category_totals[category] = category_totals.get(category, Decimal('0.00')) + amount

        if item.date:
            month_key = item.date.strftime('%Y-%m')
            if month_key in monthly_totals:
                monthly_totals[month_key]['total'] += amount

        payer = User.query.get(item.paid_by_id) if item.paid_by_id else None
        payer_name = nicknames.get(item.paid_by_id) or (payer.name if payer else 'Unknown')
        payer_totals[payer_name] = payer_totals.get(payer_name, Decimal('0.00')) + amount

    category_rows = sorted(
        ({'category': label, 'total': float(value)} for label, value in category_totals.items()),
        key=lambda row: row['total'],
        reverse=True,
    )
    payer_rows = sorted(
        ({'name': label, 'total': float(value)} for label, value in payer_totals.items()),
        key=lambda row: row['total'],
        reverse=True,
    )

    return {
        'total': float(total),
        'count': len(history_items),
        'top_category': category_rows[0]['category'] if category_rows else '',
        'category_totals': category_rows,
        'payer_totals': payer_rows[:5],
        'monthly_totals': [
            {'month': key, 'label': value['label'], 'total': float(value['total'])}
            for key, value in monthly_totals.items()
        ],
    }


@mobile_api_bp.route('/health')
def health():
    if current_app.config.get('BREVO_API_KEY'):
        email_provider = 'brevo'
    elif current_app.config.get('MAIL_PASSWORD'):
        email_provider = 'smtp'
    else:
        email_provider = 'none'
    from app import email_utils, grocery_compare
    return jsonify({
        'ok': True,
        'service': 'Splitmate mobile API',
        'email_provider': email_provider,
        'last_email_error': email_utils.last_email_error,
        'last_grocery_price_error': grocery_compare.last_web_price_error,
    })


@mobile_api_bp.route('/auth/login', methods=['POST'])
@limiter.limit('10 per minute; 50 per hour')
@limiter.limit('10 per 15 minutes', key_func=json_email_key)
def login():
    data = json_body()
    email = normalize_email(data.get('email'))
    password = data.get('password') or ''
    user = User.query.filter_by(email=email).first() if email else None

    if not user:
        pending = PendingRegistration.query.filter_by(email=email).first() if email else None
        if pending and pending.check_password(password):
            return json_error('Email verification is required before signing in.', 403)
    if not user or not user.check_password(password):
        return json_error('Invalid email or password.', 401)
    if getattr(user, 'is_suspended', False):
        return json_error('This account is suspended.', 403)
    if not user.is_email_verified:
        return json_error('Email verification is required before signing in.', 403)

    user.last_login_at = datetime.utcnow()
    user.last_activity_at = user.last_login_at
    db.session.commit()
    return jsonify(auth_payload(user))


@mobile_api_bp.route('/auth/register', methods=['POST'])
@limiter.limit('5 per hour')
def register():
    data = json_body()
    email = normalize_email(data.get('email'))
    name = (data.get('name') or '').strip()
    password = data.get('password') or ''
    confirm_password = data.get('confirm_password') or password

    if not email:
        return json_error(email_error_message(data.get('email')))
    name_error = display_name_error(name)
    if name_error:
        return json_error(name_error)
    new_password_error = password_error(password)
    if new_password_error:
        return json_error(new_password_error)
    if password != confirm_password:
        return json_error('Passwords do not match.')
    if registered_account(email):
        return json_error('Email already registered.', 409)

    # The account is created only after the emailed code is verified.
    pending, otp_sent = start_pending_registration(email, name, password)
    return jsonify({
        'user': {'email': pending.email, 'name': pending.name},
        'verification_required': True,
        'otp_sent': bool(otp_sent),
    }), 201


@mobile_api_bp.route('/auth/verify-email', methods=['POST'])
@limiter.limit('10 per minute')
def verify_email():
    data = json_body()
    email = normalize_email(data.get('email'))
    otp = (data.get('otp') or '').strip()
    user = User.query.filter_by(email=email).first() if email else None

    if not user:
        pending = PendingRegistration.query.filter_by(email=email).first() if email else None
        if not pending:
            return json_error('Invalid OTP.')
        if pending.email_otp_expires_at and pending.email_otp_expires_at < datetime.utcnow():
            return json_error('That OTP has expired. Please request a new code.')
        if pending.otp_attempts_exhausted():
            return json_error(OTP_LOCKED_MESSAGE, 429)
        if not pending.check_email_otp(otp):
            db.session.commit()
            return json_error(OTP_LOCKED_MESSAGE if pending.otp_attempts_exhausted() else 'Invalid OTP.')
        user = complete_pending_registration(pending)
        if not user:
            return json_error('That email is already registered. Sign in with your password.', 409)
        user.last_login_at = datetime.utcnow()
        user.last_activity_at = user.last_login_at
        db.session.commit()
        return jsonify(auth_payload(user))
    if user.is_email_verified:
        # Never hand out a token here without a correct code: that would let anyone sign in by email alone.
        return jsonify({'already_verified': True, 'message': 'This email is already verified. Sign in with your password.'})
    if user.email_otp_expires_at and user.email_otp_expires_at < datetime.utcnow():
        return json_error('That OTP has expired. Please request a new code.')
    if user.otp_attempts_exhausted():
        return json_error(OTP_LOCKED_MESSAGE, 429)
    if not user.check_email_otp(otp):
        # check_email_otp counted the wrong guess; save it so the limit holds across requests.
        db.session.commit()
        return json_error(OTP_LOCKED_MESSAGE if user.otp_attempts_exhausted() else 'Invalid OTP.')

    user.is_email_verified = True
    user.clear_email_otp()
    user.last_login_at = datetime.utcnow()
    user.last_activity_at = user.last_login_at
    db.session.commit()
    return jsonify(auth_payload(user))


@mobile_api_bp.route('/auth/resend-otp', methods=['POST'])
@limiter.limit('10 per hour')
@limiter.limit('3 per 10 minutes', key_func=json_email_key)
def resend_otp():
    email = normalize_email(json_body().get('email'))
    user = User.query.filter_by(email=email).first() if email else None
    if not user and email:
        # A sign-up that hasn't been verified yet lives in PendingRegistration until its code is entered.
        user = PendingRegistration.query.filter_by(email=email).first()
    # Unknown and already-verified emails get the same reply, so this can't be used to look up accounts.
    if not user or getattr(user, 'is_email_verified', False):
        return jsonify({'sent': True})

    if user.email_otp_sent_at:
        cooldown_until = user.email_otp_sent_at + timedelta(seconds=current_app.config['OTP_RESEND_COOLDOWN_SECONDS'])
        if cooldown_until > datetime.utcnow():
            return json_error('Please wait before requesting another OTP.', 429)

    try:
        sent = send_user_otp(user)
    except Exception as exc:
        current_app.logger.exception('Failed to resend mobile OTP: %s', exc)
        sent = False
    return jsonify({'sent': bool(sent)})


@mobile_api_bp.route('/auth/forgot-password', methods=['POST'])
@limiter.limit('10 per hour')
@limiter.limit('3 per hour', key_func=json_email_key)
def forgot_password():
    email = normalize_email(json_body().get('email'))
    user = User.query.filter_by(email=email).first() if email else None

    if user and not getattr(user, 'is_suspended', False):
        token = generate_password_reset_token(user)
        reset_url = url_for('auth.reset_password', token=token, _external=True)
        try:
            sent = send_password_reset_email(user, reset_url)
        except Exception as exc:
            current_app.logger.exception('Failed to send mobile password reset email: %s', exc)
            sent = False

        # Same reply either way, so this can't be used to check who has an account.
        if not sent:
            current_app.logger.warning('Password reset email could not be sent; check MAIL_PASSWORD.')

    return jsonify({
        'sent': True,
        'message': 'If an account exists for that email, password reset instructions were sent.',
    })


@mobile_api_bp.route('/me', methods=['GET', 'PATCH'])
@mobile_login_required
def me():
    user = request.mobile_user
    if request.method == 'GET':
        return jsonify({
            'user': user_payload(user),
            'currency_code': (current_app.config.get('STRIPE_CURRENCY') or 'cad').upper(),
        })

    data = json_body()
    name = (data.get('name') or '').strip()
    email = normalize_email(data.get('email'))
    name_error = display_name_error(name, 'Full name')
    if name_error:
        return json_error(name_error)
    if not email:
        return json_error('Valid email is required.')

    existing_user = User.query.filter(User.email == email, User.id != user.id).first()
    if existing_user:
        return json_error('That email is already used by another account.', 409)

    email_changed = email != user.email
    # Changing the sign-in email is a takeover risk, so it needs the current password.
    if email_changed and not user.check_password(data.get('current_password') or ''):
        return json_error('Enter your current password to change your email.', 403)

    handles, handle_error = clean_payment_handles(data)
    if handle_error:
        return json_error(handle_error)
    # Payment details need the current password and trigger an alert; a new Interac email waits for its code.
    handle_result, handle_change_error = apply_payment_handle_changes(user, handles, data.get('current_password'))
    if handle_change_error:
        db.session.rollback()
        return json_error(handle_change_error, 403)

    if 'phone' in data:
        raw_phone = str(data.get('phone') or '').strip()
        phone = normalize_phone(raw_phone) if raw_phone else None
        if raw_phone and not phone:
            return json_error('Enter a valid phone number, like 416 555 0123.')
        if phone and User.query.filter(User.phone == phone, User.id != user.id).first():
            return json_error('That phone number is already used by another account.', 409)
        user.phone = phone

    user.name = name
    otp_sent = False
    if email_changed:
        user.email = email
        user.is_email_verified = False
        user.clear_email_otp()
        try:
            otp_sent = send_user_otp(user)
        except Exception as exc:
            current_app.logger.exception('Failed to send profile verification OTP: %s', exc)
            db.session.commit()
    else:
        db.session.commit()

    payload = auth_payload(user)
    payload.update({
        'verification_required': email_changed,
        'otp_sent': bool(otp_sent),
        'interac_code_sent': bool(handle_result.get('interac_code_sent')),
    })
    return jsonify(payload)


@mobile_api_bp.route('/me/interac/verify', methods=['POST'])
@mobile_login_required
@limiter.limit('10 per 10 minutes')
def verify_interac():
    user = request.mobile_user
    error = verify_interac_code(user, json_body().get('otp'))
    db.session.commit()
    if error:
        return json_error(error)
    return jsonify({'user': user_payload(user)})


@mobile_api_bp.route('/me/interac/resend', methods=['POST'])
@mobile_login_required
@limiter.limit('3 per 10 minutes')
def resend_interac_code():
    user = request.mobile_user
    if not user.pending_interac_email:
        return json_error('There is no Interac email waiting for a code.')
    sent = send_interac_code(user)
    db.session.commit()
    return jsonify({'sent': sent})


@mobile_api_bp.route('/me/password', methods=['POST'])
@mobile_login_required
def update_password():
    data = json_body()
    current_password = data.get('current_password') or ''
    new_password = data.get('new_password') or ''
    confirm_password = data.get('confirm_password') or ''

    if not request.mobile_user.check_password(current_password):
        return json_error('Current password is incorrect.')
    new_password_error = password_error(new_password)
    if new_password_error:
        return json_error(new_password_error)
    if new_password != confirm_password:
        return json_error('New password and confirmation do not match.')

    # set_password revokes every existing token; this device gets a fresh one.
    request.mobile_user.set_password(new_password)
    db.session.commit()
    return jsonify({'updated': True, **auth_payload(request.mobile_user)})


@mobile_api_bp.route('/me/logout-all', methods=['POST'])
@mobile_login_required
def logout_all_devices():
    """Signs this account out of every phone and browser, including this one."""
    request.mobile_user.revoke_sessions()
    db.session.commit()
    return jsonify({'logged_out': True})


@mobile_api_bp.route('/receipts/scan', methods=['POST'])
@mobile_login_required
@limiter.limit('20 per hour')
def scan_receipt():
    """Reads line items from a receipt photo so the app can pick which to split."""
    upload = request.files.get('receipt')
    if not upload or not upload.filename:
        return json_error('Attach a photo of the receipt.')
    media_type = (upload.mimetype or '').lower()
    if media_type == 'image/jpg':
        media_type = 'image/jpeg'
    try:
        result = scan_receipt_image(upload.read(), media_type)
    except ReceiptScanError as exc:
        return json_error(exc.message, exc.status)
    return jsonify(result)


@mobile_api_bp.route('/me/qr')
@mobile_login_required
def profile_qr():
    """The profile contact card plus its QR modules, so the app can draw it without an SVG library."""
    payload = profile_qr_payload(request.mobile_user)
    matrix = qr_rows(payload)
    return jsonify({'payload': payload, 'size': len(matrix), 'rows': matrix})


def qr_rows(text):
    """QR modules as '0'/'1' strings, so the app can draw the code without an SVG library."""
    qr = qrcode.QRCode(border=0, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(text)
    qr.make(fit=True)
    return [''.join('1' if cell else '0' for cell in row) for row in qr.get_matrix()]


def my_invite_payload(invite):
    return {
        'id': invite.id,
        'group_id': invite.group_id,
        'group_name': invite.group.name,
        'invited_by': invite.invited_by.name if invite.invited_by else '',
        'created_at': iso_datetime(invite.created_at),
        'expires_at': iso_datetime(invite.expires_at),
    }


def accept_invite_for(user, invite):
    """Shared accept rules, matching the website's /invite/<token> page."""
    if not invite or invite.revoked_at:
        return json_error('That invite link is invalid or was revoked.', 404)
    if invite.accepted_at:
        return json_error('That invite was already accepted.', 409)
    if invite.expires_at <= datetime.utcnow():
        return json_error('That invite link has expired. Ask the group admin for a new invite.', 410)
    if normalize_email(user.email) != invite.email:
        return json_error(f'This invite was sent to {invite.email}. Sign in with that email to accept it.', 403)

    if user not in invite.group.members:
        invite.group.members.append(user)
        db.session.flush()
        set_member_nickname(invite.group.id, user)

    invite.accepted_at = datetime.utcnow()
    invite.accepted_by_id = user.id
    db.session.commit()
    return jsonify({
        'joined': True,
        'message': f'You joined "{invite.group.name}".',
        'group': group_payload(invite.group),
    })


@mobile_api_bp.route('/invites')
@mobile_login_required
def my_invites():
    user = request.mobile_user
    invites = GroupInvite.query.filter(
        GroupInvite.email == normalize_email(user.email),
        GroupInvite.accepted_at.is_(None),
        GroupInvite.revoked_at.is_(None),
        GroupInvite.expires_at > datetime.utcnow(),
    ).order_by(GroupInvite.created_at.desc()).all()
    return jsonify([
        my_invite_payload(invite)
        for invite in invites
        if user not in invite.group.members
    ])


@mobile_api_bp.route('/invites/<int:invite_id>/accept', methods=['POST'])
@mobile_login_required
def accept_my_invite(invite_id):
    return accept_invite_for(request.mobile_user, db.session.get(GroupInvite, invite_id))


@mobile_api_bp.route('/invites/accept-link', methods=['POST'])
@mobile_login_required
def accept_invite_link():
    link = (json_body().get('link') or '').strip()
    # Accept a full link (https://.../invite/<token>) or the bare token.
    token = link.rstrip('/').split('/invite/')[-1].split('?')[0].split('#')[0].strip('/')
    if not token:
        return json_error('Paste the invite link from your email.')
    return accept_invite_for(request.mobile_user, GroupInvite.query.filter_by(token=token).first())


@mobile_api_bp.route('/invite-splitmate', methods=['POST'])
@mobile_login_required
@limiter.limit('10 per hour')
def invite_splitmate():
    email = normalize_email(json_body().get('email'))
    if not email:
        return json_error('Enter a valid email address.')
    if email == normalize_email(request.mobile_user.email):
        return jsonify({'already_user': True, 'message': 'You are already using Splitmate.'})

    join_url = url_for('main.join_splitmate', _external=True)
    # Existing accounts get no email and the same reply, so this can't reveal who uses Splitmate.
    if not User.query.filter_by(email=email).first():
        try:
            send_splitmate_invite_email(email, request.mobile_user, join_url)
        except Exception as exc:
            current_app.logger.exception('Failed to send mobile Splitmate invite: %s', exc)

    return jsonify({
        'message': SPLITMATE_INVITE_MESSAGE.format(email=email),
        'email': email,
        'invite_url': join_url,
    })


@mobile_api_bp.route('/groups/<int:group_id>/money-requests', methods=['POST'])
@mobile_login_required
@limiter.limit('20 per hour')
def create_money_request(group_id):
    """Ask a member who owes you to pay. They approve it in Splitmate before you see their Interac email."""
    group, error = require_group_member(group_id)
    if error:
        return error
    try:
        payer_id = int(json_body().get('payer_id'))
    except (TypeError, ValueError):
        return json_error('Choose who to request money from.')
    owed = next((item for item in split_routes.money_requests(group, request.mobile_user) if item['payer_id'] == payer_id), None)
    if not owed:
        return json_error('That person does not owe you anything in this group.')
    if owed['request_status'] == 'pending':
        return json_error('You already asked them. Wait for them to approve it.', 409)

    money_request = MoneyRequest(group_id=group.id, requester_id=request.mobile_user.id, payer_id=payer_id,
                                 amount=owed['amount'])
    db.session.add(money_request)
    db.session.commit()
    payer = db.session.get(User, payer_id)
    try:
        send_money_request_email(payer, request.mobile_user, group, owed['amount'])
    except Exception as exc:
        current_app.logger.exception('Failed to send money request email: %s', exc)
    return jsonify({'id': money_request.id, 'status': 'pending'}), 201


@mobile_api_bp.route('/money-requests/<int:request_id>/<action>', methods=['POST'])
@mobile_login_required
def decide_money_request(request_id, action):
    """Only the person asked to pay can approve (share their Interac email) or decline."""
    if action not in {'approve', 'decline'}:
        return json_error('Unknown action.', 404)
    money_request = db.session.get(MoneyRequest, request_id)
    if not money_request or money_request.payer_id != request.mobile_user.id:
        return json_error('Request not found.', 404)
    if money_request.status != 'pending':
        return json_error('This request was already answered.', 409)
    money_request.status = 'approved' if action == 'approve' else 'declined'
    money_request.decided_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'id': money_request.id, 'status': money_request.status})


QUICK_SPLIT_MAX_PEOPLE = 10


def find_user_by_contact(contact):
    """An email or phone number -> (User or None, cleaned contact or None if it isn't a valid email/phone)."""
    contact = str(contact or '').strip()
    if '@' in contact:
        email = normalize_email(contact)
        return (User.query.filter_by(email=email).first() if email else None), email
    phone = normalize_phone(contact)
    return (User.query.filter_by(phone=phone).first() if phone else None), phone


@mobile_api_bp.route('/quick-split', methods=['POST'])
@mobile_login_required
@limiter.limit('30 per hour')
def quick_split():
    """Split one expense equally with friends found by email or phone, without making a group first.

    The same set of people reuses their earlier Quick split group, so balances stay in one place.
    """
    data = json_body()
    me = request.mobile_user
    contacts = [str(item).strip() for item in (data.get('contacts') or []) if str(item).strip()]
    if not contacts:
        return json_error('Add at least one friend by email or phone number.')
    if len(contacts) > QUICK_SPLIT_MAX_PEOPLE:
        return json_error(f'Quick split works with up to {QUICK_SPLIT_MAX_PEOPLE} people. Make a group for more.')

    friends, invalid, not_found = [], [], []
    for contact in contacts:
        user, cleaned = find_user_by_contact(contact)
        if not cleaned:
            invalid.append(contact)
        elif not user or getattr(user, 'is_suspended', False):
            not_found.append(cleaned)
        elif user.id != me.id and user not in friends:
            friends.append(user)
    if invalid:
        return json_error(f'Not a valid email or phone number: {", ".join(invalid)}')
    if not_found:
        response = jsonify({
            'error': f'Not on Splitmate yet: {", ".join(not_found)}. Invite them first.',
            'not_found': not_found,
        })
        return response, 404
    if not friends:
        return json_error('Add at least one friend other than yourself.')

    wanted_ids = {me.id, *(friend.id for friend in friends)}
    group = next(
        (candidate for candidate in me.groups.filter(Group.is_quick_split == True).all()  # noqa: E712
         if {member.id for member in candidate.members} == wanted_ids),
        None,
    )
    if group is None:
        names = ', '.join(friend.name.split()[0] for friend in friends)
        group = Group(name=f'Quick split: {names}'[:100], admin_id=me.id, is_quick_split=True)
        db.session.add(group)
        group.members.append(me)
        group.members.extend(friends)
        db.session.flush()
        for member in group.members:
            set_member_nickname(group.id, member)

    parsed, parse_error = parse_expense_data(group, {
        'description': data.get('description'),
        'amount': data.get('amount'),
        'category': data.get('category'),
        'paid_by_id': me.id,
        'split_type': 'equal',
    })
    if parse_error:
        db.session.rollback()
        return parse_error

    expense = Expense(
        description=parsed['description'],
        amount=float(parsed['amount']),
        category=parsed['category'],
        receipt_url=None,
        group_id=group.id,
        paid_by_id=me.id,
    )
    db.session.add(expense)
    db.session.flush()
    db.session.add(ExpenseHistory(
        description=expense.description,
        amount=expense.amount,
        category=expense.category,
        date=expense.date,
        paid_by_id=expense.paid_by_id,
        group_id=expense.group_id,
    ))
    for member, share in parsed['split_rows']:
        if share > 0:
            db.session.add(ExpenseSplit(expense_id=expense.id, user_id=member.id, amount_owed=float(share)))
    db.session.commit()
    return jsonify({'group': group_payload(group), 'expense': expense_payload(expense)}), 201


@mobile_api_bp.route('/devices', methods=['POST'])
@mobile_login_required
def register_device():
    data = json_body()
    token = (data.get('expo_push_token') or '').strip()
    platform = (data.get('platform') or '').strip()[:30]
    if not token:
        return json_error('Expo push token is required.')

    device = MobileDevice.query.filter_by(expo_push_token=token).first()
    if not device:
        device = MobileDevice(expo_push_token=token, user_id=request.mobile_user.id)
        db.session.add(device)

    device.user_id = request.mobile_user.id
    device.platform = platform
    device.last_seen_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'registered': True})


@mobile_api_bp.route('/dashboard')
@mobile_login_required
def dashboard():
    user = request.mobile_user
    user_groups = user.groups.all()
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    monthly_spending = []
    recent_expenses = []

    for group in user_groups:
        # ExpenseHistory already holds a copy of every active expense.
        history_sum = db.session.query(func.coalesce(func.sum(ExpenseHistory.amount), 0.0)).filter(
            ExpenseHistory.group_id == group.id,
            ExpenseHistory.date >= month_start,
        ).scalar()
        monthly_spending.append({
            'group_id': group.id,
            'group': group.name,
            'total': float(history_sum),
        })
        recent_expenses.extend(
            Expense.query.filter_by(group_id=group.id).order_by(Expense.date.desc()).limit(5).all()
        )

    recent_expenses.sort(key=lambda expense: expense.date or datetime.min, reverse=True)
    recent_rows = [{
        **expense_payload(expense),
        'group_id': expense.group_id,
        'group_name': expense.group.name,
    } for expense in recent_expenses[:10]]

    total_owed_to_user = sum(
        split.amount_owed
        for expense in Expense.query.filter_by(paid_by_id=user.id).all()
        for split in expense.splits
        if split.user_id != user.id and not split.is_settled
    )
    total_user_owes = sum(
        split.amount_owed
        for split in ExpenseSplit.query.filter_by(user_id=user.id, is_settled=False).all()
        if split.expense.paid_by_id != user.id
    )

    group_ids = [group.id for group in user_groups]
    history_items = ExpenseHistory.query.filter(
        ExpenseHistory.group_id.in_(group_ids)
    ).all() if group_ids else []

    category_totals = {}
    payer_totals = {}
    group_totals = {}
    group_names = {group.id: group.name for group in user_groups}
    payer_ids = {item.paid_by_id for item in history_items if item.paid_by_id}
    payer_names = {
        payer.id: payer.name
        for payer in User.query.filter(User.id.in_(payer_ids)).all()
    } if payer_ids else {}
    for item in history_items:
        amount = float(item.amount or 0)
        category = split_routes.normalize_expense_category(item.category)
        category_totals[category] = category_totals.get(category, 0.0) + amount
        payer_name = payer_names.get(item.paid_by_id, 'Unknown')
        payer_totals[payer_name] = payer_totals.get(payer_name, 0.0) + amount
        group_name = group_names.get(item.group_id, 'Unknown')
        group_totals[group_name] = group_totals.get(group_name, 0.0) + amount

    category_rows = sorted(
        ({'category': label, 'total': total} for label, total in category_totals.items()),
        key=lambda row: row['total'],
        reverse=True,
    )
    payer_rows = sorted(
        ({'name': label, 'total': total} for label, total in payer_totals.items()),
        key=lambda row: row['total'],
        reverse=True,
    )[:5]
    group_rows = sorted(
        ({'name': label, 'total': round(total, 2)} for label, total in group_totals.items()),
        key=lambda row: row['total'],
        reverse=True,
    )

    months = []
    for offset in range(5, -1, -1):
        month = now.month - offset
        year = now.year
        while month <= 0:
            month += 12
            year -= 1
        months.append((year, month))

    chart_data = []
    for group in user_groups:
        points = []
        for year, month in months:
            start = datetime(year, month, 1)
            end = datetime(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
            # ExpenseHistory already holds a copy of every active expense.
            history_sum = db.session.query(func.coalesce(func.sum(ExpenseHistory.amount), 0.0)).filter(
                ExpenseHistory.group_id == group.id,
                ExpenseHistory.date >= start,
                ExpenseHistory.date < end,
            ).scalar()
            points.append({
                'month': f'{year}-{month:02d}',
                'label': datetime(year, month, 1).strftime('%b'),
                'total': float(history_sum),
            })
        chart_data.append({'group_id': group.id, 'group': group.name, 'data': points})

    # Combined month-by-month totals across every group, for the dashboard trend.
    monthly_totals = []
    for index, (year, month) in enumerate(months):
        monthly_totals.append({
            'month': f'{year}-{month:02d}',
            'label': datetime(year, month, 1).strftime('%b'),
            'total': round(sum(series['data'][index]['total'] for series in chart_data), 2),
        })
    insight_total = sum(float(item.amount or 0) for item in history_items)

    return jsonify({
        'groups': [group_payload(group) for group in user_groups],
        'monthly_spending': monthly_spending,
        'recent_expenses': recent_rows,
        'total_owed_to_user': round(total_owed_to_user, 2),
        'total_user_owes': round(total_user_owes, 2),
        'chart_data': chart_data,
        'spending_insights': {
            'total': round(insight_total, 2),
            'count': len(history_items),
            'average': round(insight_total / len(history_items), 2) if history_items else 0.0,
            'top_category': category_rows[0]['category'] if category_rows else '',
            'category_totals': category_rows,
            'payer_totals': payer_rows,
            'group_totals': group_rows,
            'monthly_totals': monthly_totals,
        },
    })


@mobile_api_bp.route('/groups')
@mobile_login_required
def groups():
    user_groups = request.mobile_user.groups.all()
    return jsonify([group_payload(group) for group in user_groups])


@mobile_api_bp.route('/groups', methods=['POST'])
@mobile_login_required
def create_group():
    name = (json_body().get('name') or '').strip()
    name_error = display_name_error(name, 'Group name')
    if name_error:
        return json_error(name_error)

    group = Group(name=name, admin_id=request.mobile_user.id)
    group.members.append(request.mobile_user)
    db.session.add(group)
    db.session.flush()
    set_member_nickname(group.id, request.mobile_user)
    db.session.commit()
    return jsonify(group_payload(group)), 201


@mobile_api_bp.route('/groups/<int:group_id>')
@mobile_login_required
def group_detail(group_id):
    group, error = require_group_member(group_id)
    if error:
        return error

    nicknames = member_nickname_rows(group.id)
    expenses = Expense.query.filter_by(group_id=group.id).order_by(Expense.date.desc()).limit(20).all()
    tasks = Task.query.filter_by(group_id=group.id).order_by(Task.due_date.asc()).all()
    notes = Note.query.filter_by(group_id=group.id).order_by(Note.created_at.desc()).all()
    payments = Payment.query.filter_by(group_id=group.id).order_by(Payment.date.desc()).limit(20).all()

    return jsonify({
        'group': group_payload(group),
        'current_user_id': request.mobile_user.id,
        'pending_invites': group_pending_invite_payload(group) if group.admin_id == request.mobile_user.id else [],
        'default_split': split_routes.group_default_split_payload(group),
        # Built-in categories plus the group's own, as suggestions for the free-text category field.
        'expense_categories': split_routes.group_categories(group),
        'balances': split_routes.group_balances(group, nicknames),
        'summaries': summaries_for(group),
        'expenses': [expense_payload(expense, nicknames) for expense in expenses],
        'tasks': [task_payload(task, nicknames) for task in tasks],
        'notes': [note_payload(note, nicknames) for note in notes],
        'payments': [split_routes.payment_row(payment, nicknames, request.mobile_user) for payment in payments],
        'payment_options': split_routes.payment_options(group, request.mobile_user, nicknames),
        'money_requests': split_routes.money_requests(group, request.mobile_user, nicknames),
        'requests_for_me': split_routes.requests_for_payer(group, request.mobile_user, nicknames),
    })


@mobile_api_bp.route('/groups/<int:group_id>', methods=['PATCH'])
@mobile_login_required
def rename_group(group_id):
    group, error = require_group_member(group_id)
    if error:
        return error
    if group.admin_id != request.mobile_user.id:
        return json_error('Only the group admin can rename the group.', 403)
    name = (json_body().get('name') or '').strip()
    name_error = display_name_error(name, 'Group name')
    if name_error:
        return json_error(name_error)
    group.name = name
    db.session.commit()
    return jsonify(group_payload(group))


@mobile_api_bp.route('/groups/<int:group_id>/admin', methods=['POST'])
@mobile_login_required
def transfer_group_admin(group_id):
    """The current admin hands the admin role to another member (who then manages the group)."""
    group, error = require_group_member(group_id)
    if error:
        return error
    if group.admin_id != request.mobile_user.id:
        return json_error('Only the group admin can choose a new admin.', 403)
    try:
        new_admin = db.session.get(User, int(json_body().get('user_id')))
    except (TypeError, ValueError):
        new_admin = None
    if not new_admin or new_admin not in group.members:
        return json_error('Choose a member of this group.')
    if new_admin.id == group.admin_id:
        return json_error('You are already the admin.')
    group.admin_id = new_admin.id
    db.session.commit()
    return jsonify(group_payload(group))


@mobile_api_bp.route('/groups/<int:group_id>/leave', methods=['POST'])
@mobile_login_required
def leave_group(group_id):
    group, error = require_group_member(group_id)
    if error:
        return error
    if group.admin_id == request.mobile_user.id:
        return json_error('The admin can\'t leave the group. Make someone else admin first.', 400)
    # Leaving with money still owed would hide that debt from everyone else.
    if split_routes.member_has_open_balance(group, request.mobile_user):
        return json_error('Settle up your balances in this group before leaving.', 409)
    group.members.remove(request.mobile_user)
    db.session.commit()
    return jsonify({'left': True})


@mobile_api_bp.route('/groups/<int:group_id>', methods=['DELETE'])
@mobile_login_required
def delete_group(group_id):
    """The admin can delete a group that has no money history, or one where they're the only member left.

    While other members remain, their expense and payment history is kept (it's the group's audit log),
    so deleting is refused. A solo admin's group only holds their own history, so it can go entirely.
    """
    group, error = require_group_member(group_id)
    if error:
        return error
    if group.admin_id != request.mobile_user.id:
        return json_error('Only the group admin can delete the group.', 403)
    has_history = (
        ExpenseHistory.query.filter_by(group_id=group.id).first() is not None
        or Payment.query.filter_by(group_id=group.id).first() is not None
        or group.expenses.first() is not None
    )
    solo_admin = len(group.members) == 1
    if has_history and not solo_admin:
        return json_error('Other members still have expense or payment history here, so the group can\'t be deleted. '
                          'Once everyone else has settled up and left, you can delete it.', 409)
    # Pending invites go with the group (cascade), so their links stop working.
    db.session.delete(group)
    db.session.commit()
    return jsonify({'deleted': True})


@mobile_api_bp.route('/groups/<int:group_id>/members', methods=['POST'])
@mobile_login_required
@limiter.limit('30 per hour')
def add_group_member(group_id):
    """People join a group by accepting an invite, never by being added without asking."""
    group, error = require_group_member(group_id)
    if error:
        return error
    if group.admin_id != request.mobile_user.id:
        return json_error('Only the group admin can add members.', 403)

    email = normalize_email(json_body().get('email'))
    if not email:
        return json_error('Enter a valid email address.')
    existing_user = User.query.filter_by(email=email).first()
    if existing_user and existing_user in group.members:
        return jsonify({'invited': False, 'already_member': True, 'message': 'That person is already in this group.'})

    invite_to_group(group, request.mobile_user, email)
    db.session.commit()
    return jsonify({
        'invited': True,
        'already_member': False,
        'message': f'Invite sent to {email}. They join once they accept it.',
    }), 201


@mobile_api_bp.route('/groups/<int:group_id>/invites', methods=['GET', 'POST'])
@mobile_login_required
@limiter.limit('30 per hour', methods=['POST'])
def group_invites(group_id):
    group, error = require_group_member(group_id)
    if error:
        return error
    if group.admin_id != request.mobile_user.id:
        return json_error('Only the group admin can manage invites.', 403)

    if request.method == 'GET':
        return jsonify(group_pending_invite_payload(group))

    email = normalize_email(json_body().get('email'))
    if not email:
        return json_error('Enter a valid email address.')

    existing_user = User.query.filter_by(email=email).first()
    if existing_user and existing_user in group.members:
        return jsonify({
            'already_member': True,
            'message': f'{existing_user.name} is already in "{group.name}".',
        })

    invite, created_new, email_sent = invite_to_group(group, request.mobile_user, email)
    invite_url = url_for('main.accept_group_invite', token=invite.token, _external=True)
    db.session.commit()
    message = f'Invite sent to {email}.' if email_sent else f'Invite link created for {email}.'
    return jsonify({
        'id': invite.id,
        'message': message,
        'email': email,
        'email_sent': bool(email_sent),
        'created_new': created_new,
        'invite_url': invite_url,
        # The invitee can scan this from the admin's screen instead of waiting for the email.
        'qr_rows': qr_rows(invite_url),
        'expires_at': invite.expires_at.isoformat(),
    }), 201 if created_new else 200


@mobile_api_bp.route('/groups/<int:group_id>/invites/<int:invite_id>', methods=['DELETE'])
@mobile_login_required
def revoke_group_invite(group_id, invite_id):
    group, error = require_group_member(group_id)
    if error:
        return error
    if group.admin_id != request.mobile_user.id:
        return json_error('Only the group admin can revoke invites.', 403)

    invite = GroupInvite.query.filter_by(id=invite_id, group_id=group.id).first_or_404()
    if invite.accepted_at:
        return json_error('That invite was already accepted.')
    invite.revoked_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'revoked': True})


@mobile_api_bp.route('/groups/<int:group_id>/members/<int:user_id>', methods=['PATCH', 'DELETE'])
@mobile_login_required
def manage_group_member(group_id, user_id):
    group, error = require_group_member(group_id)
    if error:
        return error
    if group.admin_id != request.mobile_user.id:
        return json_error('Only the group admin can manage members.', 403)

    member = User.query.get_or_404(user_id)
    if member not in group.members:
        return json_error('That user is not in this group.', 404)

    if request.method == 'DELETE':
        if member.id == group.admin_id:
            return json_error('The group admin cannot be removed.')
        if split_routes.member_has_open_balance(group, member):
            return json_error('This member still has unsettled balances in the group. Settle up before removing them.', 409)
        group.members.remove(member)
        db.session.commit()
        return jsonify({'removed': True})

    nickname = (json_body().get('nickname') or '').strip()
    nickname_error = display_name_error(nickname, 'Nickname') if nickname else None
    if nickname_error:
        return json_error(nickname_error)
    display_name = set_member_nickname(group.id, member, nickname)
    db.session.commit()
    return jsonify({'nickname': display_name})


@mobile_api_bp.route('/groups/<int:group_id>/default-split', methods=['GET', 'PUT', 'DELETE'])
@mobile_login_required
def group_default_split(group_id):
    group, error = require_group_member(group_id)
    if error:
        return error

    if request.method == 'GET':
        return jsonify(split_routes.group_default_split_payload(group))
    if group.admin_id != request.mobile_user.id:
        return json_error('Only the group admin can change the default split.', 403)
    if request.method == 'DELETE':
        group.default_split_type = 'equal'
        group.default_split_config = None
        db.session.commit()
        return jsonify(split_routes.group_default_split_payload(group))

    data = json_body()
    split_type = (data.get('type') or 'equal').strip()
    if split_type not in split_routes.DEFAULT_SPLIT_TYPES:
        return json_error('Default split can be Equal, Selected People, or Percentage.')

    member_ids = {member.id for member in group.members}
    config = {}
    if split_type == 'selected':
        try:
            selected_ids = [int(member_id) for member_id in data.get('member_ids') or []]
        except (TypeError, ValueError):
            return json_error('Choose valid members from this group.')
        if not selected_ids or any(member_id not in member_ids for member_id in selected_ids):
            return json_error('Choose at least one valid person for the default split.')
        config['member_ids'] = [str(member_id) for member_id in dict.fromkeys(selected_ids)]

    if split_type == 'percentage':
        percentages = data.get('percentages') or {}
        normalized_percentages = {}
        total_percentage = Decimal('0.00')
        try:
            for member in group.members:
                percentage = money_decimal(percentages.get(str(member.id), percentages.get(member.id)))
                if percentage <= 0:
                    return json_error(f'Percentage for {member.name} must be greater than 0.')
                normalized_percentages[str(member.id)] = f'{percentage:.2f}'
                total_percentage += percentage
        except ValueError:
            return json_error('Enter a valid percentage for every member.')
        if total_percentage != Decimal('100.00'):
            return json_error('Default percentages must total 100%.')
        config = {
            'member_ids': [str(member.id) for member in group.members],
            'percentages': normalized_percentages,
        }

    group.default_split_type = split_type
    group.default_split_config = json.dumps(config) if config else None
    db.session.commit()
    return jsonify(split_routes.group_default_split_payload(group))


def parse_expense_data(group, data, existing_receipt_url=None):
    """Validate an expense payload and work out each member's share.

    Returns (parsed, None) on success or (None, error_response) on failure.
    Shared by expense creation and expense editing.
    """
    description = (data.get('description') or '').strip()
    if not description:
        return None, json_error('Description is required.')

    try:
        expense_amount = money_decimal(data.get('amount'))
    except ValueError as exc:
        return None, json_error(str(exc))
    if expense_amount <= 0:
        return None, json_error('Amount must be greater than 0.')

    raw_split_type = data.get('split_type') or 'equal'
    use_selected_members = raw_split_type == 'selected'
    split_type = 'equal' if use_selected_members else raw_split_type
    if split_type not in {'equal', 'exact', 'percentage'}:
        return None, json_error('Choose a valid split type.')

    all_members = list(group.members)
    selected_members = all_members
    if use_selected_members:
        try:
            selected_ids = {int(member_id) for member_id in data.get('split_user_ids') or []}
        except (TypeError, ValueError):
            return None, json_error('Choose valid members from this group.')
        selected_members = [member for member in all_members if member.id in selected_ids]
        if len(selected_members) != len(selected_ids):
            return None, json_error('Choose valid members from this group.')
    if not selected_members:
        return None, json_error('Choose at least one person to split with.')

    split_rows = []
    try:
        if split_type == 'equal':
            member_count = Decimal(len(selected_members))
            split_amount = (expense_amount / member_count).quantize(CENT, rounding=ROUND_HALF_UP)
            remainder = expense_amount - (split_amount * member_count)
            for index, member in enumerate(selected_members):
                split_rows.append((member, split_amount + (remainder if index == len(selected_members) - 1 else Decimal('0.00'))))

        elif split_type == 'exact':
            exact_amounts = data.get('exact_amounts') or {}
            assigned_total = Decimal('0.00')
            for member in selected_members:
                amount = money_decimal(exact_amounts.get(str(member.id), exact_amounts.get(member.id, 0)))
                if amount <= 0:
                    return None, json_error(f'Enter an amount greater than 0 for {member.name}.')
                split_rows.append((member, amount))
                assigned_total += amount
            if assigned_total != expense_amount:
                return None, json_error('Exact split amounts must total the expense amount.')

        elif split_type == 'percentage':
            percentages = data.get('percentages') or {}
            total_percentage = Decimal('0.00')
            percentage_rows = []
            for member in selected_members:
                percentage = money_decimal(percentages.get(str(member.id), percentages.get(member.id, 0)))
                if percentage <= 0:
                    return None, json_error(f'Enter a percentage greater than 0 for {member.name}.')
                percentage_rows.append((member, percentage))
                total_percentage += percentage
            if total_percentage != Decimal('100.00'):
                return None, json_error('Percentages must total 100%.')
            for member, percentage in percentage_rows:
                split_rows.append((member, (expense_amount * percentage / Decimal('100')).quantize(CENT, rounding=ROUND_HALF_UP)))
    except ValueError as exc:
        return None, json_error(str(exc))

    assigned_total = sum((share for _, share in split_rows), Decimal('0.00'))
    remainder = expense_amount - assigned_total
    if split_rows and remainder:
        member, share = split_rows[-1]
        split_rows[-1] = (member, share + remainder)

    paid_by = User.query.get(data.get('paid_by_id') or request.mobile_user.id)
    if not paid_by or paid_by not in group.members:
        return None, json_error('Choose a valid payer from this group.')

    submitted_receipt_url = (data.get('receipt_url') or '').strip()
    if submitted_receipt_url.startswith(split_routes.RECEIPT_URL_PREFIX):
        # The app echoes back the signed link it was given; store the plain path, not the signature.
        submitted_receipt_url = submitted_receipt_url.split('?', 1)[0]
    if not is_safe_link(submitted_receipt_url):
        return None, json_error('Receipt URL must start with http:// or https://.')
    receipt_url = submitted_receipt_url or existing_receipt_url
    try:
        uploaded_receipt_url = split_routes.save_receipt_file(request.files.get('receipt'))
    except ValueError as exc:
        return None, json_error(str(exc))
    if uploaded_receipt_url:
        receipt_url = uploaded_receipt_url

    category_error = split_routes.category_error(data.get('category'))
    if category_error:
        return None, json_error(category_error)
    category = split_routes.category_for_group(group, data.get('category'))
    return {
        'description': description,
        'amount': expense_amount,
        'category': category,
        'paid_by': paid_by,
        'receipt_url': receipt_url,
        'split_rows': split_rows,
    }, None


@mobile_api_bp.route('/groups/<int:group_id>/expenses', methods=['GET', 'POST', 'DELETE'])
@mobile_login_required
def add_expense(group_id):
    group, error = require_group_member(group_id)
    if error:
        return error

    if request.method == 'GET':
        query = Expense.query.filter_by(group_id=group.id)
        search = (request.args.get('q') or '').strip()
        category = (request.args.get('category') or '').strip()
        payer_id = request.args.get('payer_id', type=int)
        if search:
            query = query.filter(Expense.description.ilike(f'%{search}%'))
        if category:
            query = query.filter(Expense.category == split_routes.category_for_group(group, category))
        if payer_id:
            query = query.filter(Expense.paid_by_id == payer_id)
        nicknames = member_nickname_rows(group.id)
        return jsonify([
            expense_payload(expense, nicknames)
            for expense in query.order_by(Expense.date.desc()).limit(100).all()
        ])

    if request.method == 'DELETE':
        # Clearing wipes everyone's open balances, so only the group admin may do it (same as the website).
        if group.admin_id != request.mobile_user.id:
            return json_error('Only the group admin can clear all expenses.', 403)
        for expense in group.expenses.all():
            db.session.delete(expense)
        db.session.commit()
        return jsonify({'cleared': True})

    try:
        data = json_or_form_body()
    except ValueError as exc:
        return json_error(str(exc))
    parsed, parse_error = parse_expense_data(group, data)
    if parse_error:
        return parse_error

    expense = Expense(
        description=parsed['description'],
        amount=float(parsed['amount']),
        category=parsed['category'],
        receipt_url=parsed['receipt_url'],
        group_id=group.id,
        paid_by_id=parsed['paid_by'].id,
    )
    db.session.add(expense)
    db.session.flush()
    db.session.add(ExpenseHistory(
        description=expense.description,
        amount=expense.amount,
        category=expense.category,
        date=expense.date,
        paid_by_id=expense.paid_by_id,
        group_id=expense.group_id,
    ))
    for member, share in parsed['split_rows']:
        if share > 0:
            db.session.add(ExpenseSplit(expense_id=expense.id, user_id=member.id, amount_owed=float(share)))
    db.session.commit()
    return jsonify(expense_payload(expense)), 201


def expense_change_error(expense):
    """Only the payer or the group admin may edit or delete an expense."""
    group = expense.group
    user = request.mobile_user
    if user not in group.members:
        return json_error('Unauthorized expense access.', 403)
    if user.id not in {expense.paid_by_id, group.admin_id}:
        return json_error('Only the payer or the group admin can change this expense.', 403)
    return None


@mobile_api_bp.route('/expenses/<int:expense_id>', methods=['PUT', 'DELETE'])
@mobile_login_required
def change_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    error = expense_change_error(expense)
    if error:
        return error

    # ExpenseHistory is an immutable audit log (see models.py), so it is left
    # untouched: history and analytics keep showing the expense as originally added.
    if request.method == 'DELETE':
        db.session.delete(expense)
        db.session.commit()
        return jsonify({'deleted': True})

    # Editing re-creates the splits, which would undo any settlement already made.
    if any(split.is_settled and split.user_id != expense.paid_by_id for split in expense.splits):
        return json_error('This expense already has settled payments, so it cannot be edited. Delete it and add a corrected one instead.', 409)

    try:
        data = json_or_form_body()
    except ValueError as exc:
        return json_error(str(exc))
    parsed, parse_error = parse_expense_data(expense.group, data, existing_receipt_url=expense.receipt_url)
    if parse_error:
        return parse_error

    expense.description = parsed['description']
    expense.amount = float(parsed['amount'])
    expense.category = parsed['category']
    expense.receipt_url = parsed['receipt_url']
    expense.paid_by_id = parsed['paid_by'].id

    for split in list(expense.splits):
        db.session.delete(split)
    db.session.flush()
    for member, share in parsed['split_rows']:
        if share > 0:
            db.session.add(ExpenseSplit(expense_id=expense.id, user_id=member.id, amount_owed=float(share)))
    db.session.commit()
    return jsonify(expense_payload(expense))


@mobile_api_bp.route('/groups/<int:group_id>/payments', methods=['POST'])
@mobile_login_required
def record_payment(group_id):
    group, error = require_group_member(group_id)
    if error:
        return error

    data = json_body()
    try:
        receiver = db.session.get(User, int(data.get('receiver_id')))
    except (TypeError, ValueError):
        receiver = None
    payment, payment_error = split_routes.request_payment(group, request.mobile_user, receiver, data.get('amount'))
    if payment_error:
        return json_error(payment_error)

    db.session.commit()
    # Balances only change once the receiver confirms the money arrived.
    return jsonify({'id': payment.id, 'recorded': True, 'status': payment.status}), 201


def payment_for_mobile_member(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    if request.mobile_user not in payment.group.members:
        return None, json_error('Unauthorized payment access.', 403)
    return payment, None


@mobile_api_bp.route('/payments/<int:payment_id>/confirm', methods=['POST'])
@mobile_login_required
def confirm_payment(payment_id):
    payment, error = payment_for_mobile_member(payment_id)
    if error:
        return error
    confirm_error = split_routes.confirm_payment(payment, request.mobile_user)
    if confirm_error:
        return json_error(confirm_error, 403 if 'Only' in confirm_error else 409)
    db.session.commit()
    return jsonify({'confirmed': True, 'status': payment.status})


@mobile_api_bp.route('/payments/<int:payment_id>/decline', methods=['POST'])
@mobile_login_required
def decline_payment(payment_id):
    payment, error = payment_for_mobile_member(payment_id)
    if error:
        return error
    decline_error = split_routes.decline_payment(payment, request.mobile_user)
    if decline_error:
        return json_error(decline_error, 403 if 'Only' in decline_error else 409)
    db.session.commit()
    return jsonify({'declined': True, 'status': payment.status})


@mobile_api_bp.route('/groups/<int:group_id>/activity')
@mobile_login_required
def group_activity(group_id):
    group, error = require_group_member(group_id)
    if error:
        return error

    history_query = ExpenseHistory.query.filter_by(group_id=group.id)
    search = (request.args.get('q') or '').strip()
    category = (request.args.get('category') or '').strip()
    payer_id = request.args.get('payer_id', type=int)
    min_amount = request.args.get('min_amount')
    max_amount = request.args.get('max_amount')

    if search:
        history_query = history_query.filter(ExpenseHistory.description.ilike(f'%{search}%'))
    if category:
        history_query = history_query.filter(
            ExpenseHistory.category == split_routes.category_for_group(group, category)
        )
    if payer_id:
        history_query = history_query.filter(ExpenseHistory.paid_by_id == payer_id)

    try:
        if min_amount not in (None, ''):
            history_query = history_query.filter(ExpenseHistory.amount >= float(money_decimal(min_amount)))
        if max_amount not in (None, ''):
            history_query = history_query.filter(ExpenseHistory.amount <= float(money_decimal(max_amount)))
        start_date = datetime.strptime(request.args['start_date'], '%Y-%m-%d') if request.args.get('start_date') else None
        end_date = datetime.strptime(request.args['end_date'], '%Y-%m-%d') + timedelta(days=1) if request.args.get('end_date') else None
    except (ValueError, InvalidOperation):
        return json_error('Enter valid date and amount filters.')

    if start_date:
        history_query = history_query.filter(ExpenseHistory.date >= start_date)
    if end_date:
        history_query = history_query.filter(ExpenseHistory.date < end_date)

    nicknames = member_nickname_rows(group.id)
    expenses = history_query.order_by(ExpenseHistory.date.desc()).limit(100).all()
    expense_rows = [{
        'id': item.id,
        'type': 'expense',
        'description': item.description,
        'amount': round(item.amount, 2),
        'category': split_routes.normalize_expense_category(item.category),
        'date': item.date.isoformat() if item.date else None,
        'paid_by': nicknames.get(item.paid_by_id) or (User.query.get(item.paid_by_id).name if item.paid_by_id else ''),
    } for item in expenses]

    payment_rows = [{
        'id': payment.id,
        'type': 'payment',
        'description': 'Payment',
        'amount': round(payment.amount, 2),
        'date': payment.date.isoformat() if payment.date else None,
        'payer': nicknames.get(payment.payer_id) or payment.payer.name,
        'receiver': nicknames.get(payment.receiver_id) or payment.receiver.name,
        'method': payment.method,
        'status': payment.status,
    } for payment in Payment.query.filter_by(group_id=group.id).order_by(Payment.date.desc()).all()]

    transactions = expense_rows + payment_rows
    transactions.sort(key=lambda item: item.get('date') or '', reverse=True)
    return jsonify({
        'expense_results': expense_rows,
        'transactions': transactions[:150],
        'analytics': analytics_for(group),
    })


@mobile_api_bp.route('/groups/<int:group_id>/expenses/search')
@mobile_login_required
def search_group_expenses(group_id):
    group, error = require_group_member(group_id)
    if error:
        return error

    query_text = (request.args.get('q') or '').strip()
    category = request.args.get('category', 'all').strip()
    paid_by_id = request.args.get('paid_by_id', type=int)
    min_amount_raw = (request.args.get('min_amount') or '').strip()
    max_amount_raw = (request.args.get('max_amount') or '').strip()

    history_query = ExpenseHistory.query.filter_by(group_id=group.id)

    if query_text:
        history_query = history_query.filter(ExpenseHistory.description.ilike(f'%{query_text}%'))

    if category and category != 'all':
        history_query = history_query.filter(
            ExpenseHistory.category == split_routes.category_for_group(group, category)
        )

    if paid_by_id:
        if paid_by_id not in {member.id for member in group.members}:
            return json_error('Choose a valid payer from this group.')
        history_query = history_query.filter(ExpenseHistory.paid_by_id == paid_by_id)

    try:
        start_date = split_routes.parse_date_filter(request.args.get('date_from'))
        end_date = split_routes.parse_date_filter(request.args.get('date_to'), include_next_day=True)
    except ValueError:
        return json_error('Use YYYY-MM-DD for dates.')

    if start_date:
        history_query = history_query.filter(ExpenseHistory.date >= start_date)
    if end_date:
        history_query = history_query.filter(ExpenseHistory.date < end_date)

    try:
        if min_amount_raw:
            history_query = history_query.filter(ExpenseHistory.amount >= float(money_decimal(min_amount_raw)))
        if max_amount_raw:
            history_query = history_query.filter(ExpenseHistory.amount <= float(money_decimal(max_amount_raw)))
    except (InvalidOperation, ValueError):
        return json_error('Enter valid amount filters.')

    nicknames = member_nickname_rows(group.id)
    results = history_query.order_by(ExpenseHistory.date.desc()).limit(50).all()

    return jsonify([{
        'id': item.id,
        'description': item.description,
        'amount': round(item.amount, 2),
        'category': split_routes.normalize_expense_category(item.category),
        'date': item.date.isoformat() if item.date else None,
        'paid_by': nicknames.get(item.paid_by_id) or (User.query.get(item.paid_by_id).name if item.paid_by_id else ''),
    } for item in results])


@mobile_api_bp.route('/rewards')
@mobile_login_required
def rewards_summary():
    user = request.mobile_user
    recent = RewardTransaction.query.filter_by(user_id=user.id).order_by(
        RewardTransaction.created_at.desc()
    ).limit(5).all()
    return jsonify({
        'points': int(user.reward_points or 0),
        'progress': reward_progress(user.reward_points),
        'membership_plan': user.membership_plan or 'free',
        'membership_status': user.membership_status or 'active',
        'tiers': REWARD_TIERS,
        'recent_transactions': [{
            'id': transaction.id,
            'points': transaction.points,
            'type': transaction.type,
            'note': transaction.note or '',
            'created_at': iso_datetime(transaction.created_at),
        } for transaction in recent],
        'membership_plans': MEMBERSHIP_PLANS,
        'earning_paused': POINTS_EARNING_PAUSED,
    })


@mobile_api_bp.route('/splits/<int:split_id>/settle', methods=['POST'])
@mobile_login_required
def settle_split(split_id):
    split = ExpenseSplit.query.get_or_404(split_id)
    if request.mobile_user not in split.expense.group.members:
        return json_error('Unauthorized split access.', 403)
    # Only the person who is owed can confirm a split was paid.
    if split.expense.paid_by_id != request.mobile_user.id:
        return json_error('Only the person who paid for this expense can mark it settled.', 403)

    split.is_settled = True
    split.amount_owed = 0.0
    db.session.commit()
    return jsonify({'settled': True})


@mobile_api_bp.route('/groups/<int:group_id>/tasks', methods=['POST'])
@mobile_login_required
def add_task(group_id):
    group, error = require_group_member(group_id)
    if error:
        return error

    data = json_body()
    title = (data.get('title') or '').strip()
    if not title:
        return json_error('Task title is required.')
    try:
        due_date = datetime.fromisoformat(data.get('due_date'))
        reminder_time = datetime.fromisoformat(data.get('reminder_time')) if data.get('reminder_time') else None
    except (TypeError, ValueError):
        return json_error('Enter a valid due date.')

    assigned_to_id = data.get('assigned_to_id')
    assigned_to = User.query.get(assigned_to_id) if assigned_to_id else None
    if assigned_to and assigned_to not in group.members:
        return json_error('Assignee must be a group member.')

    task = Task(
        title=title,
        description=(data.get('description') or '').strip(),
        due_date=due_date,
        reminder_time=reminder_time,
        priority=normalize_task_priority(data.get('priority')),
        recurrence=normalize_task_recurrence(data.get('recurrence')),
        group_id=group.id,
        assigned_to_id=assigned_to.id if assigned_to else None,
        created_by_id=request.mobile_user.id,
    )
    db.session.add(task)
    db.session.commit()
    return jsonify(task_payload(task)), 201


@mobile_api_bp.route('/tasks/<int:task_id>/toggle', methods=['POST'])
@mobile_login_required
def toggle_task(task_id):
    task = Task.query.get_or_404(task_id)
    if request.mobile_user not in task.group.members:
        return json_error('Unauthorized task access.', 403)
    next_task = toggle_task_completion(task, db.session)
    db.session.commit()
    return jsonify({
        'is_completed': bool(task.is_completed),
        'next_task_id': next_task.id if next_task else None,
    })


@mobile_api_bp.route('/tasks/<int:task_id>', methods=['DELETE'])
@mobile_login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if request.mobile_user not in task.group.members:
        return json_error('Unauthorized task access.', 403)
    if request.mobile_user.id not in (task.created_by_id, task.group.admin_id):
        return json_error('Only the person who created this task or the group admin can delete it.', 403)
    db.session.delete(task)
    db.session.commit()
    return jsonify({'deleted': True})


@mobile_api_bp.route('/groups/<int:group_id>/notes', methods=['POST'])
@mobile_login_required
def add_note(group_id):
    group, error = require_group_member(group_id)
    if error:
        return error

    data = json_body()
    title = (data.get('title') or '').strip()
    if not title:
        return json_error('Note title is required.')
    note = Note(
        title=title,
        description=(data.get('description') or '').strip(),
        content=title,
        group_id=group.id,
        created_by_id=request.mobile_user.id,
    )
    db.session.add(note)
    db.session.commit()
    return jsonify(note_payload(note)), 201


@mobile_api_bp.route('/notes/<int:note_id>/toggle', methods=['POST'])
@mobile_login_required
def toggle_note(note_id):
    note = Note.query.get_or_404(note_id)
    if request.mobile_user not in note.group.members:
        return json_error('Unauthorized note access.', 403)
    note.is_completed = not note.is_completed
    db.session.commit()
    return jsonify({'is_completed': bool(note.is_completed)})


@mobile_api_bp.route('/grocery/compare', methods=['POST'])
@mobile_login_required
@limiter.limit('30 per hour')
def compare_grocery_prices():
    """Compare real store prices for a typed list like "apple, banana, 2 milk"."""
    data = json_body()
    requested_items = parse_grocery_items_from_text(str(data.get('items') or '')[:1000])
    if not requested_items:
        return json_error('Type at least one item, separated by commas or new lines.')
    return jsonify(compare_grocery_list(requested_items, location=data.get('location')))


@mobile_api_bp.route('/notes/<int:note_id>/grocery-comparison')
@mobile_login_required
def compare_note_groceries(note_id):
    note = Note.query.get_or_404(note_id)
    if request.mobile_user not in note.group.members:
        return json_error('Unauthorized note access.', 403)

    if not note_allows_grocery_comparison(note):
        return json_error('Price comparison is only available for grocery, shopping, or list notes.')

    comparison = compare_grocery_note(note, location=request.args.get('location'))
    if not comparison['requested_items']:
        return json_error('No grocery items found in this note. Add one item per line or separate items with commas.')

    return jsonify(comparison)


@mobile_api_bp.route('/notes/<int:note_id>', methods=['PATCH', 'DELETE'])
@mobile_login_required
def delete_note(note_id):
    note = Note.query.get_or_404(note_id)
    if request.mobile_user not in note.group.members:
        return json_error('Unauthorized note access.', 403)
    if request.method == 'PATCH':
        data = json_body()
        title = (data.get('title') or '').strip()
        if not title:
            return json_error('Note title is required.')
        note.title = title
        note.content = title
        note.description = (data.get('description') or '').strip()
        db.session.commit()
        return jsonify(note_payload(note))
    if request.mobile_user.id not in (note.created_by_id, note.group.admin_id):
        return json_error('Only the person who wrote this note or the group admin can delete it.', 403)
    db.session.delete(note)
    db.session.commit()
    return jsonify({'deleted': True})


@mobile_api_bp.route('/reminders/upcoming')
@mobile_login_required
def upcoming_reminders():
    now = datetime.utcnow()
    tasks = Task.query.join(Group).filter(
        Group.members.contains(request.mobile_user),
        Task.reminder_time != None,
        Task.reminder_time >= now,
        Task.is_completed == False,
    ).order_by(Task.reminder_time).limit(20).all()

    return jsonify([task_payload(task) for task in tasks])


@mobile_api_bp.route('/notes')
@mobile_login_required
def all_notes():
    notes = Note.query.join(Group).filter(
        Group.members.contains(request.mobile_user),
    ).order_by(Note.created_at.desc()).all()

    return jsonify([note_payload(note) for note in notes])


@mobile_api_bp.route('/tasks')
@mobile_login_required
def all_tasks():
    tasks = Task.query.join(Group).filter(
        Group.members.contains(request.mobile_user),
    ).order_by(Task.due_date.asc()).all()

    return jsonify([task_payload(task) for task in tasks])


@mobile_api_bp.route('/balances/people')
@mobile_login_required
def people_balances():
    """Net balance with each counterparty the current user shares at least one group with.

    Sign convention (matches `balances_for`'s per-member `net` and the dashboard's
    `total_owed_to_user`/`total_user_owes`): positive `net` means the counterparty owes
    the user money overall; negative means the user owes the counterparty.
    """
    user = request.mobile_user
    user_groups = user.groups.all()

    # other_user_id -> {
    #   'name': str,
    #   'groups': { group_id: {'group_name': str, 'cents': int} },
    # }
    people = {}

    for group in user_groups:
        nicknames = member_nickname_rows(group.id)

        for member in group.members:
            if member.id == user.id:
                continue
            entry = people.setdefault(member.id, {'name': None, 'groups': {}})
            entry['groups'].setdefault(group.id, {'group_name': group.name, 'cents': 0})
            if entry['name'] is None:
                entry['name'] = nicknames.get(member.id) or member.name

        for expense in group.expenses:
            for split in expense.splits:
                if split.user_id == expense.paid_by_id or split.is_settled:
                    continue
                if expense.paid_by_id != user.id and split.user_id != user.id:
                    continue

                split_cents = int(money_decimal(split.amount_owed) * 100)
                if expense.paid_by_id == user.id:
                    other_id = split.user_id
                    delta_cents = split_cents
                else:
                    other_id = expense.paid_by_id
                    delta_cents = -split_cents

                if other_id == user.id:
                    continue

                entry = people.setdefault(other_id, {'name': None, 'groups': {}})
                group_entry = entry['groups'].setdefault(group.id, {'group_name': group.name, 'cents': 0})
                group_entry['cents'] += delta_cents

    other_ids = [other_id for other_id, entry in people.items() if entry['name'] is None]
    if other_ids:
        for other_user in User.query.filter(User.id.in_(other_ids)).all():
            people[other_user.id]['name'] = other_user.name

    results = []
    for other_id, entry in people.items():
        groups_payload = [{
            'group_id': group_id,
            'group_name': group_data['group_name'],
            'net': float((Decimal(group_data['cents']) / 100).quantize(CENT, rounding=ROUND_HALF_UP)),
        } for group_id, group_data in entry['groups'].items()]
        groups_payload.sort(key=lambda row: row['group_id'])

        total_cents = sum(group_data['cents'] for group_data in entry['groups'].values())

        results.append({
            'user_id': other_id,
            'name': entry['name'],
            'net': float((Decimal(total_cents) / 100).quantize(CENT, rounding=ROUND_HALF_UP)),
            'groups': groups_payload,
        })

    results.sort(key=lambda row: (row['name'] or '', row['user_id']))
    return jsonify(results)


@mobile_api_bp.route('/export')
@mobile_login_required
def export_my_data():
    user = request.mobile_user
    group_ids = [group.id for group in user.groups.all()]
    data = {
        'profile': {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'created_at': iso_datetime(user.created_at),
            'reward_points': int(user.reward_points or 0),
            'membership_plan': user.membership_plan or 'free',
            'membership_status': user.membership_status or 'active',
        },
        'groups': [{
            'id': group.id,
            'name': group.name,
            'admin_id': group.admin_id,
            'created_at': iso_datetime(group.created_at),
            'members': group_member_payload(group),
        } for group in user.groups.all()],
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
            or_(Payment.payer_id == user.id, Payment.receiver_id == user.id)
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
        } for transaction in RewardTransaction.query.filter_by(user_id=user.id).order_by(RewardTransaction.created_at.desc()).all()],
    }
    return jsonify(data)


@mobile_api_bp.route('/groups/<int:group_id>/activity.csv')
@mobile_login_required
def export_group_activity_csv(group_id):
    group, error = require_group_member(group_id)
    if error:
        return error

    nicknames = member_nickname_rows(group.id)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Type',
        'Date',
        'Description',
        'Category',
        'Amount',
        'Paid By',
        'Payer',
        'Receiver',
        'Method',
        'Status'
    ])

    rows = []
    for item in ExpenseHistory.query.filter_by(group_id=group.id).all():
        payer = User.query.get(item.paid_by_id) if item.paid_by_id else None
        rows.append({
            'date': item.date,
            'values': [
                'Expense',
                item.date.strftime('%Y-%m-%d %H:%M') if item.date else '',
                item.description,
                split_routes.normalize_expense_category(item.category),
                f'{money_decimal(item.amount):.2f}',
                nicknames.get(item.paid_by_id) or (payer.name if payer else ''),
                '',
                '',
                '',
                ''
            ]
        })

    for payment in Payment.query.filter_by(group_id=group.id).all():
        rows.append({
            'date': payment.date,
            'values': [
                'Payment',
                payment.date.strftime('%Y-%m-%d %H:%M') if payment.date else '',
                'Payment',
                '',
                f'{money_decimal(payment.amount):.2f}',
                '',
                nicknames.get(payment.payer_id) or payment.payer.name,
                nicknames.get(payment.receiver_id) or payment.receiver.name,
                payment.method,
                payment.status
            ]
        })

    for row in sorted(rows, key=lambda item: item['date'] or datetime.min, reverse=True):
        writer.writerow([csv_safe(value) for value in row['values']])

    filename = f'Splitmate_{split_routes.safe_export_filename(group.name)}_activity.csv'
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )
