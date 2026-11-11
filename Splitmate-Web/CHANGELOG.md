# Changelog: Splitmate-Web

All notable changes to the backend and website. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
