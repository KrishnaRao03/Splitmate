import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from app import create_app, db
from app.group_utils import set_member_nickname
from app.models import Expense, ExpenseHistory, ExpenseSplit, Group, GroupInvite, Note, Payment, RewardTransaction, Task, User
from app.routes.mobile_api import mobile_token_for
from config import Config


class MobileApiTestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    MAIL_PASSWORD = None
    RATELIMIT_ENABLED = False


class MobileApiParityTests(unittest.TestCase):
    def setUp(self):
        self.scheduler_patch = patch('app.scheduler.start_inactivity_scheduler', return_value=None)
        self.scheduler_patch.start()
        self.app = create_app(MobileApiTestConfig)
        self.client = self.app.test_client()

        with self.app.app_context():
            admin = User(email='admin@example.com', name='Admin User', is_email_verified=True)
            admin.set_password('password123')
            member = User(email='member@example.com', name='Member User', is_email_verified=True)
            member.set_password('password123')
            db.session.add_all([admin, member])
            db.session.flush()

            group = Group(name='Parity Group', admin_id=admin.id)
            group.members.extend([admin, member])
            db.session.add(group)
            db.session.flush()
            set_member_nickname(group.id, admin)
            set_member_nickname(group.id, member)

            expense = Expense(
                description='Dinner',
                amount=60,
                category='Dining',
                group_id=group.id,
                paid_by_id=member.id,
            )
            db.session.add(expense)
            db.session.flush()
            db.session.add(ExpenseSplit(
                expense_id=expense.id,
                user_id=admin.id,
                amount_owed=30,
            ))
            db.session.add(ExpenseHistory(
                description=expense.description,
                amount=expense.amount,
                category=expense.category,
                group_id=group.id,
                paid_by_id=member.id,
            ))
            db.session.add(Task(
                title='Pay rent',
                due_date=datetime.utcnow() + timedelta(days=2),
                priority='high',
                recurrence='monthly',
                group_id=group.id,
                created_by_id=admin.id,
            ))
            db.session.add(Payment(
                payer_id=admin.id,
                receiver_id=member.id,
                amount=10,
                group_id=group.id,
                method='manual',
                status='recorded',
            ))
            db.session.add(Note(
                title='Groceries',
                content='Groceries',
                description='milk, bread',
                group_id=group.id,
                created_by_id=admin.id,
            ))
            db.session.commit()

            self.admin_id = admin.id
            self.member_id = member.id
            self.group_id = group.id
            self.token = mobile_token_for(admin)

        self.headers = {'Authorization': f'Bearer {self.token}'}

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.scheduler_patch.stop()

    def test_only_payee_can_mark_split_settled(self):
        with self.app.app_context():
            split_id = ExpenseSplit.query.filter_by(user_id=self.admin_id).first().id
            member_headers = {'Authorization': f'Bearer {mobile_token_for(db.session.get(User, self.member_id))}'}

        # The admin owes this split, so they can't clear it themselves.
        response = self.client.post(f'/api/mobile/splits/{split_id}/settle', headers=self.headers)
        self.assertEqual(response.status_code, 403)

        response = self.client.post(f'/api/mobile/splits/{split_id}/settle', headers=member_headers)
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertTrue(db.session.get(ExpenseSplit, split_id).is_settled)

    def test_expense_edit_and_delete_permissions_and_rules(self):
        with self.app.app_context():
            expense = Expense.query.filter_by(description='Dinner').first()
            expense_id = expense.id
            member_token = mobile_token_for(User.query.get(self.member_id))
            admin_token = self.token
        member_headers = {'Authorization': f'Bearer {member_token}'}

        # Dinner was paid by the member and the admin owes 30 -> it is still unsettled, so it can be edited.
        edited = self.client.put(f'/api/mobile/expenses/{expense_id}', headers=member_headers, json={
            'description': 'Dinner out',
            'amount': '80.00',
            'category': 'Dining',
            'paid_by_id': self.member_id,
            'split_type': 'equal',
        })
        self.assertEqual(edited.status_code, 200)
        payload = edited.get_json()
        self.assertEqual(payload['description'], 'Dinner out')
        self.assertEqual(payload['amount'], 80.0)
        self.assertEqual(sorted(split['amount'] for split in payload['splits']), [40.0, 40.0])

        # Invalid edits are rejected with the same rules as creation.
        bad = self.client.put(f'/api/mobile/expenses/{expense_id}', headers=member_headers, json={
            'description': 'Dinner out', 'amount': '0', 'split_type': 'equal',
        })
        self.assertEqual(bad.status_code, 400)

        # A settled split blocks editing (it would resurrect the debt).
        with self.app.app_context():
            split = ExpenseSplit.query.filter_by(expense_id=expense_id, user_id=self.admin_id).first()
            split.is_settled = True
            db.session.commit()
        blocked = self.client.put(f'/api/mobile/expenses/{expense_id}', headers=member_headers, json={
            'description': 'Dinner out', 'amount': '80.00', 'split_type': 'equal',
        })
        self.assertEqual(blocked.status_code, 409)

        # Unrelated members cannot delete; the payer and the group admin can.
        with self.app.app_context():
            outsider = User(email='outsider@example.com', name='Outsider', is_email_verified=True)
            outsider.set_password('password123')
            db.session.add(outsider)
            db.session.commit()
            outsider_headers = {'Authorization': f'Bearer {mobile_token_for(outsider)}'}
        self.assertEqual(self.client.delete(f'/api/mobile/expenses/{expense_id}', headers=outsider_headers).status_code, 403)

        deleted = self.client.delete(f'/api/mobile/expenses/{expense_id}', headers={'Authorization': f'Bearer {admin_token}'})
        self.assertEqual(deleted.status_code, 200)
        with self.app.app_context():
            self.assertIsNone(Expense.query.get(expense_id))
            # History is an immutable audit log, so it keeps the original row.
            self.assertEqual(ExpenseHistory.query.filter_by(description='Dinner').count(), 1)

    def test_member_feature_parity_contracts(self):
        dashboard = self.client.get('/api/mobile/dashboard', headers=self.headers)
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.get_json()['groups'][0]['name'], 'Parity Group')

        detail = self.client.get(f'/api/mobile/groups/{self.group_id}', headers=self.headers)
        self.assertEqual(detail.status_code, 200)
        detail_payload = detail.get_json()
        self.assertIn('default_split', detail_payload)
        self.assertIn('expense_categories', detail_payload)
        self.assertIn('payment_options', detail_payload)

        profile = self.client.patch('/api/mobile/me', headers=self.headers, json={
            'name': 'Updated Admin',
            'email': 'admin@example.com',
        })
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.get_json()['user']['name'], 'Updated Admin')

        password = self.client.post('/api/mobile/me/password', headers=self.headers, json={
            'current_password': 'password123',
            'new_password': 'NewPassword123!',
            'confirm_password': 'NewPassword123!',
        })
        self.assertEqual(password.status_code, 200)
        # Changing the password revokes the old token; the response carries a fresh one.
        self.assertEqual(self.client.get('/api/mobile/me', headers=self.headers).status_code, 401)
        self.headers = {'Authorization': f'Bearer {password.get_json()["token"]}'}

        nickname = self.client.patch(
            f'/api/mobile/groups/{self.group_id}/members/{self.member_id}',
            headers=self.headers,
            json={'nickname': 'Roomie'},
        )
        self.assertEqual(nickname.status_code, 200)
        self.assertEqual(nickname.get_json()['nickname'], 'Roomie')

        default_split = self.client.put(
            f'/api/mobile/groups/{self.group_id}/default-split',
            headers=self.headers,
            json={'type': 'selected', 'member_ids': [self.admin_id], 'percentages': {}},
        )
        self.assertEqual(default_split.status_code, 200)
        self.assertEqual(default_split.get_json()['type'], 'selected')

        expense = self.client.post(
            f'/api/mobile/groups/{self.group_id}/expenses',
            headers=self.headers,
            json={
                'description': 'Utilities',
                'amount': '100.00',
                'category': 'Utilities',
                'paid_by_id': self.admin_id,
                'split_type': 'equal',
            },
        )
        self.assertEqual(expense.status_code, 201)
        self.assertEqual(expense.get_json()['category'], 'Utilities')

        with self.app.app_context():
            note_id = Note.query.filter_by(group_id=self.group_id).first().id
        note = self.client.patch(
            f'/api/mobile/notes/{note_id}',
            headers=self.headers,
            json={'title': 'Updated groceries', 'description': 'milk, bread, eggs'},
        )
        self.assertEqual(note.status_code, 200)
        self.assertEqual(note.get_json()['title'], 'Updated groceries')

        activity = self.client.get(
            f'/api/mobile/groups/{self.group_id}/activity?category=Utilities',
            headers=self.headers,
        )
        self.assertEqual(activity.status_code, 200)
        self.assertIn('analytics', activity.get_json())
        self.assertEqual(activity.get_json()['expense_results'][0]['category'], 'Utilities')

        with patch('app.routes.main.send_group_invite_email', return_value=False):
            invite = self.client.post(
                f'/api/mobile/groups/{self.group_id}/invites',
                headers=self.headers,
                json={'email': 'newmember@example.com'},
            )
        self.assertEqual(invite.status_code, 201)
        self.assertTrue(invite.get_json()['invite_url'])

        # In-app Stripe collection is gone; settling happens outside the app.
        stripe = self.client.post(
            f'/api/mobile/groups/{self.group_id}/payments/stripe',
            headers=self.headers,
            json={'receiver_id': self.member_id, 'amount': '10.00'},
        )
        self.assertEqual(stripe.status_code, 404)

    def test_all_notes_returns_only_current_users_groups_newest_first(self):
        with self.app.app_context():
            outsider = User(email='outsider-notes@example.com', name='Outsider Notes', is_email_verified=True)
            outsider.set_password('password123')
            db.session.add(outsider)
            db.session.flush()

            other_group = Group(name='Other Group', admin_id=outsider.id)
            other_group.members.append(outsider)
            db.session.add(other_group)
            db.session.flush()
            db.session.add(Note(
                title='Outsider note',
                content='Outsider note',
                description='should not be visible',
                group_id=other_group.id,
                created_by_id=outsider.id,
            ))

            second_group = Group(name='Second Group', admin_id=self.admin_id)
            second_group.members.extend([User.query.get(self.admin_id), User.query.get(self.member_id)])
            db.session.add(second_group)
            db.session.flush()
            db.session.add(Note(
                title='Newer note',
                content='Newer note',
                description='from second group',
                group_id=second_group.id,
                created_by_id=self.admin_id,
                created_at=datetime.utcnow() + timedelta(minutes=5),
            ))
            db.session.commit()

            self.second_group_id = second_group.id
            self.other_group_id = other_group.id

        response = self.client.get('/api/mobile/notes', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        notes = response.get_json()

        titles = [note['title'] for note in notes]
        self.assertIn('Newer note', titles)
        self.assertIn('Groceries', titles)
        self.assertNotIn('Outsider note', titles)

        group_ids = {note['group_id'] for note in notes}
        self.assertIn(self.group_id, group_ids)
        self.assertIn(self.second_group_id, group_ids)
        self.assertNotIn(self.other_group_id, group_ids)

        group_names = {note['group_name'] for note in notes}
        self.assertIn('Parity Group', group_names)
        self.assertIn('Second Group', group_names)
        self.assertNotIn('Other Group', group_names)

        # Newest first.
        self.assertEqual(notes[0]['title'], 'Newer note')

    def test_all_tasks_includes_no_reminder_and_overdue_and_isolates_membership(self):
        with self.app.app_context():
            outsider = User(email='outsider-tasks@example.com', name='Outsider Tasks', is_email_verified=True)
            outsider.set_password('password123')
            db.session.add(outsider)
            db.session.flush()

            other_group = Group(name='Other Tasks Group', admin_id=outsider.id)
            other_group.members.append(outsider)
            db.session.add(other_group)
            db.session.flush()
            db.session.add(Task(
                title='Outsider task',
                due_date=datetime.utcnow() + timedelta(days=1),
                group_id=other_group.id,
                created_by_id=outsider.id,
            ))

            # No reminder_time at all -> excluded from /reminders/upcoming but must appear here.
            db.session.add(Task(
                title='No reminder task',
                due_date=datetime.utcnow() + timedelta(days=3),
                group_id=self.group_id,
                created_by_id=self.admin_id,
            ))

            # Overdue and incomplete -> also excluded from /reminders/upcoming (reminder_time < now).
            db.session.add(Task(
                title='Overdue task',
                due_date=datetime.utcnow() - timedelta(days=1),
                reminder_time=datetime.utcnow() - timedelta(days=2),
                group_id=self.group_id,
                created_by_id=self.admin_id,
            ))
            db.session.commit()

        upcoming = self.client.get('/api/mobile/reminders/upcoming', headers=self.headers)
        self.assertEqual(upcoming.status_code, 200)
        upcoming_titles = {task['title'] for task in upcoming.get_json()}
        self.assertNotIn('No reminder task', upcoming_titles)
        self.assertNotIn('Overdue task', upcoming_titles)

        response = self.client.get('/api/mobile/tasks', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        tasks = response.get_json()
        titles = {task['title'] for task in tasks}

        # Superset of /reminders/upcoming: no-reminder and overdue tasks both show up.
        self.assertIn('No reminder task', titles)
        self.assertIn('Overdue task', titles)
        self.assertIn('Pay rent', titles)

        # Membership isolation: tasks from a group the caller isn't in never appear.
        self.assertNotIn('Outsider task', titles)

        overdue_task = next(task for task in tasks if task['title'] == 'Overdue task')
        self.assertTrue(overdue_task['is_overdue'])
        no_reminder_task = next(task for task in tasks if task['title'] == 'No reminder task')
        self.assertIsNone(no_reminder_task['reminder_time'])

    def test_people_balances_nets_across_groups_and_excludes_unshared_users(self):
        with self.app.app_context():
            alice = User(email='alice@example.com', name='Alice', is_email_verified=True)
            alice.set_password('password123')
            stranger = User(email='stranger@example.com', name='Stranger', is_email_verified=True)
            stranger.set_password('password123')
            db.session.add_all([alice, stranger])
            db.session.flush()

            admin = User.query.get(self.admin_id)

            # Group A: admin paid, Alice owes admin $10.
            group_a = Group(name='Group A', admin_id=self.admin_id)
            group_a.members.extend([admin, alice])
            db.session.add(group_a)
            db.session.flush()
            expense_a = Expense(
                description='Trip A',
                amount=20,
                category='General',
                group_id=group_a.id,
                paid_by_id=self.admin_id,
            )
            db.session.add(expense_a)
            db.session.flush()
            db.session.add(ExpenseSplit(expense_id=expense_a.id, user_id=self.admin_id, amount_owed=10))
            db.session.add(ExpenseSplit(expense_id=expense_a.id, user_id=alice.id, amount_owed=10))

            # Group B: Alice paid, admin owes Alice $15.
            group_b = Group(name='Group B', admin_id=alice.id)
            group_b.members.extend([admin, alice])
            db.session.add(group_b)
            db.session.flush()
            expense_b = Expense(
                description='Trip B',
                amount=30,
                category='General',
                group_id=group_b.id,
                paid_by_id=alice.id,
            )
            db.session.add(expense_b)
            db.session.flush()
            db.session.add(ExpenseSplit(expense_id=expense_b.id, user_id=alice.id, amount_owed=15))
            db.session.add(ExpenseSplit(expense_id=expense_b.id, user_id=self.admin_id, amount_owed=15))

            # Stranger shares no group with admin at all.
            stranger_group = Group(name='Stranger Group', admin_id=stranger.id)
            stranger_group.members.append(stranger)
            db.session.add(stranger_group)

            db.session.commit()
            self.alice_id = alice.id
            self.stranger_id = stranger.id
            self.group_a_id = group_a.id
            self.group_b_id = group_b.id

        response = self.client.get('/api/mobile/balances/people', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        people = response.get_json()

        user_ids = {person['user_id'] for person in people}
        # Stranger shares no group with the admin -> excluded entirely.
        self.assertNotIn(self.stranger_id, user_ids)
        # Member (Parity Group) shares a group but no unsettled debt -> still included with net 0.
        self.assertIn(self.member_id, user_ids)

        alice_entry = next(person for person in people if person['user_id'] == self.alice_id)
        # Admin owes Alice $10 in group A (owed TO admin, so -10 from admin's perspective is wrong
        # direction check below) and Alice owes admin... recompute via sign convention:
        # Group A: admin paid, alice owes 10 -> alice owes admin => net +10 (alice owes user).
        # Group B: alice paid, admin owes 15 -> admin owes alice => net -15 (user owes alice).
        # Combined net = 10 - 15 = -5 (user owes alice $5 overall) -- partial cancellation, not simple addition.
        self.assertEqual(alice_entry['net'], -5.0)

        groups_by_id = {group['group_id']: group['net'] for group in alice_entry['groups']}
        self.assertEqual(groups_by_id[self.group_a_id], 10.0)
        self.assertEqual(groups_by_id[self.group_b_id], -15.0)

    def test_group_activity_csv_export(self):
        with self.app.app_context():
            admin_session_id = db.session.get(User, self.admin_id).get_id()
        with self.client.session_transaction() as session:
            session['_user_id'] = admin_session_id
            session['_fresh'] = True

        response = self.client.get(f'/split/api/group/{self.group_id}/activity.csv')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'text/csv')
        self.assertIn('Splitmate_Parity_Group_activity.csv', response.headers['Content-Disposition'])

        csv_text = response.get_data(as_text=True)
        self.assertIn('Type,Date,Description,Category,Amount,Paid By,Payer,Receiver,Method,Status', csv_text)
        self.assertIn('Expense,', csv_text)
        self.assertIn('Dinner', csv_text)
        self.assertIn('Payment,', csv_text)
        self.assertIn('recorded', csv_text)

    def test_search_group_expenses_filters_by_text_and_category_and_checks_membership(self):
        with self.app.app_context():
            group = Group.query.get(self.group_id)
            db.session.add(ExpenseHistory(
                description='Grocery run',
                amount=45,
                category='Groceries',
                group_id=group.id,
                paid_by_id=self.admin_id,
            ))
            db.session.add(ExpenseHistory(
                description='Movie night',
                amount=25,
                category='Entertainment',
                group_id=group.id,
                paid_by_id=self.admin_id,
            ))
            db.session.commit()

            outsider = User(email='outsider-search@example.com', name='Outsider Search', is_email_verified=True)
            outsider.set_password('password123')
            db.session.add(outsider)
            db.session.commit()
            outsider_headers = {'Authorization': f'Bearer {mobile_token_for(outsider)}'}

        # Text search ('q') matches description case-insensitively.
        text_search = self.client.get(
            f'/api/mobile/groups/{self.group_id}/expenses/search?q=grocery',
            headers=self.headers,
        )
        self.assertEqual(text_search.status_code, 200)
        text_results = text_search.get_json()
        descriptions = {item['description'] for item in text_results}
        self.assertEqual(descriptions, {'Grocery run'})

        # Category filter matches exactly (normalized) and excludes other categories.
        category_search = self.client.get(
            f'/api/mobile/groups/{self.group_id}/expenses/search?category=Entertainment',
            headers=self.headers,
        )
        self.assertEqual(category_search.status_code, 200)
        category_results = category_search.get_json()
        self.assertEqual({item['description'] for item in category_results}, {'Movie night'})
        self.assertEqual(category_results[0]['category'], 'Entertainment')

        # A user who is not a member of the group is rejected.
        unauthorized = self.client.get(
            f'/api/mobile/groups/{self.group_id}/expenses/search?q=grocery',
            headers=outsider_headers,
        )
        self.assertIn(unauthorized.status_code, (403, 404))

    def test_export_group_activity_csv_returns_csv_for_member_and_blocks_non_member(self):
        with self.app.app_context():
            outsider = User(email='outsider-csv@example.com', name='Outsider Csv', is_email_verified=True)
            outsider.set_password('password123')
            db.session.add(outsider)
            db.session.commit()
            outsider_headers = {'Authorization': f'Bearer {mobile_token_for(outsider)}'}

        response = self.client.get(
            f'/api/mobile/groups/{self.group_id}/activity.csv',
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'text/csv')
        body = response.get_data(as_text=True)
        self.assertIn('Dinner', body)
        self.assertIn('10.00', body)
        self.assertTrue(body.strip())

        unauthorized = self.client.get(
            f'/api/mobile/groups/{self.group_id}/activity.csv',
            headers=outsider_headers,
        )
        self.assertIn(unauthorized.status_code, (403, 404))

    def test_export_my_data_scopes_to_current_user_and_isolates_other_groups(self):
        with self.app.app_context():
            outsider = User(email='outsider-export@example.com', name='Outsider Export', is_email_verified=True)
            outsider.set_password('password123')
            db.session.add(outsider)
            db.session.flush()

            other_group = Group(name='Other Export Group', admin_id=outsider.id)
            other_group.members.append(outsider)
            db.session.add(other_group)
            db.session.flush()
            other_expense = Expense(
                description='Outsider expense',
                amount=99,
                category='General',
                group_id=other_group.id,
                paid_by_id=outsider.id,
            )
            db.session.add(other_expense)
            db.session.add(Task(
                title='Outsider task',
                due_date=datetime.utcnow() + timedelta(days=1),
                group_id=other_group.id,
                created_by_id=outsider.id,
            ))
            db.session.add(Note(
                title='Outsider note',
                content='Outsider note',
                group_id=other_group.id,
                created_by_id=outsider.id,
            ))
            db.session.commit()
            other_group_id = other_group.id

        response = self.client.get('/api/mobile/export', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        self.assertEqual(data['profile']['email'], 'admin@example.com')

        group_ids = {group['id'] for group in data['groups']}
        self.assertIn(self.group_id, group_ids)
        self.assertNotIn(other_group_id, group_ids)

        expense_descriptions = {expense['description'] for expense in data['expenses']}
        self.assertIn('Dinner', expense_descriptions)
        self.assertNotIn('Outsider expense', expense_descriptions)

        task_titles = {task['title'] for task in data['tasks']}
        self.assertIn('Pay rent', task_titles)
        self.assertNotIn('Outsider task', task_titles)

        note_titles = {note['title'] for note in data['notes']}
        self.assertIn('Groceries', note_titles)
        self.assertNotIn('Outsider note', note_titles)

        self.assertIn('payments', data)
        self.assertIn('rewards', data)


    def test_dashboard_insights_include_group_totals_average_and_trend(self):
        response = self.client.get('/api/mobile/dashboard', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        insights = response.get_json()['spending_insights']

        self.assertEqual(insights['count'], 1)
        self.assertEqual(insights['average'], 60.0)
        self.assertEqual(insights['group_totals'], [{'name': 'Parity Group', 'total': 60.0}])
        self.assertEqual(len(insights['monthly_totals']), 6)
        # The setUp expense was added this month, so it lands in the last bucket.
        self.assertEqual(insights['monthly_totals'][-1]['total'], 60.0)

    def test_me_includes_join_date_and_rewards_include_tiers_recent_and_plans(self):
        me = self.client.get('/api/mobile/me', headers=self.headers).get_json()
        self.assertTrue(me['user']['created_at'])

        with self.app.app_context():
            payment = Payment.query.first()
            for index in range(7):
                db.session.add(RewardTransaction(
                    user_id=self.admin_id,
                    points=10 + index,
                    type='earn',
                    note='Stripe payment reward',
                    created_at=datetime.utcnow() - timedelta(days=7 - index),
                    payment_id=payment.id if index == 0 else None,
                ))
            db.session.commit()

        rewards = self.client.get('/api/mobile/rewards', headers=self.headers).get_json()
        self.assertEqual([tier['points'] for tier in rewards['tiers']], [500, 1000, 2500])
        self.assertEqual([plan['id'] for plan in rewards['membership_plans']], ['free', 'pro_month', 'pro_year'])
        self.assertEqual(len(rewards['recent_transactions']), 5)
        # Newest first.
        self.assertEqual(rewards['recent_transactions'][0]['points'], 16)

    def test_profile_qr_returns_contact_card_and_square_matrix(self):
        response = self.client.get('/api/mobile/me/qr', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('BEGIN:VCARD', data['payload'])
        self.assertIn('EMAIL:admin@example.com', data['payload'])
        self.assertEqual(len(data['rows']), data['size'])
        self.assertTrue(all(len(row) == data['size'] and set(row) <= {'0', '1'} for row in data['rows']))
        self.assertEqual(self.client.get('/api/mobile/me/qr').status_code, 401)

    def test_invitee_can_list_and_accept_group_invites_in_app(self):
        with self.app.app_context():
            invitee = User(email='invitee@example.com', name='Invitee', is_email_verified=True)
            invitee.set_password('password123')
            db.session.add(invitee)
            db.session.flush()
            live = GroupInvite(group_id=self.group_id, email='invitee@example.com', token='live-token',
                               invited_by_id=self.admin_id, expires_at=datetime.utcnow() + timedelta(days=7))
            by_link = GroupInvite(group_id=self.group_id, email='invitee@example.com', token='link-token',
                                  invited_by_id=self.admin_id, expires_at=datetime.utcnow() + timedelta(days=7))
            expired = GroupInvite(group_id=self.group_id, email='invitee@example.com', token='old-token',
                                  invited_by_id=self.admin_id, expires_at=datetime.utcnow() - timedelta(days=1))
            other = GroupInvite(group_id=self.group_id, email='someone@example.com', token='other-token',
                                invited_by_id=self.admin_id, expires_at=datetime.utcnow() + timedelta(days=7))
            db.session.add_all([live, by_link, expired, other])
            db.session.commit()
            invitee_headers = {'Authorization': f'Bearer {mobile_token_for(invitee)}'}
            invitee_id, live_id, other_id = invitee.id, live.id, other.id

        listed = self.client.get('/api/mobile/invites', headers=invitee_headers).get_json()
        self.assertIn(live_id, {row['id'] for row in listed})
        self.assertNotIn(other_id, {row['id'] for row in listed})
        self.assertTrue(all(row['group_name'] == 'Parity Group' for row in listed))

        # Someone else's invite can't be accepted, and an expired link is rejected.
        self.assertEqual(self.client.post(f'/api/mobile/invites/{other_id}/accept', headers=invitee_headers).status_code, 403)
        expired_response = self.client.post('/api/mobile/invites/accept-link', headers=invitee_headers,
                                            json={'link': 'http://localhost:5000/invite/old-token'})
        self.assertEqual(expired_response.status_code, 410)

        accepted = self.client.post(f'/api/mobile/invites/{live_id}/accept', headers=invitee_headers)
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.get_json()['group']['id'], self.group_id)
        self.assertEqual(self.client.post(f'/api/mobile/invites/{live_id}/accept', headers=invitee_headers).status_code, 409)

        # Once a member, the remaining invite is hidden from the list but its link still resolves cleanly.
        self.assertEqual(self.client.get('/api/mobile/invites', headers=invitee_headers).get_json(), [])
        by_link_response = self.client.post('/api/mobile/invites/accept-link', headers=invitee_headers,
                                            json={'link': 'https://splitmate.example/invite/link-token/'})
        self.assertEqual(by_link_response.status_code, 200)

        with self.app.app_context():
            group = db.session.get(Group, self.group_id)
            self.assertIn(invitee_id, [member.id for member in group.members])
            self.assertEqual(db.session.get(GroupInvite, live_id).accepted_by_id, invitee_id)

    def test_receipt_scan_validates_upload_and_returns_parsed_items(self):
        import io
        import json as jsonlib
        from types import SimpleNamespace
        from app import receipt_scan

        def upload(data=b'fake-image', name='receipt.jpg', mimetype='image/jpeg'):
            return {'receipt': (io.BytesIO(data), name, mimetype)}

        # Not signed in, nothing attached, wrong file type.
        self.assertEqual(self.client.post('/api/mobile/receipts/scan').status_code, 401)
        self.assertEqual(self.client.post('/api/mobile/receipts/scan', headers=self.headers, data={}).status_code, 400)
        bad_type = self.client.post('/api/mobile/receipts/scan', headers=self.headers,
                                    data=upload(name='r.pdf', mimetype='application/pdf'), content_type='multipart/form-data')
        self.assertEqual(bad_type.status_code, 400)

        # Without an API key the server says scanning isn't set up.
        with patch.dict('os.environ', {'GEMINI_API_KEY': ''}):
            missing_key = self.client.post('/api/mobile/receipts/scan', headers=self.headers,
                                           data=upload(), content_type='multipart/form-data')
        self.assertEqual(missing_key.status_code, 503)

        reply = {
            'is_receipt': True, 'merchant': 'No Frills', 'currency': 'CAD',
            'items': [
                {'name': 'Milk 2L', 'quantity': 1, 'price': 4.99},
                {'name': 'Eggs', 'quantity': 2, 'price': 7.004},
                {'name': '  ', 'quantity': 1, 'price': 1},
            ],
            'tax': 0, 'total': 11.99,
        }
        captured = {}

        class FakeModels:
            def generate_content(self, **kwargs):
                captured.update(kwargs)
                return SimpleNamespace(candidates=[SimpleNamespace(finish_reason='STOP')],
                                       text=jsonlib.dumps(reply))

        fake_client = SimpleNamespace(models=FakeModels())
        with patch.object(receipt_scan.genai, 'Client', return_value=fake_client), \
                patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'}):
            response = self.client.post('/api/mobile/receipts/scan', headers=self.headers,
                                        data=upload(mimetype='image/jpg'), content_type='multipart/form-data')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['merchant'], 'No Frills')
        self.assertEqual([item['name'] for item in data['items']], ['Milk 2L', 'Eggs'])
        self.assertEqual(data['items'][1]['price'], 7.0)
        self.assertEqual(data['total'], 11.99)
        # The image goes to the model as inline JPEG bytes with a JSON schema for the reply.
        image_part = captured['contents'][0]
        self.assertEqual(image_part.inline_data.mime_type, 'image/jpeg')
        self.assertEqual(image_part.inline_data.data, b'fake-image')
        self.assertEqual(captured['config'].response_mime_type, 'application/json')
        self.assertEqual(captured['config'].response_json_schema, receipt_scan.RECEIPT_SCHEMA)

        # A photo that isn't a receipt is reported clearly.
        reply.update({'is_receipt': False, 'items': []})
        with patch.object(receipt_scan.genai, 'Client', return_value=fake_client), \
                patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'}):
            not_receipt = self.client.post('/api/mobile/receipts/scan', headers=self.headers,
                                           data=upload(), content_type='multipart/form-data')
        self.assertEqual(not_receipt.status_code, 422)


if __name__ == '__main__':
    unittest.main()
