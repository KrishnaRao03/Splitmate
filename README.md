# Splitmate

Splitmate helps roommates, friends, travel groups and small teams share expenses, settle up, and keep group tasks and notes in one place.

This repository holds the two parts of the product:

| Folder | What it is | Stack |
| --- | --- | --- |
| [`Splitmate-Web/`](Splitmate-Web/README.md) | Backend server, website and admin dashboard. Also serves the JSON API the mobile app uses (`/api/mobile`). | Python 3.13, Flask, SQLAlchemy, SQLite or PostgreSQL |
| [`Splitmate-App/`](Splitmate-App/README.md) | iOS and Android app. | Expo SDK 58, React Native 0.88, TypeScript |

```text
Splitmate/
├── Splitmate-Web/        Flask backend + website (see its README)
├── Splitmate-App/        Expo mobile app (see its README)
├── docs/                 Project proposal, website guide, older project notes
├── assets/logo/          Logo source images
├── .github/              Pull request template and CI workflow
├── CONTRIBUTING.md       How to branch, commit and open a pull request
└── CLAUDE.md             Coding guidelines for AI assistants working in this repo
```

## How the pieces fit

```text
  Browser ──HTML pages──▶ ┌──────────────────────────┐
                          │ Splitmate-Web (Flask)    │──▶ SQLite / PostgreSQL
  Splitmate-App ──JSON──▶ │   /api/mobile/*          │──▶ Gmail SMTP (codes, reminders)
  (Bearer token)          └──────────────────────────┘──▶ Google Gemini (receipt scan)
```

The website and the app share one database and one set of accounts. The app never talks to the database directly; every call goes through `/api/mobile` (documented in [`Splitmate-Web/docs/API.md`](Splitmate-Web/docs/API.md)).

## Quick start

You need **Python 3.11+** (3.13 is used day to day), **Node.js 22** and **npm**. For a phone, install **Expo Go**.

1. Start the backend (Windows shown; macOS/Linux commands are in the comments):

   ```bash
   cd Splitmate-Web
   python -m venv venv
   venv\Scripts\activate          # macOS/Linux: source venv/bin/activate
   pip install -r requirements.txt
   copy .env.example .env         # macOS/Linux: cp .env.example .env   (then edit it)
   python run.py
   ```

   The site is now at http://127.0.0.1:5000.

2. Start the app in a second terminal:

   ```bash
   cd Splitmate-App
   npm install
   copy .env.example .env         # set EXPO_PUBLIC_SPLITMATE_API_URL=http://<your-computer-ip>:5000/api/mobile
   npm run start
   ```

   Scan the QR code with Expo Go. The phone must be on the same Wi-Fi as the computer.

Each folder's README has the full setup, configuration and troubleshooting.

## Checks

Run both before opening a pull request. CI runs them on every pull request too.

```bash
cd Splitmate-Web && python -m unittest discover -s tests
cd Splitmate-App && npm run typecheck
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Never commit `.env` files, databases or anything in `instance/`.

## Security

Known issues and their fixes are tracked in [`Splitmate-Web/docs/SECURITY_AUDIT.md`](Splitmate-Web/docs/SECURITY_AUDIT.md). Report new security problems privately to the maintainer instead of opening a public issue.
