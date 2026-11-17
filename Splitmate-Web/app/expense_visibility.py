"""An expense is shown only to the person who paid it and the people it is split with.

Everyone else in the group, including the admin, doesn't see it in lists, history, search, charts or exports.
"""
from sqlalchemy import or_, select

from app import db
from app.models import Expense, ExpenseHistory, ExpenseSplit


def participant_ids_text(paid_by_id, user_ids):
    ids = sorted({int(paid_by_id)} | {int(user_id) for user_id in user_ids if user_id})
    return ',' + ','.join(str(user_id) for user_id in ids) + ','


def history_for_expense(expense, split_user_ids):
    """The history copy of a new expense, remembering who it was shared with."""
    return ExpenseHistory(
        description=expense.description,
        amount=expense.amount,
        category=expense.category,
        date=expense.date,
        paid_by_id=expense.paid_by_id,
        group_id=expense.group_id,
        expense_id=expense.id,
        participant_ids=participant_ids_text(expense.paid_by_id, split_user_ids),
    )


def _expense_ids_shared_with(user_id):
    return select(ExpenseSplit.expense_id).where(ExpenseSplit.user_id == user_id)


def visible_expenses(query, user):
    """Limit an Expense query to expenses this user paid or shares in."""
    return query.filter(or_(Expense.paid_by_id == user.id, Expense.id.in_(_expense_ids_shared_with(user.id))))


def visible_history(query, user):
    """Limit an ExpenseHistory query the same way. An expense edited later to include this user also counts."""
    return query.filter(or_(
        ExpenseHistory.paid_by_id == user.id,
        ExpenseHistory.participant_ids.like(f'%,{user.id},%'),
        ExpenseHistory.expense_id.in_(_expense_ids_shared_with(user.id)),
    ))


def can_see_expense(expense, user):
    return expense.paid_by_id == user.id or any(split.user_id == user.id for split in expense.splits)


def fill_history_participants():
    """One-off for rows saved before this existed: link each history row to its live expense when one matches,
    and record who it was shared with. Rows whose expense was deleted are kept for the payer only."""
    rows = ExpenseHistory.query.filter(ExpenseHistory.participant_ids.is_(None)).all()
    if not rows:
        return
    claimed = {row.expense_id for row in ExpenseHistory.query.filter(ExpenseHistory.expense_id.isnot(None)).all()}
    for row in rows:
        match = next((
            expense for expense in Expense.query.filter_by(
                group_id=row.group_id, paid_by_id=row.paid_by_id, description=row.description,
            ).all()
            if expense.id not in claimed and abs((expense.amount or 0) - (row.amount or 0)) < 0.005
        ), None)
        if match:
            claimed.add(match.id)
            row.expense_id = match.id
            row.participant_ids = participant_ids_text(match.paid_by_id, [split.user_id for split in match.splits])
        else:
            row.participant_ids = participant_ids_text(row.paid_by_id, []) if row.paid_by_id else ','
    db.session.commit()
