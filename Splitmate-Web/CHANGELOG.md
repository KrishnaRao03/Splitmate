# Changelog: Splitmate-Web

All notable changes to the backend and website. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
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
