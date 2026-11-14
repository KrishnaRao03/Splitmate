"""The full task flow the app uses: add, assign, remind, repeat, complete/undo, delete permissions."""
import unittest
from datetime import datetime, timedelta

from app import db
from app.models import Task
from tests.test_security_fixes import SecurityFixTests


class TaskFlowTests(SecurityFixTests):
    def add_task(self, headers, **fields):
        due = (datetime.utcnow() + timedelta(days=1)).replace(microsecond=0)
        body = {'title': 'Take out bins', 'due_date': due.isoformat() + 'Z', **fields}
        return self.client.post(f'/api/mobile/groups/{self.group_id}/tasks', headers=headers, json=body)

    def test_any_member_can_add_a_task_with_every_field(self):
        due = (datetime.utcnow() + timedelta(days=2)).replace(microsecond=0)
        created = self.add_task(self.member_h, title='Pay internet', description='Rogers bill',
                                due_date=due.isoformat() + 'Z', reminder_time=(due - timedelta(hours=1)).isoformat() + 'Z',
                                priority='high', recurrence='monthly', assigned_to_id=self.admin_id)
        self.assertEqual(created.status_code, 201)
        task = created.get_json()
        self.assertEqual((task['title'], task['priority'], task['recurrence']), ('Pay internet', 'high', 'monthly'))
        self.assertEqual(task['assigned_to_id'], self.admin_id)
        self.assertIsNotNone(task['reminder_time'])
        self.assertTrue(task['can_delete'])  # the creator

    def test_task_validation_and_membership(self):
        self.assertEqual(self.add_task(self.member_h, title='  ').status_code, 400)
        self.assertEqual(self.add_task(self.member_h, due_date='not a date').status_code, 400)
        self.assertEqual(self.add_task(self.member_h, assigned_to_id=self.outsider_id).status_code, 400)
        self.assertEqual(self.add_task(self.outsider_h).status_code, 403)

    def test_completing_a_repeating_task_creates_the_next_one_and_undo_works(self):
        task_id = self.add_task(self.member_h, recurrence='weekly').get_json()['id']
        done = self.client.post(f'/api/mobile/tasks/{task_id}/toggle', headers=self.member_h).get_json()
        self.assertTrue(done['is_completed'])
        self.assertIsNotNone(done['next_task_id'])
        with self.app.app_context():
            original, following = db.session.get(Task, task_id), db.session.get(Task, done['next_task_id'])
            self.assertEqual(following.due_date - original.due_date, timedelta(days=7))
        undone = self.client.post(f'/api/mobile/tasks/{task_id}/toggle', headers=self.member_h).get_json()
        self.assertFalse(undone['is_completed'])

    def test_can_delete_flag_matches_who_may_delete(self):
        task_id = self.add_task(self.admin_h).get_json()['id']
        # Created by the admin: the other member sees can_delete false and really can't delete.
        as_member = {task['id']: task for task in self.client.get('/api/mobile/tasks', headers=self.member_h).get_json()}
        self.assertFalse(as_member[task_id]['can_delete'])
        self.assertEqual(self.client.delete(f'/api/mobile/tasks/{task_id}', headers=self.member_h).status_code, 403)

        member_task = self.add_task(self.member_h).get_json()['id']
        as_admin = {task['id']: task for task in self.client.get('/api/mobile/tasks', headers=self.admin_h).get_json()}
        self.assertTrue(as_admin[member_task]['can_delete'])  # the group admin
        self.assertEqual(self.client.delete(f'/api/mobile/tasks/{member_task}', headers=self.admin_h).status_code, 200)


if __name__ == '__main__':
    unittest.main()
