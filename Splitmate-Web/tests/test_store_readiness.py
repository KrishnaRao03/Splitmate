"""Things both app stores check: in-app account deletion, a privacy policy and a deletion page."""
import unittest
from unittest.mock import patch

from app import create_app, db
from app.models import Group, Payment, Referral, User
from app.routes.mobile_api import mobile_token_for
from tests.test_billing import BillingConfig


class StoreReadinessTests(unittest.TestCase):
    def setUp(self):
        self.scheduler_patch = patch('app.scheduler.start_inactivity_scheduler', return_value=None)
        self.scheduler_patch.start()
        self.app = create_app(BillingConfig)
        self.app.config['ADMIN_EMAILS'] = {'boss@example.com'}
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.user = self.make_user('ana@example.com', 'Ana')
        self.headers = {'Authorization': f'Bearer {mobile_token_for(self.user)}'}

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        self.scheduler_patch.stop()

    def make_user(self, email, name):
        user = User(email=email, name=name, is_email_verified=True, phone='+14165550101' if name == 'Ana' else None)
        user.set_password('Strong-pass-1')
        db.session.add(user)
        db.session.commit()
        return user

    def delete(self, password='Strong-pass-1', headers=None):
        return self.client.post('/api/mobile/me/delete', headers=headers or self.headers, json={'password': password})

    def test_wrong_password_keeps_the_account(self):
        self.assertEqual(self.delete('nope').status_code, 403)
        self.assertIsNotNone(db.session.get(User, self.user.id))

    def test_account_without_history_is_removed_and_its_token_stops_working(self):
        db.session.add(Referral(inviter_id=self.user.id, email='x@example.com'))
        db.session.commit()
        user_id = self.user.id
        self.assertEqual(self.delete().status_code, 200)
        db.session.expire_all()
        self.assertIsNone(db.session.get(User, user_id))
        self.assertEqual(self.client.get('/api/mobile/me', headers=self.headers).status_code, 401)

    def test_account_with_shared_history_is_anonymized(self):
        friend = self.make_user('ben@example.com', 'Ben')
        group = Group(name='Flat', admin_id=friend.id)
        db.session.add(group)
        db.session.flush()
        db.session.add(Payment(payer_id=self.user.id, receiver_id=friend.id, amount=5, group_id=group.id))
        db.session.commit()
        self.assertEqual(self.delete().status_code, 200)
        db.session.expire_all()
        user = db.session.get(User, self.user.id)
        self.assertEqual(user.name, 'Deleted user')
        self.assertIsNone(user.phone)
        self.assertTrue(user.is_suspended)

    def test_paid_pro_must_be_cancelled_first(self):
        self.user.membership_plan, self.user.membership_status = 'pro', 'active'
        db.session.commit()
        response = self.delete()
        self.assertEqual(response.status_code, 409)
        self.assertIn('Cancel Splitmate Pro', response.get_json()['error'])

    def test_admin_cannot_delete_themselves(self):
        boss = self.make_user('boss@example.com', 'Boss')
        self.assertEqual(self.delete(headers={'Authorization': f'Bearer {mobile_token_for(boss)}'}).status_code, 409)

    def test_website_deletion_page(self):
        page = self.client.get('/delete-account').get_data(as_text=True)
        self.assertIn('Settings, then tap Delete account', page)
        self.client.post('/login', data={'email': 'ana@example.com', 'password': 'Strong-pass-1'})
        self.client.post('/delete-account', data={'password': 'Strong-pass-1', 'confirm': 'nope'})
        self.assertIsNotNone(db.session.get(User, self.user.id))
        user_id = self.user.id
        self.client.post('/delete-account', data={'password': 'Strong-pass-1', 'confirm': 'DELETE'})
        db.session.expire_all()
        self.assertIsNone(db.session.get(User, user_id))

    def test_privacy_policy_names_providers_and_deletion(self):
        page = self.client.get('/privacy').get_data(as_text=True)
        for text in ('Google Gemini', 'Stripe', 'Delete account', "We don't sell your data"):
            self.assertIn(text, page.replace('&#39;', "'"))
        self.assertEqual(self.client.get('/terms').status_code, 200)

    def test_inviter_gets_an_email_with_the_points(self):
        from app.models import PendingRegistration
        from app.routes.auth import complete_pending_registration
        db.session.add(Referral(inviter_id=self.user.id, email='new@example.com'))
        pending = PendingRegistration(email='new@example.com', name='Cleo', password_hash='x')
        db.session.add(pending)
        db.session.commit()
        with patch('app.email_utils.send_email', return_value=True) as sent:
            complete_pending_registration(pending)
        subject = sent.call_args.args[1]
        self.assertEqual(subject, 'You earned 200 Splitmate points')
        self.assertIn('Cleo joined Splitmate', sent.call_args.args[2])


if __name__ == '__main__':
    unittest.main()
