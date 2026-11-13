import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from app import create_app, db
from app.models import Expense, ExpenseSplit, Group, User
from app.payment_security import mask_email
from app.routes.mobile_api import mobile_token_for
from config import Config


class InteracConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    MAIL_PASSWORD = None
    BREVO_API_KEY = None
    RATELIMIT_ENABLED = False
    WTF_CSRF_ENABLED = False


class InteracProtectionTests(unittest.TestCase):
    def setUp(self):
        self.scheduler_patch = patch('app.scheduler.start_inactivity_scheduler', return_value=None)
        self.scheduler_patch.start()
        self.codes = []
        self.alerts = []
        self.code_patch = patch('app.payment_security.send_interac_verification_code',
                                side_effect=lambda user, email, otp: self.codes.append((email, otp)) or True)
        self.alert_patch = patch('app.payment_security.send_payment_details_changed_email',
                                 side_effect=lambda user, changes: self.alerts.append(changes) or True)
        self.request_mail_patch = patch('app.routes.mobile_api.send_money_request_email')
        for item in (self.code_patch, self.alert_patch, self.request_mail_patch):
            item.start()
        self.app = create_app(InteracConfig)
        self.client = self.app.test_client()
        with self.app.app_context():
            owner = User(email='owner@example.com', name='Owner', is_email_verified=True)
            payer = User(email='payer@example.com', name='Payer', is_email_verified=True)
            outsider = User(email='out@example.com', name='Out', is_email_verified=True)
            for user in (owner, payer, outsider):
                user.set_password('Strong-pass-1')
                db.session.add(user)
            db.session.flush()
            group = Group(name='Flat', admin_id=owner.id)
            group.members.extend([owner, payer])
            db.session.add(group)
            db.session.flush()
            expense = Expense(description='Rent', amount=100, group_id=group.id, paid_by_id=owner.id)
            db.session.add(expense)
            db.session.flush()
            db.session.add(ExpenseSplit(expense_id=expense.id, user_id=payer.id, amount_owed=50))
            db.session.commit()
            self.group_id, self.payer_id = group.id, payer.id
            self.owner_h = {'Authorization': f'Bearer {mobile_token_for(owner)}'}
            self.payer_h = {'Authorization': f'Bearer {mobile_token_for(payer)}'}
            self.out_h = {'Authorization': f'Bearer {mobile_token_for(outsider)}'}

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        for item in (self.code_patch, self.alert_patch, self.request_mail_patch, self.scheduler_patch):
            item.stop()

    def save(self, headers, email, password='Strong-pass-1', **extra):
        name = 'Owner' if headers is self.owner_h else 'Payer'
        return self.client.patch('/api/mobile/me', headers=headers, json={
            'name': name, 'email': f'{name.lower()}@example.com', 'interac_email': email,
            'current_password': password, **extra})

    def payer_methods(self):
        options = self.client.get(f'/api/mobile/groups/{self.group_id}', headers=self.payer_h).get_json()['payment_options']
        return {method['type']: method for method in options[0]['payment_methods']}

    def test_masking(self):
        self.assertEqual(mask_email('krishna@gmail.com'), 'k•••a@gmail.com')
        self.assertEqual(mask_email('ab@x.com'), 'a•••@x.com')

    def test_changes_need_the_password_and_send_an_alert(self):
        self.assertEqual(self.save(self.owner_h, 'pay@example.com', password='wrong').status_code, 403)
        self.assertEqual(self.save(self.owner_h, 'pay@example.com', password='', paypal_username='me').status_code, 403)
        self.assertEqual(self.alerts, [])

        response = self.save(self.owner_h, 'pay@example.com', paypal_username='ownerpays')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['interac_code_sent'])
        self.assertEqual(len(self.alerts), 1)
        self.assertIn('PayPal.Me username updated', self.alerts[0])

        # Saving the same details again changes nothing, so it needs no password and sends no alert.
        unchanged = self.client.patch('/api/mobile/me', headers=self.owner_h, json={
            'name': 'Owner', 'email': 'owner@example.com', 'interac_email': 'pay@example.com', 'paypal_username': 'ownerpays'})
        self.assertEqual(unchanged.status_code, 200)
        self.assertEqual(len(self.alerts), 1)

    def test_interac_email_is_hidden_until_its_code_is_entered(self):
        self.save(self.owner_h, 'pay@example.com')
        self.assertEqual(self.codes[-1][0], 'pay@example.com')
        self.assertNotIn('interac', self.payer_methods())

        wrong = self.client.post('/api/mobile/me/interac/verify', headers=self.owner_h, json={'otp': '000000'})
        self.assertEqual(wrong.status_code, 400)
        ok = self.client.post('/api/mobile/me/interac/verify', headers=self.owner_h, json={'otp': self.codes[-1][1]})
        self.assertEqual(ok.status_code, 200)
        self.assertTrue(ok.get_json()['user']['interac_email_verified'])
        self.assertEqual(self.payer_methods()['interac']['handle'], 'pay@example.com')

        # Switching to a new address keeps the old verified one until the new one is confirmed.
        self.save(self.owner_h, 'new@example.com')
        self.assertEqual(self.payer_methods()['interac']['handle'], 'pay@example.com')

    def test_expired_codes_and_too_many_attempts_are_refused(self):
        self.save(self.owner_h, 'pay@example.com')
        for _ in range(5):
            self.client.post('/api/mobile/me/interac/verify', headers=self.owner_h, json={'otp': '000000'})
        locked = self.client.post('/api/mobile/me/interac/verify', headers=self.owner_h, json={'otp': self.codes[-1][1]})
        self.assertIn('Too many', locked.get_json()['error'])

        self.client.post('/api/mobile/me/interac/resend', headers=self.owner_h)
        with self.app.app_context():
            user = User.query.filter_by(email='owner@example.com').one()
            user.interac_otp_expires_at = datetime.utcnow() - timedelta(minutes=1)
            db.session.commit()
        expired = self.client.post('/api/mobile/me/interac/verify', headers=self.owner_h, json={'otp': self.codes[-1][1]})
        self.assertIn('expired', expired.get_json()['error'])

    def test_requests_need_the_payers_approval_before_their_email_is_shown(self):
        url = f'/api/mobile/groups/{self.group_id}/money-requests'
        created = self.client.post(url, headers=self.owner_h, json={'payer_id': self.payer_id})
        self.assertEqual(created.status_code, 201)
        self.assertEqual(self.client.post(url, headers=self.owner_h, json={'payer_id': self.payer_id}).status_code, 409)
        # Only someone who actually owes you can be asked, and only by a group member.
        self.assertEqual(self.client.post(url, headers=self.payer_h, json={'payer_id': 1}).status_code, 400)
        self.assertEqual(self.client.post(url, headers=self.out_h, json={'payer_id': self.payer_id}).status_code, 403)

        owner_view = self.client.get(f'/api/mobile/groups/{self.group_id}', headers=self.owner_h).get_json()
        self.assertEqual(owner_view['money_requests'][0]['request_status'], 'pending')
        self.assertIsNone(owner_view['money_requests'][0]['email'])
        payer_view = self.client.get(f'/api/mobile/groups/{self.group_id}', headers=self.payer_h).get_json()
        request_id = payer_view['requests_for_me'][0]['id']
        self.assertEqual(payer_view['requests_for_me'][0]['amount'], 50.0)

        # Only the payer can answer it.
        self.assertEqual(self.client.post(f'/api/mobile/money-requests/{request_id}/approve', headers=self.owner_h).status_code, 404)
        self.assertEqual(self.client.post(f'/api/mobile/money-requests/{request_id}/approve', headers=self.payer_h).status_code, 200)
        self.assertEqual(self.client.post(f'/api/mobile/money-requests/{request_id}/decline', headers=self.payer_h).status_code, 409)

        owner_view = self.client.get(f'/api/mobile/groups/{self.group_id}', headers=self.owner_h).get_json()
        self.assertEqual(owner_view['money_requests'][0]['request_status'], 'approved')
        self.assertEqual(owner_view['money_requests'][0]['email'], 'payer@example.com')
        self.assertEqual(owner_view['money_requests'][0]['masked_email'], 'p•••r@example.com')

    def test_declined_request_keeps_the_email_hidden(self):
        created = self.client.post(f'/api/mobile/groups/{self.group_id}/money-requests', headers=self.owner_h,
                                   json={'payer_id': self.payer_id}).get_json()
        self.client.post(f'/api/mobile/money-requests/{created["id"]}/decline', headers=self.payer_h)
        owner_view = self.client.get(f'/api/mobile/groups/{self.group_id}', headers=self.owner_h).get_json()
        self.assertEqual(owner_view['money_requests'][0]['request_status'], 'declined')
        self.assertIsNone(owner_view['money_requests'][0]['email'])


    def test_website_profile_needs_password_and_verifies_the_code(self):
        self.client.post('/login', data={'email': 'owner@example.com', 'password': 'Strong-pass-1'})
        form = {'form_type': 'details', 'name': 'Owner', 'email': 'owner@example.com', 'interac_email': 'pay@example.com'}
        self.client.post('/profile', data=form)
        with self.app.app_context():
            owner = User.query.filter_by(email='owner@example.com').first()
            self.assertIsNone(owner.pending_interac_email)
        self.client.post('/profile', data={**form, 'current_password': 'Strong-pass-1'})
        self.assertEqual(self.codes[-1][0], 'pay@example.com')
        self.client.post('/profile', data={'form_type': 'interac_verify', 'otp': self.codes[-1][1]})
        with self.app.app_context():
            owner = User.query.filter_by(email='owner@example.com').first()
            self.assertEqual(owner.interac_email, 'pay@example.com')
            self.assertTrue(owner.interac_email_verified)


if __name__ == '__main__':
    unittest.main()
