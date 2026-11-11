# Splitmate Website Guide

**What this is:** a plain-language tour of everything the Splitmate website can do today, page by page, plus who can do what and a short technical overview at the end.
**Based on:** the code in `Splitmate-Web` as of November 2, 2026 (app version shown in Settings: *MVP 0.1, Launch Prep*).

---

## 1. Splitmate in one paragraph

Splitmate is a shared-living app for roommates, friends, and trips. You create a **group**, invite people, and then the group can **split expenses**, see **who owes whom**, **settle up** (by recording a cash/e-transfer payment or paying online through Stripe), keep a shared **task calendar** with reminders, and keep **shared notes**, including grocery lists that Splitmate can **price-compare across Toronto grocery stores**. Online payments earn **Splitmate Points** toward gift-card rewards. A separate **Admin area** lets the app owner watch user growth, manage accounts, and send "we miss you" reminder emails.

---

## 2. Who uses the site (roles)

| Role | Who they are | What they can do |
|---|---|---|
| **Visitor** | Not signed in | See Login, Register, Forgot Password, the Join Splitmate page, a group invite landing page, Privacy Policy and Terms. |
| **Member** | Any signed-in, verified user | Use every main page: Dashboard, Split, Tasks, Notes, Profile. Inside a group they can add expenses, record payments, add/complete tasks, and add/edit notes. |
| **Group admin** | The person who created a group | Everything a member can do, plus: invite, add and remove members, revoke invites, set nicknames, set the group's default split, and clear the group's recent expenses. The group admin can't be removed from their own group. |
| **App admin** | Emails listed in the `ADMIN_EMAILS` setting (defaults to the mail account) | Signs in separately at `/admin` to see reports, create/edit/suspend users, send password resets, and send inactivity reminders. Admin accounts can't be suspended or un-verified, and their email can only change through the setting. |

---

## 3. Accounts and sign-in

### Register
- Enter **full name, email, and password** (at least 6 characters). The email is checked for a realistic format and domain.
- Splitmate emails a **6-digit verification code (OTP)**. The code lasts **10 minutes**, and you can ask for a new one once every **60 seconds** ("Resend OTP").
- After verifying, you land on the Dashboard (or back on the invite you came from).

### Log in
- Email + password. A password show/hide toggle is built in.
- If the account isn't verified yet, Splitmate sends a fresh code and takes you to the verification page.
- **Suspended** accounts are blocked with a "contact an administrator" message.

### Forgot / reset password
- Enter your email and Splitmate sends a **reset link valid for 30 minutes** (not sent for suspended accounts).
- The link opens a page to choose a new password.

### Log out
- From the account menu (top right).

### Join Splitmate page (`/join`)
- The page a non-user lands on when someone invites them to the app. It offers Login or Register, with their email pre-filled.

---

## 4. Navigation and layout

- **Top bar:** Splitmate logo, then **Home**, **Split**, **Tasks**, **Notes**.
- **Account menu:** Profile, Membership, Settings, **Help Chat**, Log out.
- **Light / dark theme toggle:** follows your device setting the first time, then remembers your choice in the browser.
- Messages ("Expense added", "Invite sent", errors) pop up as banners after each action.
- The layout is responsive and works on phone screens.

---

## 5. Dashboard (Home)

The landing page after login. It pulls together everything across all your groups.

- **You Owe / You're Owed:** your unsettled totals across every group.
- **Your Groups:** a card for each group you're in, with a **Manage** button (see Group management below). **Create Group** opens a quick dialog where you type a group name.
- **Monthly Spending:** how much each group has spent so far this month.
- **Recent Activity:** the 10 newest expenses across your groups.
- **Spending Insights:**
  - Total spent, number of expenses, average expense, and top category.
  - **By Category** bar list (Groceries, Rent, Dining, and so on).
  - **By Group** bar list.
  - **Monthly Trend** for the last 6 months.
  - **Paid By:** the top 5 people who've paid the most.

Insights use the permanent transaction history, so they stay accurate even after a group clears its recent expenses.

---

## 6. Groups and invitations

Opened from **Manage** on a group card (also available on the Split, Tasks and Notes pages).

| Action | Who | Details |
|---|---|---|
| Create a group | Anyone | You become its admin and first member. |
| See members | Members | Each member shows their group nickname, full name and email. |
| **Invite by email** | Group admin | Creates a private invite link that lasts **7 days** and emails it. If email isn't set up, the link is shown so you can copy and share it yourself. Re-inviting the same email reuses the open link. |
| Add an existing user directly | Group admin | Type the email of someone who already has a Splitmate account and they're added right away. |
| Pending invites | Group admin | Lists open invites with a **Revoke** button. |
| Nicknames | Group admin | Give a member a display name for this group (for example "Sam (upstairs)"). Nicknames show everywhere in that group. |
| Remove a member | Group admin | Removes anyone except the admin. |
| **Invite a friend to Splitmate** | Anyone | Emails a non-user a link to the Join page (not tied to a group). |

**Accepting an invite (`/invite/<link>`):** a visitor sees who invited them and to which group, then logs in or registers. The invite only works for the email it was sent to, and expired, revoked or already-used links are rejected with a clear message.

---

## 7. Split Expenses page

This is the core money page. Pick a group at the top and everything below updates for that group.

### Add Expense
- **Description, Amount, Category, Paid By** (any group member, defaults to you).
- **Categories:** General, Groceries, Dining, Rent, Utilities, Transport, Travel, Entertainment, Shopping, Health, Other.
- **Receipt (optional):** upload an image (PNG, JPG, GIF, WEBP) or PDF; later shown as **View Receipt**.
- **Split Type:**
  - **Equal Split** – divided evenly among everyone.
  - **Split With Selected People** – equal split among only the people you tick (with Select All).
  - **Exact Amount** – type each person's share; must add up to the total.
  - **By Percentage** – type each person's percent; must add up to 100%.
  - Amounts are rounded to the cent and any leftover cent goes to the last person, so totals always match.
- **Default split:** the group admin can save a default (Equal, Selected People, or Percentage) so the form starts pre-filled for that group, and can reset it back to Equal.

### Balances
- For each member: what they've paid for others, what they owe, and their **net** (positive = owed money, negative = owes money). Settled amounts drop out.

### Expense Breakdown and Recent Expenses
- Each expense with who paid and how it was split per person, and its settled status.
- **Mark as settled:** only the person who paid an expense can mark someone's share as settled.
- **Clear Recent History (group admin only):** clears the group's active expenses and open balances. The permanent transaction history is kept, so insights, search, and CSV export still include them.

### Record Payment (settling up)
- Shows only the people **you currently owe**, with the amount.
- **Record Payment (manual):** log a cash or e-transfer payment. You can't pay more than you owe, and you can't pay yourself. The payment settles your oldest debts to that person first.
- **Pay online with Stripe** (only when Stripe keys are configured): opens a secure Stripe Checkout page in CAD by default. When Stripe confirms the payment, Splitmate settles the debt and awards **Splitmate Points**.

### Payment Activity
- The last 20 payments in the group with payer, receiver, method (manual or Stripe), status (Recorded, Pending, Paid) and points earned.

### Expense Search
- Searches the group's full history by **text, category, payer, date range, and min/max amount** (up to 50 results).

### Group analytics and export
- Group-level totals by category, top payers, and a 6-month trend.
- **Export CSV:** downloads every expense and payment in the group (Type, Date, Description, Category, Amount, Paid By, Payer, Receiver, Method, Status).

---

## 8. Tasks & Calendar page

A shared chore and to-do calendar for each group.

- **Add Task:** Title, Description (optional), **Due Date & Time**, **Reminder** time (optional), **Assign To** a member or "Anyone", **Priority** (Low, Medium, High), and **Repeat** (Does not repeat, Daily, Weekly, Monthly).
- **Calendar:** a month view with previous/next arrows; tasks appear on their due dates.
- **Upcoming Tasks:** list with priority, assignee, and an **overdue** flag for late, unfinished tasks.
- **Complete / un-complete** a task with one click. Completing a **repeating** task automatically creates the next one (for example next week's "Take out trash"), and won't create duplicates.
- **Delete** a task.
- **Browser reminders:** if Task Notifications are turned on in Settings and the browser allows it, Splitmate shows a desktop notification when a reminder time arrives. It checks every minute while the site is open.

---

## 9. Notes page

Shared notes for each group, such as house rules, wifi passwords, or shopping lists.

- **Add Note** with a Title and Description.
- **Edit**, **Delete**, and **mark as done** (checkbox).
- Each note shows who wrote it and when.

### Grocery price comparison
- When a note looks like a shopping list (its title or description mentions words like *grocery, shopping list, buy, store, pantry, Walmart, No Frills, meal prep*), a **compare prices** button appears.
- Write one item per line or separate items with commas. Quantities like "2 milk" or "3 x eggs" are understood.
- Splitmate matches each item against store catalogues and shows, for each store, the **total basket price**, which items are **in stock, out of stock or not found**, and highlights the **best grocery match** (cheapest store that has the items).
- **Prices source:** live weekly Toronto prices from TrimCart for **No Frills, Walmart, FreshCo, Metro, Food Basics and Sobeys** (refreshed at most every 6 hours). If that service is unreachable, a built-in demo catalogue is used instead, and the result says which source was used.

---

## 10. Profile & Settings page

### Account details
- Name, email, **verified / pending verification** badge, and join date.
- **Edit Details:** change name or email. Changing your email requires verifying the new address with a code.
- **Change Password:** current password, new password (6+ characters), and confirmation.

### Profile QR
- A QR code holding your Splitmate contact card, so a friend can scan it to get your name and email. **Download QR** saves it as an image.

### Splitmate Points (rewards)
- **1 point per dollar** paid through **Stripe** (manual payments don't earn points).
- Progress bar toward the next reward, with tiers: **500 pts = $5 gift card**, **1,000 pts = $10 gift card**, **2,500 pts = $25 gift card**.
- Your 5 most recent point earnings.

### Membership
- **Free** ($0): split expenses, tasks and notes; manual and Stripe settlement tracking; basic grocery price compare; earn points on Stripe payments.
- **Splitmate Plus** ($4.99/month, "Recommended"): ad-light experience, live grocery price history and alerts, advanced insights, 2x points promos, and priority support chat.
- Your current plan is marked. Upgrading shows **Billing Setup Needed** because paid billing isn't connected yet.

### Settings
- **Theme:** Light or Dark.
- **Task Notifications:** on/off, plus a **Browser Permission** "Allow" button and a status (allowed, blocked, not supported).
- **Help Chat:** opens the support assistant (below).
- **Account Data – Download:** exports your profile, groups, expenses, payments, tasks, notes, and rewards as a JSON file.
- **Privacy Policy** and **Terms** links.
- **App Version:** MVP 0.1 (Launch Prep).

---

## 11. Help Chat

A built-in "Splitmate Help" chat window, opened from the account menu or Settings. It gives instant, pre-written answers based on keywords in your question, covering invites, groups, splits and payments, tasks and reminders, notes and grocery prices, theme, points and rewards, membership, app-store launch, and profile/password. It isn't a live person or an AI. It's a quick FAQ helper.

---

## 12. Privacy Policy and Terms

Public pages (no login needed), last updated August 6, 2026.

- **Privacy:** what Splitmate stores (account, groups, expenses, payments, notes, tasks, device notification tokens, rewards, settings); that Stripe processes online payments; how notes are used for grocery comparison; possible ads and analytics in the free app; and data export from Settings. It notes that account deletion still needs to be added before a public launch.
- **Terms:** how the app may be used; only verified Stripe payments earn points, and redemptions may need identity/fraud checks; membership depends on the active plan and app-store billing; the free version may show ads; users should double-check balances and grocery prices.

---

## 13. Admin area (`/admin`)

A separate, owner-only back office with its own sign-in. Only verified accounts whose email is in `ADMIN_EMAILS` can enter.

### Dashboard
- Cards: **Total users** (and how many are verified), **New this month** (with change vs last month), **No split this month**, and **Reminder candidates**.
- **New Users by Month** growth chart.
- Shortcuts to the reports and reminder automation.

### Users report
- Tabs: **All Users, New This Month, No Split This Month, Never Used Core** (never split, paid, made a task or note), **Long Inactive, Suspended, Reminder Ready**.
- Per user: created date, last login, last usage, days idle, last reminder, number of groups, expenses and payments, and status.
- Show 10, 25, 50 or all rows.
- **Create User:** add an account by name and email; Splitmate emails them a password-setup link.
- **Manage a user:** edit name/email (**Save Profile**), toggle **Verified** and **Suspended** (**Save Status**), and **Send Password Reset**.

### Email reminders
- **Automation rules:** a user becomes a candidate after **30 days** of no activity, gets at most one reminder every **14 days**, and the job runs **daily at 14:00 UTC**. All of these can be changed in settings.
- Lists of **Reminder Candidates** and **Long Inactive Users** with how long they've been idle.
- **Send Reminders Now** button to run the job on demand.
- Only verified, non-suspended users are emailed.

---

## 14. Emails Splitmate sends

| Email | When |
|---|---|
| Verification code (OTP) | Registering, logging in unverified, or changing email |
| Password reset link | Forgot Password, or an admin clicking Send Password Reset / Create User |
| Group invite | A group admin invites someone |
| Splitmate invite | A user invites a friend to the app |
| Inactivity reminder | Daily automated job or the admin's "Send Reminders Now" |

All email goes through Gmail SMTP using the account in `.env`. If the mail password isn't set, the site still works and shows links or messages so you can share manually.

---

## 15. Mobile app support

The same backend powers the **Splitmate Expo mobile app** through a JSON API at `/api/mobile/...`. It covers everything above (login/register/OTP, dashboard, groups and invites, expenses, payments and Stripe, tasks, notes, grocery comparison, rewards, export, CSV) and adds a few app-only extras:

- **Editing expenses** (only by the payer or the group admin, and not after payments have settled them).
- **Push notification device registration** (Expo push tokens).
- A **people balances** view across all groups.
- A health-check endpoint.

The app signs in with a secure token that lasts 30 days instead of a browser cookie.

---

## 16. Not finished yet (worth knowing)

These are shown in the site but aren't fully working yet:

- **Splitmate Plus billing:** the plan is displayed but there's no payment flow ("Billing Setup Needed").
- **Redeeming points:** the site shows "Reward available" at 500 points, but there's no redeem/gift-card flow yet.
- **Account deletion:** the Privacy Policy says this must be added before public launch.
- **Grocery price history/alerts and ads:** listed as Plus/Free plan features but not built.
- **Task reminders on the website** only fire while a Splitmate tab is open (the mobile app handles push).

---

## 17. Technical overview

| Area | Details |
|---|---|
| Language / framework | Python 3.13, **Flask 3.0** with blueprints: `auth`, `main`, `split`, `tasks`, `notes`, `admin`, `mobile_api` |
| Database | **PostgreSQL** locally (database `splitmate`) via `DATABASE_URL`; falls back to SQLite if not set. **SQLAlchemy 2.0.49** (pinned) + Flask-SQLAlchemy, **Flask-Migrate/Alembic** migrations, and a one-off SQLite→Postgres migration script |
| Main data tables | User, Group (+ group_members with nicknames), Expense, ExpenseSplit, ExpenseHistory (permanent copy), Payment, RewardTransaction, Note, Task, GroupInvite, MobileDevice |
| Auth & security | Flask-Login sessions; hashed passwords and OTPs (Werkzeug); signed, time-limited reset links and mobile tokens; **CSRF protection** on all web forms (the token-based mobile API is exempt); safe redirect checks; CORS allow-list for the mobile web build |
| Payments | **Stripe Checkout** (optional, `STRIPE_SECRET_KEY`), currency CAD by default |
| Email | Gmail SMTP (`MAIL_USERNAME`, `MAIL_PASSWORD`) |
| Background jobs | **APScheduler** daily inactivity-reminder job; user "last activity" is updated at most every 5 minutes |
| Other libraries | `qrcode` (profile QR), `email-validator`, Flask-WTF |
| Frontend | Server-rendered Jinja templates, one stylesheet (`style.css`) with light/dark themes, vanilla JavaScript (`app.js` + page scripts), Inter font |
| File uploads | Receipts saved to `app/static/uploads/receipts` with random file names |
| Grocery data | TrimCart weekly Toronto prices (cached 6 h) with a built-in demo fallback |
| Tests | `tests/` – mobile API, web security, email validation (`python -m unittest discover tests`) |
| Run locally | From `Splitmate-Web`: `.\venv\Scripts\python.exe run.py`, then open http://127.0.0.1:5000 |
