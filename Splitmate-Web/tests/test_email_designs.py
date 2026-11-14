import json
import unittest
from unittest.mock import patch

from flask import Flask

from app import create_app, db, email_utils
from app.models import Expense, ExpenseSplit, Group, Payment, User
from app.routes.mobile_api import mobile_token_for
from config import Config


def make_app():
    app = Flask(__name__)
    app.config.update(OTP_EXPIRY_MINUTES=10, PASSWORD_RESET_EXPIRY_MINUTES=30, GROUP_INVITE_EXPIRY_DAYS=7,
                      MAIL_DEFAULT_SENDER='sender@example.com', BREVO_API_KEY='key')
    return app


class Person:
    def __init__(self, name, email):
        self.name, self.email = name, email


class GroupStub:
    name = 'Flat 4B'
    currency = 'INR'


class EmailDesignTests(unittest.TestCase):
    def sent(self, call):
        app = make_app()
        with app.app_context(), patch('app.email_utils.urllib.request.urlopen') as urlopen:
            self.assertTrue(call())
        return json.loads(urlopen.call_args.args[0].data)

    def test_every_email_has_the_logo_yellow_button_and_no_gradient(self):
        payload = self.sent(lambda: email_utils.send_inactivity_reminder_email(Person('Sam', 'sam@example.com'), 31))
        html = payload['htmlContent']
        self.assertIn('/static/images/splitmate-logo.png', html)
        self.assertIn('alt="Splitmate"', html)
        self.assertIn('#ffc83d', html)
        self.assertNotIn('gradient', html)
        self.assertIn('https://splitmate-app.onrender.com', html)

    def test_invites_open_the_app_not_the_website(self):
        payload = self.sent(lambda: email_utils.send_group_invite_email(
            'new@example.com', GroupStub(), Person('Sam', 'sam@example.com'),
            'https://splitmate-web.onrender.com/invite/abc123'))
        self.assertIn('https://splitmate-app.onrender.com/?invite=abc123', payload['htmlContent'])
        self.assertIn('https://splitmate-app.onrender.com/?invite=abc123', payload['textContent'])
        self.assertNotIn('splitmate-web.onrender.com/invite', payload['htmlContent'])

        join = self.sent(lambda: email_utils.send_splitmate_invite_email(
            'friend@example.com', Person('Sam', 'sam@example.com'), 'https://splitmate-web.onrender.com/join'))
        self.assertIn('https://splitmate-app.onrender.com', join['htmlContent'])
        self.assertNotIn('splitmate-web.onrender.com/join', join['htmlContent'])

    def test_app_url_comes_from_the_environment(self):
        with patch.dict('os.environ', {'APP_URL': 'https://example.test/app/'}):
            payload = self.sent(lambda: email_utils.send_inactivity_reminder_email(Person('Sam', 'sam@example.com'), 40))
        self.assertIn('https://example.test/app', payload['htmlContent'])

    def test_amounts_use_the_group_currency(self):
        payload = self.sent(lambda: email_utils.send_money_request_email(
            Person('Ana', 'ana@example.com'), Person('Sam', 'sam@example.com'), GroupStub(), 250))
        self.assertIn('₹250.00 INR', payload['subject'])

    def test_membership_confirmation(self):
        payload = self.sent(lambda: email_utils.send_membership_confirmation_email(
            Person('Sam', 'sam@example.com'), 'Splitmate Pro', renews_on='Dec 14, 2026', amount_text='$4.99 / month'))
        self.assertEqual(payload['subject'], 'Welcome to Splitmate Pro')
        self.assertIn('Membership active', payload['htmlContent'])
        self.assertIn('Dec 14, 2026', payload['htmlContent'])


class PaymentEmailTestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    MAIL_PASSWORD = None
    BREVO_API_KEY = None
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False


class PaymentEmailFlowTests(unittest.TestCase):
    def setUp(self):
        self.scheduler_patch = patch('app.scheduler.start_inactivity_scheduler', return_value=None)
        self.scheduler_patch.start()
        self.app = create_app(PaymentEmailTestConfig)
        self.client = self.app.test_client()
        with self.app.app_context():
            owed = User(email='owed@example.com', name='Owed', is_email_verified=True)
            payer = User(email='payer@example.com', name='Payer', is_email_verified=True)
            for user in (owed, payer):
                user.set_password('Strong-pass-123')
            db.session.add_all([owed, payer])
            db.session.flush()
            group = Group(name='Trip', admin_id=owed.id, currency='CAD')
            group.members.extend([owed, payer])
            db.session.add(group)
            db.session.flush()
            expense = Expense(description='Hotel', amount=100, group_id=group.id, paid_by_id=owed.id)
            db.session.add(expense)
            db.session.flush()
            split = ExpenseSplit(expense_id=expense.id, user_id=payer.id, amount_owed=50)
            db.session.add(split)
            db.session.commit()
            self.group_id, self.owed_id, self.split_id = group.id, owed.id, split.id
            self.owed_h = {'Authorization': f'Bearer {mobile_token_for(owed)}'}
            self.payer_h = {'Authorization': f'Bearer {mobile_token_for(payer)}'}

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.scheduler_patch.stop()

    def test_recording_then_confirming_a_payment_emails_both_sides(self):
        with patch('app.email_utils.send_payment_recorded_email') as recorded, \
                patch('app.email_utils.send_payment_confirmed_email') as confirmed:
            created = self.client.post(f'/api/mobile/groups/{self.group_id}/payments', headers=self.payer_h,
                                       json={'receiver_id': self.owed_id, 'amount': '50'})
            self.assertEqual(created.status_code, 201)
            self.assertEqual(recorded.call_count, 1)
            receiver, payer, group, amount = recorded.call_args.args
            self.assertEqual((receiver.email, payer.email, amount), ('owed@example.com', 'payer@example.com', 50.0))
            confirmed.assert_not_called()

            done = self.client.post(f'/api/mobile/payments/{created.get_json()["id"]}/confirm', headers=self.owed_h)
            self.assertEqual(done.status_code, 200)
            recipients = sorted((call.args[0].email, call.args[4]) for call in confirmed.call_args_list)
            self.assertEqual(recipients, [('owed@example.com', False), ('payer@example.com', True)])

    def test_settling_a_split_tells_the_person_who_owed(self):
        with patch('app.email_utils.send_payment_confirmed_email') as confirmed:
            self.assertEqual(self.client.post(f'/api/mobile/splits/{self.split_id}/settle', headers=self.owed_h).status_code, 200)
        user, other, group, amount, paid_by_user = confirmed.call_args.args
        self.assertEqual((user.email, other.email, amount, paid_by_user), ('payer@example.com', 'owed@example.com', 50.0, True))

    def test_a_failed_email_does_not_undo_the_payment(self):
        with patch('app.email_utils.send_payment_recorded_email', side_effect=RuntimeError('mail down')):
            created = self.client.post(f'/api/mobile/groups/{self.group_id}/payments', headers=self.payer_h,
                                       json={'receiver_id': self.owed_id, 'amount': '20'})
        self.assertEqual(created.status_code, 201)
        with self.app.app_context():
            self.assertEqual(Payment.query.count(), 1)


if __name__ == '__main__':
    unittest.main()
