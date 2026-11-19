"""Lifecycle rules that used to live only in scattered flags: email changes, settling, requests, tasks, notes."""
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from app import create_app, db
from app.group_utils import set_member_nickname
from app.models import (
    Expense, ExpenseSplit, FeatureUsage, Group, GroupInvite, MoneyRequest, Note, Payment, Task, User,
)
from app.receipt_scan import ReceiptScanError
from app.routes.mobile_api import mobile_token_for
from config import Config


class FixesConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    MAIL_PASSWORD = None
    BREVO_API_KEY = None
    RATELIMIT_ENABLED = False
    WTF_CSRF_ENABLED = False
    OTP_RESEND_COOLDOWN_SECONDS = 0


class StateMachineFixesTests(unittest.TestCase):
    def setUp(self):
        self.patches = [
            patch('app.scheduler.start_inactivity_scheduler', return_value=None),
            patch('app.routes.auth.send_verification_otp', side_effect=self.capture_code),
            patch('app.routes.mobile_api.send_money_request_email'),
            patch('app.routes.split.notify_payment_confirmed'),
            patch('app.routes.split.notify_split_settled'),
        ]
        for item in self.patches:
            item.start()
        self.sent = []
        self.app = create_app(FixesConfig)
        self.client = self.app.test_client()
        with self.app.app_context():
            owed = User(email='owed@example.com', name='Owed', is_email_verified=True)
            payer = User(email='payer@example.com', name='Payer', is_email_verified=True)
            for user in (owed, payer):
                user.set_password('Strong-pass-1')
            db.session.add_all([owed, payer])
            db.session.flush()
            group = Group(name='Flat', admin_id=owed.id)
            group.members.extend([owed, payer])
            db.session.add(group)
            db.session.flush()
            set_member_nickname(group.id, owed)
            set_member_nickname(group.id, payer)
            db.session.commit()
            self.owed_id, self.payer_id, self.group_id = owed.id, payer.id, group.id
            self.owed = {'Authorization': f'Bearer {mobile_token_for(owed)}'}
            self.payer = {'Authorization': f'Bearer {mobile_token_for(payer)}'}

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        for item in self.patches:
            item.stop()

    def capture_code(self, user, otp, to=None):
        self.sent.append((to or user.email, otp))
        return True

    def add_expense(self, amount=40):
        """Owed paid `amount`, split equally with Payer."""
        response = self.client.post(f'/api/mobile/groups/{self.group_id}/expenses', headers=self.owed, json={
            'description': 'Groceries', 'amount': str(amount), 'split_type': 'equal'})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()['id']

    def pay(self, amount):
        response = self.client.post(f'/api/mobile/groups/{self.group_id}/payments', headers=self.payer,
                                    json={'receiver_id': self.owed_id, 'amount': str(amount)})
        self.assertIn(response.status_code, (200, 201), response.get_json())
        with self.app.app_context():
            return Payment.query.order_by(Payment.id.desc()).first().id

    # Email changes

    def test_new_email_waits_for_its_code_and_the_old_one_keeps_working(self):
        response = self.client.patch('/api/mobile/me', headers=self.payer, json={
            'name': 'Payer', 'email': 'new.payer@example.com', 'current_password': 'Strong-pass-1'})
        self.assertEqual(response.status_code, 200)
        user = response.get_json()['user']
        self.assertEqual(user['email'], 'payer@example.com')
        self.assertEqual(user['pending_email'], 'new.payer@example.com')
        self.assertTrue(user['is_email_verified'])
        self.assertEqual(self.sent[-1][0], 'new.payer@example.com')
        # Still signed in, and still signs in with the old address.
        self.assertEqual(self.client.get('/api/mobile/me', headers=self.payer).status_code, 200)
        login = self.client.post('/api/mobile/auth/login', json={'email': 'payer@example.com', 'password': 'Strong-pass-1'})
        self.assertEqual(login.status_code, 200)

        verified = self.client.post('/api/mobile/me/email/verify', headers=self.payer, json={'otp': self.sent[-1][1]})
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(verified.get_json()['user']['email'], 'new.payer@example.com')
        self.assertEqual(verified.get_json()['user']['pending_email'], '')
        fresh = {'Authorization': f'Bearer {verified.get_json()["token"]}'}
        self.assertEqual(self.client.get('/api/mobile/me', headers=fresh).status_code, 200)

    def test_website_email_change_also_waits_for_the_code(self):
        self.client.post('/login', data={'email': 'payer@example.com', 'password': 'Strong-pass-1'})
        self.client.post('/profile', data={'form_type': 'details', 'name': 'Payer', 'email': 'web.new@example.com',
                                           'country': 'CA', 'current_password': 'Strong-pass-1'})
        with self.app.app_context():
            user = db.session.get(User, self.payer_id)
            self.assertEqual((user.email, user.pending_email, user.is_email_verified),
                             ('payer@example.com', 'web.new@example.com', True))
        self.assertEqual(self.sent[-1][0], 'web.new@example.com')
        self.client.post('/verify-email', data={'otp': self.sent[-1][1]})
        with self.app.app_context():
            user = db.session.get(User, self.payer_id)
            self.assertEqual((user.email, user.pending_email), ('web.new@example.com', None))

    def test_an_unproven_email_cannot_pick_up_someone_elses_invite(self):
        with self.app.app_context():
            other = Group(name='Private', admin_id=self.owed_id)
            other.members.append(db.session.get(User, self.owed_id))
            db.session.add(other)
            db.session.flush()
            invite = GroupInvite(group_id=other.id, email='victim@example.com', token='tok-victim',
                                 invited_by_id=self.owed_id, expires_at=datetime.utcnow() + timedelta(days=7))
            db.session.add(invite)
            # An account left unverified by the old email-change flow.
            payer = db.session.get(User, self.payer_id)
            payer.email, payer.is_email_verified = 'victim@example.com', False
            db.session.commit()
            token = {'Authorization': f'Bearer {mobile_token_for(payer)}'}
        self.assertEqual(self.client.get('/api/mobile/invites', headers=token).get_json(), [])
        accept = self.client.post('/api/mobile/invites/accept-link', headers=token, json={'link': 'tok-victim'})
        self.assertEqual(accept.status_code, 403)

    def test_quick_split_ignores_unverified_emails(self):
        with self.app.app_context():
            ghost = User(email='ghost@example.com', name='Ghost', is_email_verified=False)
            ghost.set_password('Strong-pass-1')
            db.session.add(ghost)
            db.session.commit()
        response = self.client.post('/api/mobile/quick-split', headers=self.owed, json={
            'contacts': ['ghost@example.com'], 'description': 'Taxi', 'amount': '20'})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()['not_found'], ['ghost@example.com'])

    # Shares, payments and requests

    def test_editing_after_a_part_payment_is_blocked(self):
        expense_id = self.add_expense(40)
        self.client.post(f'/api/mobile/payments/{self.pay(5)}/confirm', headers=self.owed)
        with self.app.app_context():
            split = ExpenseSplit.query.filter_by(user_id=self.payer_id).one()
            self.assertEqual((split.amount_owed, split.share_amount, split.is_settled), (15.0, 20.0, False))
        edit = self.client.put(f'/api/mobile/expenses/{expense_id}', headers=self.owed, json={
            'description': 'Groceries', 'amount': '60', 'split_type': 'equal'})
        self.assertEqual(edit.status_code, 409)

    def test_untouched_expenses_can_still_be_edited(self):
        expense_id = self.add_expense(40)
        edit = self.client.put(f'/api/mobile/expenses/{expense_id}', headers=self.owed, json={
            'description': 'Groceries', 'amount': '60', 'split_type': 'equal'})
        self.assertEqual(edit.status_code, 200, edit.get_json())

    def test_settling_closes_waiting_payments_and_money_requests(self):
        self.add_expense(40)
        payment_id = self.pay(10)
        request_id = self.client.post(f'/api/mobile/groups/{self.group_id}/money-requests', headers=self.owed,
                                      json={'payer_id': self.payer_id}).get_json()['id']
        settled = self.client.post(f'/api/mobile/groups/{self.group_id}/settle-person', headers=self.owed,
                                   json={'user_id': self.payer_id})
        self.assertEqual(settled.status_code, 200)
        with self.app.app_context():
            self.assertEqual(db.session.get(Payment, payment_id).status, 'cancelled')
            self.assertEqual(db.session.get(Payment, payment_id).amount, 10)
            self.assertEqual(db.session.get(MoneyRequest, request_id).status, 'settled')
        # A late confirm no longer turns into a $0 payment.
        confirm = self.client.post(f'/api/mobile/payments/{payment_id}/confirm', headers=self.owed)
        self.assertEqual(confirm.status_code, 409)
        with self.app.app_context():
            self.assertEqual(db.session.get(Payment, payment_id).status, 'cancelled')

    def test_an_old_approval_does_not_carry_over_to_a_new_debt(self):
        self.add_expense(40)
        request_id = self.client.post(f'/api/mobile/groups/{self.group_id}/money-requests', headers=self.owed,
                                      json={'payer_id': self.payer_id}).get_json()['id']
        self.client.post(f'/api/mobile/money-requests/{request_id}/approve', headers=self.payer)
        self.client.post(f'/api/mobile/groups/{self.group_id}/settle-person', headers=self.owed,
                         json={'user_id': self.payer_id})
        self.add_expense(30)
        detail = self.client.get(f'/api/mobile/groups/{self.group_id}', headers=self.owed).get_json()
        row = next(item for item in detail['money_requests'] if item['payer_id'] == self.payer_id)
        self.assertEqual(row['request_status'], 'none')
        self.assertIsNone(row['email'])

    def test_asking_again_right_after_a_decline_waits_a_day(self):
        self.add_expense(40)
        url = f'/api/mobile/groups/{self.group_id}/money-requests'
        request_id = self.client.post(url, headers=self.owed, json={'payer_id': self.payer_id}).get_json()['id']
        self.client.post(f'/api/mobile/money-requests/{request_id}/decline', headers=self.payer)
        self.assertEqual(self.client.post(url, headers=self.owed, json={'payer_id': self.payer_id}).status_code, 429)
        with self.app.app_context():
            db.session.get(MoneyRequest, request_id).decided_at = datetime.utcnow() - timedelta(days=2)
            db.session.commit()
        self.assertEqual(self.client.post(url, headers=self.owed, json={'payer_id': self.payer_id}).status_code, 201)

    def test_settling_one_share_twice_is_refused_and_leaves_a_payment(self):
        self.add_expense(40)
        with self.app.app_context():
            split_id = ExpenseSplit.query.filter_by(user_id=self.payer_id).one().id
        self.assertEqual(self.client.post(f'/api/mobile/splits/{split_id}/settle', headers=self.owed).status_code, 200)
        self.assertEqual(self.client.post(f'/api/mobile/splits/{split_id}/settle', headers=self.owed).status_code, 409)
        with self.app.app_context():
            payments = Payment.query.filter_by(payer_id=self.payer_id, receiver_id=self.owed_id).all()
            self.assertEqual([(p.amount, p.status) for p in payments], [(20.0, 'recorded')])

    def test_deleting_an_expense_closes_payments_waiting_on_it(self):
        expense_id = self.add_expense(40)
        payment_id = self.pay(10)
        self.client.delete(f'/api/mobile/expenses/{expense_id}', headers=self.owed)
        with self.app.app_context():
            self.assertEqual(db.session.get(Payment, payment_id).status, 'cancelled')

    # Tasks, notes and limits

    def test_undoing_a_recurring_task_takes_back_its_next_repeat(self):
        with self.app.app_context():
            task = Task(title='Bins', due_date=datetime(2026, 12, 1, 9), recurrence='weekly',
                        group_id=self.group_id, created_by_id=self.owed_id)
            db.session.add(task)
            db.session.commit()
            task_id = task.id
        url = f'/api/mobile/tasks/{task_id}/toggle'
        self.client.post(url, headers=self.owed, json={'is_completed': True})
        self.client.post(url, headers=self.owed, json={'is_completed': True})  # A double tap changes nothing.
        with self.app.app_context():
            self.assertEqual(Task.query.filter_by(title='Bins').count(), 2)
        self.client.post(url, headers=self.owed, json={'is_completed': False})
        with self.app.app_context():
            self.assertEqual(Task.query.filter_by(title='Bins').count(), 1)
            self.assertFalse(db.session.get(Task, task_id).is_completed)

    def test_note_toggle_sets_the_state_it_was_given(self):
        with self.app.app_context():
            note = Note(title='Milk', content='Milk', group_id=self.group_id, created_by_id=self.owed_id)
            db.session.add(note)
            db.session.commit()
            note_id = note.id
        url = f'/api/mobile/notes/{note_id}/toggle'
        for _ in range(2):
            self.assertTrue(self.client.post(url, headers=self.owed, json={'is_completed': True}).get_json()['is_completed'])
        # Older apps that send nothing still flip it.
        self.assertFalse(self.client.post(url, headers=self.owed).get_json()['is_completed'])

    def test_a_failed_receipt_scan_gives_the_free_scan_back(self):
        with patch('app.routes.mobile_api.scan_receipt_image', side_effect=ReceiptScanError('Could not read it')):
            response = self.client.post('/api/mobile/receipts/scan', headers=self.owed,
                                        data={'receipt': (__import__('io').BytesIO(b'img'), 'r.jpg', 'image/jpeg')},
                                        content_type='multipart/form-data')
        self.assertEqual(response.status_code, 400)
        with self.app.app_context():
            row = FeatureUsage.query.filter_by(user_id=self.owed_id, feature='receipt_scan').first()
            self.assertEqual(row.count if row else 0, 0)


if __name__ == '__main__':
    unittest.main()
