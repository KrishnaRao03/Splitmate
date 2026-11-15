import unittest
from decimal import Decimal
from email.message import EmailMessage
from unittest.mock import patch

from app import create_app, db
from app.models import Expense, ExpenseHistory, ExpenseSplit, Group, InboxPurchase, User
from app.purchase_inbox import handle_inbox_message, parse_purchase_alert
from app.routes.mobile_api import mobile_token_for
from config import Config


class InboxConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    MAIL_PASSWORD = None
    BREVO_API_KEY = None
    RATELIMIT_ENABLED = False
    INBOX_EMAIL = 'splitmate.inbox@gmail.com'
    INBOX_IMAP_PASSWORD = None


class ParseAlertTests(unittest.TestCase):
    def test_common_bank_alert_wordings(self):
        cases = [
            ('A purchase of $45.67 was made at COSTCO WHOLESALE on your RBC credit card.', '45.67', 'COSTCO WHOLESALE'),
            ('A transaction of $12.34 at TIM HORTONS #123 was made on your TD card', '12.34', 'TIM HORTONS #123'),
            ('Your CIBC card was used for $1,056.00 at LOBLAWS', '1056.00', 'LOBLAWS'),
            ('Purchase amount: $10.00\nMerchant: UBER EATS\nCard ending 1234', '10.00', 'UBER EATS'),
            ('You spent CAD 8.50 at Starbucks.', '8.50', 'Starbucks'),
        ]
        for text, amount, merchant in cases:
            with self.subTest(text=text):
                self.assertEqual(parse_purchase_alert(text), (Decimal(amount), merchant))

    def test_html_alerts_and_missing_store(self):
        self.assertEqual(parse_purchase_alert('<p>Amount: <b>$5.25</b></p>'), (Decimal('5.25'), 'Card purchase'))

    def test_not_a_purchase(self):
        self.assertIsNone(parse_purchase_alert('Your statement is ready to view.'))
        self.assertIsNone(parse_purchase_alert('A refund of $20.00 was credited to your account.'))


class PurchaseInboxApiTests(unittest.TestCase):
    def setUp(self):
        self.scheduler_patch = patch('app.scheduler.start_inactivity_scheduler', return_value=None)
        self.scheduler_patch.start()
        self.app = create_app(InboxConfig)
        self.client = self.app.test_client()
        with self.app.app_context():
            me = User(email='me@example.com', name='Me', is_email_verified=True)
            sam = User(email='sam@example.com', name='Sam', is_email_verified=True)
            other = User(email='other@example.com', name='Other', is_email_verified=True)
            for user in (me, sam, other):
                user.set_password('Strong-pass-1')
                db.session.add(user)
            db.session.flush()
            home = Group(name='Home', admin_id=me.id, members=[me, sam])
            trip = Group(name='Trip', admin_id=me.id, members=[me, sam])
            theirs = Group(name='Theirs', admin_id=other.id, members=[other])
            db.session.add_all([home, trip, theirs])
            db.session.commit()
            self.ids = {'me': me.id, 'sam': sam.id, 'home': home.id, 'trip': trip.id, 'theirs': theirs.id}
            self.headers = {'Authorization': f'Bearer {mobile_token_for(me)}'}
            self.sam_headers = {'Authorization': f'Bearer {mobile_token_for(sam)}'}

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.scheduler_patch.stop()

    def inbox(self):
        response = self.client.get('/api/mobile/inbox', headers=self.headers)
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def paste(self, text='A purchase of $30.00 was made at PIZZA PLACE on your card.'):
        return self.client.post('/api/mobile/inbox/paste', headers=self.headers, json={'text': text})

    def test_inbox_gives_a_personal_forwarding_address(self):
        data = self.inbox()
        self.assertRegex(data['address'], r'^splitmate\.inbox\+[0-9a-f]{10}@gmail\.com$')
        self.assertEqual(data['address'], self.inbox()['address'])
        self.assertEqual([g['name'] for g in data['groups']], ['Home', 'Trip'])

    def test_default_group_must_be_ones_own(self):
        response = self.client.post('/api/mobile/inbox/settings', headers=self.headers,
                                    json={'default_group_id': self.ids['theirs']})
        self.assertEqual(response.status_code, 403)
        response = self.client.post('/api/mobile/inbox/settings', headers=self.headers,
                                    json={'default_group_id': self.ids['home']})
        self.assertEqual(response.get_json()['default_group_id'], self.ids['home'])
        me = self.client.get('/api/mobile/me', headers=self.headers).get_json()
        self.assertEqual(me['user']['default_group_id'], self.ids['home'])

    def test_paste_then_share_to_default_group(self):
        self.client.post('/api/mobile/inbox/settings', headers=self.headers, json={'default_group_id': self.ids['home']})
        purchase = self.paste().get_json()
        self.assertEqual((purchase['amount'], purchase['merchant']), (30.0, 'PIZZA PLACE'))

        response = self.client.post(f'/api/mobile/inbox/{purchase["id"]}/share', headers=self.headers, json={})
        self.assertEqual(response.status_code, 201, response.get_json())
        body = response.get_json()
        self.assertEqual(body['group']['name'], 'Home')
        self.assertEqual(sorted(s['amount'] for s in body['expense']['splits']), [15.0, 15.0])
        self.assertEqual(self.inbox()['purchases'], [])
        again = self.client.post(f'/api/mobile/inbox/{purchase["id"]}/share', headers=self.headers, json={})
        self.assertEqual(again.status_code, 409)

    def test_share_needs_a_group_and_only_the_owner_can_sort(self):
        purchase = self.paste().get_json()
        no_group = self.client.post(f'/api/mobile/inbox/{purchase["id"]}/share', headers=self.headers, json={})
        self.assertEqual(no_group.status_code, 400)
        stranger = self.client.post(f'/api/mobile/inbox/{purchase["id"]}/personal', headers=self.sam_headers)
        self.assertEqual(stranger.status_code, 404)
        personal = self.client.post(f'/api/mobile/inbox/{purchase["id"]}/personal', headers=self.headers)
        self.assertEqual(personal.get_json()['status'], 'personal')

    def test_paste_without_an_amount_is_rejected(self):
        self.assertEqual(self.paste('hello there').status_code, 400)

    def test_forwarded_email_lands_in_the_right_inbox_once(self):
        address = self.inbox()['address']
        message = EmailMessage()
        message['From'] = 'alerts@bank.example'
        message['To'] = address
        message['Subject'] = 'Purchase alert'
        message['Message-ID'] = '<abc@bank.example>'
        message['Date'] = 'Sun, 15 Nov 2026 10:00:00 -0500'
        message.set_content('A purchase of $12.40 was made at METRO on your credit card.')
        with self.app.app_context():
            self.assertEqual(handle_inbox_message(message.as_bytes()), 'added')
            self.assertEqual(handle_inbox_message(message.as_bytes()), 'duplicate')
            message.replace_header('To', 'splitmate.inbox+nobody@gmail.com')
            self.assertEqual(handle_inbox_message(message.as_bytes()), 'unknown_address')
        purchases = self.inbox()['purchases']
        self.assertEqual([(p['merchant'], p['amount'], p['source']) for p in purchases], [('METRO', 12.4, 'email')])

    def test_forwarding_confirmation_is_emailed_to_the_user(self):
        address = self.inbox()['address']
        message = EmailMessage()
        message['To'] = address
        message['Subject'] = '(#123) Gmail Forwarding Confirmation - Receive Mail from me@example.com'
        message.set_content('Confirmation code: 987654321')
        with self.app.app_context(), patch('app.purchase_inbox.send_email') as send:
            self.assertEqual(handle_inbox_message(message.as_bytes()), 'confirm')
            self.assertEqual(send.call_args[0][0], 'me@example.com')
            self.assertIn('987654321', send.call_args[0][2])

    def add_expense(self, group_id, headers=None):
        response = self.client.post(f'/api/mobile/groups/{group_id}/expenses', headers=headers or self.headers,
                                    json={'description': 'Groceries', 'amount': '40'})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()['id']

    def test_move_expense_to_another_group(self):
        expense_id = self.add_expense(self.ids['home'])
        response = self.client.post(f'/api/mobile/expenses/{expense_id}/move', headers=self.headers,
                                    json={'group_id': self.ids['trip']})
        self.assertEqual(response.status_code, 200, response.get_json())
        with self.app.app_context():
            expense = db.session.get(Expense, expense_id)
            self.assertEqual(expense.group_id, self.ids['trip'])
            self.assertEqual(ExpenseSplit.query.filter_by(expense_id=expense_id).count(), 2)
            self.assertEqual(ExpenseHistory.query.filter_by(group_id=self.ids['home']).count(), 1)

    def test_move_rules(self):
        expense_id = self.add_expense(self.ids['home'], headers=self.sam_headers)
        # Not the payer and not an admin of the target, but Me is admin of Home, so it is allowed only into own groups.
        mine = self.client.post(f'/api/mobile/expenses/{expense_id}/move', headers=self.headers,
                                json={'group_id': self.ids['theirs']})
        self.assertEqual(mine.status_code, 403)
        same = self.client.post(f'/api/mobile/expenses/{expense_id}/move', headers=self.sam_headers,
                                json={'group_id': self.ids['home']})
        self.assertEqual(same.status_code, 400)
        with self.app.app_context():
            split = ExpenseSplit.query.filter_by(expense_id=expense_id, user_id=self.ids['me']).first()
            split.is_settled = True
            db.session.commit()
        settled = self.client.post(f'/api/mobile/expenses/{expense_id}/move', headers=self.sam_headers,
                                   json={'group_id': self.ids['trip']})
        self.assertEqual(settled.status_code, 409)


if __name__ == '__main__':
    unittest.main()
