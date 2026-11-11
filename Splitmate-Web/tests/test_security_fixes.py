"""One test (or more) per item in docs/SECURITY_AUDIT.md."""
import io
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from importlib import metadata
from unittest.mock import patch

from app import create_app, db, limiter
from app.models import Expense, ExpenseSplit, Group, GroupInvite, Note, Payment, Task, User
from app.routes.auth import generate_password_reset_token
from app.routes.mobile_api import mobile_token_for
from config import BASE_DIR, Config


class SecurityTestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    MAIL_PASSWORD = None
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False


class RateLimitedConfig(SecurityTestConfig):
    RATELIMIT_ENABLED = True


class SecurityFixTests(unittest.TestCase):
    config_class = SecurityTestConfig

    def setUp(self):
        self.scheduler_patch = patch('app.scheduler.start_inactivity_scheduler', return_value=None)
        self.scheduler_patch.start()
        self.app = create_app(self.config_class)
        self.instance_dir = tempfile.mkdtemp()
        self.app.instance_path = self.instance_dir
        self.client = self.app.test_client()
        if self.app.config['RATELIMIT_ENABLED']:
            limiter.reset()

        with self.app.app_context():
            admin = User(email='admin@example.com', name='Admin', is_email_verified=True)
            admin.set_password('password123')
            member = User(email='member@example.com', name='Member', is_email_verified=True)
            member.set_password('password123')
            outsider = User(email='outsider@example.com', name='Outsider', is_email_verified=True)
            outsider.set_password('password123')
            db.session.add_all([admin, member, outsider])
            db.session.flush()

            group = Group(name='Flat', admin_id=admin.id)
            group.members.extend([admin, member])
            db.session.add(group)
            db.session.flush()

            # Admin paid 60 for dinner; the member owes 30.
            expense = Expense(description='Dinner', amount=60, group_id=group.id, paid_by_id=admin.id)
            db.session.add(expense)
            db.session.flush()
            db.session.add(ExpenseSplit(expense_id=expense.id, user_id=member.id, amount_owed=30))
            db.session.commit()

            self.admin_id, self.member_id, self.outsider_id = admin.id, member.id, outsider.id
            self.group_id = group.id
            self.admin_h = self.headers_for(admin)
            self.member_h = self.headers_for(member)
            self.outsider_h = self.headers_for(outsider)

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.scheduler_patch.stop()
        shutil.rmtree(self.instance_dir, ignore_errors=True)

    def headers_for(self, user):
        return {'Authorization': f'Bearer {mobile_token_for(user)}'}

    def web_login(self, email, password='password123'):
        return self.client.post('/login', data={'email': email, 'password': password})


class CriticalFixes(SecurityFixTests):
    def test_1_verify_email_never_signs_in_a_verified_user(self):
        response = self.client.post('/api/mobile/auth/verify-email', json={'email': 'admin@example.com'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('token', response.get_json())
        self.assertTrue(response.get_json()['already_verified'])

    def test_1_verify_email_still_works_with_the_right_code(self):
        with self.app.app_context():
            user = User(email='new@example.com', name='New', is_email_verified=False)
            user.set_password('password123')
            user.set_email_otp('123456', datetime.utcnow() + timedelta(minutes=10))
            db.session.add(user)
            db.session.commit()
        response = self.client.post('/api/mobile/auth/verify-email', json={'email': 'new@example.com', 'otp': '123456'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('token', response.get_json())

    def test_2_debug_is_off_by_default_and_werkzeug_is_patched(self):
        with open(os.path.join(BASE_DIR, 'run.py'), encoding='utf-8') as run_file:
            self.assertIn("os.environ.get('FLASK_DEBUG', 'false')", run_file.read())
        major, minor, patch_level = (int(part) for part in metadata.version('werkzeug').split('.')[:3])
        self.assertGreaterEqual((major, minor, patch_level), (3, 1, 4))


class HighFixes(SecurityFixTests):
    def test_3_manual_payment_waits_for_the_receiver(self):
        recorded = self.client.post(f'/api/mobile/groups/{self.group_id}/payments', headers=self.member_h,
                                    json={'receiver_id': self.admin_id, 'amount': '30'})
        self.assertEqual(recorded.status_code, 201)
        self.assertEqual(recorded.get_json()['status'], 'pending')
        payment_id = recorded.get_json()['id']
        with self.app.app_context():
            self.assertFalse(ExpenseSplit.query.filter_by(user_id=self.member_id).first().is_settled)

        # Can't pile up more pending payments than is owed.
        again = self.client.post(f'/api/mobile/groups/{self.group_id}/payments', headers=self.member_h,
                                 json={'receiver_id': self.admin_id, 'amount': '1'})
        self.assertEqual(again.status_code, 400)

        # The payer can't confirm their own payment; the receiver can.
        self.assertEqual(self.client.post(f'/api/mobile/payments/{payment_id}/confirm', headers=self.member_h).status_code, 403)
        self.assertEqual(self.client.post(f'/api/mobile/payments/{payment_id}/confirm', headers=self.admin_h).status_code, 200)
        with self.app.app_context():
            self.assertTrue(ExpenseSplit.query.filter_by(user_id=self.member_id).first().is_settled)
            self.assertEqual(db.session.get(Payment, payment_id).status, 'recorded')

    def test_3_declined_payment_changes_nothing(self):
        payment_id = self.client.post(f'/api/mobile/groups/{self.group_id}/payments', headers=self.member_h,
                                      json={'receiver_id': self.admin_id, 'amount': '10'}).get_json()['id']
        self.assertEqual(self.client.post(f'/api/mobile/payments/{payment_id}/decline', headers=self.admin_h).status_code, 200)
        self.assertEqual(self.client.post(f'/api/mobile/payments/{payment_id}/confirm', headers=self.admin_h).status_code, 409)
        self.assertEqual(self.client.post(f'/api/mobile/payments/{payment_id}/confirm', headers=self.outsider_h).status_code, 403)
        with self.app.app_context():
            self.assertEqual(ExpenseSplit.query.filter_by(user_id=self.member_id).first().amount_owed, 30)

    def test_3_web_payment_is_pending_until_confirmed(self):
        self.web_login('member@example.com')
        self.client.post('/split/pay', data={'group_id': self.group_id, 'receiver_id': self.admin_id, 'amount': '30'})
        with self.app.app_context():
            payment = Payment.query.filter_by(status='pending').one()
            payment_id = payment.id
            self.assertFalse(ExpenseSplit.query.filter_by(user_id=self.member_id).first().is_settled)
        self.client.post(f'/split/payments/{payment_id}/confirm')
        with self.app.app_context():
            self.assertEqual(db.session.get(Payment, payment_id).status, 'pending')

        self.client.post('/logout')
        self.web_login('admin@example.com')
        self.client.post(f'/split/payments/{payment_id}/confirm')
        with self.app.app_context():
            self.assertEqual(db.session.get(Payment, payment_id).status, 'recorded')
            self.assertTrue(ExpenseSplit.query.filter_by(user_id=self.member_id).first().is_settled)

    def test_4_only_admin_can_clear_all_expenses(self):
        self.assertEqual(self.client.delete(f'/api/mobile/groups/{self.group_id}/expenses', headers=self.member_h).status_code, 403)
        self.assertEqual(self.client.delete(f'/api/mobile/groups/{self.group_id}/expenses', headers=self.admin_h).status_code, 200)
        with self.app.app_context():
            self.assertEqual(Expense.query.count(), 0)

    def test_5_markup_is_refused_in_names_and_escaped_on_tasks_page(self):
        payload = '<img src=x onerror=alert(1)>'
        self.assertEqual(self.client.patch('/api/mobile/me', headers=self.member_h,
                                           json={'name': payload, 'email': 'member@example.com'}).status_code, 400)
        self.assertEqual(self.client.post('/api/mobile/auth/register', json={
            'name': payload, 'email': 'x@example.com', 'password': 'password123'}).status_code, 400)
        self.assertEqual(self.client.patch(f'/api/mobile/groups/{self.group_id}/members/{self.member_id}',
                                           headers=self.admin_h, json={'nickname': payload}).status_code, 400)
        self.assertEqual(self.client.post('/api/mobile/groups', headers=self.admin_h, json={'name': payload}).status_code, 400)
        with open(os.path.join(BASE_DIR, 'app', 'templates', 'tasks.html'), encoding='utf-8') as template:
            self.assertIn('${escapeHtml(m.name)}', template.read())

    def test_7_stripe_routes_are_gone_and_link_out_methods_are_offered(self):
        self.assertEqual(self.client.post(f'/api/mobile/groups/{self.group_id}/payments/stripe',
                                          headers=self.member_h, json={}).status_code, 404)
        self.web_login('member@example.com')
        self.assertEqual(self.client.post('/split/stripe/pay').status_code, 404)

        self.client.patch('/api/mobile/me', headers=self.admin_h, json={
            'name': 'Admin', 'email': 'admin@example.com',
            'interac_email': 'admin-pay@example.com', 'paypal_username': 'adminpays', 'upi_id': 'admin@okbank',
        })
        options = self.client.get(f'/api/mobile/groups/{self.group_id}', headers=self.member_h).get_json()['payment_options']
        methods = {method['type']: method for method in options[0]['payment_methods']}
        self.assertEqual(methods['interac']['handle'], 'admin-pay@example.com')
        self.assertEqual(methods['paypal']['url'], 'https://paypal.me/adminpays/30.00CAD')
        self.assertTrue(methods['upi']['url'].startswith('upi://pay?pa=admin%40okbank'))

        bad = self.client.patch('/api/mobile/me', headers=self.admin_h, json={
            'name': 'Admin', 'email': 'admin@example.com', 'paypal_username': 'not valid!'})
        self.assertEqual(bad.status_code, 400)

    def test_7_money_requests_list_who_owes_you_and_where_to_send_the_request(self):
        requests = self.client.get(f'/api/mobile/groups/{self.group_id}', headers=self.admin_h).get_json()['money_requests']
        self.assertEqual(requests, [{'payer_id': self.member_id, 'payer': 'Member', 'amount': 30.0, 'email': 'member@example.com'}])

        # Their Interac email is used once they share one, and pending payments are not requested twice.
        self.client.patch('/api/mobile/me', headers=self.member_h, json={
            'name': 'Member', 'email': 'member@example.com', 'interac_email': 'member-pay@example.com'})
        self.client.post(f'/api/mobile/groups/{self.group_id}/payments', headers=self.member_h,
                         json={'receiver_id': self.admin_id, 'amount': '10'})
        requests = self.client.get(f'/api/mobile/groups/{self.group_id}', headers=self.admin_h).get_json()['money_requests']
        self.assertEqual(requests[0]['email'], 'member-pay@example.com')
        self.assertEqual(requests[0]['amount'], 20.0)

        # The person who owes has nobody to request from.
        member_view = self.client.get(f'/api/mobile/groups/{self.group_id}', headers=self.member_h).get_json()
        self.assertEqual(member_view['money_requests'], [])


class RateLimitFixes(SecurityFixTests):
    config_class = RateLimitedConfig

    def test_6_repeated_logins_are_rate_limited(self):
        codes = [self.client.post('/api/mobile/auth/login', json={'email': 'admin@example.com', 'password': f'wrong{i}'}).status_code
                 for i in range(11)]
        self.assertEqual(codes[:10], [401] * 10)
        self.assertEqual(codes[10], 429)
        self.assertIn('error', self.client.post('/api/mobile/auth/login', json={'email': 'admin@example.com'}).get_json())

    def test_6_password_reset_emails_are_rate_limited_per_address(self):
        codes = [self.client.post('/api/mobile/auth/forgot-password', json={'email': 'admin@example.com'}).status_code
                 for _ in range(4)]
        self.assertEqual(codes, [200, 200, 200, 429])


class OtpLockoutFixes(SecurityFixTests):
    def test_6_otp_stops_working_after_five_wrong_guesses(self):
        with self.app.app_context():
            user = User(email='new@example.com', name='New', is_email_verified=False)
            user.set_password('password123')
            user.set_email_otp('123456', datetime.utcnow() + timedelta(minutes=10))
            db.session.add(user)
            db.session.commit()
        for guess in range(5):
            self.client.post('/api/mobile/auth/verify-email', json={'email': 'new@example.com', 'otp': f'00000{guess}'})
        right_code = self.client.post('/api/mobile/auth/verify-email', json={'email': 'new@example.com', 'otp': '123456'})
        self.assertEqual(right_code.status_code, 429)
        self.assertNotIn('token', right_code.get_json())


class MediumFixes(SecurityFixTests):
    def test_8_password_change_and_logout_all_revoke_tokens(self):
        changed = self.client.post('/api/mobile/me/password', headers=self.member_h, json={
            'current_password': 'password123', 'new_password': 'newpassword1', 'confirm_password': 'newpassword1'})
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(self.client.get('/api/mobile/me', headers=self.member_h).status_code, 401)
        fresh = {'Authorization': f'Bearer {changed.get_json()["token"]}'}
        self.assertEqual(self.client.get('/api/mobile/me', headers=fresh).status_code, 200)

        self.assertEqual(self.client.post('/api/mobile/me/logout-all', headers=fresh).status_code, 200)
        self.assertEqual(self.client.get('/api/mobile/me', headers=fresh).status_code, 401)

    def test_8_web_session_ends_when_password_changes_elsewhere(self):
        self.web_login('member@example.com')
        self.assertEqual(self.client.get('/profile').status_code, 200)
        self.client.post('/api/mobile/me/password', headers=self.member_h, json={
            'current_password': 'password123', 'new_password': 'newpassword1', 'confirm_password': 'newpassword1'})
        self.assertEqual(self.client.get('/profile').status_code, 302)

    def test_8_password_reset_link_works_only_once(self):
        with self.app.test_request_context():
            token = generate_password_reset_token(db.session.get(User, self.member_id))
        first = self.client.post(f'/reset-password/{token}', data={'password': 'brandnew123', 'confirm_password': 'brandnew123'})
        self.assertIn('/login', first.headers['Location'])
        second = self.client.post(f'/reset-password/{token}', data={'password': 'again12345', 'confirm_password': 'again12345'})
        self.assertIn('/forgot-password', second.headers['Location'])
        with self.app.app_context():
            self.assertTrue(db.session.get(User, self.member_id).check_password('brandnew123'))

    def test_9_email_change_needs_the_current_password(self):
        without = self.client.patch('/api/mobile/me', headers=self.member_h, json={'name': 'Member', 'email': 'thief@example.com'})
        self.assertEqual(without.status_code, 403)
        with_password = self.client.patch('/api/mobile/me', headers=self.member_h, json={
            'name': 'Member', 'email': 'member2@example.com', 'current_password': 'password123'})
        self.assertEqual(with_password.status_code, 200)

        self.web_login('admin@example.com')
        self.client.post('/profile', data={'form_type': 'details', 'name': 'Admin', 'email': 'thief@example.com'})
        with self.app.app_context():
            self.assertEqual(db.session.get(User, self.admin_id).email, 'admin@example.com')

    def test_10_javascript_receipt_links_are_rejected(self):
        response = self.client.post(f'/api/mobile/groups/{self.group_id}/expenses', headers=self.admin_h, json={
            'description': 'x', 'amount': '1', 'split_type': 'equal', 'receipt_url': 'javascript:alert(document.cookie)'})
        self.assertEqual(response.status_code, 400)
        ok = self.client.post(f'/api/mobile/groups/{self.group_id}/expenses', headers=self.admin_h, json={
            'description': 'x', 'amount': '1', 'split_type': 'equal', 'receipt_url': 'https://example.com/r.jpg'})
        self.assertEqual(ok.status_code, 201)

        self.web_login('admin@example.com')
        self.client.post('/split/add', data={'group_id': self.group_id, 'description': 'y', 'amount': '5',
                                             'split_type': 'equal', 'receipt_url': 'javascript:alert(1)'})
        with self.app.app_context():
            self.assertIsNone(Expense.query.filter_by(description='y').first())

    def test_11_member_with_open_balance_cannot_be_removed_and_balances_survive_old_members(self):
        blocked = self.client.delete(f'/api/mobile/groups/{self.group_id}/members/{self.member_id}', headers=self.admin_h)
        self.assertEqual(blocked.status_code, 409)

        # Data from before this fix: a member left while still owing money.
        with self.app.app_context():
            group = db.session.get(Group, self.group_id)
            group.members.remove(db.session.get(User, self.member_id))
            db.session.commit()
        detail = self.client.get(f'/api/mobile/groups/{self.group_id}', headers=self.admin_h)
        self.assertEqual(detail.status_code, 200)
        self.assertIn('Member', [row['name'] for row in detail.get_json()['balances']])

    def test_12_no_account_lookup_and_no_adding_people_without_consent(self):
        known = self.client.post('/api/mobile/invite-splitmate', headers=self.admin_h, json={'email': 'outsider@example.com'})
        unknown = self.client.post('/api/mobile/invite-splitmate', headers=self.admin_h, json={'email': 'nobody@example.com'})
        self.assertNotIn('Outsider', json.dumps(known.get_json()))
        self.assertEqual(known.get_json()['message'].replace('outsider', 'X'), unknown.get_json()['message'].replace('nobody', 'X'))

        added = self.client.post(f'/api/mobile/groups/{self.group_id}/members', headers=self.admin_h,
                                 json={'email': 'outsider@example.com'})
        self.assertEqual(added.status_code, 201)
        self.assertNotIn('member', added.get_json())
        with self.app.app_context():
            group = db.session.get(Group, self.group_id)
            self.assertNotIn(self.outsider_id, [member.id for member in group.members])
            self.assertEqual(GroupInvite.query.filter_by(email='outsider@example.com').count(), 1)

        self.assertEqual(self.client.post('/api/mobile/auth/resend-otp', json={'email': 'nobody@example.com'}).status_code, 200)

    def test_13_uploads_are_capped_and_receipts_are_private(self):
        too_big = self.client.post('/api/mobile/receipts/scan', headers=self.admin_h,
                                   data={'receipt': (io.BytesIO(b'0' * (11 * 1024 * 1024)), 'r.jpg', 'image/jpeg')},
                                   content_type='multipart/form-data')
        self.assertEqual(too_big.status_code, 413)

        created = self.client.post(f'/api/mobile/groups/{self.group_id}/expenses', headers=self.admin_h, data={
            'payload': json.dumps({'description': 'Groceries', 'amount': '20', 'split_type': 'equal'}),
            'receipt': (io.BytesIO(b'\x89PNG fake'), 'receipt.png', 'image/png'),
        }, content_type='multipart/form-data')
        self.assertEqual(created.status_code, 201)
        signed_url = created.get_json()['receipt_url']
        self.assertIn('?sig=', signed_url)
        plain_url = signed_url.split('?', 1)[0]
        self.assertTrue(plain_url.startswith('/receipts/'))
        self.assertFalse(os.path.isdir(os.path.join(BASE_DIR, 'app', 'static', 'uploads', 'receipts', plain_url.rsplit('/', 1)[1])))

        self.assertEqual(self.client.get(signed_url).status_code, 200)
        self.assertEqual(self.client.get(plain_url).status_code, 404)
        self.assertEqual(self.client.get(plain_url + '?sig=forged').status_code, 404)

        self.web_login('outsider@example.com')
        self.assertEqual(self.client.get(plain_url).status_code, 404)
        self.client.post('/logout')
        self.web_login('member@example.com')
        self.assertEqual(self.client.get(plain_url).status_code, 200)

    def test_14_cookies_are_samesite_and_secure_is_configurable(self):
        self.assertEqual(self.app.config['SESSION_COOKIE_SAMESITE'], 'Lax')
        self.assertEqual(self.app.config['REMEMBER_COOKIE_SAMESITE'], 'Lax')
        self.assertTrue(self.app.config['REMEMBER_COOKIE_HTTPONLY'])
        self.assertIn('SESSION_COOKIE_SECURE', self.app.config)


class LowFixes(SecurityFixTests):
    def test_16_csv_export_neutralises_formulas(self):
        self.client.post(f'/api/mobile/groups/{self.group_id}/expenses', headers=self.admin_h,
                         json={'description': '=HYPERLINK("http://evil")', 'amount': '5', 'split_type': 'equal'})
        with self.app.app_context():
            from app.models import ExpenseHistory
            db.session.add(ExpenseHistory(description='=HYPERLINK("http://evil")', amount=5, group_id=self.group_id, paid_by_id=self.admin_id))
            db.session.commit()
        csv_text = self.client.get(f'/api/mobile/groups/{self.group_id}/activity.csv', headers=self.admin_h).get_data(as_text=True)
        self.assertIn("'=HYPERLINK", csv_text)
        self.assertNotIn(',=HYPERLINK', csv_text)

    def test_17_passwords_need_eight_characters(self):
        short = self.client.post('/api/mobile/auth/register', json={'name': 'Short', 'email': 's@example.com', 'password': 'abc1234'})
        self.assertEqual(short.status_code, 400)
        self.assertIn('8', short.get_json()['error'])

    def test_18_logout_needs_post(self):
        self.web_login('member@example.com')
        self.assertEqual(self.client.get('/logout').status_code, 405)
        self.assertEqual(self.client.get('/admin/logout').status_code, 405)

    def test_21_only_creator_or_admin_can_delete_tasks_and_notes(self):
        with self.app.app_context():
            task = Task(title='Bins', due_date=datetime.utcnow(), group_id=self.group_id, created_by_id=self.admin_id)
            note = Note(title='List', content='List', group_id=self.group_id, created_by_id=self.admin_id)
            own_note = Note(title='Mine', content='Mine', group_id=self.group_id, created_by_id=self.member_id)
            db.session.add_all([task, note, own_note])
            db.session.commit()
            task_id, note_id, own_note_id = task.id, note.id, own_note.id
        self.assertEqual(self.client.delete(f'/api/mobile/tasks/{task_id}', headers=self.member_h).status_code, 403)
        self.assertEqual(self.client.delete(f'/api/mobile/notes/{note_id}', headers=self.member_h).status_code, 403)
        self.assertEqual(self.client.delete(f'/api/mobile/notes/{own_note_id}', headers=self.member_h).status_code, 200)
        self.assertEqual(self.client.delete(f'/api/mobile/tasks/{task_id}', headers=self.admin_h).status_code, 200)


if __name__ == '__main__':
    unittest.main()
