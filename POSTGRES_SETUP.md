# PostgreSQL Setup

Splitmate is ready to use PostgreSQL through `DATABASE_URL`.

## 1. Install or Create PostgreSQL

Use one of these options:

- Local PostgreSQL for Windows
- Docker PostgreSQL
- Cloud PostgreSQL such as Neon, Supabase, Render, Railway, or Heroku

Create a database named `splitmate`.

## 2. Configure `.env`

Add a PostgreSQL connection string:

```env
DATABASE_URL=postgresql://postgres:your-postgres-password@localhost:5432/splitmate
```

Cloud providers sometimes give URLs that start with `postgres://`; Splitmate normalizes those automatically.

## 3. Migrate Current SQLite Data

Run this once after `DATABASE_URL` points at the PostgreSQL database:

```powershell
venv\Scripts\python.exe scripts\migrate_sqlite_to_postgres.py
```

If the target database already has rows and you want to replace them:

```powershell
venv\Scripts\python.exe scripts\migrate_sqlite_to_postgres.py --force
```

## 4. Run the App

```powershell
venv\Scripts\python.exe -m flask --app run:app run --host 127.0.0.1 --port 5001
```

## Useful Commands

Initialize migrations has already been done. For future model changes:

```powershell
venv\Scripts\python.exe -m flask --app run:app db migrate -m "Describe schema change"
venv\Scripts\python.exe -m flask --app run:app db upgrade
```
