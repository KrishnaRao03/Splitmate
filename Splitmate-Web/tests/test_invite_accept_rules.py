"""Who may accept a group invite (invite_accept_problem), checked directly for the cases the API tests skip."""
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from app import create_app, db
from app.group_utils import invite_accept_problem, join_group_from_invite
from app.models import Group, GroupInvite, User
from config import Config


class InviteRulesConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    MAIL_PASSWORD = None
    BREVO_API_KEY = None
    RATELIMIT_ENABLED = False
    WTF_CSRF_ENABLED = False


class InviteAcceptRulesTests(unittest.TestCase):
    def setUp(self):
        self.scheduler = patch('app.scheduler.start_inactivity_scheduler', return_value=None)
        self.scheduler.start()
        self.app = create_app(InviteRulesConfig)
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.admin = User(email='admin@example.com', name='Admin', is_email_verified=True)
        self.admin.set_password('Strong-pass-1')
        db.session.add(self.admin)
        db.session.flush()
        self.group = Group(name='Flat', admin_id=self.admin.id)
        self.group.members.append(self.admin)
        db.session.add(self.group)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        self.scheduler.stop()

    def user(self, email, verified=True, phone=None):
        user = User(email=email, name=email.split('@')[0], is_email_verified=verified, phone=phone)
        user.set_password('Strong-pass-1')
        db.session.add(user)
        db.session.commit()
        return user

    def invite(self, email='', phone=None, **extra):
        invite = GroupInvite(group_id=self.group.id, email=email, phone=phone, token=f'token-{email or phone}',
                             invited_by_id=self.admin.id,
                             expires_at=extra.pop('expires_at', datetime.utcnow() + timedelta(days=7)), **extra)
        db.session.add(invite)
        db.session.commit()
        return invite

    def test_missing_or_revoked_invite_is_not_found(self):
        friend = self.user('friend@example.com')
        self.assertEqual(invite_accept_problem(friend, None)[1], 404)
        revoked = self.invite('friend@example.com', revoked_at=datetime.utcnow())
        self.assertEqual(invite_accept_problem(friend, revoked)[1], 404)

    def test_email_invite_matches_address_ignoring_case_but_needs_verified_email(self):
        invite = self.invite('friend@example.com')
        self.assertIsNone(invite_accept_problem(self.user('Friend@Example.com'), invite))
        unverified = self.user('friend2@example.com', verified=False)
        unverified_invite = self.invite('friend2@example.com')
        message, status = invite_accept_problem(unverified, unverified_invite)
        self.assertEqual(status, 403)
        self.assertIn('friend2@example.com', message)

    def test_phone_invite_blocked_when_another_account_owns_the_number(self):
        self.user('owner@example.com', phone='+14165550123')
        invite = self.invite(phone='+14165550123')
        message, status = invite_accept_problem(self.user('nophone@example.com'), invite)
        self.assertEqual(status, 403)
        self.assertIn('Another Splitmate account', message)

    def test_join_refuses_invite_revoked_after_the_check(self):
        friend = self.user('friend@example.com')
        invite = self.invite('friend@example.com')
        self.assertIsNone(invite_accept_problem(friend, invite))
        invite.revoked_at = datetime.utcnow()  # Revoked by the admin between the check and the join.
        self.assertFalse(join_group_from_invite(friend, invite))
        self.assertNotIn(friend, self.group.members)
        self.assertIsNone(invite.accepted_at)


if __name__ == '__main__':
    unittest.main()
