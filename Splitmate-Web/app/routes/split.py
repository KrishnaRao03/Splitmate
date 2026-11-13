import csv
import io
import json
import os
from uuid import uuid4

from flask import Blueprint, Response, current_app, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.utils import secure_filename

from app import db
from app.models import Group, Expense, ExpenseSplit, ExpenseHistory, Payment, User
from app.group_utils import group_member_payload, group_pending_invite_payload, member_nickname_rows
from app.security import csv_safe, is_safe_link, payment_methods_for

split_bp = Blueprint('split', __name__, url_prefix='/split')
CENT = Decimal('0.01')
ALLOWED_RECEIPT_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf'}
RECEIPT_URL_PREFIX = '/receipts/'
RECEIPT_LINK_MAX_AGE = 60 * 60
RECEIPT_LINK_SALT = 'receipt-link'
# A manual payment is 'pending' until the person who was paid confirms it.
PAYMENT_STATUS_LABELS = {
    'pending': 'Waiting for confirmation',
    'recorded': 'Confirmed',
    'paid': 'Paid',
    'declined': 'Declined',
}
EXPENSE_CATEGORIES = [
    'General',
    'Groceries',
    'Dining',
    'Rent',
    'Utilities',
    'Transport',
    'Travel',
    'Entertainment',
    'Shopping',
    'Health',
    'Other'
]
DEFAULT_SPLIT_TYPES = {'equal', 'selected', 'percentage'}


def money_decimal(value):
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)

MAX_CATEGORY_LENGTH = 40  # matches the expense.category column

def normalize_expense_category(value):
    """Built-in categories keep their spelling ("groceries" -> "Groceries"); anything else is the
    user's own label, trimmed to the column size. Markup characters fall back to General."""
    category = ' '.join((value or '').split())[:MAX_CATEGORY_LENGTH].strip()
    if not category or '<' in category or '>' in category:
        return 'General'
    for known in EXPENSE_CATEGORIES:
        if known.lower() == category.lower():
            return known
    return category

def category_error(value):
    if '<' in (value or '') or '>' in (value or ''):
        return 'Category cannot contain < or >.'
    return None

def used_categories(group):
    """Custom categories already used in this group, oldest spelling first, so new expenses reuse them."""
    rows = db.session.query(ExpenseHistory.category).filter(ExpenseHistory.group_id == group.id).distinct().all()
    rows += db.session.query(Expense.category).filter(Expense.group_id == group.id).distinct().all()
    seen = {}
    for (category,) in rows:
        cleaned = normalize_expense_category(category)
        if cleaned not in EXPENSE_CATEGORIES:
            seen.setdefault(cleaned.lower(), cleaned)
    return sorted(seen.values(), key=str.lower)

def group_categories(group):
    """Suggestions for the category field: the built-in list, then this group's own categories."""
    return EXPENSE_CATEGORIES + used_categories(group)

def category_for_group(group, value):
    """Normalizes a typed category and matches it to one the group already uses, ignoring case."""
    category = normalize_expense_category(value)
    for existing in used_categories(group):
        if existing.lower() == category.lower():
            return existing
    return category

def group_default_split_payload(group):
    split_type = group.default_split_type if group.default_split_type in DEFAULT_SPLIT_TYPES else 'equal'
    config = {}

    if group.default_split_config:
        try:
            loaded_config = json.loads(group.default_split_config)
            if isinstance(loaded_config, dict):
                config = loaded_config
        except (TypeError, ValueError):
            config = {}

    return {
        'type': split_type,
        'member_ids': [str(member_id) for member_id in config.get('member_ids', [])],
        'percentages': {
            str(member_id): str(percent)
            for member_id, percent in (config.get('percentages') or {}).items()
        }
    }

def parse_date_filter(value, *, include_next_day=False):
    raw_value = (value or '').strip()
    if not raw_value:
        return None

    parsed = datetime.strptime(raw_value, '%Y-%m-%d')
    return parsed + timedelta(days=1) if include_next_day else parsed

def validate_member_ids(group, member_ids):
    member_id_set = {member.id for member in group.members}
    unique_ids = []

    for member_id in member_ids:
        if member_id not in member_id_set:
            raise ValueError('Choose valid members from this group.')

        if member_id not in unique_ids:
            unique_ids.append(member_id)

    return unique_ids

def payment_currency_code():
    return (current_app.config.get('STRIPE_CURRENCY') or 'cad').lower()

def format_payment_amount(amount):
    return f'{payment_currency_code().upper()} {money_decimal(amount):.2f}'

def safe_export_filename(value):
    cleaned = ''.join(char if char.isalnum() else '_' for char in (value or 'group')).strip('_')
    return cleaned or 'group'

def is_allowed_receipt(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_RECEIPT_EXTENSIONS

def save_receipt_file(receipt_file):
    if not receipt_file or not receipt_file.filename:
        return None

    original_filename = secure_filename(receipt_file.filename)
    if not original_filename:
        return None

    if not is_allowed_receipt(original_filename):
        raise ValueError('Receipt must be an image or PDF file.')

    _, extension = os.path.splitext(original_filename)
    upload_dir = receipt_upload_dir()
    os.makedirs(upload_dir, exist_ok=True)

    stored_filename = f'{uuid4().hex}{extension.lower()}'
    receipt_file.save(os.path.join(upload_dir, stored_filename))
    return f'{RECEIPT_URL_PREFIX}{stored_filename}'

def receipt_upload_dir():
    # Outside static/, so receipts are only served through the access-checked /receipts/ route.
    return os.path.join(current_app.instance_path, 'receipts')

def receipt_link_serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt=RECEIPT_LINK_SALT)

def signed_receipt_url(receipt_url):
    """Uploaded receipts get a short-lived signed link, so the app can open them in a browser."""
    if not receipt_url or not receipt_url.startswith(RECEIPT_URL_PREFIX):
        return receipt_url
    filename = receipt_url[len(RECEIPT_URL_PREFIX):]
    return f'{receipt_url}?sig={receipt_link_serializer().dumps(filename)}'

def receipt_signature_valid(filename, signature):
    try:
        return receipt_link_serializer().loads(signature or '', max_age=RECEIPT_LINK_MAX_AGE) == filename
    except (BadSignature, SignatureExpired):
        return False

def member_has_open_balance(group, user):
    """True while the user still owes, or is owed, money on an unsettled split in this group."""
    return db.session.query(ExpenseSplit.id).join(Expense).filter(
        Expense.group_id == group.id,
        ExpenseSplit.is_settled == False,
        ExpenseSplit.user_id != Expense.paid_by_id,
        ((ExpenseSplit.user_id == user.id) | (Expense.paid_by_id == user.id)),
    ).first() is not None

def group_balances(group, nicknames=None):
    nicknames = nicknames if nicknames is not None else member_nickname_rows(group.id)
    balances = {}

    def entry(user):
        return balances.setdefault(user.id, {
            'id': user.id,
            'name': nicknames.get(user.id) or user.name,
            'paid': 0,
            'owes': 0,
            'net': 0,
        })

    for member in group.members:
        entry(member)

    for expense in group.expenses:
        for split in expense.splits:
            if split.user_id == expense.paid_by_id or split.is_settled:
                continue
            # Former members can still have open splits from before they left; keep them listed.
            entry(expense.added_by)['paid'] += split.amount_owed
            entry(split.user)['owes'] += split.amount_owed

    for balance in balances.values():
        balance['paid'] = round(balance['paid'], 2)
        balance['owes'] = round(balance['owes'], 2)
        balance['net'] = round(balance['paid'] - balance['owes'], 2)

    return list(balances.values())

def pending_payment_total(group, payer, receiver):
    pending = Payment.query.filter_by(
        group_id=group.id, payer_id=payer.id, receiver_id=receiver.id, status='pending'
    ).all()
    return sum((money_decimal(payment.amount) for payment in pending), Decimal('0.00'))

def request_payment(group, payer, receiver, amount):
    """Records that payer says they paid receiver. Balances only change once receiver confirms.

    Returns (payment, None) or (None, error message).
    """
    if not receiver or receiver not in group.members or receiver.id == payer.id:
        return None, 'Choose a valid receiver from this group.'
    try:
        payment_amount = money_decimal(amount)
    except (InvalidOperation, ValueError, TypeError):
        return None, 'Enter a valid payment amount.'
    if payment_amount <= 0:
        return None, 'Payment amount must be greater than 0.'

    _, total_owed = outstanding_splits_for(group, payer, receiver)
    available = total_owed - pending_payment_total(group, payer, receiver)
    if total_owed <= 0:
        return None, 'There is no outstanding balance for that receiver.'
    if available <= 0:
        return None, 'You already have payments to this person waiting for confirmation.'
    if payment_amount > available:
        return None, f'You can record up to {format_payment_amount(available)} right now.'

    return create_payment_record(group, payer, receiver, payment_amount, status='pending'), None

def confirm_payment(payment, user):
    """The receiver confirms the money arrived; only then are the payer's splits settled."""
    if payment.receiver_id != user.id:
        return 'Only the person who was paid can confirm this payment.'
    if payment.status != 'pending':
        return 'This payment is not waiting for confirmation.'

    group = db.session.get(Group, payment.group_id)
    _, total_owed = outstanding_splits_for(group, payment.payer, payment.receiver)
    amount = min(money_decimal(payment.amount), total_owed)
    if amount > 0:
        settle_outstanding_splits(group, payment.payer, payment.receiver, amount)
    payment.amount = float(amount)
    payment.status = 'recorded'
    return None

def decline_payment(payment, user):
    """Either side can withdraw a pending payment (the receiver didn't get it, or the payer made a mistake)."""
    if user.id not in (payment.receiver_id, payment.payer_id):
        return 'Only the payer or the receiver can decline this payment.'
    if payment.status != 'pending':
        return 'This payment is not waiting for confirmation.'
    payment.status = 'declined'
    return None

def payment_row(payment, nicknames, viewer):
    return {
        'id': payment.id,
        'amount': round(payment.amount, 2),
        'date': payment.date.isoformat() if payment.date else None,
        'payer_id': payment.payer_id,
        'receiver_id': payment.receiver_id,
        'payer': nicknames.get(payment.payer_id) or payment.payer.name,
        'receiver': nicknames.get(payment.receiver_id) or payment.receiver.name,
        'method': payment.method,
        'status': payment.status,
        'status_label': PAYMENT_STATUS_LABELS.get(payment.status, payment.status.title()),
        'can_confirm': payment.status == 'pending' and payment.receiver_id == viewer.id,
        'can_decline': payment.status == 'pending' and viewer.id in (payment.receiver_id, payment.payer_id),
        'reward_points_awarded': int(payment.reward_points_awarded or 0),
    }

def payment_options(group, payer, nicknames=None):
    """Who the payer owes in this group, how much, and the receiver's link-out ways to pay."""
    nicknames = nicknames if nicknames is not None else member_nickname_rows(group.id)
    currency = payment_currency_code()
    options = []
    for receiver in group.members:
        if receiver.id == payer.id:
            continue
        _, total_owed = outstanding_splits_for(group, payer, receiver)
        if total_owed <= 0:
            continue
        pending = pending_payment_total(group, payer, receiver)
        name = nicknames.get(receiver.id) or receiver.name
        options.append({
            'receiver_id': receiver.id,
            'receiver': name,
            'max_amount': float(max(total_owed - pending, Decimal('0.00'))),
            'owed': float(total_owed),
            'pending_amount': float(pending),
            'payment_methods': payment_methods_for(receiver, total_owed - pending if total_owed > pending else total_owed, currency, name),
        })
    options.sort(key=lambda item: item['receiver'].lower())
    return options

def money_requests(group, receiver, nicknames=None):
    """Who owes `receiver` in this group, and the state of receiver's request to each of them.

    A payer's Interac email is only included once they approved the request in Splitmate.
    """
    from app.models import MoneyRequest
    from app.payment_security import mask_email

    nicknames = nicknames if nicknames is not None else member_nickname_rows(group.id)
    requests = []
    for payer in group.members:
        if payer.id == receiver.id:
            continue
        _, total_owed = outstanding_splits_for(group, payer, receiver)
        requestable = total_owed - pending_payment_total(group, payer, receiver)
        if requestable <= 0:
            continue
        latest = MoneyRequest.query.filter_by(group_id=group.id, requester_id=receiver.id, payer_id=payer.id) \
            .order_by(MoneyRequest.created_at.desc(), MoneyRequest.id.desc()).first()
        approved = bool(latest and latest.status == 'approved')
        email = None
        if approved:
            verified = payer.interac_email and getattr(payer, 'interac_email_verified', False)
            email = payer.interac_email if verified else payer.email
        requests.append({
            'payer_id': payer.id,
            'payer': nicknames.get(payer.id) or payer.name,
            'amount': float(requestable),
            'request_id': latest.id if latest else None,
            'request_status': latest.status if latest else 'none',
            'email': email,
            'masked_email': mask_email(email) if email else None,
        })
    requests.sort(key=lambda item: item['payer'].lower())
    return requests


def requests_for_payer(group, payer, nicknames=None):
    """Pending requests asking `payer` to pay someone in this group, for them to approve or decline."""
    from app.models import MoneyRequest

    nicknames = nicknames if nicknames is not None else member_nickname_rows(group.id)
    pending = MoneyRequest.query.filter_by(group_id=group.id, payer_id=payer.id, status='pending') \
        .order_by(MoneyRequest.created_at.desc()).all()
    return [{
        'id': item.id,
        'requester_id': item.requester_id,
        'requester': nicknames.get(item.requester_id) or item.requester.name,
        'amount': float(item.amount),
        'created_at': item.created_at.isoformat() if item.created_at else None,
    } for item in pending]


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

def create_payment_record(group, payer, receiver, amount, method='manual',
                          stripe_checkout_session_id=None, status='recorded'):
    payment_amount = money_decimal(amount)

    payment = Payment(
        payer_id=payer.id,
        receiver_id=receiver.id,
        amount=float(payment_amount),
        group_id=group.id,
        method=method,
        stripe_checkout_session_id=stripe_checkout_session_id,
        status=status
    )
    db.session.add(payment)
    return payment

@split_bp.route('/')
@login_required
def index():
    groups = current_user.groups.all()
    groups_json = [
        {
            'id': g.id,
            'name': g.name,
            'admin_id': g.admin_id,
            'members': group_member_payload(g),
            'pending_invites': group_pending_invite_payload(g) if g.admin_id == current_user.id else [],
            'default_split': group_default_split_payload(g)
        }
        for g in groups
    ]
    return render_template(
        'split.html',
        groups=groups,
        groups_json=groups_json,
        expense_categories=EXPENSE_CATEGORIES
    )

@split_bp.route('/add', methods=['POST'])
@login_required
def add_expense():
    group_id = request.form.get('group_id', type=int)
    description = request.form.get('description', '').strip()
    amount = request.form.get('amount', type=float)
    raw_category = request.form.get('category')
    paid_by_id = request.form.get('paid_by_id', type=int) or current_user.id
    receipt_url = request.form.get('receipt_url', '').strip() or None
    receipt_file = request.files.get('receipt')
    raw_split_type = request.form.get('split_type', 'equal')
    use_selected_members = raw_split_type == 'selected'
    split_type = 'equal' if use_selected_members else raw_split_type

    group = Group.query.get_or_404(group_id)
    if current_user not in group.members:
        flash('You are not a member of this group.', 'error')
        return redirect(url_for('split.index'))

    paid_by = User.query.get(paid_by_id)
    if not paid_by or paid_by not in group.members:
        flash('Choose a valid payer from this group.', 'error')
        return redirect(url_for('split.index'))

    if not description or not amount or amount <= 0:
        flash('Valid description and amount are required.', 'error')
        return redirect(url_for('split.index'))

    if not is_safe_link(receipt_url):
        flash('Receipt URL must start with http:// or https://.', 'error')
        return redirect(url_for('split.index'))

    if category_error(raw_category):
        flash(category_error(raw_category), 'error')
        return redirect(url_for('split.index'))
    category = category_for_group(group, raw_category)

    all_members = list(group.members)
    if split_type not in {'equal', 'exact', 'percentage'}:
        flash('Choose a valid split type.', 'error')
        return redirect(url_for('split.index'))

    selected_members = all_members
    if use_selected_members:
        selected_member_ids = request.form.getlist('split_user_ids', type=int)
        selected_member_id_set = set(selected_member_ids)
        selected_members = [member for member in all_members if member.id in selected_member_id_set]

        if len(selected_members) != len(selected_member_id_set):
            flash('Choose valid members from this group.', 'error')
            return redirect(url_for('split.index'))

    if not selected_members:
        flash('Choose at least one person in Split with.', 'error')
        return redirect(url_for('split.index'))

    expense_amount = money_decimal(amount)
    split_rows = []

    def form_money(field_name, label):
        raw_value = (request.form.get(field_name, '') or '').strip() or '0'
        try:
            value = money_decimal(raw_value)
        except (InvalidOperation, ValueError):
            raise ValueError(f'Enter a valid {label}.')

        if value < 0:
            raise ValueError(f'{label.capitalize()} cannot be negative.')

        return value

    try:
        if split_type == 'equal':
            member_count = Decimal(len(selected_members))
            split_amount = (expense_amount / member_count).quantize(CENT, rounding=ROUND_HALF_UP)
            remainder = expense_amount - (split_amount * member_count)

            for i, member in enumerate(selected_members):
                share = split_amount + (remainder if i == len(selected_members) - 1 else Decimal('0.00'))
                split_rows.append((member, share))

        elif split_type == 'exact':
            assigned_total = Decimal('0.00')
            for member in selected_members:
                member_amount = form_money(f'amount_{member.id}', f'amount for {member.name}')
                if member_amount <= 0:
                    raise ValueError(f'Enter an amount greater than 0 for {member.name}.')

                split_rows.append((member, member_amount))
                assigned_total += member_amount

            if assigned_total != expense_amount:
                raise ValueError(f'Exact split amounts must total {format_payment_amount(expense_amount)}.')

        elif split_type == 'percentage':
            percentages = []
            total_percentage = Decimal('0.00')
            for member in selected_members:
                percentage = form_money(f'percent_{member.id}', f'percentage for {member.name}')
                if percentage <= 0:
                    raise ValueError(f'Enter a percentage greater than 0 for {member.name}.')

                percentages.append((member, percentage))
                total_percentage += percentage

            if total_percentage != Decimal('100.00'):
                raise ValueError('Percentages for selected users must total 100%.')

            for member, percentage in percentages:
                member_amount = (expense_amount * percentage / Decimal('100')).quantize(CENT, rounding=ROUND_HALF_UP)
                split_rows.append((member, member_amount))

            assigned_total = sum((share for _, share in split_rows), Decimal('0.00'))
            remainder = expense_amount - assigned_total
            if split_rows and remainder:
                member, share = split_rows[-1]
                split_rows[-1] = (member, share + remainder)

        else:
            flash('Choose a valid split type.', 'error')
            return redirect(url_for('split.index'))
    except ValueError as exc:
        flash(str(exc), 'error')
        return redirect(url_for('split.index'))

    try:
        uploaded_receipt_url = save_receipt_file(receipt_file)
    except ValueError as exc:
        flash(str(exc), 'error')
        return redirect(url_for('split.index'))

    if uploaded_receipt_url:
        receipt_url = uploaded_receipt_url

    # Create active expense
    expense = Expense(
        description=description,
        amount=float(expense_amount),
        category=category,
        receipt_url=receipt_url,
        group_id=group_id,
        paid_by_id=paid_by.id
    )
    db.session.add(expense)
    db.session.flush()  # get expense.id

    # Immediate immutable history copy
    history_copy = ExpenseHistory(
        description=expense.description,
        amount=expense.amount,
        category=expense.category,
        date=expense.date,
        paid_by_id=expense.paid_by_id,
        group_id=expense.group_id
    )
    db.session.add(history_copy)

    for member, share in split_rows:
        if share > 0:
            db.session.add(ExpenseSplit(
                expense_id=expense.id,
                user_id=member.id,
                amount_owed=float(share)
            ))

    db.session.commit()
    flash('Expense added and recorded in transaction history.', 'success')
    return redirect(url_for('split.index'))

@split_bp.route('/clear_recent/<int:group_id>', methods=['POST'])
@login_required
def clear_recent(group_id):
    group = Group.query.get_or_404(group_id)
    if current_user not in group.members:
        flash('Unauthorized', 'error')
        return redirect(url_for('split.index'))

    # Clearing wipes everyone's open balances, so only the group admin may do it.
    if group.admin_id != current_user.id:
        flash('Only the group admin can clear recent expenses.', 'error')
        return redirect(url_for('split.index'))

    # Remove active expenses only; history already has copies
    for exp in group.expenses.all():
        db.session.delete(exp)

    db.session.commit()
    flash('Recent expenses cleared. Transaction history retained.', 'success')
    return redirect(url_for('split.index'))

@split_bp.route('/pay', methods=['POST'])
@login_required
def record_payment():
    group_id = request.form.get('group_id', type=int)
    receiver_id = request.form.get('receiver_id', type=int)
    amount = request.form.get('amount', type=float)

    group = Group.query.get_or_404(group_id)
    if current_user not in group.members:
        flash('Unauthorized.', 'error')
        return redirect(url_for('split.index'))

    receiver = db.session.get(User, receiver_id) if receiver_id else None
    _, error = request_payment(group, current_user, receiver, amount if amount else 0)
    if error:
        flash(error, 'error')
        return redirect(url_for('split.index'))

    db.session.commit()
    flash(f'Payment recorded. {receiver.name} needs to confirm it before your balance changes.', 'success')
    return redirect(url_for('split.index'))

def payment_for_member(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    if current_user not in payment.group.members:
        return None
    return payment

@split_bp.route('/payments/<int:payment_id>/confirm', methods=['POST'])
@login_required
def confirm_payment_view(payment_id):
    payment = payment_for_member(payment_id)
    error = confirm_payment(payment, current_user) if payment else 'Unauthorized.'
    if error:
        flash(error, 'error')
    else:
        db.session.commit()
        flash('Payment confirmed and balances updated.', 'success')
    return redirect(url_for('split.index'))

@split_bp.route('/payments/<int:payment_id>/decline', methods=['POST'])
@login_required
def decline_payment_view(payment_id):
    payment = payment_for_member(payment_id)
    error = decline_payment(payment, current_user) if payment else 'Unauthorized.'
    if error:
        flash(error, 'error')
    else:
        db.session.commit()
        flash('Payment declined. Balances were not changed.', 'info')
    return redirect(url_for('split.index'))

@split_bp.route('/settle/<int:split_id>', methods=['POST'])
@login_required
def settle_split(split_id):
    split = ExpenseSplit.query.get_or_404(split_id)
    # Only the person who is owed can confirm a split was paid.
    if split.expense.paid_by_id != current_user.id:
        flash('Only the person who paid for this expense can mark it settled.', 'error')
        return redirect(url_for('split.index'))

    split.is_settled = True
    split.amount_owed = 0.0
    db.session.commit()
    flash('Marked as settled.', 'success')
    return redirect(url_for('split.index'))

@split_bp.route('/api/group/<int:group_id>/summaries')
@login_required
def group_summaries(group_id):
    group = Group.query.get_or_404(group_id)
    if current_user not in group.members:
        return jsonify({'error': 'Unauthorized'}), 403

    expenses = Expense.query.filter_by(group_id=group_id).order_by(Expense.date.desc()).all()
    nicknames = member_nickname_rows(group.id)
    summaries = []

    for exp in expenses:
        payer = nicknames.get(exp.paid_by_id) or exp.added_by.name
        for split in exp.splits:
            if split.user_id == exp.paid_by_id:
                continue
            is_settled = bool(split.is_settled)
            summaries.append({
                'split_id': split.id,
                'expense': exp.description,
                'expense_amount': round(exp.amount, 2),
                'date': exp.date.strftime('%Y-%m-%d') if exp.date else '',
                'payer_id': exp.paid_by_id,
                'payer': payer,
                'owed_by_id': split.user_id,
                'owed_by': nicknames.get(split.user_id) or split.user.name,
                'amount_owed': round(split.amount_owed, 2),
                'is_settled': is_settled,
                'status': 'settled' if is_settled else 'outstanding',
                'status_label': 'Settled' if is_settled else 'Outstanding'
            })

    return jsonify(summaries)

@split_bp.route('/api/balances/<int:group_id>')
@login_required
def get_balances(group_id):
    group = Group.query.get_or_404(group_id)
    if current_user not in group.members:
        return jsonify({'error': 'Unauthorized'}), 403

    return jsonify(group_balances(group))

@split_bp.route('/api/group/<int:group_id>/payment-options')
@login_required
def get_payment_options(group_id):
    group = Group.query.get_or_404(group_id)
    if current_user not in group.members:
        return jsonify({'error': 'Unauthorized'}), 403

    return jsonify(payment_options(group, current_user))

@split_bp.route('/api/group/<int:group_id>/expenses')
@login_required
def get_group_expenses(group_id):
    group = Group.query.get_or_404(group_id)
    if current_user not in group.members:
        return jsonify({'error': 'Unauthorized'}), 403

    expenses = Expense.query.filter_by(group_id=group_id).order_by(Expense.date.desc()).all()
    nicknames = member_nickname_rows(group.id)
    return jsonify([{
        'id': e.id,
        'description': e.description,
        'amount': e.amount,
        'category': normalize_expense_category(e.category),
        'date': e.date.isoformat() if e.date else None,
        'paid_by': nicknames.get(e.paid_by_id) or e.added_by.name,
        'receipt_url': e.receipt_url,
        'splits': [{
            'id': s.id,
            'user': nicknames.get(s.user_id) or s.user.name,
            'amount': s.amount_owed,
            'is_settled': s.is_settled
        } for s in e.splits]
    } for e in expenses])

@split_bp.route('/api/group/<int:group_id>/expense-search')
@login_required
def search_group_expenses(group_id):
    group = Group.query.get_or_404(group_id)
    if current_user not in group.members:
        return jsonify({'error': 'Unauthorized'}), 403

    query_text = (request.args.get('q') or '').strip()
    category = request.args.get('category', 'all').strip()
    paid_by_id = request.args.get('paid_by_id', type=int)
    min_amount_raw = (request.args.get('min_amount') or '').strip()
    max_amount_raw = (request.args.get('max_amount') or '').strip()

    history_query = ExpenseHistory.query.filter_by(group_id=group.id)

    if query_text:
        history_query = history_query.filter(ExpenseHistory.description.ilike(f'%{query_text}%'))

    if category and category != 'all':
        history_query = history_query.filter(ExpenseHistory.category == category_for_group(group, category))

    if paid_by_id:
        if paid_by_id not in {member.id for member in group.members}:
            return jsonify({'error': 'Choose a valid payer from this group.'}), 400
        history_query = history_query.filter(ExpenseHistory.paid_by_id == paid_by_id)

    try:
        start_date = parse_date_filter(request.args.get('date_from'))
        end_date = parse_date_filter(request.args.get('date_to'), include_next_day=True)
    except ValueError:
        return jsonify({'error': 'Use YYYY-MM-DD for dates.'}), 400

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
        return jsonify({'error': 'Enter valid amount filters.'}), 400

    nicknames = member_nickname_rows(group.id)
    results = history_query.order_by(ExpenseHistory.date.desc()).limit(50).all()

    return jsonify([{
        'id': item.id,
        'description': item.description,
        'amount': round(item.amount, 2),
        'category': normalize_expense_category(item.category),
        'date': item.date.isoformat() if item.date else None,
        'paid_by': nicknames.get(item.paid_by_id) or (User.query.get(item.paid_by_id).name if item.paid_by_id else '')
    } for item in results])

@split_bp.route('/api/group/<int:group_id>/analytics')
@login_required
def get_group_analytics(group_id):
    group = Group.query.get_or_404(group_id)
    if current_user not in group.members:
        return jsonify({'error': 'Unauthorized'}), 403

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
            'total': Decimal('0.00')
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

        category = normalize_expense_category(item.category)
        category_totals[category] = category_totals.get(category, Decimal('0.00')) + amount

        if item.date:
            key = item.date.strftime('%Y-%m')
            if key in monthly_totals:
                monthly_totals[key]['total'] += amount

        payer_name = nicknames.get(item.paid_by_id) or (User.query.get(item.paid_by_id).name if item.paid_by_id else 'Unknown')
        payer_totals[payer_name] = payer_totals.get(payer_name, Decimal('0.00')) + amount

    category_rows = sorted(
        [{'category': key, 'total': float(value)} for key, value in category_totals.items()],
        key=lambda row: row['total'],
        reverse=True
    )
    payer_rows = sorted(
        [{'name': key, 'total': float(value)} for key, value in payer_totals.items()],
        key=lambda row: row['total'],
        reverse=True
    )

    return jsonify({
        'total': float(total),
        'count': len(history_items),
        'top_category': category_rows[0]['category'] if category_rows else '',
        'category_totals': category_rows,
        'payer_totals': payer_rows[:5],
        'monthly_totals': [
            {'month': key, 'label': value['label'], 'total': float(value['total'])}
            for key, value in monthly_totals.items()
        ]
    })

@split_bp.route('/api/group/<int:group_id>/default-split', methods=['POST'])
@login_required
def save_group_default_split(group_id):
    group = Group.query.get_or_404(group_id)
    if current_user not in group.members:
        return jsonify({'error': 'Unauthorized'}), 403
    if group.admin_id != current_user.id:
        return jsonify({'error': 'Only the group admin can change the default split.'}), 403

    split_type = (request.form.get('default_split_type') or 'equal').strip()
    if split_type not in DEFAULT_SPLIT_TYPES:
        return jsonify({'error': 'Default split can be Equal, Selected People, or Percentage.'}), 400

    config = {}

    try:
        if split_type == 'selected':
            member_ids = validate_member_ids(group, request.form.getlist('default_member_ids', type=int))
            if not member_ids:
                raise ValueError('Choose at least one person for the default split.')
            config['member_ids'] = [str(member_id) for member_id in member_ids]

        if split_type == 'percentage':
            percentages = {}
            total_percentage = Decimal('0.00')
            for member in group.members:
                raw_percentage = (request.form.get(f'percent_{member.id}', '') or '').strip()
                if not raw_percentage:
                    raise ValueError(f'Enter a percentage for {member.name}.')

                percentage = money_decimal(raw_percentage)
                if percentage <= 0:
                    raise ValueError(f'Percentage for {member.name} must be greater than 0.')

                percentages[str(member.id)] = f'{percentage:.2f}'
                total_percentage += percentage

            if total_percentage != Decimal('100.00'):
                raise ValueError('Default percentages must total 100%.')

            config['member_ids'] = [str(member.id) for member in group.members]
            config['percentages'] = percentages
    except (InvalidOperation, ValueError) as exc:
        return jsonify({'error': str(exc)}), 400

    group.default_split_type = split_type
    group.default_split_config = json.dumps(config) if config else None
    db.session.commit()

    return jsonify({
        'message': 'Default split saved for this group.',
        'default_split': group_default_split_payload(group)
    })

@split_bp.route('/api/group/<int:group_id>/default-split', methods=['DELETE'])
@login_required
def clear_group_default_split(group_id):
    group = Group.query.get_or_404(group_id)
    if current_user not in group.members:
        return jsonify({'error': 'Unauthorized'}), 403
    if group.admin_id != current_user.id:
        return jsonify({'error': 'Only the group admin can change the default split.'}), 403

    group.default_split_type = 'equal'
    group.default_split_config = None
    db.session.commit()

    return jsonify({
        'message': 'Default split reset to equal split.',
        'default_split': group_default_split_payload(group)
    })

@split_bp.route('/api/group/<int:group_id>/payments')
@login_required
def get_group_payments(group_id):
    group = Group.query.get_or_404(group_id)
    if current_user not in group.members:
        return jsonify({'error': 'Unauthorized'}), 403

    payments = Payment.query.filter_by(group_id=group_id).order_by(Payment.date.desc()).limit(20).all()
    nicknames = member_nickname_rows(group.id)
    return jsonify([payment_row(payment, nicknames, current_user) for payment in payments])

@split_bp.route('/api/group/<int:group_id>/history')
@login_required
def get_group_history(group_id):
    group = Group.query.get_or_404(group_id)
    if current_user not in group.members:
        return jsonify({'error': 'Unauthorized'}), 403

    expenses = ExpenseHistory.query.filter_by(group_id=group_id).all()
    payments = Payment.query.filter_by(group_id=group_id).all()

    history_items = [{
        'type': 'expense',
        'description': h.description,
        'amount': h.amount,
        'date': h.date.isoformat() if h.date else None,
        'paid_by': User.query.get(h.paid_by_id).name if h.paid_by_id else ''
    } for h in expenses]

    history_items.extend({
        'type': 'payment',
        'description': 'Payment',
        'amount': p.amount,
        'date': p.date.isoformat() if p.date else None,
        'payer': p.payer.name if p.payer else '',
        'receiver': p.receiver.name if p.receiver else '',
        'method': p.method,
        'status': p.status
    } for p in payments)

    history_items.sort(key=lambda item: item['date'] or '', reverse=True)
    return jsonify(history_items)

@split_bp.route('/api/group/<int:group_id>/activity.csv')
@login_required
def export_group_activity_csv(group_id):
    group = Group.query.get_or_404(group_id)
    if current_user not in group.members:
        return jsonify({'error': 'Unauthorized'}), 403

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
                normalize_expense_category(item.category),
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

    filename = f'Splitmate_{safe_export_filename(group.name)}_activity.csv'
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )
