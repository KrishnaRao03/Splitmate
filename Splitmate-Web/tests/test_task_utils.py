"""Unit tests for the small date and value helpers behind repeating tasks."""
import unittest
from datetime import datetime
from types import SimpleNamespace

from app.task_utils import (
    add_one_month,
    next_recurring_datetime,
    normalize_task_priority,
    normalize_task_recurrence,
    task_is_overdue,
)


class AddOneMonthTests(unittest.TestCase):
    def test_moves_to_the_same_day_next_month(self):
        self.assertEqual(add_one_month(datetime(2026, 3, 15, 9, 30)), datetime(2026, 4, 15, 9, 30))

    def test_december_rolls_into_january_of_next_year(self):
        self.assertEqual(add_one_month(datetime(2026, 12, 10)), datetime(2027, 1, 10))

    def test_month_end_is_clamped_to_the_shorter_month(self):
        self.assertEqual(add_one_month(datetime(2026, 1, 31)), datetime(2026, 2, 28))
        self.assertEqual(add_one_month(datetime(2026, 3, 31)), datetime(2026, 4, 30))

    def test_leap_year_february_keeps_the_29th(self):
        self.assertEqual(add_one_month(datetime(2028, 1, 31)), datetime(2028, 2, 29))


class NextRecurringDatetimeTests(unittest.TestCase):
    start = datetime(2026, 11, 17, 8, 0)

    def test_each_repeat_option(self):
        self.assertEqual(next_recurring_datetime(self.start, 'daily'), datetime(2026, 11, 18, 8, 0))
        self.assertEqual(next_recurring_datetime(self.start, 'weekly'), datetime(2026, 11, 24, 8, 0))
        self.assertEqual(next_recurring_datetime(self.start, 'monthly'), datetime(2026, 12, 17, 8, 0))

    def test_repeat_value_is_case_and_space_insensitive(self):
        self.assertEqual(next_recurring_datetime(self.start, '  Weekly '), datetime(2026, 11, 24, 8, 0))

    def test_no_next_date_without_a_date_or_repeat(self):
        self.assertIsNone(next_recurring_datetime(None, 'daily'))
        self.assertIsNone(next_recurring_datetime(self.start, 'none'))
        self.assertIsNone(next_recurring_datetime(self.start, 'yearly'))


class NormalizeTests(unittest.TestCase):
    def test_priority_falls_back_to_medium(self):
        self.assertEqual(normalize_task_priority(' HIGH '), 'high')
        self.assertEqual(normalize_task_priority(None), 'medium')
        self.assertEqual(normalize_task_priority('urgent'), 'medium')

    def test_recurrence_falls_back_to_none(self):
        self.assertEqual(normalize_task_recurrence('Monthly'), 'monthly')
        self.assertEqual(normalize_task_recurrence(''), 'none')
        self.assertEqual(normalize_task_recurrence('hourly'), 'none')


class TaskIsOverdueTests(unittest.TestCase):
    now = datetime(2026, 11, 17, 12, 0)

    def task(self, due_date, is_completed=False):
        return SimpleNamespace(due_date=due_date, is_completed=is_completed)

    def test_past_due_and_not_done_is_overdue(self):
        self.assertTrue(task_is_overdue(self.task(datetime(2026, 11, 16)), now=self.now))

    def test_future_completed_or_undated_tasks_are_not_overdue(self):
        self.assertFalse(task_is_overdue(self.task(datetime(2026, 11, 18)), now=self.now))
        self.assertFalse(task_is_overdue(self.task(datetime(2026, 11, 16), is_completed=True), now=self.now))
        self.assertFalse(task_is_overdue(self.task(None), now=self.now))


if __name__ == '__main__':
    unittest.main()
