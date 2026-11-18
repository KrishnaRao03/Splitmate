"""Who gets the "we miss you" reminder email, and what happens after it is sent."""
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from app import create_app, db
from app.inactivity_reminders import inactive_reminder_candidates, send_inactivity_reminders
from app.models import User
from tests.test_billing import BillingConfig

NOW = datetime(2026, 11, 18, 12, 0)


class ReminderConfig(BillingConfig):
    INACTIVITY_REMINDER_DAYS = 30
    INACTIVITY_EMAIL_COOLDOWN_DAYS = 14


class InactivityReminderTests(unittest.TestCase):
    def setUp(self):
        self.scheduler_patch = patch('app.scheduler.start_inactivity_scheduler', return_value=None)
        self.scheduler_patch.start()
        self.app = create_app(ReminderConfig)
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        self.scheduler_patch.stop()

    def make_user(self, email, idle_days, verified=True, suspended=False, reminded_days_ago=None):
        user = User(
            email=email,
            name=email.split('@')[0],
            is_email_verified=verified,
            is_suspended=suspended,
            created_at=NOW - timedelta(days=365),
            last_activity_at=NOW - timedelta(days=idle_days),
        )
        if reminded_days_ago is not None:
            user.last_inactivity_email_sent_at = NOW - timedelta(days=reminded_days_ago)
        user.set_password('Strong-pass-1')
        db.session.add(user)
        db.session.commit()
        return user

    def test_only_idle_verified_active_users_outside_cooldown_are_picked(self):
        idle = self.make_user('idle@example.com', idle_days=40)
        self.make_user('recent@example.com', idle_days=5)
        self.make_user('unverified@example.com', idle_days=40, verified=False)
        self.make_user('suspended@example.com', idle_days=40, suspended=True)
        self.make_user('reminded@example.com', idle_days=40, reminded_days_ago=3)
        old_reminder = self.make_user('old-reminder@example.com', idle_days=40, reminded_days_ago=20)

        emails = {user.email for user in inactive_reminder_candidates(NOW)}

        self.assertEqual(emails, {idle.email, old_reminder.email})

    def test_nothing_is_sent_without_mail_settings(self):
        self.make_user('idle@example.com', idle_days=40)

        with patch('app.inactivity_reminders.send_inactivity_reminder_email') as send:
            result = send_inactivity_reminders(NOW)

        send.assert_not_called()
        self.assertEqual(result['skipped'], 1)
        self.assertEqual(result['sent'], 0)

    def test_sent_reminder_records_time_and_failed_one_does_not(self):
        sent_user = self.make_user('ok@example.com', idle_days=40)
        failed_user = self.make_user('bad@example.com', idle_days=40)
        self.app.config['MAIL_PASSWORD'] = 'set-for-test'

        def fake_send(user, days_idle):
            self.assertEqual(days_idle, 40)
            return user.email == 'ok@example.com'

        with patch('app.inactivity_reminders.send_inactivity_reminder_email', side_effect=fake_send):
            result = send_inactivity_reminders(NOW)

        self.assertEqual((result['sent'], result['failed'], result['candidates']), (1, 1, 2))
        self.assertEqual(db.session.get(User, sent_user.id).last_inactivity_email_sent_at, NOW)
        self.assertIsNone(db.session.get(User, failed_user.id).last_inactivity_email_sent_at)
