# Splitmate

Splitmate is a Flask web application for managing shared group expenses, balances, notes, tasks, payments, and transaction history.

## Features

- User registration, login, email verification, and password reset
- Group-based expense splitting
- Equal, exact amount, and percentage expense splits
- Recent expense tracking and transaction history
- Balance overview for group members
- Manual payment recording and optional Stripe Checkout flow through the app's Stripe account
- Admin dashboard with user growth, inactive-user lists, and reminder email controls
- Group notes and task management
- Gmail SMTP configuration through environment variables

## Tech Stack

- Python
- Flask
- Flask-SQLAlchemy
- Flask-Login
- SQLite for local development
- Stripe SDK for optional online payments
- HTML, CSS, and JavaScript templates

## Project Structure

```text
Splitmate/
  app/
    routes/          Flask route modules
    static/          CSS and JavaScript assets
    templates/       Jinja HTML templates
    __init__.py      App factory and database setup
    models.py        SQLAlchemy models
    email_utils.py   Email helper functions
  config.py          Application configuration
  run.py             Local application entry point
  requirements.txt   Python dependencies
  .env.example       Example environment variables
```

## Local Setup

1. Create and activate a virtual environment.

```bash
python -m venv venv
venv\Scripts\activate
```

2. Install dependencies.

```bash
pip install -r requirements.txt
```

3. Create a `.env` file using `.env.example` as a template.

```text
SECRET_KEY=change-this-to-a-random-secret
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-gmail-app-password
STRIPE_SECRET_KEY=
STRIPE_PUBLISHABLE_KEY=
```

4. Run the app.

```bash
python run.py
```

5. Open the app in a browser.

```text
http://127.0.0.1:5000
```

## Environment Variables

The app reads configuration from `.env`. Do not commit `.env` to GitHub.

- `SECRET_KEY`: Flask session/security key
- `MAIL_SERVER`: SMTP server, default is Gmail
- `MAIL_PORT`: SMTP port, default is 587
- `MAIL_USE_TLS`: Whether SMTP TLS is enabled
- `MAIL_USERNAME`: Email account used to send OTP and reset emails
- `MAIL_PASSWORD`: Gmail app password or SMTP password
- `MAIL_DEFAULT_SENDER`: Default sender address
- `ADMIN_EMAILS`: Comma-separated app admin email addresses. Defaults to `MAIL_USERNAME`.
- `STRIPE_SECRET_KEY`: Optional Stripe secret key
- `STRIPE_PUBLISHABLE_KEY`: Optional Stripe publishable key for client-side Stripe features
- `STRIPE_CURRENCY`: Stripe currency, default is `cad`
- `INACTIVITY_REMINDER_DAYS`: Days of no app activity before a reminder is eligible, default is `30`
- `INACTIVITY_EMAIL_COOLDOWN_DAYS`: Days before another inactivity reminder can be sent to the same user, default is `14`
- `INACTIVITY_EMAILS_ENABLED`: Enables the daily inactive-user email job, default is `true`
- `INACTIVITY_EMAIL_HOUR_UTC`: UTC hour for the daily inactive-user email job, default is `14`

## Security Notes

- Never upload `.env`, real passwords, local database files, or virtual environments.
- Rotate any password or app password that was ever stored in a plain text file.
- Use `.env.example` only for placeholder values.

## GitHub Repository Name

Recommended repository name: `splitmate`
