import unittest
from unittest.mock import patch

from app import create_app, db
from app.models import Expense, ExpenseHistory, ExpenseSplit, Group, User
from config import Config


class WebSecurityTestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    MAIL_PASSWORD = None
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False


class CsrfEnabledTestConfig(WebSecurityTestConfig):
    WTF_CSRF_ENABLED = True


class WebSecurityTests(unittest.TestCase):
    config_class = WebSecurityTestConfig

    def setUp(self):
        self.scheduler_patch = patch('app.scheduler.start_inactivity_scheduler', return_value=None)
        self.scheduler_patch.start()
        self.app = create_app(self.config_class)
        self.client = self.app.test_client()

        with self.app.app_context():
            admin = User(email='admin@example.com', name='Admin User', is_email_verified=True)
            admin.set_password('password123')
            member = User(email='member@example.com', name='Member User', is_email_verified=True)
            member.set_password('password123')
            db.session.add_all([admin, member])
            db.session.flush()

            group = Group(name='Flat', admin_id=admin.id)
            group.members.extend([admin, member])
            db.session.add(group)
            db.session.flush()

            # Admin paid; member owes half.
            expense = Expense(description='Dinner', amount=60, group_id=group.id, paid_by_id=admin.id)
            db.session.add(expense)
            db.session.flush()
            split = ExpenseSplit(expense_id=expense.id, user_id=member.id, amount_owed=30)
            db.session.add(split)
            db.session.add(ExpenseHistory(description='Dinner', amount=60, group_id=group.id, paid_by_id=admin.id))
            db.session.commit()

            self.group_id = group.id
            self.split_id = split.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.scheduler_patch.stop()

    def login(self, email, next_url=None):
        url = '/login' + (f'?next={next_url}' if next_url else '')
        return self.client.post(url, data={'email': email, 'password': 'password123'})


class WebAccessTests(WebSecurityTests):
    def test_login_ignores_offsite_next(self):
        response = self.login('member@example.com', next_url='https://evil.example/')
        self.assertNotIn('evil.example', response.headers['Location'])

    def test_login_keeps_local_next(self):
        response = self.login('member@example.com', next_url='/split/')
        self.assertTrue(response.headers['Location'].endswith('/split/'))

    def test_debtor_cannot_mark_own_split_settled(self):
        self.login('member@example.com')
        self.client.post(f'/split/settle/{self.split_id}')
        with self.app.app_context():
            self.assertFalse(db.session.get(ExpenseSplit, self.split_id).is_settled)

    def test_payee_can_mark_split_settled(self):
        self.login('admin@example.com')
        self.client.post(f'/split/settle/{self.split_id}')
        with self.app.app_context():
            split = db.session.get(ExpenseSplit, self.split_id)
            self.assertTrue(split.is_settled)
            self.assertEqual(split.amount_owed, 0.0)

    def test_only_group_admin_can_clear_recent(self):
        self.login('member@example.com')
        self.client.post(f'/split/clear_recent/{self.group_id}')
        with self.app.app_context():
            self.assertEqual(Expense.query.count(), 1)

        self.client.post('/logout')
        self.login('admin@example.com')
        self.client.post(f'/split/clear_recent/{self.group_id}')
        with self.app.app_context():
            self.assertEqual(Expense.query.count(), 0)
            self.assertEqual(ExpenseHistory.query.count(), 1)


class CsrfTests(WebSecurityTests):
    config_class = CsrfEnabledTestConfig

    def test_web_post_without_token_is_rejected(self):
        response = self.client.post('/login', data={'email': 'member@example.com', 'password': 'password123'})
        self.assertEqual(response.status_code, 400)

    def test_mobile_api_is_exempt(self):
        response = self.client.post('/api/mobile/auth/login', json={'email': 'member@example.com', 'password': 'password123'})
        self.assertNotEqual(response.status_code, 400)


if __name__ == '__main__':
    unittest.main()
