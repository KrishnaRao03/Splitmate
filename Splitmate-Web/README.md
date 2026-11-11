# Splitmate-Web

The Flask backend for Splitmate. It serves:

- **the website**: sign-up, groups, expense splitting, payments, notes, tasks, profile;
- **the admin dashboard** at `/admin`: user growth, user management, inactivity reminder emails;
- **the mobile API** at `/api/mobile`: the JSON API used by [`../Splitmate-App`](../Splitmate-App/README.md). It is documented in [`docs/API.md`](docs/API.md).

## Features

- Accounts: registration with email verification codes (OTP), login, password reset, "log out everywhere", account suspension by admins
- Groups: create, rename, delete, transfer admin, leave, invite by email or link (invites expire after 7 days), member nicknames
- Expenses: equal, selected-members, exact-amount and percentage splits; categories (including custom ones); a default split per group; receipt photos; search and filters; CSV export
- Settling up: record payments between members, confirm or decline incoming payments, settle single splits, per-person balances across all groups
- Payment handles: Interac e-mail, PayPal username and UPI ID on the profile, plus a profile QR code
- Receipt scanning: reads totals and line items from a receipt photo with Google Gemini (optional)
- Notes and grocery lists, with a grocery price comparison across stores (live TrimCart data or a demo catalogue)
- Tasks with due dates, reminders, assignees, priority and recurrence
- Rewards points and membership plans
- Insights: monthly spending and totals by category, payer and group
- Inactive-user reminder emails, sent daily by a background scheduler
- Security: CSRF protection on web forms, rate limits on sign-in and email-sending routes, signed and revocable mobile tokens, upload size limits

## Tech stack

| Area | Choice |
| --- | --- |
| Language | Python 3.13 (3.11+ should work) |
| Web framework | Flask 3.1, Jinja templates, plain CSS/JS in `app/static` |
| Database | SQLAlchemy 2 via Flask-SQLAlchemy. SQLite by default, PostgreSQL in production (`psycopg2-binary`) |
| Auth | Flask-Login (web sessions), `itsdangerous` signed tokens (mobile) |
| Security | Flask-WTF (CSRF), Flask-Limiter (rate limits) |
| Background jobs | APScheduler (daily inactivity emails) |
| Email | SMTP (Gmail app password) |
| AI | `google-genai` for receipt scanning |
| Other | `qrcode`, `email-validator`, Flask-Migrate (Alembic) |

## Folder structure

```text
Splitmate-Web/
├── app/
│   ├── __init__.py            App factory, extensions, start-up schema upgrades, CORS for /api/mobile
│   ├── models.py              SQLAlchemy models (User, Group, Expense, ExpenseSplit, ExpenseHistory,
│   │                          Payment, RewardTransaction, Note, Task, GroupInvite, MobileDevice)
│   ├── routes/
│   │   ├── auth.py            Login, register, verify email, password reset, invites, profile
│   │   ├── main.py            Home/dashboard, groups, members, invites, legal pages
│   │   ├── split.py           Expenses, splits, payments, balances, analytics (/split)
│   │   ├── notes.py           Notes and grocery comparison (/notes)
│   │   ├── tasks.py           Tasks and upcoming reminders (/tasks)
│   │   ├── admin.py           Admin dashboard (/admin)
│   │   └── mobile_api.py      JSON API for the mobile app (/api/mobile)
│   ├── templates/             Jinja pages and modals
│   ├── static/                CSS, JS and images (uploads/ is git-ignored)
│   ├── email_utils.py         Sending OTP, reset and reminder emails
│   ├── email_validation.py    Shared email address rules
│   ├── group_utils.py         Group membership helpers
│   ├── task_utils.py          Task due dates and recurrence
│   ├── receipt_scan.py        Gemini receipt scanning
│   ├── grocery_compare.py     Grocery price comparison
│   ├── rewards.py             Reward points and membership plans
│   ├── inactivity_reminders.py + scheduler.py   Daily inactive-user emails
│   ├── admin_utils.py         Admin checks
│   └── security.py            Security helpers
├── migrations/                Flask-Migrate (Alembic) configuration
├── scripts/
│   └── migrate_sqlite_to_postgres.py   Copy a local SQLite database into PostgreSQL
├── tests/                     unittest suite (in-memory SQLite)
├── docs/
│   ├── API.md                 Mobile API reference
│   └── SECURITY_AUDIT.md      Security review and fixes
├── config.py                  Settings, read from environment variables / .env
├── run.py                     Development entry point
├── requirements.txt
├── .env.example               Every supported variable, with placeholder values
├── POSTGRES_SETUP.md          Moving from SQLite to PostgreSQL
└── setup_gmail_env.ps1/.bat   Helper to store Gmail settings in .env
```

## Setup

### Windows (PowerShell)

```powershell
cd Splitmate-Web
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

### macOS / Linux

```bash
cd Splitmate-Web
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` (see below). For a first local run you only need `SECRET_KEY`. Delete the `DATABASE_URL` line to use SQLite, and fill in the `MAIL_*` values if you want verification emails to actually send.

## Running

```bash
python run.py
```

- Website: http://127.0.0.1:5000
- Mobile API health check: http://127.0.0.1:5000/api/mobile/health
- Admin dashboard: http://127.0.0.1:5000/admin. Admins are the addresses in `ADMIN_EMAILS`.

The server listens on `0.0.0.0:5000`, so phones on the same network can reach it at `http://<your-computer-ip>:5000`. Tables are created on first start, and missing columns are added automatically by the `ensure_*_schema` helpers in `app/__init__.py`. The SQLite file is `instance/splitmate.db`.

`run.py` reads these optional variables:

| Variable | Default | Meaning |
| --- | --- | --- |
| `FLASK_RUN_HOST` | `0.0.0.0` | Interface to listen on |
| `FLASK_RUN_PORT` | `5000` | Port |
| `FLASK_DEBUG` | `false` | Werkzeug debugger. Never turn it on when others can reach the server. |
| `FLASK_USE_RELOADER` | `false` | Restart on code changes |

## Environment variables

All settings are read in `config.py` from the process environment, then from `.env` (the process environment wins). `.env` is git-ignored; `.env.example` holds placeholders only.

| Variable | Default | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | random, saved in `instance/secret_key` | Signs sessions and mobile tokens. Set a long random value in production. |
| `DATABASE_URL` | SQLite `instance/splitmate.db` | PostgreSQL URL. `postgres://` is rewritten to `postgresql://`. |
| `SECURE_COOKIES` | `false` | Set `true` when served over HTTPS |
| `RATELIMIT_ENABLED` | `true` | Turn rate limiting off for local testing only |
| `MAIL_SERVER` / `MAIL_PORT` / `MAIL_USE_TLS` | `smtp.gmail.com` / `587` / `true` | SMTP server |
| `MAIL_USERNAME` / `MAIL_PASSWORD` | none | SMTP login. For Gmail use an app password; spaces are stripped. |
| `MAIL_DEFAULT_SENDER` | `MAIL_USERNAME` | From address |
| `ADMIN_EMAILS` | `MAIL_USERNAME` | Comma-separated admin addresses |
| `OTP_EXPIRY_MINUTES` | `10` | How long an email verification code is valid |
| `OTP_RESEND_COOLDOWN_SECONDS` | `60` | Wait before another code can be sent |
| `PASSWORD_RESET_EXPIRY_MINUTES` | `30` | Reset link lifetime |
| `ACTIVITY_UPDATE_INTERVAL_MINUTES` | `5` | How often "last active" is written |
| `INACTIVITY_REMINDER_DAYS` | `30` | Days without activity before a reminder |
| `INACTIVITY_EMAIL_COOLDOWN_DAYS` | `14` | Minimum gap between reminders to one user |
| `INACTIVITY_EMAILS_ENABLED` | `true` | Run the daily reminder job |
| `INACTIVITY_EMAIL_HOUR_UTC` | `14` | Hour (UTC) the job runs |
| `MOBILE_TOKEN_EXPIRY_DAYS` | `30` | Mobile login lifetime |
| `MOBILE_API_CORS_ORIGINS` | `http://localhost:8082,http://127.0.0.1:8082` | Browser origins allowed to call `/api/mobile` (Expo web) |
| `GROUP_INVITE_EXPIRY_DAYS` | `7` | Invite link lifetime |
| `STRIPE_CURRENCY` | `cad` | Display currency for the whole app. The name is historical; Stripe itself is no longer used. |
| `GEMINI_API_KEY` | none | Enables receipt scanning |
| `RECEIPT_SCAN_MODEL` | `gemini-3.6-flash` | Gemini model used for receipts |
| `GROCERY_PRICE_SOURCE` | `trimcart` | `trimcart` (live prices, falls back to demo data) or `demo` |

## Testing

The tests use `unittest` with an in-memory SQLite database, so they never touch your real data or send email.

```bash
python -m unittest discover -s tests          # everything
python -m unittest tests.test_mobile_api -v   # one module
```

| Test module | Covers |
| --- | --- |
| `test_mobile_api.py` | The mobile API end to end |
| `test_security_fixes.py`, `test_web_security.py` | Fixes from `docs/SECURITY_AUDIT.md`, CSRF, safe login redirects, who may settle splits |
| `test_group_management.py` | Renaming, admin hand-over, leaving and deleting groups, invite QR codes |
| `test_custom_categories.py` | Custom expense categories |
| `test_email_validation.py` | Email address rules |
| `test_task_flow.py`, `test_note_flow.py` | Tasks and notes on the website |

## How the mobile app connects

1. The app calls `POST /api/mobile/auth/login` and receives a token.
2. Every later request sends `Authorization: Bearer <token>`.
3. Tokens are signed with `SECRET_KEY` and expire after `MOBILE_TOKEN_EXPIRY_DAYS`. Changing the password or calling `/me/logout-all` revokes all existing tokens.
4. `/api/mobile` is exempt from CSRF, because it uses tokens instead of cookies.

See [`docs/API.md`](docs/API.md) for every endpoint.

## Website routes (overview)

| Prefix | Module | Pages |
| --- | --- | --- |
| `/` | `auth.py`, `main.py` | Login, register, verify email, forgot/reset password, home dashboard, profile, invite links, privacy, terms |
| `/split` | `split.py` | Add expenses, pay, settle, confirm/decline payments, plus JSON helpers under `/split/api/...` used by the page scripts |
| `/notes` | `notes.py` | Notes and grocery comparison |
| `/tasks` | `tasks.py` | Tasks and upcoming reminders |
| `/admin` | `admin.py` | Admin login, dashboard, users, emails, inactivity reminders |

## Database

- Development uses SQLite in `instance/` (git-ignored).
- For PostgreSQL, set `DATABASE_URL` and follow [`POSTGRES_SETUP.md`](POSTGRES_SETUP.md). `scripts/migrate_sqlite_to_postgres.py` copies existing SQLite data across.
- Flask-Migrate is configured in `migrations/`, but schema changes are currently applied at start-up by the `ensure_*_schema` helpers.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| Verification emails don't arrive | Check `MAIL_USERNAME` / `MAIL_PASSWORD`. Gmail needs 2-step verification and an [app password](https://myaccount.google.com/apppasswords). |
| Phone can't reach the server | Use the computer's LAN IP, not `127.0.0.1`. Both devices must be on the same Wi-Fi. Allow Python through Windows Firewall on private networks. |
| `429 Too Many Requests` | You hit a rate limit. Wait, or set `RATELIMIT_ENABLED=false` locally. |
| Everyone is logged out after a restart | `SECRET_KEY` changed. Set it in `.env`, or keep `instance/secret_key`. |
| Receipt scan says it isn't set up | Add `GEMINI_API_KEY` to `.env` and restart. |
| `ModuleNotFoundError` | Activate the venv and run `pip install -r requirements.txt`. |

## Security

- Never commit `.env`, `instance/`, databases or uploads (all git-ignored).
- Rotate any key or password that was ever committed or shared.
- Known issues and fixes: [`docs/SECURITY_AUDIT.md`](docs/SECURITY_AUDIT.md).
