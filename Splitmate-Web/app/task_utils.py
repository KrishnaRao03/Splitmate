from calendar import monthrange
from datetime import datetime, timedelta

from app.models import Task


VALID_TASK_PRIORITIES = {'low', 'medium', 'high'}
VALID_TASK_RECURRENCES = {'none', 'daily', 'weekly', 'monthly'}


def normalize_task_priority(value):
    priority = str(value or 'medium').strip().lower()
    return priority if priority in VALID_TASK_PRIORITIES else 'medium'


def normalize_task_recurrence(value):
    recurrence = str(value or 'none').strip().lower()
    return recurrence if recurrence in VALID_TASK_RECURRENCES else 'none'


def task_is_overdue(task, now=None):
    now = now or datetime.now()
    return bool(task.due_date and not task.is_completed and task.due_date < now)


def add_one_month(value):
    year = value.year + (1 if value.month == 12 else 0)
    month = 1 if value.month == 12 else value.month + 1
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def next_recurring_datetime(value, recurrence):
    if not value:
        return None

    recurrence = normalize_task_recurrence(recurrence)
    if recurrence == 'daily':
        return value + timedelta(days=1)
    if recurrence == 'weekly':
        return value + timedelta(days=7)
    if recurrence == 'monthly':
        return add_one_month(value)
    return None


def create_next_recurring_task(task):
    recurrence = normalize_task_recurrence(task.recurrence)
    next_due_date = next_recurring_datetime(task.due_date, recurrence)
    if recurrence == 'none' or not next_due_date:
        return None

    next_reminder_time = next_recurring_datetime(task.reminder_time, recurrence) if task.reminder_time else None
    existing = Task.query.filter_by(
        group_id=task.group_id,
        title=task.title,
        due_date=next_due_date,
        assigned_to_id=task.assigned_to_id,
        recurrence=recurrence,
        is_completed=False,
    ).first()
    if existing:
        return existing

    return Task(
        title=task.title,
        description=task.description,
        due_date=next_due_date,
        reminder_time=next_reminder_time,
        priority=normalize_task_priority(task.priority),
        recurrence=recurrence,
        group_id=task.group_id,
        assigned_to_id=task.assigned_to_id,
        created_by_id=task.created_by_id,
    )


def toggle_task_completion(task, db_session):
    if task.is_completed:
        task.is_completed = False
        return None

    task.is_completed = True
    next_task = create_next_recurring_task(task)
    if next_task and not next_task.id:
        db_session.add(next_task)
    return next_task
