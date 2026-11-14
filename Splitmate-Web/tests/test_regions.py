import unittest
from unittest.mock import patch

from sqlalchemy import inspect, text

from app import create_app, db, ensure_region_schema
from app.models import Group, User
from app.routes.mobile_api import mobile_token_for
from config import Config


class RegionTestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    MAIL_PASSWORD = None
    BREVO_API_KEY = None
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False


SIGNUP = {'name': 'Priya', 'email': 'priya@example.com', 'password': 'Strong-pass-123', 'confirm_password': 'Strong-pass-123'}


class RegionTests(unittest.TestCase):
    def setUp(self):
        self.scheduler_patch = patch('app.scheduler.start_inactivity_scheduler', return_value=None)
        self.scheduler_patch.start()
        self.codes = []
        self.email_patch = patch('app.routes.auth.send_verification_otp',
                                 side_effect=lambda user, otp: self.codes.append(otp) or True)
        self.email_patch.start()
        self.app = create_app(RegionTestConfig)
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.email_patch.stop()
        self.scheduler_patch.stop()

    def make_user(self, email='sam@example.com', country='CA'):
        with self.app.app_context():
            user = User(email=email, name='Sam', is_email_verified=True, country=country)
            user.set_password('Strong-pass-123')
            db.session.add(user)
            db.session.commit()
            return user.id, {'Authorization': f'Bearer {mobile_token_for(user)}'}

    def test_country_is_required_at_sign_up_and_sets_the_currency(self):
        self.assertEqual(self.client.post('/api/mobile/auth/register', json=SIGNUP).status_code, 400)
        self.assertEqual(self.client.post('/api/mobile/auth/register', json={**SIGNUP, 'country': 'XX'}).status_code, 400)

        self.assertEqual(self.client.post('/api/mobile/auth/register', json={**SIGNUP, 'country': 'in'}).status_code, 201)
        verified = self.client.post('/api/mobile/auth/verify-email', json={'email': 'priya@example.com', 'otp': self.codes[-1]})
        data = verified.get_json()
        self.assertEqual(data['currency_code'], 'INR')
        self.assertEqual(data['user']['country'], 'IN')
        self.assertEqual(data['user']['payment_fields'], ['upi_id', 'paypal_username'])

    def test_website_sign_up_needs_a_country(self):
        page = self.client.get('/register').get_data(as_text=True)
        self.assertIn('name="country"', page)
        self.assertIn('India (INR)', page)
        self.client.post('/register', data=SIGNUP)
        self.assertEqual(self.codes, [])
        self.client.post('/register', data={**SIGNUP, 'country': 'GB'})
        self.client.post('/verify-email', data={'otp': self.codes[-1]})
        with self.app.app_context():
            self.assertEqual(User.query.filter_by(email='priya@example.com').one().country, 'GB')

    def test_groups_use_the_creators_currency_unless_another_is_picked(self):
        _, headers = self.make_user(country='US')
        default = self.client.post('/api/mobile/groups', json={'name': 'Road trip'}, headers=headers).get_json()
        self.assertEqual(default['currency'], 'USD')
        picked = self.client.post('/api/mobile/groups', json={'name': 'Paris', 'currency': 'eur'}, headers=headers).get_json()
        self.assertEqual(picked['currency'], 'EUR')
        bogus = self.client.post('/api/mobile/groups', json={'name': 'Moon', 'currency': 'XYZ'}, headers=headers).get_json()
        self.assertEqual(bogus['currency'], 'USD')

    def test_changing_country_needs_the_password(self):
        user_id, headers = self.make_user()
        denied = self.client.patch('/api/mobile/me', headers=headers,
                                   json={'name': 'Sam', 'email': 'sam@example.com', 'country': 'AU'})
        self.assertEqual(denied.status_code, 403)
        allowed = self.client.patch('/api/mobile/me', headers=headers, json={
            'name': 'Sam', 'email': 'sam@example.com', 'country': 'AU', 'current_password': 'Strong-pass-123'})
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.get_json()['currency_code'], 'AUD')

    def test_country_list_is_public(self):
        data = self.client.get('/api/mobile/countries').get_json()
        self.assertEqual(data['default'], 'CA')
        canada = next(country for country in data['countries'] if country['code'] == 'CA')
        self.assertEqual(canada['currency'], 'CAD')
        self.assertIn('interac_email', canada['payment_fields'])

    def test_existing_rows_become_canada_and_cad(self):
        user_id, _ = self.make_user(country='US')
        with self.app.app_context():
            db.session.add(Group(name='Old group', admin_id=user_id, currency='USD'))
            db.session.commit()
            # Simulate a database from before regions existed, then upgrade it.
            db.session.execute(text('ALTER TABLE "user" DROP COLUMN country'))
            db.session.execute(text('ALTER TABLE "group" DROP COLUMN currency'))
            db.session.commit()
            ensure_region_schema()
            self.assertIn('country', {c['name'] for c in inspect(db.engine).get_columns('user')})
            self.assertEqual(db.session.execute(text('SELECT country FROM "user"')).scalar(), 'CA')
            self.assertEqual(db.session.execute(text('SELECT currency FROM "group"')).scalar(), 'CAD')


if __name__ == '__main__':
    unittest.main()
