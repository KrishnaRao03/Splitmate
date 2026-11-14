"""Emails every other group member when someone adds a task or note."""
import threading

from flask import current_app


def _deliver(app, messages):
    from app.email_utils import send_group_item_email
    with app.app_context():
        for message in messages:
            try:
                send_group_item_email(**message)
            except Exception as exc:  # A failed email never undoes the task or note.
                app.logger.exception('Failed to send group item email: %s', exc)


def notify_group_item_added(kind, item, author):
    """kind is 'task' or 'note'. Everyone in the group except the author gets an email.

    Everything the email needs is read here, then the emails go out on a background thread so
    adding a task never waits on the mail server (tests send them straight away).
    """
    group = item.group
    details = []
    if kind == 'task':
        if item.due_date:
            details.append(('Due', item.due_date.strftime('%b %d, %Y %H:%M UTC')))
        assignee = getattr(item, 'assigned_to', None)
        details.append(('Assigned to', assignee.name if assignee else 'Anyone'))
    messages = [{
        'recipient_email': member.email,
        'recipient_name': member.name,
        'kind': kind,
        'group_name': group.name,
        'author_name': author.name,
        'title': item.title,
        'description': (item.description or '').strip(),
        'details': details,
    } for member in group.members
        if member.id != author.id and member.email and not getattr(member, 'is_suspended', False)]
    if not messages:
        return
    app = current_app._get_current_object()
    if app.config.get('TESTING'):
        _deliver(app, messages)
    else:
        threading.Thread(target=_deliver, args=(app, messages), daemon=True).start()
