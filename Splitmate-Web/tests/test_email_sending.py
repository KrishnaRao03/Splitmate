import json
import unittest
from unittest.mock import patch

from flask import Flask

from app import email_utils


class EmailSendingTests(unittest.TestCase):
    def make_app(self, **config):
        app = Flask(__name__)
        app.config.update(
            MAIL_DEFAULT_SENDER='sender@example.com',
            MAIL_USERNAME='sender@example.com',
            MAIL_PASSWORD='app-password',
            MAIL_SERVER='smtp.example.com',
            MAIL_PORT=587,
            MAIL_USE_TLS=True,
            BREVO_API_KEY=None,
        )
        app.config.update(config)
        return app

    def test_brevo_api_is_used_when_key_is_set(self):
        app = self.make_app(BREVO_API_KEY='brevo-key')
        with app.app_context(), \
                patch('app.email_utils.urllib.request.urlopen') as urlopen, \
                patch('app.email_utils.smtplib.SMTP') as smtp:
            self.assertTrue(email_utils.send_email('to@example.com', 'Subject', 'Body'))

        smtp.assert_not_called()
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, email_utils.BREVO_SEND_URL)
        self.assertEqual(request.get_header('Api-key'), 'brevo-key')
        payload = json.loads(request.data)
        self.assertEqual(payload['sender']['email'], 'sender@example.com')
        self.assertEqual(payload['to'], [{'email': 'to@example.com'}])
        self.assertEqual(payload['subject'], 'Subject')
        self.assertEqual(payload['textContent'], 'Body')

    def test_smtp_is_used_without_brevo_key(self):
        app = self.make_app()
        with app.app_context(), \
                patch('app.email_utils.urllib.request.urlopen') as urlopen, \
                patch('app.email_utils.smtplib.SMTP') as smtp:
            self.assertTrue(email_utils.send_email('to@example.com', 'Subject', 'Body'))

        urlopen.assert_not_called()
        smtp.return_value.__enter__.return_value.send_message.assert_called_once()


if __name__ == '__main__':
    unittest.main()
