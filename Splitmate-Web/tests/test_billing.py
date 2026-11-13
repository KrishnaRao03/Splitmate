import io
import json
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import stripe

from app import create_app, db
from app.models import User
from app.routes.mobile_api import mobile_token_for
from config import Config

WEBHOOK_SECRET = 'whsec_test'


class BillingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    MAIL_PASSWORD = None
    BREVO_API_KEY = None
    RATELIMIT_ENABLED = False
    WTF_CSRF_ENABLED = False
    STRIPE_SECRET_KEY = 'sk_test_x'
    STRIPE_WEBHOOK_SECRET = WEBHOOK_SECRET
    PRO_PRICE_MONTHLY_CENTS = 299
    PRO_PRICE_YEARLY_CENTS = 2499
    MOBILE_API_CORS_ORIGINS = {'https://splitmate-app.onrender.com'}


def signed(payload):
    timestamp = int(time.time())
    signature = stripe.WebhookSignature._compute_signature(f'{timestamp}.{payload}', WEBHOOK_SECRET)
    return {'Stripe-Signature': f't={timestamp},v1={signature}', 'Content-Type': 'application/json'}


class BillingTests(unittest.TestCase):
    def setUp(self):
        self.scheduler_patch = patch('app.scheduler.start_inactivity_scheduler', return_value=None)
        self.scheduler_patch.start()
        self.app = create_app(BillingConfig)
        self.client = self.app.test_client()
        with self.app.app_context():
            user = User(email='buyer@example.com', name='Buyer', is_email_verified=True)
            user.set_password('Strong-pass-1')
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id
            self.headers = {'Authorization': f'Bearer {mobile_token_for(user)}'}

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.scheduler_patch.stop()

    def send(self, kind, obj):
        payload = json.dumps({'type': kind, 'data': {'object': obj}})
        return self.client.post('/stripe/webhook', data=payload, headers=signed(payload))

    def subscription(self, status='active', sub_id='sub_1', interval='year'):
        return {'id': sub_id, 'object': 'subscription', 'customer': 'cus_1', 'status': status,
                'metadata': {'user_id': str(self.user_id)}, 'cancel_at_period_end': False,
                'items': {'data': [{'current_period_end': 1893456000, 'price': {'recurring': {'interval': interval}}}]}}

    def rewards(self):
        return self.client.get('/api/mobile/rewards', headers=self.headers).get_json()

    def test_plans_show_prices_from_config(self):
        plans = self.rewards()['membership_plans']
        self.assertEqual([(p['id'], p['price']) for p in plans], [('free', 'CA$0'), ('pro_month', 'CA$2.99'), ('pro_year', 'CA$24.99')])
        self.assertTrue(plans[0]['is_current'])

    def test_checkout_uses_configured_price_and_trusted_return_url(self):
        with patch('stripe.Customer.create', return_value=SimpleNamespace(id='cus_1')), \
                patch('stripe.checkout.Session.create', return_value=SimpleNamespace(url='https://checkout.stripe.com/x')) as create:
            response = self.client.post('/api/mobile/membership/checkout', headers=self.headers, json={
                'interval': 'month', 'return_url': 'https://splitmate-app.onrender.com'})
            self.assertEqual(response.get_json()['url'], 'https://checkout.stripe.com/x')
            kwargs = create.call_args.kwargs
            self.assertEqual(kwargs['line_items'][0]['price_data']['unit_amount'], 299)
            self.assertTrue(kwargs['success_url'].startswith('https://splitmate-app.onrender.com/'))

            self.client.post('/api/mobile/membership/checkout', headers=self.headers, json={
                'interval': 'year', 'return_url': 'https://evil.example.com'})
            self.assertNotIn('evil', create.call_args.kwargs['success_url'])
        with self.app.app_context():
            self.assertEqual(db.session.get(User, self.user_id).stripe_customer_id, 'cus_1')

    def test_webhook_needs_a_valid_signature(self):
        payload = json.dumps({'type': 'customer.subscription.created', 'data': {'object': self.subscription()}})
        response = self.client.post('/stripe/webhook', data=payload, headers={'Stripe-Signature': 't=1,v1=bad'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.rewards()['membership_plan'], 'free')

    def test_subscription_events_turn_pro_on_and_off(self):
        self.assertEqual(self.send('customer.subscription.created', self.subscription()).status_code, 200)
        data = self.rewards()
        self.assertEqual(data['membership_plan'], 'pro')
        self.assertEqual(data['membership_interval'], 'year')
        self.assertTrue(data['membership_plans'][2]['is_current'])

        # A different, older subscription ending leaves the current one alone.
        self.send('customer.subscription.deleted', self.subscription(status='canceled', sub_id='sub_old'))
        self.assertEqual(self.rewards()['membership_plan'], 'pro')

        self.send('customer.subscription.deleted', self.subscription(status='canceled'))
        self.assertEqual(self.rewards()['membership_plan'], 'free')

    def test_website_upgrade_redirects_to_stripe(self):
        self.client.post('/login', data={'email': 'buyer@example.com', 'password': 'Strong-pass-1'})
        with patch('stripe.Customer.create', return_value=SimpleNamespace(id='cus_1')), \
                patch('stripe.checkout.Session.create', return_value=SimpleNamespace(url='https://checkout.stripe.com/y')):
            response = self.client.post('/membership/checkout', data={'interval': 'month'})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers['Location'], 'https://checkout.stripe.com/y')
        self.assertEqual(self.client.get('/profile').status_code, 200)


    def test_free_plan_gets_monthly_limits_and_pro_is_unlimited(self):
        self.app.config['FREE_GROCERY_COMPARES_PER_MONTH'] = 2
        with patch('app.routes.mobile_api.compare_grocery_list', return_value={'stores': []}):
            first = self.client.post('/api/mobile/grocery/compare', headers=self.headers, json={'items': 'milk'})
            self.assertEqual(first.get_json()['usage'], {'used': 1, 'limit': 2, 'remaining': 1})
            self.client.post('/api/mobile/grocery/compare', headers=self.headers, json={'items': 'milk'})
            blocked = self.client.post('/api/mobile/grocery/compare', headers=self.headers, json={'items': 'milk'})
            self.assertEqual(blocked.status_code, 402)
            self.assertTrue(blocked.get_json()['limit_reached'])

            self.send('customer.subscription.created', self.subscription())
            unlimited = self.client.post('/api/mobile/grocery/compare', headers=self.headers, json={'items': 'milk'})
            self.assertEqual(unlimited.status_code, 200)
            self.assertIsNone(unlimited.get_json()['usage']['limit'])

    def test_receipt_scans_stop_at_the_free_limit(self):
        self.app.config['FREE_RECEIPT_SCANS_PER_MONTH'] = 1
        photo = lambda: {'receipt': (io.BytesIO(b'jpg'), 'r.jpg', 'image/jpeg')}
        with patch('app.routes.mobile_api.scan_receipt_image', return_value={'items': []}) as scan:
            ok = self.client.post('/api/mobile/receipts/scan', headers=self.headers, data=photo(), content_type='multipart/form-data')
            self.assertEqual(ok.get_json()['usage']['remaining'], 0)
            blocked = self.client.post('/api/mobile/receipts/scan', headers=self.headers, data=photo(), content_type='multipart/form-data')
            self.assertEqual(blocked.status_code, 402)
            self.assertEqual(scan.call_count, 1)
        self.assertEqual(self.rewards()['usage']['receipt_scan']['remaining'], 0)


if __name__ == '__main__':
    unittest.main()
