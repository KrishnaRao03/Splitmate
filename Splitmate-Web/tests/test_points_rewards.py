"""Points buy Pro time and extra scans; they are earned by referrals and settling up, with caps."""
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from app import create_app, db
from app import billing
from app.models import Group, Payment, PendingRegistration, Referral, RewardTransaction, User
from app.rewards import award_referral_pro, award_settle, redeem
from app.routes.auth import complete_pending_registration
from app.routes.mobile_api import mobile_token_for
from tests.test_billing import BillingConfig


class PointsRewardsTests(unittest.TestCase):
    def setUp(self):
        self.scheduler_patch = patch('app.scheduler.start_inactivity_scheduler', return_value=None)
        self.scheduler_patch.start()
        self.app = create_app(BillingConfig)
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.user = self.make_user('ana@example.com', 'Ana')
        self.friend = self.make_user('ben@example.com', 'Ben')
        self.headers = {'Authorization': f'Bearer {mobile_token_for(self.user)}'}

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        self.scheduler_patch.stop()

    def make_user(self, email, name):
        user = User(email=email, name=name, is_email_verified=True)
        user.set_password('Strong-pass-1')
        db.session.add(user)
        db.session.commit()
        return user

    def sign_up(self, email):
        pending = PendingRegistration(email=email, name=email.split('@')[0], password_hash='x')
        db.session.add(pending)
        db.session.commit()
        return complete_pending_registration(pending)

    def payment(self, amount=20):
        group = Group(name='Flat', admin_id=self.friend.id)
        db.session.add(group)
        db.session.flush()
        payment = Payment(payer_id=self.user.id, receiver_id=self.friend.id, amount=amount, group_id=group.id)
        db.session.add(payment)
        db.session.flush()
        return payment

    def test_redeem_needs_enough_points_and_takes_them(self):
        self.assertIn('You need 100 points', redeem(self.user, 'scans_5'))
        self.user.reward_points = 650
        self.assertIsNone(redeem(self.user, 'scans_5'))
        self.assertIsNone(redeem(self.user, 'pro_week'))
        db.session.commit()
        self.assertEqual(self.user.reward_points, 50)
        self.assertEqual(self.user.bonus_receipt_scans, 5)
        self.assertTrue(billing.is_pro(self.user))
        self.assertFalse(billing.is_paid_pro(self.user))
        self.assertEqual(RewardTransaction.query.filter_by(user_id=self.user.id, type='redeem').count(), 2)
        self.assertEqual(redeem(self.user, 'cash'), 'Choose a reward.')

    def test_pro_time_adds_on_and_runs_out(self):
        self.user.reward_points = 2000
        redeem(self.user, 'pro_week')
        redeem(self.user, 'pro_month')
        self.assertAlmostEqual((self.user.points_pro_until - datetime.utcnow()).days, 36, delta=1)
        self.user.points_pro_until = datetime.utcnow() - timedelta(minutes=1)
        self.assertFalse(billing.is_pro(self.user))

    def test_bonus_scans_are_used_only_after_the_free_allowance(self):
        self.app.config['FREE_RECEIPT_SCANS_PER_MONTH'] = 1
        self.user.bonus_receipt_scans = 2
        self.assertEqual(billing.feature_usage(self.user, 'receipt_scan')['remaining'], 3)
        billing.record_feature_use(self.user, 'receipt_scan')
        self.assertEqual(self.user.bonus_receipt_scans, 2)
        billing.record_feature_use(self.user, 'receipt_scan')
        billing.record_feature_use(self.user, 'receipt_scan')
        self.assertEqual(self.user.bonus_receipt_scans, 0)
        self.assertIsNotNone(billing.feature_limit_error(self.user, 'receipt_scan'))

    def test_invited_friend_joining_earns_points_with_a_monthly_cap(self):
        for index in range(7):
            db.session.add(Referral(inviter_id=self.user.id, email=f'new{index}@example.com'))
        db.session.commit()
        for index in range(7):
            new_user = self.sign_up(f'new{index}@example.com')
            self.assertEqual(new_user.referred_by_id, self.user.id)
        self.assertEqual(self.user.reward_points, 5 * 200)
        self.assertIsNone(self.sign_up('stranger@example.com').referred_by_id)

    def test_splitmate_invite_records_a_referral(self):
        with patch('app.routes.mobile_api.send_splitmate_invite_email'):
            self.client.post('/api/mobile/invite-splitmate', headers=self.headers, json={'email': 'pal@example.com'})
            self.client.post('/api/mobile/invite-splitmate', headers=self.headers, json={'email': 'pal@example.com'})
        self.assertEqual(Referral.query.filter_by(inviter_id=self.user.id, email='pal@example.com').count(), 1)

    def test_friend_going_pro_pays_the_inviter_once(self):
        self.friend.referred_by_id = self.user.id
        db.session.commit()
        award_referral_pro(self.friend)
        award_referral_pro(self.friend)
        db.session.commit()
        self.assertEqual(self.user.reward_points, 500)

    def test_settling_up_earns_points_up_to_fifty_a_month(self):
        for _ in range(7):
            award_settle(self.payment())
        db.session.commit()
        self.assertEqual(self.user.reward_points, 50)
        self.assertEqual(self.friend.reward_points, 0)

    def test_tiny_payments_earn_nothing(self):
        award_settle(self.payment(amount=0.5))
        self.assertEqual(self.user.reward_points, 0)

    def test_mobile_redeem_endpoint(self):
        self.user.reward_points = 120
        db.session.commit()
        summary = self.client.get('/api/mobile/rewards', headers=self.headers).get_json()
        self.assertEqual([r['affordable'] for r in summary['rewards']], [True, True, False, False])
        self.assertFalse(summary['earning_paused'])
        ok = self.client.post('/api/mobile/rewards/redeem', headers=self.headers, json={'reward_id': 'compares_5'})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.get_json()['points'], 20)
        self.assertEqual(ok.get_json()['bonus_grocery_compares'], 5)
        poor = self.client.post('/api/mobile/rewards/redeem', headers=self.headers, json={'reward_id': 'pro_week'})
        self.assertEqual(poor.status_code, 400)

    def test_website_profile_redeems(self):
        self.user.reward_points = 100
        db.session.commit()
        self.client.post('/login', data={'email': 'ana@example.com', 'password': 'Strong-pass-1'})
        page = self.client.get('/profile').get_data(as_text=True)
        self.assertIn('1 week of Pro', page)
        self.client.post('/profile', data={'form_type': 'redeem_reward', 'reward_id': 'scans_5'})
        db.session.refresh(self.user)
        self.assertEqual(self.user.reward_points, 0)
        self.assertEqual(self.user.bonus_receipt_scans, 5)


if __name__ == '__main__':
    unittest.main()
