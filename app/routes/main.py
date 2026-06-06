from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy import func
from app import db
from app.models import User, Group, Expense, ExpenseSplit, ExpenseHistory

main_bp = Blueprint('main', __name__)

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
            'members': [{'id': m.id, 'name': m.name, 'email': m.email} for m in g.members]
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

@main_bp.route('/group/create', methods=['POST'])
@login_required
def create_group():
    name = request.form.get('name', '').strip()
    if not name:
        flash('Group name is required', 'error')
        return redirect(url_for('main.home'))

    group = Group(name=name, admin_id=current_user.id)
    group.members.append(current_user)
    db.session.add(group)
    db.session.commit()

    flash(f'Group "{name}" created!', 'success')
    return redirect(url_for('main.home'))
