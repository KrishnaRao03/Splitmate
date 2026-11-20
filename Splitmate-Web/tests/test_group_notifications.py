"""Group members get an email when someone else adds a task or note."""
import unittest
from unittest.mock import patch

from app import db
from app.models import Group, User
from tests.test_security_fixes import SecurityFixTests


class GroupNotificationTests(SecurityFixTests):
    def add_task(self, **extra):
        body = {'title': 'Buy milk', 'due_date': '2026-12-01T18:00:00', **extra}
        return self.client.post(f'/api/mobile/groups/{self.group_id}/tasks', headers=self.admin_h, json=body)

    def test_new_task_emails_everyone_except_the_author(self):
        with patch('app.email_utils.send_group_item_email') as send:
            self.assertEqual(self.add_task(assigned_to_id=self.member_id).status_code, 201)
        send.assert_called_once()
        email = send.call_args.kwargs
        self.assertEqual(email['recipient_email'], 'member@example.com')
        self.assertEqual(email['kind'], 'task')
        self.assertEqual(email['group_name'], 'Flat')
        self.assertEqual(email['author_name'], 'Admin')
        self.assertEqual(email['details'], [('Due', 'Dec 01, 2026 18:00 UTC'), ('Assigned to', 'Member')])

    def test_unassigned_task_says_anyone(self):
        with patch('app.email_utils.send_group_item_email') as send:
            self.add_task()
        self.assertIn(('Assigned to', 'Anyone'), send.call_args.kwargs['details'])

    def test_new_note_has_no_task_details(self):
        with patch('app.email_utils.send_group_item_email') as send:
            response = self.client.post(f'/api/mobile/groups/{self.group_id}/notes', headers=self.member_h,
                                        json={'title': 'Wifi password is on the fridge'})
        self.assertEqual(response.status_code, 201)
        email = send.call_args.kwargs
        self.assertEqual(email['recipient_email'], 'admin@example.com')
        self.assertEqual(email['kind'], 'note')
        self.assertEqual(email['details'], [])

    def test_suspended_members_are_skipped(self):
        with self.app.app_context():
            db.session.get(User, self.member_id).is_suspended = True
            db.session.commit()
        with patch('app.email_utils.send_group_item_email') as send:
            self.assertEqual(self.add_task().status_code, 201)
        send.assert_not_called()

    def test_failed_email_does_not_undo_the_task(self):
        with patch('app.email_utils.send_group_item_email', side_effect=RuntimeError('mail server down')):
            response = self.add_task()
        self.assertEqual(response.status_code, 201)
        with self.app.app_context():
            self.assertEqual(db.session.get(Group, self.group_id).tasks.count(), 1)


if __name__ == '__main__':
    unittest.main()
