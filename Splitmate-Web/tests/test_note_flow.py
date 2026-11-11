"""The full notes flow the app uses, matching the website: add, edit, done/undo, delete rules, grocery compare."""
import unittest

from tests.test_security_fixes import SecurityFixTests


class NoteFlowTests(SecurityFixTests):
    def add_note(self, headers, title='Grocery list', description='milk, bread, eggs'):
        return self.client.post(f'/api/mobile/groups/{self.group_id}/notes', headers=headers,
                                json={'title': title, 'description': description})

    def test_add_edit_and_mark_done(self):
        created = self.add_note(self.member_h)
        self.assertEqual(created.status_code, 201)
        note = created.get_json()
        self.assertTrue(note['can_delete'])
        self.assertTrue(note['can_compare_prices'])

        edited = self.client.patch(f'/api/mobile/notes/{note["id"]}', headers=self.admin_h,
                                   json={'title': 'Wi-Fi password', 'description': 'hunter2'})
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.get_json()['title'], 'Wi-Fi password')
        self.assertFalse(edited.get_json()['can_compare_prices'])

        self.assertTrue(self.client.post(f'/api/mobile/notes/{note["id"]}/toggle', headers=self.member_h).get_json()['is_completed'])
        self.assertFalse(self.client.post(f'/api/mobile/notes/{note["id"]}/toggle', headers=self.member_h).get_json()['is_completed'])

    def test_validation_and_membership(self):
        self.assertEqual(self.add_note(self.member_h, title='  ').status_code, 400)
        self.assertEqual(self.add_note(self.outsider_h).status_code, 403)
        note_id = self.add_note(self.member_h).get_json()['id']
        self.assertEqual(self.client.get(f'/api/mobile/notes/{note_id}/grocery-comparison', headers=self.outsider_h).status_code, 403)
        self.assertNotIn(note_id, [note['id'] for note in self.client.get('/api/mobile/notes', headers=self.outsider_h).get_json()])

    def test_can_delete_flag_matches_who_may_delete(self):
        note_id = self.add_note(self.admin_h).get_json()['id']
        as_member = {note['id']: note for note in self.client.get('/api/mobile/notes', headers=self.member_h).get_json()}
        self.assertFalse(as_member[note_id]['can_delete'])
        self.assertEqual(self.client.delete(f'/api/mobile/notes/{note_id}', headers=self.member_h).status_code, 403)

        member_note = self.add_note(self.member_h, title='Chores').get_json()['id']
        as_admin = {note['id']: note for note in self.client.get('/api/mobile/notes', headers=self.admin_h).get_json()}
        self.assertTrue(as_admin[member_note]['can_delete'])
        self.assertEqual(self.client.delete(f'/api/mobile/notes/{member_note}', headers=self.admin_h).status_code, 200)

    def test_grocery_comparison_from_the_app(self):
        note_id = self.add_note(self.member_h).get_json()['id']
        comparison = self.client.get(f'/api/mobile/notes/{note_id}/grocery-comparison', headers=self.member_h)
        self.assertEqual(comparison.status_code, 200)
        data = comparison.get_json()
        self.assertEqual(len(data['requested_items']), 3)
        self.assertTrue(data['stores'])

        other = self.add_note(self.member_h, title='Door code', description='1234').get_json()['id']
        self.assertEqual(self.client.get(f'/api/mobile/notes/{other}/grocery-comparison', headers=self.member_h).status_code, 400)


if __name__ == '__main__':
    unittest.main()
