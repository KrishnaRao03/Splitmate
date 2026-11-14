"""Categories are free text: built-ins keep their spelling, custom ones are kept, reused and charted."""
import unittest

from app import db
from app.models import Expense
from tests.test_security_fixes import SecurityFixTests


class CustomCategoryTests(SecurityFixTests):
    def add(self, category, description='Thing', amount='10'):
        return self.client.post(f'/api/mobile/groups/{self.group_id}/expenses', headers=self.admin_h, json={
            'description': description, 'amount': amount, 'split_type': 'equal', 'category': category})

    def test_custom_categories_are_saved_cleaned_and_matched(self):
        created = self.add('  Pet   supplies ')
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.get_json()['category'], 'Pet supplies')

        # A built-in typed in any case keeps its usual spelling.
        self.assertEqual(self.add('groceries').get_json()['category'], 'Groceries')
        # A custom one typed differently matches the group's existing spelling instead of making a duplicate.
        self.assertEqual(self.add('PET SUPPLIES').get_json()['category'], 'Pet supplies')
        # Blank still means General; very long labels are cut to the column size.
        self.assertEqual(self.add('').get_json()['category'], 'General')
        self.assertEqual(len(self.add('x' * 80).get_json()['category']), 40)

    def test_markup_is_refused(self):
        response = self.add('<script>')
        self.assertEqual(response.status_code, 400)
        self.assertIn('<', response.get_json()['error'])
        with self.app.app_context():
            self.assertEqual(Expense.query.filter_by(category='<script>').count(), 0)

    def test_group_suggestions_and_insights_include_custom_categories(self):
        self.add('Pet supplies', amount='25')
        detail = self.client.get(f'/api/mobile/groups/{self.group_id}', headers=self.admin_h).get_json()
        self.assertEqual(detail['expense_categories'][:2], ['General', 'Groceries'])
        self.assertIn('Pet supplies', detail['expense_categories'])
        self.assertEqual(detail['expense_categories'].count('Pet supplies'), 1)

        activity = self.client.get(f'/api/mobile/groups/{self.group_id}/activity?category=pet%20supplies',
                                   headers=self.admin_h).get_json()
        self.assertEqual([row['category'] for row in activity['expense_results']], ['Pet supplies'])
        totals = {row['category']: row['total'] for row in activity['analytics']['category_totals']}
        self.assertEqual(totals['Pet supplies'], 25.0)

        dashboard = self.client.get('/api/mobile/dashboard', headers=self.admin_h).get_json()
        self.assertIn('Pet supplies', [row['category'] for row in dashboard['spending_insights']['category_totals']])

    def test_editing_an_expense_keeps_its_custom_category(self):
        expense_id = self.add('Pet supplies').get_json()['id']
        edited = self.client.put(f'/api/mobile/expenses/{expense_id}', headers=self.admin_h, json={
            'description': 'Cat food', 'amount': '12', 'split_type': 'equal', 'category': 'Pet supplies'})
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.get_json()['category'], 'Pet supplies')
        with self.app.app_context():
            self.assertEqual(db.session.get(Expense, expense_id).category, 'Pet supplies')


if __name__ == '__main__':
    unittest.main()
