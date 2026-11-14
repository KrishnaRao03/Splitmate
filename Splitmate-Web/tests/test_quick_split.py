import unittest
from unittest.mock import patch

from app import create_app, db
from app.models import ExpenseSplit, Group, User
from app.routes.mobile_api import mobile_token_for
from app.security import normalize_phone
from config import Config


class QuickSplitConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    MAIL_PASSWORD = None
    BREVO_API_KEY = None
    RATELIMIT_ENABLED = False


class QuickSplitTests(unittest.TestCase):
    def setUp(self):
        self.scheduler_patch = patch('app.scheduler.start_inactivity_scheduler', return_value=None)
        self.scheduler_patch.start()
        self.app = create_app(QuickSplitConfig)
        self.client = self.app.test_client()
        with self.app.app_context():
            users = {}
            for key, email, phone in [('me', 'me@example.com', None), ('sam', 'sam@example.com', '+14165550123'),
                                      ('alex', 'alex@example.com', None)]:
                user = User(email=email, name=key.title() + ' Person', is_email_verified=True, phone=phone)
                user.set_password('Strong-pass-1')
                db.session.add(user)
                users[key] = user
            db.session.commit()
            self.headers = {'Authorization': f'Bearer {mobile_token_for(users["me"])}'}
            self.alex_headers = {'Authorization': f'Bearer {mobile_token_for(users["alex"])}'}

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.scheduler_patch.stop()

    def split(self, contacts, amount='30', headers=None):
        return self.client.post('/api/mobile/quick-split', headers=headers or self.headers, json={
            'contacts': contacts, 'description': 'Pizza', 'amount': amount,
        })

    def test_phone_numbers_are_normalized(self):
        self.assertEqual(normalize_phone('(416) 555-0123'), '+14165550123')
        self.assertEqual(normalize_phone('+91 98765 43210'), '+919876543210')
        self.assertIsNone(normalize_phone('12345'))

    def test_split_by_email_and_phone_and_reuse_the_same_group(self):
        response = self.split(['alex@example.com', '416-555-0123'])
        self.assertEqual(response.status_code, 201, response.get_json())
        group_id = response.get_json()['group']['id']
        with self.app.app_context():
            group = db.session.get(Group, group_id)
            self.assertTrue(group.is_quick_split)
            self.assertEqual(len(group.members), 3)
            shares = sorted(split.amount_owed for split in ExpenseSplit.query.all())
            self.assertEqual(shares, [10.0, 10.0, 10.0])

        again = self.split(['416 555 0123', 'ALEX@example.com'], amount='12')
        self.assertEqual(again.get_json()['group']['id'], group_id)
        self.assertEqual(self.split(['alex@example.com']).get_json()['group']['id'] != group_id, True)

    def test_unknown_and_invalid_contacts_are_reported_without_creating_anything(self):
        response = self.split(['nobody@example.com'])
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()['not_found'], ['nobody@example.com'])
        self.assertEqual(self.split(['not a contact']).status_code, 400)
        self.assertEqual(self.split(['me@example.com']).status_code, 400)
        self.assertEqual(self.split(['alex@example.com'], amount='0').status_code, 400)
        with self.app.app_context():
            self.assertEqual(Group.query.count(), 0)

    def test_phone_is_unique_per_account(self):
        profile = {'name': 'Alex Person', 'email': 'alex@example.com', 'phone': '4165550123'}
        response = self.client.patch('/api/mobile/me', headers=self.alex_headers, json=profile)
        self.assertEqual(response.status_code, 409)
        profile['phone'] = '647 555 0199'
        response = self.client.patch('/api/mobile/me', headers=self.alex_headers, json=profile)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['user']['phone'], '+16475550199')
        profile['phone'] = 'abc'
        self.assertEqual(self.client.patch('/api/mobile/me', headers=self.alex_headers, json=profile).status_code, 400)


if __name__ == '__main__':
    unittest.main()
