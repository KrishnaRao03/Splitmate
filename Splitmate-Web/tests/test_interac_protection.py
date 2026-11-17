import unittest
from unittest.mock import patch

from app import create_app, db
from app.models import Expense, ExpenseSplit, Group, MoneyRequest, User
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
        url = '/api/mobile/me'
        body = {'name': 'Owner', 'email': 'owner@example.com', 'paypal_username': 'ownerpays'}
        self.assertEqual(self.client.patch(url, headers=self.owner_h, json={**body, 'current_password': 'wrong'}).status_code, 403)
        self.assertEqual(self.alerts, [])

        response = self.client.patch(url, headers=self.owner_h, json={**body, 'current_password': 'Strong-pass-1'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.alerts), 1)
        self.assertIn('PayPal.Me username updated', self.alerts[0])

        # Saving the same details again changes nothing, so it needs no password and sends no alert.
        self.assertEqual(self.client.patch(url, headers=self.owner_h, json=body).status_code, 200)
        self.assertEqual(len(self.alerts), 1)

    def test_interac_email_field_is_removed(self):
        # The app no longer offers it, and a submitted value is ignored: no code, no pending address.
        response = self.save(self.owner_h, 'pay@example.com')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()['interac_code_sent'])
        self.assertNotIn('interac_email', response.get_json()['user'])
        self.assertNotIn('interac_email', response.get_json()['user']['payment_fields'])
        self.assertEqual(self.codes, [])

        self.client.post('/login', data={'email': 'owner@example.com', 'password': 'Strong-pass-1'})
        self.client.post('/profile', data={'form_type': 'details', 'name': 'Owner', 'email': 'owner@example.com',
                                           'interac_email': 'pay@example.com', 'current_password': 'Strong-pass-1'})
        self.assertEqual(self.codes, [])
        self.assertNotIn('Interac e-Transfer email', self.client.get('/profile').get_data(as_text=True))

        # An Interac email saved before the removal stays in the database but is never shown to payers.
        with self.app.app_context():
            owner = User.query.filter_by(email='owner@example.com').first()
            self.assertIsNone(owner.pending_interac_email)
            owner.interac_email, owner.interac_email_verified = 'old@example.com', True
            db.session.commit()
        self.assertNotIn('interac', self.payer_methods())

    def test_request_email_carries_no_interac_details(self):
        from app.routes import mobile_api
        with self.app.app_context():
            owner = User.query.filter_by(email='owner@example.com').first()
            owner.interac_email, owner.interac_email_verified = 'owner.bank@example.com', True
            db.session.commit()
        self.client.post(f'/api/mobile/groups/{self.group_id}/money-requests', headers=self.owner_h,
                         json={'payer_id': self.payer_id})
        self.assertEqual(mobile_api.send_money_request_email.call_args.args[4], [])

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



if __name__ == '__main__':
    unittest.main()
