# Changelog: Splitmate-Web

All notable changes to the backend and website. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed
- Changing your email no longer swaps it straight away. The new address waits in `pending_email` (new column, added at start-up) until its emailed code is entered; until then you keep signing in with the old one. New app endpoints `POST /api/mobile/me/email/verify` (returns a fresh token) and `/api/mobile/me/email/resend`. Group invites and Quick split only match verified emails.
- Typing an email into Register no longer deletes an old unverified account with that email. It is replaced only once the new sign-up's code is entered, and never if it has a subscription or points.
- Editing an expense after a part payment is refused, like after a full one. `expense_split` gets `share_amount` (the share as added) so part payments can be told apart.
- Settling up (whole person, one share, or deleting the expense) cancels payments still waiting for confirmation (new `cancelled` status) and marks money requests `settled`, so an old approval doesn't carry over to new debts and a late confirm can't record $0. Settling one share twice is refused, and it now records a confirmed payment.
- After a declined money request, the same person can be asked again after a day.
- Confirming or declining a payment, answering a money request, accepting an invite, spending points, counting wrong passwords and using a free scan or comparison now lock the row first, so two requests at once can't both get through. A failed scan or comparison gives the use back.
- Stripe: webhooks re-read the subscription from Stripe so a late event can't turn Pro back on; an ended subscription is forgotten so the admin panel can give or remove Pro again; checkout is refused while a just-paid subscription waits for its webhook.
- Un-ticking a recurring task removes the next repeat it created. Task and note toggles accept `{"is_completed": true|false}`, so a double tap can't flip them back.
- The inactive-user reminder also runs a couple of minutes after the server starts, since the free server is often asleep at the daily time.

### Removed
- The leftover Interac email confirmation (`/api/mobile/me/interac/verify`, `/resend` and the website form).

### Added
- Admin-only email: addresses in `ADMIN_EMAILS` open `/admin` only. They can't sign in to the website or app, sign up, or be taken by a profile email change, and Quick split doesn't match them. `/admin/setup` emails the admin address a link to create or reset its password (the link also verifies it). The System page warns when an admin account also belongs to groups. `ADMIN_EMAILS` no longer falls back to `MAIL_USERNAME`.
- Admin dashboard reorganized: grouped side menu with icons (People, Money, Outreach, Settings), a slide-in menu on phones, an Overview with key numbers and a "Needs attention" row, a collapsible "Add a user" form, and every table turns into stacked cards on phone screens.
- Invite people by mobile number. `POST /api/mobile/groups/<id>/invites` takes `{"phone": ...}` as well as `{"email": ...}` and returns the invite link plus `sms_message`, which the app opens in the phone's own Messages app (no SMS service). `POST /api/mobile/invite-splitmate` takes `{"phone": ...}` the same way. `group_invite` gets `phone` (encrypted) and `phone_hash` columns, added automatically at start-up. A mobile invite can be accepted by the account with that number, or by an account with no number yet, which then gets it.
- `GET /api/mobile/friends` lists people you share a group with (`?group_id=` adds `in_group` / `invited`), and `POST /api/mobile/groups/<id>/invites` takes `{"friend_id": ...}` to invite one of them by their account email.

### Changed
- Dashboard: Recent activity removed. Spending insights keeps the totals, with a "View all" link on the heading's line that opens a new `/insights` page holding By category, Monthly trend, By group and Paid by.
- Expenses are shown only to the person who paid and the people in the split, in every list, history, search, chart, dashboard and export, on the website and in the app. Other group members, including the admin, no longer see them. `expense_history` gets `participant_ids` and `expense_id`; at start-up existing rows are matched to their live expense, and rows whose expense was already deleted stay visible to the payer only. Receipts follow the same rule.
- Grocery comparison uses real prices only: weekly TrimCart data, plus a Gemini + Google Search lookup of the stores' websites for items the weekly data lacks. The automatic fallback to sample prices is gone.
- New "Compare grocery prices" box on the Notes screen (app and website): type a list, get stores sorted cheapest first (`POST /api/mobile/grocery/compare`).
- Emails (verification code, password reset, invites, reminders) are branded HTML with a plain-text fallback.
- New passwords need at least 8 characters with an uppercase letter, a lowercase letter, a number and a special character. Sign-in is unchanged, so existing passwords keep working.
- Email addresses with cut-short or mistyped provider domains (name@gmail.c, name@gmail.co, name@gmial.com) are refused with a "Did you mean" suggestion.
- Sign-ups are stored in a new `pending_registration` table until the emailed code is verified; the `user` row is created only after verification (website and mobile API). Unverified sign-ups older than 7 days are cleared out.

### Added
- Admin panel: Groups (with group detail and invite revoking), Activity (expenses and payments), Audit Log and System pages.
- Admin user actions: sign out everywhere, delete never-used accounts (typed confirmation), CSV export.
- Every admin action and sign-in attempt is recorded in a new `admin_audit_log` table.
- Admin sessions end after 30 minutes of inactivity.
- `cryptography` dependency (pinned).

### Security
- Interac e-mail, PayPal username and UPI ID are encrypted in the database with `FIELD_ENCRYPTION_KEY` (Fernet). Existing rows are encrypted at start-up.
- `scripts/protect_env.py` encrypts secrets in `.env` with Windows DPAPI, and `config.py` decrypts them at start-up.
- `config.py` no longer falls back to a personal Gmail address.

## [0.1.0] - 2026-11-11

First documented release.

### Added
- Mobile API under `/api/mobile` with bearer tokens that can be revoked (see `docs/API.md`).
- Receipt scanning with Google Gemini (`GEMINI_API_KEY`).
- Grocery price comparison for notes (`GROCERY_PRICE_SOURCE`).
- Rewards points and membership plans.
- Group management: rename, admin hand-over, leave, delete, invite links with QR codes, nicknames, default splits, custom categories.
- Payment confirmation and decline, per-person balances, payment handles (Interac, PayPal, UPI), profile QR code, data export, activity CSV export.
- Task priority, recurrence and assignees.
- Admin dashboard with user management and inactivity reminder emails.
- PostgreSQL support through `DATABASE_URL`, plus a SQLite-to-PostgreSQL migration script.
- unittest suite (70 tests).

### Changed
- Moved the backend into `Splitmate-Web/` inside the Splitmate repository.
- `.env.example` lists every supported variable, with placeholder values only.

### Security
- Fixes from `docs/SECURITY_AUDIT.md`: no token from verify-email for already-verified accounts, debug mode off by default, CSRF on web forms, rate limits on sign-in and email routes, safe login redirects, upload size limit, updated Werkzeug, payments pending until the receiver confirms, OTP lockout after five wrong guesses, token revocation on password change, members join only by accepting an invite.

### Removed
- Stripe payments. `STRIPE_CURRENCY` is kept only as the display currency setting.
