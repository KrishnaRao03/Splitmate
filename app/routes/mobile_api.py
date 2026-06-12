from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import wraps

from flask import Blueprint, current_app, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app import db
from app.email_validation import normalize_email
from app.group_utils import group_member_payload, member_nickname_rows, set_member_nickname
from app.models import (
    Expense,
    ExpenseHistory,
    ExpenseSplit,
    Group,
    MobileDevice,
    Note,
    Payment,
    Task,
    User,
)
from app.routes.auth import generate_otp, send_user_otp


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
    return token_serializer().dumps({'user_id': user.id, 'email': user.email}, salt=TOKEN_SALT)


def mobile_token_max_age():
    days = int(current_app.config.get('MOBILE_TOKEN_EXPIRY_DAYS') or 30)
    return days * 24 * 60 * 60


def user_payload(user):
    return {
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'is_email_verified': bool(user.is_email_verified),
    }


def auth_payload(user):
    return {
        'token': mobile_token_for(user),
        'user': user_payload(user),
        'currency_code': (current_app.config.get('STRIPE_CURRENCY') or 'cad').upper(),
    }


def json_body():
    return request.get_json(silent=True) or {}


def json_error(message, status=400):
    return jsonify({'error': message}), status


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

    user = User.query.get(data.get('user_id'))
    if not user or user.email != data.get('email') or getattr(user, 'is_suspended', False):
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
        'date': expense.date.isoformat() if expense.date else None,
        'paid_by_id': expense.paid_by_id,
        'paid_by': nicknames.get(expense.paid_by_id) or expense.added_by.name,
        'receipt_url': expense.receipt_url,
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
        'is_completed': bool(task.is_completed),
        'assigned_to_id': task.assigned_to_id,
        'assigned_to': (nicknames.get(task.assigned_to_id) or task.assigned_to.name) if task.assigned_to else None,
        'created_by': nicknames.get(task.created_by_id) or task.created_by.name,
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
        'group_id': note.group_id,
        'group_name': note.group.name,
    }


def balances_for(group):
    balances = {}
    nicknames = member_nickname_rows(group.id)
    for member in group.members:
        balances[member.id] = {
            'id': member.id,
            'name': nicknames.get(member.id) or member.name,
            'paid': 0,
            'owes': 0,
            'net': 0,
        }

    for expense in group.expenses:
        for split in expense.splits:
            if split.user_id == expense.paid_by_id or split.is_settled:
                continue
            balances[expense.paid_by_id]['paid'] += split.amount_owed
            balances[split.user_id]['owes'] += split.amount_owed

    for balance in balances.values():
        balance['paid'] = round(balance['paid'], 2)
        balance['owes'] = round(balance['owes'], 2)
        balance['net'] = round(balance['paid'] - balance['owes'], 2)

    return list(balances.values())


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


def outstanding_splits_for(group, payer, receiver):
    splits = ExpenseSplit.query.join(Expense).filter(
        Expense.group_id == group.id,
        Expense.paid_by_id == receiver.id,
        ExpenseSplit.user_id == payer.id,
        ExpenseSplit.is_settled == False
    ).order_by(Expense.date.asc(), ExpenseSplit.id.asc()).all()
    total = sum((money_decimal(split.amount_owed) for split in splits), Decimal('0.00'))
    return splits, total


def settle_outstanding_splits(group, payer, receiver, amount):
    outstanding_splits, _ = outstanding_splits_for(group, payer, receiver)
    remaining = money_decimal(amount)

    for split in outstanding_splits:
        owed = money_decimal(split.amount_owed)
        if remaining >= owed:
            split.amount_owed = 0.0
            split.is_settled = True
            remaining -= owed
        else:
            split.amount_owed = float(owed - remaining)
            remaining = Decimal('0.00')

        if remaining <= 0:
            break


@mobile_api_bp.route('/health')
def health():
    return jsonify({'ok': True, 'service': 'Splitmate mobile API'})


@mobile_api_bp.route('/auth/login', methods=['POST'])
def login():
    data = json_body()
    email = normalize_email(data.get('email'))
    password = data.get('password') or ''
    user = User.query.filter_by(email=email).first() if email else None

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
def register():
    data = json_body()
    email = normalize_email(data.get('email'))
    name = (data.get('name') or '').strip()
    password = data.get('password') or ''
    confirm_password = data.get('confirm_password') or password

    if not email:
        return json_error('A valid email is required.')
    if not name:
        return json_error('Name is required.')
    if len(password) < 6:
        return json_error('Password must be at least 6 characters.')
    if password != confirm_password:
        return json_error('Passwords do not match.')
    if User.query.filter_by(email=email).first():
        return json_error('Email already registered.', 409)

    user = User(email=email, name=name, is_email_verified=False)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    try:
        otp_sent = send_user_otp(user)
    except Exception as exc:
        current_app.logger.exception('Failed to send mobile verification OTP: %s', exc)
        otp_sent = False

    db.session.commit()
    return jsonify({
        'user': user_payload(user),
        'verification_required': True,
        'otp_sent': bool(otp_sent),
    }), 201


@mobile_api_bp.route('/auth/verify-email', methods=['POST'])
def verify_email():
    data = json_body()
    email = normalize_email(data.get('email'))
    otp = (data.get('otp') or '').strip()
    user = User.query.filter_by(email=email).first() if email else None

    if not user:
        return json_error('Verification session not found.', 404)
    if user.is_email_verified:
        return jsonify(auth_payload(user))
    if user.email_otp_expires_at and user.email_otp_expires_at < datetime.utcnow():
        return json_error('That OTP has expired. Please request a new code.')
    if not user.check_email_otp(otp):
        return json_error('Invalid OTP.')

    user.is_email_verified = True
    user.clear_email_otp()
    user.last_login_at = datetime.utcnow()
    user.last_activity_at = user.last_login_at
    db.session.commit()
    return jsonify(auth_payload(user))


@mobile_api_bp.route('/auth/resend-otp', methods=['POST'])
def resend_otp():
    email = normalize_email(json_body().get('email'))
    user = User.query.filter_by(email=email).first() if email else None
    if not user:
        return json_error('Account not found.', 404)
    if user.is_email_verified:
        return jsonify({'sent': False, 'already_verified': True})

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


@mobile_api_bp.route('/me')
@mobile_login_required
def me():
    return jsonify({
        'user': user_payload(request.mobile_user),
        'currency_code': (current_app.config.get('STRIPE_CURRENCY') or 'cad').upper(),
    })


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


@mobile_api_bp.route('/groups')
@mobile_login_required
def groups():
    user_groups = request.mobile_user.groups.all()
    return jsonify([group_payload(group) for group in user_groups])


@mobile_api_bp.route('/groups', methods=['POST'])
@mobile_login_required
def create_group():
    name = (json_body().get('name') or '').strip()
    if not name:
        return json_error('Group name is required.')

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
        'balances': balances_for(group),
        'summaries': summaries_for(group),
        'expenses': [expense_payload(expense, nicknames) for expense in expenses],
        'tasks': [task_payload(task, nicknames) for task in tasks],
        'notes': [note_payload(note, nicknames) for note in notes],
        'payments': [{
            'id': payment.id,
            'amount': round(payment.amount, 2),
            'date': payment.date.isoformat() if payment.date else None,
            'payer': nicknames.get(payment.payer_id) or payment.payer.name,
            'receiver': nicknames.get(payment.receiver_id) or payment.receiver.name,
            'method': payment.method,
            'status': payment.status,
        } for payment in payments],
    })


@mobile_api_bp.route('/groups/<int:group_id>/members', methods=['POST'])
@mobile_login_required
def add_group_member(group_id):
    group, error = require_group_member(group_id)
    if error:
        return error
    if group.admin_id != request.mobile_user.id:
        return json_error('Only the group admin can add members.', 403)

    email = normalize_email(json_body().get('email'))
    user = User.query.filter_by(email=email).first() if email else None
    if not user:
        return json_error('No Splitmate account found with that email.', 404)
    if user in group.members:
        return jsonify({'member': user_payload(user), 'already_member': True})

    group.members.append(user)
    db.session.flush()
    set_member_nickname(group.id, user)
    db.session.commit()
    return jsonify({'member': user_payload(user), 'already_member': False}), 201


@mobile_api_bp.route('/groups/<int:group_id>/expenses', methods=['POST'])
@mobile_login_required
def add_expense(group_id):
    group, error = require_group_member(group_id)
    if error:
        return error

    data = json_body()
    description = (data.get('description') or '').strip()
    if not description:
        return json_error('Description is required.')

    try:
        expense_amount = money_decimal(data.get('amount'))
    except ValueError as exc:
        return json_error(str(exc))
    if expense_amount <= 0:
        return json_error('Amount must be greater than 0.')

    raw_split_type = data.get('split_type') or 'equal'
    use_selected_members = raw_split_type == 'selected'
    split_type = 'equal' if use_selected_members else raw_split_type
    if split_type not in {'equal', 'exact', 'percentage'}:
        return json_error('Choose a valid split type.')

    all_members = list(group.members)
    selected_members = all_members
    if use_selected_members:
        selected_ids = {int(member_id) for member_id in data.get('split_user_ids') or []}
        selected_members = [member for member in all_members if member.id in selected_ids]
        if len(selected_members) != len(selected_ids):
            return json_error('Choose valid members from this group.')
    if not selected_members:
        return json_error('Choose at least one person to split with.')

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
                    return json_error(f'Enter an amount greater than 0 for {member.name}.')
                split_rows.append((member, amount))
                assigned_total += amount
            if assigned_total != expense_amount:
                return json_error('Exact split amounts must total the expense amount.')

        elif split_type == 'percentage':
            percentages = data.get('percentages') or {}
            total_percentage = Decimal('0.00')
            percentage_rows = []
            for member in selected_members:
                percentage = money_decimal(percentages.get(str(member.id), percentages.get(member.id, 0)))
                if percentage <= 0:
                    return json_error(f'Enter a percentage greater than 0 for {member.name}.')
                percentage_rows.append((member, percentage))
                total_percentage += percentage
            if total_percentage != Decimal('100.00'):
                return json_error('Percentages must total 100%.')
            for member, percentage in percentage_rows:
                split_rows.append((member, (expense_amount * percentage / Decimal('100')).quantize(CENT, rounding=ROUND_HALF_UP)))
    except ValueError as exc:
        return json_error(str(exc))

    assigned_total = sum((share for _, share in split_rows), Decimal('0.00'))
    remainder = expense_amount - assigned_total
    if split_rows and remainder:
        member, share = split_rows[-1]
        split_rows[-1] = (member, share + remainder)

    expense = Expense(
        description=description,
        amount=float(expense_amount),
        group_id=group.id,
        paid_by_id=request.mobile_user.id,
    )
    db.session.add(expense)
    db.session.flush()
    db.session.add(ExpenseHistory(
        description=expense.description,
        amount=expense.amount,
        date=expense.date,
        paid_by_id=expense.paid_by_id,
        group_id=expense.group_id,
    ))
    for member, share in split_rows:
        if share > 0:
            db.session.add(ExpenseSplit(expense_id=expense.id, user_id=member.id, amount_owed=float(share)))
    db.session.commit()
    return jsonify(expense_payload(expense)), 201


@mobile_api_bp.route('/groups/<int:group_id>/payments', methods=['POST'])
@mobile_login_required
def record_payment(group_id):
    group, error = require_group_member(group_id)
    if error:
        return error

    data = json_body()
    receiver = User.query.get(data.get('receiver_id'))
    if not receiver or receiver not in group.members or receiver.id == request.mobile_user.id:
        return json_error('Choose a valid receiver.')
    try:
        amount = money_decimal(data.get('amount'))
    except ValueError as exc:
        return json_error(str(exc))
    if amount <= 0:
        return json_error('Payment amount must be greater than 0.')
    _, total_owed = outstanding_splits_for(group, request.mobile_user, receiver)
    if total_owed <= 0:
        return json_error('There is no outstanding balance for that receiver.')
    if amount > total_owed:
        return json_error('Payment cannot be greater than the outstanding balance.')

    payment = Payment(
        payer_id=request.mobile_user.id,
        receiver_id=receiver.id,
        amount=float(amount),
        group_id=group.id,
        method='manual',
        status='recorded',
    )
    db.session.add(payment)
    settle_outstanding_splits(group, request.mobile_user, receiver, amount)
    db.session.commit()
    return jsonify({'id': payment.id, 'recorded': True}), 201


@mobile_api_bp.route('/splits/<int:split_id>/settle', methods=['POST'])
@mobile_login_required
def settle_split(split_id):
    split = ExpenseSplit.query.get_or_404(split_id)
    if request.mobile_user not in split.expense.group.members:
        return json_error('Unauthorized split access.', 403)
    if split.user_id != request.mobile_user.id and split.expense.paid_by_id != request.mobile_user.id:
        return json_error('Only the payer or owed user can settle this split.', 403)

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
    task.is_completed = not task.is_completed
    db.session.commit()
    return jsonify({'is_completed': bool(task.is_completed)})


@mobile_api_bp.route('/tasks/<int:task_id>', methods=['DELETE'])
@mobile_login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if request.mobile_user not in task.group.members:
        return json_error('Unauthorized task access.', 403)
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


@mobile_api_bp.route('/notes/<int:note_id>', methods=['DELETE'])
@mobile_login_required
def delete_note(note_id):
    note = Note.query.get_or_404(note_id)
    if request.mobile_user not in note.group.members:
        return json_error('Unauthorized note access.', 403)
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
