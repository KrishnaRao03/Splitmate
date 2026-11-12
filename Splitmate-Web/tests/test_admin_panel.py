import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from app import create_app, db
from app.models import AdminAuditLog, Expense, ExpenseSplit, Group, GroupInvite, Payment, User
from config import Config


class AdminPanelTestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    MAIL_PASSWORD = None
    BREVO_API_KEY = None
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    ADMIN_EMAILS = {'owner@example.com'}


class AdminPanelTests(unittest.TestCase):
    def setUp(self):
        self.scheduler_patch = patch('app.scheduler.start_inactivity_scheduler', return_value=None)
        self.scheduler_patch.start()
        self.app = create_app(AdminPanelTestConfig)
        self.client = self.app.test_client()

        with self.app.app_context():
            owner = User(email='owner@example.com', name='Owner', is_email_verified=True)
            owner.set_password('owner-password')
            member = User(email='member@example.com', name='Member', is_email_verified=True)
            member.set_password('member-password')
            unused = User(email='unused@example.com', name='Unused', is_email_verified=False)
            unused.set_password('unused-password')
            db.session.add_all([owner, member, unused])
            db.session.flush()

            group = Group(name='Flat 4B', admin_id=member.id)
            group.members.append(member)
            db.session.add(group)
            db.session.flush()
            expense = Expense(description='Groceries', amount=42.5, group_id=group.id, paid_by_id=member.id)
            db.session.add(expense)
            db.session.flush()
            db.session.add(ExpenseSplit(expense_id=expense.id, user_id=member.id, amount_owed=42.5))
            db.session.add(Payment(payer_id=member.id, receiver_id=member.id, amount=5, group_id=group.id, status='pending'))
            invite = GroupInvite(
                group_id=group.id, email='friend@example.com', token='invite-token', invited_by_id=member.id,
                expires_at=datetime.utcnow() + timedelta(days=7),
            )
            db.session.add(invite)
            db.session.commit()
            self.owner_id, self.member_id, self.unused_id = owner.id, member.id, unused.id
            self.group_id, self.invite_id = group.id, invite.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.scheduler_patch.stop()

    def admin_login(self, email='owner@example.com', password='owner-password'):
        return self.client.post('/admin/login', data={'email': email, 'password': password})

    def audit_actions(self):
        with self.app.app_context():
            return [entry.action for entry in AdminAuditLog.query.order_by(AdminAuditLog.id).all()]

    def test_only_the_configured_admin_can_sign_in(self):
        response = self.admin_login('member@example.com', 'member-password')
        self.assertIn(b'Invalid admin email or password', response.data)
        self.assertEqual(self.client.get('/admin/').status_code, 302)

        self.admin_login('owner@example.com', 'wrong-password')
        self.assertEqual(self.client.get('/admin/').status_code, 302)

        self.admin_login()
        self.assertEqual(self.client.get('/admin/').status_code, 200)
        self.assertEqual(self.audit_actions(), ['admin.login_failed', 'admin.login_failed', 'admin.login'])

    def test_every_admin_page_loads(self):
        self.admin_login()
        for path in ('/admin/', '/admin/users', '/admin/emails', '/admin/groups', f'/admin/groups/{self.group_id}',
                     '/admin/activity', '/admin/activity?status=pending', '/admin/audit', '/admin/system'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)

        groups_page = self.client.get('/admin/groups').get_data(as_text=True)
        self.assertIn('Flat 4B', groups_page)
        self.assertIn('42.50', groups_page)
        detail = self.client.get(f'/admin/groups/{self.group_id}').get_data(as_text=True)
        self.assertIn('friend@example.com', detail)
        self.assertIn('Groceries', detail)
        system_page = self.client.get('/admin/system').get_data(as_text=True)
        self.assertIn('Connected', system_page)
        self.assertIn('owner@example.com', system_page)

    def test_admin_session_times_out_when_idle(self):
        self.admin_login()
        with self.client.session_transaction() as session:
            session['admin_seen_at'] = (datetime.utcnow() - timedelta(minutes=31)).timestamp()
        response = self.client.get('/admin/users')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login', response.headers['Location'])

    def test_unused_account_can_be_deleted_only_with_confirmation(self):
        self.admin_login()
        self.client.post(f'/admin/users/{self.unused_id}/delete', data={'confirm_email': 'wrong@example.com'})
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(User, self.unused_id))

        self.client.post(f'/admin/users/{self.unused_id}/delete', data={'confirm_email': 'unused@example.com'})
        with self.app.app_context():
            self.assertIsNone(db.session.get(User, self.unused_id))
        self.assertIn('user.delete', self.audit_actions())

    def test_accounts_with_history_and_admins_cannot_be_deleted(self):
        self.admin_login()
        self.client.post(f'/admin/users/{self.member_id}/delete', data={'confirm_email': 'member@example.com'})
        self.client.post(f'/admin/users/{self.owner_id}/delete', data={'confirm_email': 'owner@example.com'})
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(User, self.member_id))
            self.assertIsNotNone(db.session.get(User, self.owner_id))
        self.assertNotIn('user.delete', self.audit_actions())

    def test_sign_out_everywhere_revokes_tokens(self):
        self.admin_login()
        with self.app.app_context():
            before = db.session.get(User, self.member_id).token_version or 0
        self.client.post(f'/admin/users/{self.member_id}/sign-out')
        with self.app.app_context():
            self.assertEqual(db.session.get(User, self.member_id).token_version, before + 1)
        self.assertIn('user.sign_out_everywhere', self.audit_actions())

    def test_users_export_is_csv(self):
        self.admin_login()
        response = self.client.get('/admin/users/export.csv')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'text/csv')
        body = response.get_data(as_text=True)
        self.assertTrue(body.startswith('id,name,email'))
        self.assertIn('member@example.com', body)

    def test_invite_can_be_revoked(self):
        self.admin_login()
        self.client.post(f'/admin/groups/{self.group_id}/invites/{self.invite_id}/revoke')
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(GroupInvite, self.invite_id).revoked_at)
        self.assertIn('group.revoke_invite', self.audit_actions())

    def test_admin_pages_need_admin_sign_in(self):
        for path in ('/admin/groups', '/admin/activity', '/admin/audit', '/admin/system', '/admin/users/export.csv'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302, path)
            self.assertIn('/admin/login', response.headers['Location'])


if __name__ == '__main__':
    unittest.main()
