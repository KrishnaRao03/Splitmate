from app import db
from datetime import datetime

from app.models import GroupInvite, group_members


def clean_nickname(value, fallback):
    nickname = (value or '').strip()
    return nickname or fallback


def member_nickname_rows(group_id):
    rows = db.session.execute(
        db.select(
            group_members.c.user_id,
            group_members.c.nickname
        ).where(group_members.c.group_id == group_id)
    ).all()
    return {user_id: nickname for user_id, nickname in rows}


def nickname_for(group, user):
    nicknames = member_nickname_rows(group.id)
    return clean_nickname(nicknames.get(user.id), user.name)


def group_member_payload(group):
    nicknames = member_nickname_rows(group.id)
    return [
        {
            'id': member.id,
            'name': clean_nickname(nicknames.get(member.id), member.name),
            'nickname': clean_nickname(nicknames.get(member.id), member.name),
            'full_name': member.name,
            'email': member.email
        }
        for member in group.members
    ]


def group_pending_invite_payload(group):
    now = datetime.utcnow()
    invites = GroupInvite.query.filter(
        GroupInvite.group_id == group.id,
        GroupInvite.accepted_at.is_(None),
        GroupInvite.revoked_at.is_(None),
        GroupInvite.expires_at > now
    ).order_by(GroupInvite.created_at.desc()).all()

    return [
        {
            'id': invite.id,
            'email': invite.email,
            'created_at': invite.created_at.isoformat() if invite.created_at else None,
            'expires_at': invite.expires_at.isoformat() if invite.expires_at else None,
            'invited_by': invite.invited_by.name if invite.invited_by else ''
        }
        for invite in invites
    ]


def set_member_nickname(group_id, user, nickname=None):
    display_name = clean_nickname(nickname, user.name)
    db.session.execute(
        group_members.update()
        .where(group_members.c.group_id == group_id)
        .where(group_members.c.user_id == user.id)
        .values(nickname=display_name)
    )
    return display_name
