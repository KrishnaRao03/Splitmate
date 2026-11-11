import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet
from sqlalchemy import text

from app import create_app, db
from app.field_encryption import encrypt_existing_payment_handles
from app.models import User
from app.routes.mobile_api import mobile_token_for
from config import Config, _load_env_file
from env_crypto import is_protected, protect_value, unprotect_value


class FieldEncryptionTestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    MAIL_PASSWORD = None
    RATELIMIT_ENABLED = False
    FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()


def raw_handles(user_id):
    return db.session.execute(
        text('SELECT interac_email, paypal_username, upi_id FROM "user" WHERE id = :id'), {'id': user_id}
    ).one()


class PaymentHandleEncryptionTests(unittest.TestCase):
    def setUp(self):
        self.scheduler_patch = patch('app.scheduler.start_inactivity_scheduler', return_value=None)
        self.scheduler_patch.start()
        self.app = create_app(FieldEncryptionTestConfig)
        self.client = self.app.test_client()
        with self.app.app_context():
            user = User(email='payee@example.com', name='Payee', is_email_verified=True)
            user.set_password('password123')
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id
            self.token = mobile_token_for(user)

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.scheduler_patch.stop()

    def test_handles_are_encrypted_in_the_database_and_plain_through_the_api(self):
        response = self.client.patch(
            '/api/mobile/me',
            json={
                'name': 'Payee',
                'email': 'payee@example.com',
                'interac_email': 'pay@example.com',
                'paypal_username': 'payee',
                'upi_id': 'payee@upi',
            },
            headers={'Authorization': f'Bearer {self.token}'},
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(response.get_json()['user']['interac_email'], 'pay@example.com')

        with self.app.app_context():
            for value in raw_handles(self.user_id):
                self.assertTrue(value.startswith('enc:'))
            self.assertNotIn('pay@example.com', ''.join(raw_handles(self.user_id)))
            user = db.session.get(User, self.user_id)
            self.assertEqual((user.interac_email, user.paypal_username, user.upi_id), ('pay@example.com', 'payee', 'payee@upi'))

        me = self.client.get('/api/mobile/me', headers={'Authorization': f'Bearer {self.token}'}).get_json()
        self.assertEqual(me['user']['upi_id'], 'payee@upi')

    def test_existing_plain_text_rows_are_encrypted_once_and_still_readable(self):
        with self.app.app_context():
            db.session.execute(
                text("UPDATE \"user\" SET interac_email = 'old@example.com', paypal_username = NULL, upi_id = 'old@upi' WHERE id = :id"),
                {'id': self.user_id},
            )
            db.session.commit()

            encrypt_existing_payment_handles(db)
            first = raw_handles(self.user_id)
            self.assertTrue(first[0].startswith('enc:'))
            self.assertIsNone(first[1])
            self.assertTrue(first[2].startswith('enc:'))

            encrypt_existing_payment_handles(db)
            self.assertEqual(raw_handles(self.user_id), first)

            db.session.expire_all()
            user = db.session.get(User, self.user_id)
            self.assertEqual((user.interac_email, user.upi_id), ('old@example.com', 'old@upi'))

    def test_a_wrong_key_hides_the_value_instead_of_breaking_the_page(self):
        with self.app.app_context():
            user = db.session.get(User, self.user_id)
            user.interac_email = 'pay@example.com'
            db.session.commit()

            self.app.config['FIELD_ENCRYPTION_KEY'] = Fernet.generate_key().decode()
            db.session.expire_all()
            with self.assertLogs(self.app.logger, level='WARNING'):
                self.assertIsNone(db.session.get(User, self.user_id).interac_email)

    def test_a_malformed_key_stops_start_up(self):
        class BadKeyConfig(FieldEncryptionTestConfig):
            FIELD_ENCRYPTION_KEY = 'not-a-fernet-key'

        with self.assertRaises(ValueError):
            create_app(BadKeyConfig)


@unittest.skipUnless(sys.platform == 'win32', 'DPAPI is Windows-only')
class ProtectedEnvFileTests(unittest.TestCase):
    def test_protected_values_round_trip(self):
        protected = protect_value('s3cret value')
        self.assertTrue(is_protected(protected))
        self.assertNotIn('s3cret', protected)
        self.assertEqual(unprotect_value(protected), 's3cret value')

    def test_env_loader_decrypts_protected_values_and_real_env_vars_win(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, '.env')
            with open(path, 'w', encoding='utf-8') as env_file:
                env_file.write(f'SPLITMATE_TEST_PROTECTED={protect_value("from-dpapi")}\n')
                env_file.write('SPLITMATE_TEST_OVERRIDDEN=from-file\n')

            with patch.dict(os.environ, {'SPLITMATE_TEST_OVERRIDDEN': 'from-environment'}):
                _load_env_file(path)
                self.assertEqual(os.environ['SPLITMATE_TEST_PROTECTED'], 'from-dpapi')
                self.assertEqual(os.environ['SPLITMATE_TEST_OVERRIDDEN'], 'from-environment')
            os.environ.pop('SPLITMATE_TEST_PROTECTED', None)


if __name__ == '__main__':
    unittest.main()
