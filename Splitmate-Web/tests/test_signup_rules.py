import json
import unittest
from unittest.mock import patch

from flask import Flask

from app import create_app, db, email_utils
from app.email_validation import normalize_email
from app.security import password_error
from config import Config


class SignupRulesTestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    MAIL_PASSWORD = None
    BREVO_API_KEY = None
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False


class PasswordRuleTests(unittest.TestCase):
    def test_new_passwords_need_upper_lower_number_and_symbol(self):
        self.assertIsNone(password_error('Splitmate1!'))
        for weak in ('short1!', 'password123!', 'PASSWORD123!', 'Password!!!', 'Password123', ''):
            self.assertIsNotNone(password_error(weak), weak)
        self.assertEqual(password_error('Password123'), 'Password needs a special character (like ! @ # $).')


class EmailRuleTests(unittest.TestCase):
    def test_cut_short_or_mistyped_provider_domains_are_rejected(self):
        for bad in ('a@gmail.c', 'a@gmail.co', 'a@gmail.con', 'a@gmial.com', 'a@gamail.com', 'a@gamail', 'a@yahoo.co', 'a@hotmail.cm', 'a@icloud.co'):
            self.assertIsNone(normalize_email(bad), bad)

    def test_real_addresses_still_work(self):
        for good in ('a@gmail.com', 'a@yahoo.co.in', 'a@hotmail.co.uk', 'a@outlook.com', 'a@company.co', 'a@uni.edu.au'):
            self.assertEqual(normalize_email(good), good, good)


class SignupMessageTests(unittest.TestCase):
    def setUp(self):
        self.scheduler_patch = patch('app.scheduler.start_inactivity_scheduler', return_value=None)
        self.scheduler_patch.start()
        self.app = create_app(SignupRulesTestConfig)
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.scheduler_patch.stop()

    def test_register_suggests_the_full_gmail_address(self):
        response = self.client.post('/api/mobile/auth/register', json={
            'name': 'Typo', 'email': 'typo@gmail.c', 'password': 'Splitmate1!', 'confirm_password': 'Splitmate1!'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('typo@gmail.com', response.get_json()['error'])

    def test_register_rejects_a_weak_password(self):
        response = self.client.post('/api/mobile/auth/register', json={
            'name': 'Weak', 'email': 'weak@example.com', 'password': 'password123', 'confirm_password': 'password123'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('uppercase', response.get_json()['error'])


class HtmlEmailTests(unittest.TestCase):
    def test_verification_email_has_a_branded_html_version_with_the_code(self):
        app = Flask(__name__)
        app.config.update(OTP_EXPIRY_MINUTES=10, MAIL_DEFAULT_SENDER='sender@example.com', BREVO_API_KEY='key')

        class User:
            name = '<b>Krishna</b>'
            email = 'k@example.com'

        with app.app_context(), patch('app.email_utils.urllib.request.urlopen') as urlopen:
            self.assertTrue(email_utils.send_verification_otp(User, '482915'))

        payload = json.loads(urlopen.call_args.args[0].data)
        self.assertEqual(payload['subject'], '482915 is your Splitmate code')
        self.assertIn('482915', payload['textContent'])
        html = payload['htmlContent']
        self.assertIn('Splitmate', html)
        for digit in '482915':
            self.assertIn(f'>{digit}</span>', html)
        self.assertNotIn('<b>Krishna</b>', html)
        self.assertIn('&lt;b&gt;Krishna&lt;/b&gt;', html)


if __name__ == '__main__':
    unittest.main()
