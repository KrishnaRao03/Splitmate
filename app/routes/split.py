import os
from uuid import uuid4

from flask import Blueprint, current_app, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from werkzeug.utils import secure_filename

from app import db
from app.models import Group, Expense, ExpenseSplit, ExpenseHistory, Payment, User
from app.group_utils import group_member_payload, member_nickname_rows

try:
    import stripe
except ImportError:
    stripe = None

split_bp = Blueprint('split', __name__, url_prefix='/split')
CENT = Decimal('0.01')
ALLOWED_RECEIPT_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf'}


def money_decimal(value):
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)

def stripe_enabled():
    return stripe is not None and bool(current_app.config.get('STRIPE_SECRET_KEY'))

def configure_stripe():
    if not stripe_enabled():
        return False
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    return True

def amount_to_minor_units(amount):
    return int((money_decimal(amount) * Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

def payment_currency_code():
    return (current_app.config.get('STRIPE_CURRENCY') or 'cad').lower()

def format_payment_amount(amount):
    return f'{payment_currency_code().upper()} {money_decimal(amount):.2f}'

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
    upload_dir = os.path.join(current_app.static_folder, 'uploads', 'receipts')
    os.makedirs(upload_dir, exist_ok=True)

    stored_filename = f'{uuid4().hex}{extension.lower()}'
    receipt_file.save(os.path.join(upload_dir, stored_filename))
    return url_for('static', filename=f'uploads/receipts/{stored_filename}')

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

def apply_payment_to_splits(group, payer, receiver, amount, method='manual',
                            stripe_checkout_session_id=None, status='recorded'):
    payment_amount = money_decimal(amount)

    if stripe_checkout_session_id:
        existing = Payment.query.filter_by(stripe_checkout_session_id=stripe_checkout_session_id).first()
        if existing:
            return existing, False

    payment = create_payment_record(
        group,
        payer,
        receiver,
        payment_amount,
        method=method,
        stripe_checkout_session_id=stripe_checkout_session_id,
        status=status
    )
    settle_outstanding_splits(group, payer, receiver, payment_amount)
    return payment, True

@split_bp.route('/')
@login_required
def index():
    groups = current_user.groups.all()
    groups_json = [
        {
            'id': g.id,
            'name': g.name,
            'members': group_member_payload(g)
        }
        for g in groups
    ]
    return render_template(
        'split.html',
        groups=groups,
        groups_json=groups_json,
        stripe_enabled=stripe_enabled()
    )

@split_bp.route('/add', methods=['POST'])
@login_required
def add_expense():
    group_id = request.form.get('group_id', type=int)
    description = request.form.get('description', '').strip()
    amount = request.form.get('amount', type=float)
    receipt_url = request.form.get('receipt_url', '').strip() or None
    receipt_file = request.files.get('receipt')
    split_type = request.form.get('split_type', 'equal')

    group = Group.query.get_or_404(group_id)
    if current_user not in group.members:
        flash('You are not a member of this group.', 'error')
        return redirect(url_for('split.index'))

    if not description or not amount or amount <= 0:
        flash('Valid description and amount are required.', 'error')
        return redirect(url_for('split.index'))

    all_members = list(group.members)
    selected_member_ids = request.form.getlist('split_user_ids', type=int)
    selected_member_id_set = set(selected_member_ids)
    selected_members = [member for member in all_members if member.id in selected_member_id_set]

    if not selected_members:
        flash('Choose at least one person in Split with.', 'error')
        return redirect(url_for('split.index'))

    if len(selected_members) != len(selected_member_id_set):
        flash('Choose valid members from this group.', 'error')
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
                    raise ValueError(f'Enter an amount greater than 0 for {member.name}, or remove them from Split with.')

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
                    raise ValueError(f'Enter a percentage greater than 0 for {member.name}, or remove them from Split with.')

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
        receipt_url=receipt_url,
        group_id=group_id,
        paid_by_id=current_user.id
    )
    db.session.add(expense)
    db.session.flush()  # get expense.id

    # Immediate immutable history copy
    history_copy = ExpenseHistory(
        description=expense.description,
        amount=expense.amount,
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
    receiver = User.query.get(receiver_id)

    if current_user not in group.members:
        flash('Unauthorized.', 'error')
        return redirect(url_for('split.index'))

    if not receiver or receiver not in group.members:
        flash('Choose a valid receiver from this group.', 'error')
        return redirect(url_for('split.index'))

    if receiver.id == current_user.id:
        flash('You cannot pay yourself.', 'error')
        return redirect(url_for('split.index'))

    if not amount or amount <= 0:
        flash('Enter a valid payment amount.', 'error')
        return redirect(url_for('split.index'))

    payment_amount = money_decimal(amount)
    _, total_owed = outstanding_splits_for(group, current_user, receiver)
    if total_owed <= 0:
        flash(f'You do not currently owe {receiver.name} anything in this group.', 'info')
        return redirect(url_for('split.index'))

    if payment_amount > total_owed:
        flash(f'You only owe {receiver.name} {format_payment_amount(total_owed)}.', 'error')
        return redirect(url_for('split.index'))

    apply_payment_to_splits(group, current_user, receiver, payment_amount)

    db.session.commit()
    flash('Payment recorded.', 'success')
    return redirect(url_for('split.index'))

@split_bp.route('/stripe/pay', methods=['POST'])
@login_required
def create_stripe_payment():
    group_id = request.form.get('group_id', type=int)
    receiver_id = request.form.get('receiver_id', type=int)
    amount = request.form.get('amount', type=float)

    group = Group.query.get_or_404(group_id)
    receiver = User.query.get(receiver_id)

    if current_user not in group.members:
        flash('Unauthorized.', 'error')
        return redirect(url_for('split.index'))

    if not receiver or receiver not in group.members:
        flash('Choose a valid receiver from this group.', 'error')
        return redirect(url_for('split.index'))

    if receiver.id == current_user.id:
        flash('You cannot pay yourself.', 'error')
        return redirect(url_for('split.index'))

    if not amount or amount <= 0:
        flash('Enter a valid payment amount.', 'error')
        return redirect(url_for('split.index'))

    if not stripe_enabled():
        flash('Stripe is not configured yet. Add STRIPE_SECRET_KEY to .env first.', 'error')
        return redirect(url_for('split.index'))

    payment_amount = money_decimal(amount)
    _, total_owed = outstanding_splits_for(group, current_user, receiver)
    if total_owed <= 0:
        flash(f'You do not currently owe {receiver.name} anything in this group.', 'info')
        return redirect(url_for('split.index'))

    if payment_amount > total_owed:
        flash(f'You only owe {receiver.name} {format_payment_amount(total_owed)}.', 'error')
        return redirect(url_for('split.index'))

    metadata = {
        'group_id': str(group.id),
        'payer_id': str(current_user.id),
        'receiver_id': str(receiver.id),
        'amount': str(payment_amount)
    }

    try:
        configure_stripe()
        checkout_session = stripe.checkout.Session.create(
            mode='payment',
            customer_email=current_user.email,
            success_url=url_for('split.stripe_payment_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('split.index', _external=True),
            metadata=metadata,
            line_items=[{
                'price_data': {
                    'currency': payment_currency_code(),
                    'product_data': {
                        'name': f'Splitmate payment to {receiver.name}',
                        'description': f'{group.name} settlement'
                    },
                    'unit_amount': amount_to_minor_units(payment_amount)
                },
                'quantity': 1
            }],
            payment_intent_data={
                'metadata': metadata
            }
        )
        create_payment_record(
            group,
            current_user,
            receiver,
            payment_amount,
            method='stripe',
            stripe_checkout_session_id=checkout_session.id,
            status='pending'
        )
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('Failed to create Stripe Checkout session: %s', exc)
        flash('Could not start Stripe payment. Check your Stripe configuration.', 'error')
        return redirect(url_for('split.index'))

    return redirect(checkout_session.url, code=303)

@split_bp.route('/stripe/payment-success')
@login_required
def stripe_payment_success():
    session_id = request.args.get('session_id', '').strip()
    if not session_id:
        flash('Stripe did not return a checkout session.', 'error')
        return redirect(url_for('split.index'))

    if not stripe_enabled():
        flash('Stripe is not configured, so the payment could not be verified.', 'error')
        return redirect(url_for('split.index'))

    payment = Payment.query.filter_by(stripe_checkout_session_id=session_id).first()
    if payment and payment.status == 'paid':
        flash('Payment was already recorded.', 'info')
        return redirect(url_for('split.index'))

    try:
        configure_stripe()
        checkout_session = stripe.checkout.Session.retrieve(session_id)
    except Exception as exc:
        current_app.logger.exception('Failed to retrieve Stripe Checkout session: %s', exc)
        flash('Could not verify the Stripe payment.', 'error')
        return redirect(url_for('split.index'))

    if checkout_session.get('payment_status') != 'paid':
        flash('Stripe payment was not completed.', 'error')
        return redirect(url_for('split.index'))

    metadata = checkout_session.get('metadata') or {}
    try:
        payer_id = int(metadata.get('payer_id'))
        group_id = int(metadata.get('group_id'))
        receiver_id = int(metadata.get('receiver_id'))
        amount = money_decimal(metadata.get('amount'))
    except (TypeError, ValueError):
        flash('Stripe payment metadata was invalid.', 'error')
        return redirect(url_for('split.index'))

    if payer_id != current_user.id:
        flash('This Stripe payment belongs to another user session.', 'error')
        return redirect(url_for('split.index'))

    group = Group.query.get_or_404(group_id)
    receiver = User.query.get_or_404(receiver_id)

    if current_user not in group.members or receiver not in group.members:
        flash('Stripe payment group membership is invalid.', 'error')
        return redirect(url_for('split.index'))

    if payment:
        if payment.payer_id != current_user.id or payment.receiver_id != receiver.id or payment.group_id != group.id:
            flash('Stripe payment record did not match this settlement.', 'error')
            return redirect(url_for('split.index'))

        payment.status = 'paid'
        payment.amount = float(amount)
    else:
        payment = create_payment_record(
            group,
            current_user,
            receiver,
            amount,
            method='stripe',
            stripe_checkout_session_id=session_id,
            status='paid'
        )

    settle_outstanding_splits(group, current_user, receiver, amount)
    db.session.commit()
    flash('Online payment completed and recorded.', 'success')
    return redirect(url_for('split.index'))

@split_bp.route('/settle/<int:split_id>', methods=['POST'])
@login_required
def settle_split(split_id):
    split = ExpenseSplit.query.get_or_404(split_id)
    if split.user_id != current_user.id and split.expense.paid_by_id != current_user.id:
        flash('Unauthorized.', 'error')
        return redirect(url_for('split.index'))

    split.is_settled = True
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

    balances = {}
    nicknames = member_nickname_rows(group.id)
    for member in group.members:
        balances[member.id] = {'id': member.id, 'name': nicknames.get(member.id) or member.name, 'paid': 0, 'owes': 0, 'net': 0}

    for exp in group.expenses:
        for split in exp.splits:
            if split.user_id == exp.paid_by_id or split.is_settled:
                continue
            balances[exp.paid_by_id]['paid'] += split.amount_owed
            balances[split.user_id]['owes'] += split.amount_owed

    for uid in balances:
        b = balances[uid]
        b['net'] = round(b['paid'] - b['owes'], 2)

    return jsonify(list(balances.values()))

@split_bp.route('/api/group/<int:group_id>/payment-options')
@login_required
def get_payment_options(group_id):
    group = Group.query.get_or_404(group_id)
    if current_user not in group.members:
        return jsonify({'error': 'Unauthorized'}), 403

    owed_by_receiver = {}
    nicknames = member_nickname_rows(group.id)
    outstanding_splits = ExpenseSplit.query.join(Expense).filter(
        Expense.group_id == group.id,
        ExpenseSplit.user_id == current_user.id,
        Expense.paid_by_id != current_user.id,
        ExpenseSplit.is_settled == False
    ).all()

    for split in outstanding_splits:
        receiver_id = split.expense.paid_by_id
        owed_by_receiver[receiver_id] = owed_by_receiver.get(receiver_id, Decimal('0.00')) + money_decimal(split.amount_owed)

    options = []
    for receiver_id, owed_amount in owed_by_receiver.items():
        receiver = User.query.get(receiver_id)
        if receiver:
            options.append({
                'id': receiver.id,
                'name': nicknames.get(receiver.id) or receiver.name,
                'amount_owed': float(owed_amount),
                'can_receive_online': stripe_enabled()
            })

    options.sort(key=lambda item: item['name'].lower())
    return jsonify(options)

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

@split_bp.route('/api/group/<int:group_id>/payments')
@login_required
def get_group_payments(group_id):
    group = Group.query.get_or_404(group_id)
    if current_user not in group.members:
        return jsonify({'error': 'Unauthorized'}), 403

    payments = Payment.query.filter_by(group_id=group_id).order_by(Payment.date.desc()).limit(20).all()
    nicknames = member_nickname_rows(group.id)
    return jsonify([{
        'id': payment.id,
        'amount': round(payment.amount, 2),
        'date': payment.date.isoformat() if payment.date else None,
        'payer': nicknames.get(payment.payer_id) or payment.payer.name,
        'receiver': nicknames.get(payment.receiver_id) or payment.receiver.name,
        'method': payment.method,
        'status': payment.status,
        'status_label': {
            'pending': 'Pending',
            'paid': 'Paid',
            'recorded': 'Recorded'
        }.get(payment.status, payment.status.title())
    } for payment in payments])

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
