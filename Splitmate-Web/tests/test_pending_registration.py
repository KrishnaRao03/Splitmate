import unittest
from unittest.mock import patch

from app import create_app, db
from app.models import PendingRegistration, User
from config import Config


class PendingRegistrationTestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    MAIL_PASSWORD = None
    BREVO_API_KEY = None
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    OTP_RESEND_COOLDOWN_SECONDS = 0


SIGNUP = {'name': 'New Person', 'email': 'new@example.com', 'password': 'Strong-pass-123', 'confirm_password': 'Strong-pass-123', 'country': 'CA'}


class PendingRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.scheduler_patch = patch('app.scheduler.start_inactivity_scheduler', return_value=None)
        self.scheduler_patch.start()
        self.sent_codes = []
        self.email_patch = patch('app.routes.auth.send_verification_otp', side_effect=self.capture_code)
        self.email_patch.start()
        self.app = create_app(PendingRegistrationTestConfig)
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.email_patch.stop()
        self.scheduler_patch.stop()

    def capture_code(self, user, otp):
        self.sent_codes.append(otp)
        return True

    def counts(self):
        with self.app.app_context():
            return User.query.filter_by(email='new@example.com').count(), PendingRegistration.query.count()

    def test_mobile_signup_creates_the_user_only_after_the_code_is_verified(self):
        response = self.client.post('/api/mobile/auth/register', json=SIGNUP)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()['user']['email'], 'new@example.com')
        self.assertTrue(response.get_json()['otp_sent'])
        self.assertEqual(self.counts(), (0, 1))

        wrong = self.client.post('/api/mobile/auth/verify-email', json={'email': 'new@example.com', 'otp': '000000' if self.sent_codes[-1] != '000000' else '111111'})
        self.assertEqual(wrong.status_code, 400)
        self.assertEqual(self.counts(), (0, 1))

        right = self.client.post('/api/mobile/auth/verify-email', json={'email': 'new@example.com', 'otp': self.sent_codes[-1]})
        self.assertEqual(right.status_code, 200)
        self.assertIn('token', right.get_json())
        self.assertEqual(self.counts(), (1, 0))
        with self.app.app_context():
            user = User.query.filter_by(email='new@example.com').first()
            self.assertTrue(user.is_email_verified)
            self.assertEqual(user.name, 'New Person')
            self.assertTrue(user.check_password('Strong-pass-123'))

    def test_signing_in_before_verifying_asks_for_the_code(self):
        self.client.post('/api/mobile/auth/register', json=SIGNUP)
        response = self.client.post('/api/mobile/auth/login', json={'email': 'new@example.com', 'password': 'Strong-pass-123'})
        self.assertEqual(response.status_code, 403)
        self.assertIn('verification', response.get_json()['error'])
        wrong_password = self.client.post('/api/mobile/auth/login', json={'email': 'new@example.com', 'password': 'nope-nope-123'})
        self.assertEqual(wrong_password.status_code, 401)

    def test_registering_again_replaces_the_pending_signup_and_resend_works(self):
        self.client.post('/api/mobile/auth/register', json=SIGNUP)
        self.client.post('/api/mobile/auth/register', json={**SIGNUP, 'name': 'Renamed Person'})
        self.assertEqual(self.counts(), (0, 1))
        self.assertEqual(self.client.post('/api/mobile/auth/resend-otp', json={'email': 'new@example.com'}).get_json(), {'sent': True})
        self.assertEqual(len(self.sent_codes), 3)
        response = self.client.post('/api/mobile/auth/verify-email', json={'email': 'new@example.com', 'otp': self.sent_codes[-1]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['user']['name'], 'Renamed Person')

    def test_a_failed_email_creates_no_account(self):
        self.email_patch.stop()
        with patch('app.routes.auth.send_verification_otp', side_effect=RuntimeError('Brevo said no')):
            response = self.client.post('/api/mobile/auth/register', json=SIGNUP)
        self.email_patch.start()
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.get_json()['otp_sent'])
        self.assertEqual(self.counts()[0], 0)

    def test_existing_accounts_still_cannot_register_twice(self):
        with self.app.app_context():
            user = User(email='new@example.com', name='Existing', is_email_verified=True)
            user.set_password('Strong-pass-123')
            db.session.add(user)
            db.session.commit()
        response = self.client.post('/api/mobile/auth/register', json=SIGNUP)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.counts(), (1, 0))

    def test_an_old_unverified_account_without_groups_can_sign_up_again(self):
        with self.app.app_context():
            stale = User(email='new@example.com', name='Old Attempt', is_email_verified=False)
            stale.set_password('Old-pass-123')
            db.session.add(stale)
            db.session.commit()
        response = self.client.post('/api/mobile/auth/register', json=SIGNUP)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.counts(), (0, 1))
        self.client.post('/api/mobile/auth/verify-email', json={'email': 'new@example.com', 'otp': self.sent_codes[-1]})
        with self.app.app_context():
            user = User.query.filter_by(email='new@example.com').one()
            self.assertTrue(user.is_email_verified)
            self.assertEqual(user.name, 'New Person')

    def test_website_signup_creates_the_user_only_after_the_code_is_verified(self):
        response = self.client.post('/register', data=SIGNUP)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/verify-email', response.headers['Location'])
        self.assertEqual(self.counts(), (0, 1))

        self.assertEqual(self.client.get('/verify-email').status_code, 200)
        self.client.post('/verify-email', data={'otp': self.sent_codes[-1]})
        self.assertEqual(self.counts(), (1, 0))
        home = self.client.get('/')
        self.assertEqual(home.status_code, 200)


if __name__ == '__main__':
    unittest.main()
