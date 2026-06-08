from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Group, Note
from app.group_utils import member_nickname_rows

notes_bp = Blueprint('notes', __name__, url_prefix='/notes')

@notes_bp.route('/')
@login_required
def index():
    groups = current_user.groups.all()
    return render_template('notes.html', groups=groups)

@notes_bp.route('/add', methods=['POST'])
@login_required
def add_note():
    group_id = request.form.get('group_id', type=int)
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()

    group = Group.query.get_or_404(group_id)
    if current_user not in group.members:
        flash('Unauthorized', 'error')
        return redirect(url_for('notes.index'))

    if not title:
        flash('Note title is required', 'error')
        return redirect(url_for('notes.index'))

    note = Note(
        title=title,
        description=description,
        content=title,
        group_id=group_id,
        created_by_id=current_user.id
    )
    db.session.add(note)
    db.session.commit()

    flash('Note added', 'success')
    return redirect(url_for('notes.index'))

@notes_bp.route('/edit/<int:note_id>', methods=['POST'])
@login_required
def edit_note(note_id):
    note = Note.query.get_or_404(note_id)
    group = note.group

    if current_user not in group.members:
        flash('Unauthorized', 'error')
        return redirect(url_for('notes.index'))

    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()

    if not title:
        flash('Note title is required', 'error')
        return redirect(url_for('notes.index'))

    note.title = title
    note.description = description
    note.content = title
    db.session.commit()

    flash('Note updated', 'success')
    return redirect(url_for('notes.index'))

@notes_bp.route('/toggle/<int:note_id>', methods=['POST'])
@login_required
def toggle_note(note_id):
    note = Note.query.get_or_404(note_id)
    group = note.group

    if current_user not in group.members:
        return jsonify({'error': 'Unauthorized'}), 403

    note.is_completed = not note.is_completed
    db.session.commit()

    return jsonify({'success': True, 'is_completed': note.is_completed})

@notes_bp.route('/delete/<int:note_id>', methods=['POST'])
@login_required
def delete_note(note_id):
    note = Note.query.get_or_404(note_id)
    group = note.group

    if current_user not in group.members:
        flash('Unauthorized', 'error')
        return redirect(url_for('notes.index'))

    db.session.delete(note)
    db.session.commit()

    flash('Note deleted', 'success')
    return redirect(url_for('notes.index'))

@notes_bp.route('/api/group/<int:group_id>')
@login_required
def get_group_notes(group_id):
    group = Group.query.get_or_404(group_id)
    if current_user not in group.members:
        return jsonify({'error': 'Unauthorized'}), 403

    notes = Note.query.filter_by(group_id=group_id) \
        .order_by(Note.created_at.desc()).all()
    nicknames = member_nickname_rows(group.id)

    return jsonify([{
        'id': n.id,
        'title': n.title or n.content,
        'description': n.description or '',
        'content': n.content,
        'is_completed': n.is_completed,
        'created_at': n.created_at.isoformat(),
        'created_by': nicknames.get(n.created_by_id) or n.created_by.name
    } for n in notes])
