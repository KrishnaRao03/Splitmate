"""Rename, leave and delete a group from the app, plus the invite QR code."""
import unittest
from unittest.mock import patch

from app import db
from app.models import Expense, ExpenseHistory, ExpenseSplit, Group, GroupInvite, Note, Payment, User
from tests.test_security_fixes import SecurityFixTests


class GroupManagementTests(SecurityFixTests):
    def test_only_admin_can_rename_and_names_are_validated(self):
        url = f'/api/mobile/groups/{self.group_id}'
        self.assertEqual(self.client.patch(url, headers=self.member_h, json={'name': 'Mine now'}).status_code, 403)
        self.assertEqual(self.client.patch(url, headers=self.outsider_h, json={'name': 'Nope'}).status_code, 403)
        self.assertEqual(self.client.patch(url, headers=self.admin_h, json={'name': '<b>x</b>'}).status_code, 400)
        renamed = self.client.patch(url, headers=self.admin_h, json={'name': 'Apartment 4B'})
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(renamed.get_json()['name'], 'Apartment 4B')

    def test_member_can_leave_only_after_settling_and_admin_cannot_leave(self):
        url = f'/api/mobile/groups/{self.group_id}/leave'
        # The member still owes 30 from the setUp dinner.
        self.assertEqual(self.client.post(url, headers=self.member_h).status_code, 409)
        with self.app.app_context():
            split = ExpenseSplit.query.filter_by(user_id=self.member_id).first()
            split.is_settled = True
            db.session.commit()
        self.assertEqual(self.client.post(url, headers=self.member_h).status_code, 200)
        with self.app.app_context():
            self.assertNotIn(self.member_id, [member.id for member in db.session.get(Group, self.group_id).members])
        self.assertEqual(self.client.post(url, headers=self.admin_h).status_code, 400)

    def test_only_empty_groups_can_be_deleted_so_history_is_kept(self):
        # The setUp group has an expense, so deleting would lose history.
        self.assertEqual(self.client.delete(f'/api/mobile/groups/{self.group_id}', headers=self.member_h).status_code, 403)
        self.assertEqual(self.client.delete(f'/api/mobile/groups/{self.group_id}', headers=self.admin_h).status_code, 409)

        with self.app.app_context():
            empty = Group(name='Trip that never happened', admin_id=self.admin_id)
            empty.members.append(db.session.get(User, self.admin_id))
            db.session.add(empty)
            db.session.flush()
            db.session.add(Note(title='Packing', content='Packing', group_id=empty.id, created_by_id=self.admin_id))
            db.session.commit()
            empty_id = empty.id
        self.assertEqual(self.client.delete(f'/api/mobile/groups/{empty_id}', headers=self.admin_h).status_code, 200)
        with self.app.app_context():
            self.assertIsNone(db.session.get(Group, empty_id))
            # The other group and its expense are untouched.
            self.assertEqual(Expense.query.filter_by(group_id=self.group_id).count(), 1)

    def test_a_group_with_only_history_left_is_not_deleted(self):
        with self.app.app_context():
            Expense.query.filter_by(group_id=self.group_id).delete()
            db.session.add(ExpenseHistory(description='Dinner', amount=60, group_id=self.group_id, paid_by_id=self.admin_id))
            db.session.commit()
        self.assertEqual(self.client.delete(f'/api/mobile/groups/{self.group_id}', headers=self.admin_h).status_code, 409)

    def test_solo_admin_can_delete_a_group_with_history_and_its_invites_stop_working(self):
        with self.app.app_context():
            # Everyone else settled up and left; the admin is the only member, with history and an invite out.
            group = db.session.get(Group, self.group_id)
            ExpenseSplit.query.filter_by(user_id=self.member_id).first().is_settled = True
            group.members.remove(db.session.get(User, self.member_id))
            db.session.add(ExpenseHistory(description='Dinner', amount=60, group_id=self.group_id, paid_by_id=self.admin_id))
            db.session.add(Payment(payer_id=self.member_id, receiver_id=self.admin_id, amount=30,
                                   group_id=self.group_id, method='manual', status='recorded'))
            db.session.commit()
        with patch('app.routes.main.send_group_invite_email', return_value=False):
            invite = self.client.post(f'/api/mobile/groups/{self.group_id}/invites', headers=self.admin_h,
                                      json={'email': 'late@example.com'}).get_json()
        token = invite['invite_url'].rstrip('/').rsplit('/', 1)[1]

        self.assertEqual(self.client.delete(f'/api/mobile/groups/{self.group_id}', headers=self.admin_h).status_code, 200)
        with self.app.app_context():
            self.assertIsNone(db.session.get(Group, self.group_id))
            self.assertEqual(Expense.query.filter_by(group_id=self.group_id).count(), 0)
            self.assertEqual(ExpenseHistory.query.filter_by(group_id=self.group_id).count(), 0)
            self.assertEqual(Payment.query.filter_by(group_id=self.group_id).count(), 0)
            self.assertIsNone(GroupInvite.query.filter_by(token=token).first())

        # The would-be invitee's link no longer works.
        late_headers = None
        with self.app.app_context():
            late = User(email='late@example.com', name='Late', is_email_verified=True)
            late.set_password('password123')
            db.session.add(late)
            db.session.commit()
            late_headers = self.headers_for(late)
        self.assertEqual(self.client.post('/api/mobile/invites/accept-link', headers=late_headers,
                                          json={'link': invite['invite_url']}).status_code, 404)

    def test_admin_cannot_delete_while_other_members_have_history(self):
        with self.app.app_context():
            db.session.add(ExpenseHistory(description='Dinner', amount=60, group_id=self.group_id, paid_by_id=self.admin_id))
            db.session.commit()
        response = self.client.delete(f'/api/mobile/groups/{self.group_id}', headers=self.admin_h)
        self.assertEqual(response.status_code, 409)
        self.assertIn('left', response.get_json()['error'])

    def test_admin_can_hand_over_admin_to_a_member_then_leave(self):
        url = f'/api/mobile/groups/{self.group_id}/admin'
        # Only the current admin can choose, and only a member of the group.
        self.assertEqual(self.client.post(url, headers=self.member_h, json={'user_id': self.member_id}).status_code, 403)
        self.assertEqual(self.client.post(url, headers=self.admin_h, json={'user_id': self.outsider_id}).status_code, 400)
        self.assertEqual(self.client.post(url, headers=self.admin_h, json={'user_id': 'x'}).status_code, 400)

        handed = self.client.post(url, headers=self.admin_h, json={'user_id': self.member_id})
        self.assertEqual(handed.status_code, 200)
        self.assertEqual(handed.get_json()['admin_id'], self.member_id)

        # The old admin is now a regular member: no admin powers, and can leave once settled.
        self.assertEqual(self.client.patch(f'/api/mobile/groups/{self.group_id}', headers=self.admin_h,
                                           json={'name': 'Mine'}).status_code, 403)
        self.assertEqual(self.client.patch(f'/api/mobile/groups/{self.group_id}', headers=self.member_h,
                                           json={'name': 'New name'}).status_code, 200)
        with self.app.app_context():
            ExpenseSplit.query.filter_by(user_id=self.member_id).first().is_settled = True
            db.session.commit()
        self.assertEqual(self.client.post(f'/api/mobile/groups/{self.group_id}/leave', headers=self.admin_h).status_code, 200)

    def test_invite_reply_includes_a_qr_code_of_the_link(self):
        with patch('app.routes.main.send_group_invite_email', return_value=False):
            invite = self.client.post(f'/api/mobile/groups/{self.group_id}/invites', headers=self.admin_h,
                                      json={'email': 'friend@example.com'}).get_json()
        rows = invite['qr_rows']
        self.assertTrue(rows)
        self.assertEqual(len(rows), len(rows[0]))
        self.assertTrue(set(''.join(rows)) <= {'0', '1'})
        self.assertIn('/invite/', invite['invite_url'])


if __name__ == '__main__':
    unittest.main()
