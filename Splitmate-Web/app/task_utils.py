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


def find_next_recurring_task(task):
    """The open next repeat of a recurring task, if one exists."""
    recurrence = normalize_task_recurrence(task.recurrence)
    next_due_date = next_recurring_datetime(task.due_date, recurrence)
    if recurrence == 'none' or not next_due_date:
        return None
    return Task.query.filter_by(
        group_id=task.group_id,
        title=task.title,
        due_date=next_due_date,
        assigned_to_id=task.assigned_to_id,
        recurrence=recurrence,
        is_completed=False,
    ).first()


def create_next_recurring_task(task):
    recurrence = normalize_task_recurrence(task.recurrence)
    next_due_date = next_recurring_datetime(task.due_date, recurrence)
    if recurrence == 'none' or not next_due_date:
        return None

    next_reminder_time = next_recurring_datetime(task.reminder_time, recurrence) if task.reminder_time else None
    existing = find_next_recurring_task(task)
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


def wanted_completion(data, current):
    """The done state the client asked for, or the opposite of the current one if it didn't say.
    Sending the wanted state means a double tap or a retry lands where the person meant."""
    value = (data or {}).get('is_completed')
    return (not current) if value is None else bool(value)


def toggle_task_completion(task, db_session, completed=None):
    """Marks the task done or not done (`completed`, or the opposite of now). Returns the next
    repeat of a recurring task, made when it's marked done."""
    completed = (not task.is_completed) if completed is None else completed
    if completed == bool(task.is_completed):
        return None
    if task.is_completed:
        task.is_completed = False
        # Undoing "done" also takes back the next repeat it made, unless that one was already ticked off.
        spawned = find_next_recurring_task(task)
        if spawned is not None and spawned.id:
            db_session.delete(spawned)
        return None

    task.is_completed = True
    next_task = create_next_recurring_task(task)
    if next_task and not next_task.id:
        db_session.add(next_task)
    return next_task
