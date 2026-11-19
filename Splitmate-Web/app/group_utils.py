from app import db
from datetime import datetime

from app.models import GroupInvite, group_members, lock_row


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
            'sent_to': invite.sent_to,
            'by_phone': invite.is_phone_invite,
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


def invite_accept_problem(user, invite):
    """Why this user can't accept this invite, as (message, status), or None when they can.

    Email invites need the invited email. Mobile invites need the invited number on the account,
    or an account with no number yet (the number is added to it when they accept).
    """
    from app.models import User
    from app.email_validation import normalize_email

    if not invite or invite.revoked_at:
        return 'That invite link is invalid or was revoked.', 404
    if invite.accepted_at:
        return 'That invite was already accepted.', 409
    if invite.expires_at <= datetime.utcnow():
        return 'That invite link has expired. Ask the group admin for a new invite.', 410
    if not invite.is_phone_invite:
        # Only a proven email counts: an unverified one could be anyone's address typed into a profile.
        if normalize_email(user.email) != invite.email or not user.is_email_verified:
            return f'This invite was sent to {invite.email}. Sign in with that email to accept it.', 403
        return None
    if user.phone_hash == invite.phone_hash:
        return None
    if user.phone_hash:
        return (f'This invite was sent to the mobile number {invite.sent_to}. '
                'Sign in with the account that uses that number to accept it.'), 403
    if User.query.filter(User.phone_hash == invite.phone_hash, User.id != user.id).first():
        return (f'Another Splitmate account uses {invite.sent_to}. '
                'Sign in with that account to accept this invite.'), 403
    return None


def join_group_from_invite(user, invite):
    """Adds the user to the invite's group and marks it accepted. Check invite_accept_problem first; caller commits.

    Returns False if another request accepted or revoked the invite in the meantime.
    """
    # Locked until commit, then checked again, so two accepts at once can't both get in.
    lock_row(invite)
    if invite.accepted_at or invite.revoked_at:
        return False
    if invite.is_phone_invite and not user.phone:
        user.phone = invite.phone  # They got the text, so this is their number.
    if user not in invite.group.members:
        invite.group.members.append(user)
        db.session.flush()
        set_member_nickname(invite.group.id, user)
    invite.accepted_at = datetime.utcnow()
    invite.accepted_by_id = user.id
    return True
