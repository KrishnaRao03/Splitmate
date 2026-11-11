from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from app.models import Group, Task, User
from app.group_utils import group_member_payload, group_pending_invite_payload, member_nickname_rows
from app.task_utils import (
    normalize_task_priority,
    normalize_task_recurrence,
    task_is_overdue,
    toggle_task_completion,
)

tasks_bp = Blueprint('tasks', __name__, url_prefix='/tasks')


@tasks_bp.route('/')
@login_required
def index():
    # Get all groups with simple member data for JSON
    groups = current_user.groups.all()
    groups_json = [{
        'id': g.id,
        'name': g.name,
        'admin_id': g.admin_id,
        'members': group_member_payload(g),
        'pending_invites': group_pending_invite_payload(g) if g.admin_id == current_user.id else []
    } for g in groups]

    return render_template('tasks.html', groups=groups, groups_json=groups_json)


@tasks_bp.route('/add', methods=['POST'])
@login_required
def add_task():
    group_id = request.form.get('group_id', type=int)
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    due_date_str = request.form.get('due_date')
    reminder_str = request.form.get('reminder_time')
    assigned_to_id = request.form.get('assigned_to_id', type=int)
    priority = normalize_task_priority(request.form.get('priority'))
    recurrence = normalize_task_recurrence(request.form.get('recurrence'))

    group = Group.query.get_or_404(group_id)
    if current_user not in group.members:
        flash('Unauthorized', 'error')
        return redirect(url_for('tasks.index'))

    if not title or not due_date_str:
        flash('Title and due date are required', 'error')
        return redirect(url_for('tasks.index'))

    try:
        due_date = datetime.fromisoformat(due_date_str)
        reminder_time = datetime.fromisoformat(reminder_str) if reminder_str else None
    except ValueError:
        flash('Invalid date format', 'error')
        return redirect(url_for('tasks.index'))

    assigned_to = User.query.get(assigned_to_id) if assigned_to_id else None
    if assigned_to and assigned_to not in group.members:
        flash('Assignee must be a group member', 'error')
        return redirect(url_for('tasks.index'))

    task = Task(
        title=title,
        description=description,
        due_date=due_date,
        reminder_time=reminder_time,
        priority=priority,
        recurrence=recurrence,
        group_id=group_id,
        assigned_to_id=assigned_to.id if assigned_to else None,
        created_by_id=current_user.id
    )
    db.session.add(task)
    db.session.commit()

    flash('Task added to calendar', 'success')
    return redirect(url_for('tasks.index'))


@tasks_bp.route('/complete/<int:task_id>', methods=['POST'])
@login_required
def complete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if current_user not in task.group.members:
        return jsonify({'error': 'Unauthorized'}), 403

    next_task = toggle_task_completion(task, db.session)
    db.session.commit()

    return jsonify({
        'success': True,
        'is_completed': task.is_completed,
        'next_task_id': next_task.id if next_task else None
    })


@tasks_bp.route('/delete/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if current_user not in task.group.members:
        flash('Unauthorized', 'error')
        return redirect(url_for('tasks.index'))

    if current_user.id not in (task.created_by_id, task.group.admin_id):
        flash('Only the person who created this task or the group admin can delete it.', 'error')
        return redirect(url_for('tasks.index'))

    db.session.delete(task)
    db.session.commit()
    flash('Task deleted', 'success')
    return redirect(url_for('tasks.index'))


@tasks_bp.route('/api/group/<int:group_id>')
@login_required
def get_group_tasks(group_id):
    group = Group.query.get_or_404(group_id)
    if current_user not in group.members:
        return jsonify({'error': 'Unauthorized'}), 403

    tasks = Task.query.filter_by(group_id=group_id).order_by(Task.due_date.asc()).all()
    nicknames = member_nickname_rows(group.id)
    return jsonify([{
        'id': t.id,
        'title': t.title,
        'description': t.description,
        'due_date': t.due_date.isoformat(),
        'reminder_time': t.reminder_time.isoformat() if t.reminder_time else None,
        'priority': t.priority or 'medium',
        'recurrence': t.recurrence or 'none',
        'is_completed': t.is_completed,
        'is_overdue': task_is_overdue(t),
        'assigned_to': (nicknames.get(t.assigned_to_id) or t.assigned_to.name) if t.assigned_to else None,
        'created_by': nicknames.get(t.created_by_id) or t.created_by.name
    } for t in tasks])


@tasks_bp.route('/api/upcoming')
@login_required
def get_upcoming_reminders():
    now = datetime.utcnow()

    upcoming = Task.query.join(Group).filter(
        Group.members.contains(current_user),
        Task.reminder_time != None,
        Task.reminder_time >= now,
        Task.is_completed == False
    ).order_by(Task.reminder_time).limit(10).all()

    return jsonify([{
        'id': t.id,
        'title': t.title,
        'due_date': t.due_date.isoformat(),
        'reminder_time': t.reminder_time.isoformat(),
        'priority': t.priority or 'medium',
        'recurrence': t.recurrence or 'none',
        'group_name': t.group.name
    } for t in upcoming])
