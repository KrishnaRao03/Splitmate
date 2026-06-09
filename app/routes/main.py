from flask import Blueprint, current_app, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy import func
from app import db
from app.email_validation import normalize_email
from app.models import User, Group, Expense, ExpenseSplit, ExpenseHistory
from app.routes.auth import send_user_otp, set_pending_verification
from app.group_utils import group_member_payload, set_member_nickname

main_bp = Blueprint('main', __name__)

def safe_redirect_target(default_endpoint='main.home'):
    target = request.form.get('next', '').strip()
    if target.startswith('/') and not target.startswith('//'):
        return target
    return url_for(default_endpoint)

@main_bp.route('/')
@login_required
def home():
    groups = current_user.groups.all()

    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)

    monthly_spending = {}
    recent_expenses = []

    # Build monthly totals (active + history) and recent items
    for group in groups:
        active_sum = db.session.query(func.coalesce(func.sum(Expense.amount), 0.0)).filter(
            Expense.group_id == group.id,
            Expense.date >= month_start
        ).scalar()

        history_sum = db.session.query(func.coalesce(func.sum(ExpenseHistory.amount), 0.0)).filter(
            ExpenseHistory.group_id == group.id,
            ExpenseHistory.date >= month_start
        ).scalar()

        monthly_spending[group.name] = float(active_sum) + float(history_sum)

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

    # Build last 6 months series for charts (active + history)
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
    chart_data = []

    for group in groups:
        points = []
        for (yy, mm) in months:
            start = datetime(yy, mm, 1)
            end = datetime(yy + (1 if mm == 12 else 0), (1 if mm == 12 else mm + 1), 1)

            a_sum = db.session.query(func.coalesce(func.sum(Expense.amount), 0.0)).filter(
                Expense.group_id == group.id,
                Expense.date >= start,
                Expense.date < end
            ).scalar()

            h_sum = db.session.query(func.coalesce(func.sum(ExpenseHistory.amount), 0.0)).filter(
                ExpenseHistory.group_id == group.id,
                ExpenseHistory.date >= start,
                ExpenseHistory.date < end
            ).scalar()

            total = float(a_sum) + float(h_sum)
            points.append({'label': f'{yy}-{str(mm).zfill(2)}', 'total': total})

        chart_data.append({'group': group.name, 'data': points})

    # JSON-safe group data for Manage modal (prevents "User is not JSON serializable")
    groups_json = [
        {
            'id': g.id,
            'name': g.name,
            'admin_id': g.admin_id,
            'members': group_member_payload(g)
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
        chart_data=chart_data
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

            if not name:
                errors.append('Full name is required.')
            if not email:
                errors.append('Valid email is required.')

            existing_user = User.query.filter(
                User.email == email,
                User.id != current_user.id
            ).first() if email else None
            if existing_user:
                errors.append('That email is already used by another account.')

            if errors:
                for error in errors:
                    flash(error, 'error')
                return redirect(url_for('main.profile'))

            email_changed = email != current_user.email
            current_user.name = name

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

        if form_type == 'password':
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')
            errors = []

            if not current_user.check_password(current_password):
                errors.append('Current password is incorrect.')
            if len(new_password) < 6:
                errors.append('New password must be at least 6 characters.')
            if new_password != confirm_password:
                errors.append('New password and confirmation do not match.')

            if errors:
                for error in errors:
                    flash(error, 'error')
                return redirect(url_for('main.profile'))

            current_user.set_password(new_password)
            db.session.commit()
            flash('Password updated.', 'success')
            return redirect(url_for('main.profile'))

        flash('Choose a valid profile action.', 'error')
        return redirect(url_for('main.profile'))

    return render_template('profile.html')

@main_bp.route('/group/create', methods=['POST'])
@login_required
def create_group():
    name = request.form.get('name', '').strip()
    redirect_target = safe_redirect_target()
    if not name:
        flash('Group name is required', 'error')
        return redirect(redirect_target)

    group = Group(name=name, admin_id=current_user.id)
    group.members.append(current_user)
    db.session.add(group)
    db.session.flush()
    set_member_nickname(group.id, current_user)
    db.session.commit()

    flash(f'Group "{name}" created!', 'success')
    return redirect(redirect_target)

@main_bp.route('/group/<int:group_id>/members/add', methods=['POST'])
@login_required
def add_group_member(group_id):
    group = Group.query.get_or_404(group_id)
    if group.admin_id != current_user.id:
        flash('Only the group admin can add members.', 'error')
        return redirect(url_for('main.home'))

    email = normalize_email(request.form.get('email'))
    if not email:
        flash('Enter a valid member email.', 'error')
        return redirect(url_for('main.home'))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash('No Splitmate account found with that email.', 'error')
        return redirect(url_for('main.home'))

    if user in group.members:
        flash(f'{user.name} is already in this group.', 'info')
        return redirect(url_for('main.home'))

    group.members.append(user)
    db.session.flush()
    set_member_nickname(group.id, user)
    db.session.commit()
    flash(f'{user.name} added to "{group.name}".', 'success')
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

    group.members.remove(user)
    db.session.commit()
    flash(f'{user.name} removed from "{group.name}".', 'success')
    return redirect(url_for('main.home'))
