"""Who can see an expense: only the payer and the people it is split with."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import create_app, db
from app.expense_visibility import (
    can_see_expense, participant_ids_text, visible_expenses, visible_history,
)
from app.models import Expense, ExpenseHistory, ExpenseSplit, Group, User
from config import Config


class VisibilityConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    MAIL_PASSWORD = None
    BREVO_API_KEY = None
    RATELIMIT_ENABLED = False
    WTF_CSRF_ENABLED = False


class ParticipantIdsTextTests(unittest.TestCase):
    def test_includes_payer_sorted_without_duplicates(self):
        self.assertEqual(participant_ids_text(3, [5, 1, 3, 5]), ',1,3,5,')

    def test_skips_empty_ids_and_accepts_text(self):
        self.assertEqual(participant_ids_text('2', [None, 0, '7']), ',2,7,')

    def test_payer_only(self):
        self.assertEqual(participant_ids_text(4, []), ',4,')


class ExpenseVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.scheduler = patch('app.scheduler.start_inactivity_scheduler', return_value=None)
        self.scheduler.start()
        self.app = create_app(VisibilityConfig)
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.payer, self.sharer, self.outsider = (
            User(email=f'{name}@example.com', name=name.title()) for name in ('payer', 'sharer', 'outsider')
        )
        for user in (self.payer, self.sharer, self.outsider):
            user.set_password('Strong-pass-1')
        db.session.add_all([self.payer, self.sharer, self.outsider])
        db.session.flush()
        group = Group(name='Flat', admin_id=self.outsider.id)
        group.members.extend([self.payer, self.sharer, self.outsider])
        db.session.add(group)
        db.session.flush()
        self.expense = Expense(description='Pizza', amount=20, group_id=group.id, paid_by_id=self.payer.id)
        db.session.add(self.expense)
        db.session.flush()
        db.session.add(ExpenseSplit(expense_id=self.expense.id, user_id=self.sharer.id, amount_owed=10))
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        self.scheduler.stop()

    def test_payer_and_sharer_see_it_but_group_admin_does_not(self):
        self.assertTrue(can_see_expense(self.expense, self.payer))
        self.assertTrue(can_see_expense(self.expense, self.sharer))
        self.assertFalse(can_see_expense(self.expense, self.outsider))

    def test_visible_expenses_filters_the_query(self):
        self.assertEqual(visible_expenses(Expense.query, self.sharer).count(), 1)
        self.assertEqual(visible_expenses(Expense.query, self.outsider).count(), 0)

    def test_history_id_match_does_not_leak_to_a_similar_id(self):
        # User 1 must not match a row shared with user 11.
        db.session.add(ExpenseHistory(description='Taxi', amount=5, participant_ids=',11,'))
        db.session.commit()
        query = ExpenseHistory.query.filter_by(description='Taxi')
        self.assertEqual(visible_history(query, SimpleNamespace(id=1)).count(), 0)
        self.assertEqual(visible_history(query, SimpleNamespace(id=11)).count(), 1)

    def test_history_counts_people_added_to_the_live_expense_later(self):
        db.session.add(ExpenseHistory(
            description='Pizza', amount=20, expense_id=self.expense.id,
            participant_ids=participant_ids_text(self.payer.id, []),
        ))
        db.session.commit()
        self.assertEqual(visible_history(ExpenseHistory.query, self.sharer).count(), 1)
        self.assertEqual(visible_history(ExpenseHistory.query, self.outsider).count(), 0)


if __name__ == '__main__':
    unittest.main()
