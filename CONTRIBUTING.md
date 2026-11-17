# Contributing to Splitmate

This guide covers both `Splitmate-Web` (Flask) and `Splitmate-App` (Expo).

## Getting set up

Follow the setup sections of [`Splitmate-Web/README.md`](Splitmate-Web/README.md) and [`Splitmate-App/README.md`](Splitmate-App/README.md). Use your own `.env` files and never commit them.

## Branches

- `main` is always releasable. Don't push to it directly.
- Create one branch per change, named by type:
  - `feature/<short-name>` for new behaviour
  - `fix/<short-name>` for bug fixes
  - `docs/<short-name>`, `chore/<short-name>`, `refactor/<short-name>`
- Keep branches short-lived and rebase on `main` before opening a pull request.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/) with the area as the scope:

```text
<type>(<scope>): <summary in the imperative, under about 72 characters>

<optional body: what changed and why>
```

- Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `ci`
- Scopes: `web`, `app`, `api` (changes to `/api/mobile` on both sides), `docs`, `ci`
- Examples: `feat(app): add task calendar screen`, `fix(api): reject expired invite links`

Make one logical change per commit. Keep formatting-only changes out of behaviour changes.

## Rules that keep the two halves in sync

- Every API call in the app goes through `Splitmate-App/src/api/client.ts`. Its methods must match the routes in `Splitmate-Web/app/routes/mobile_api.py`, and `Splitmate-App/src/types.ts` must match the JSON the server returns. Change both sides in the same pull request and update `Splitmate-Web/docs/API.md`.
- Backend changes need a test in `Splitmate-Web/tests/`. Mobile API changes go in `tests/test_mobile_api.py`.
- Money: the server uses `Decimal` rounded to cents, and the app uses `formatMoney` / `parseAmount` from `src/utils/money.ts`. Never do money maths on strings or floats.
- Dates: the server sends naive UTC ISO strings. In the app, read them with `parseServerDate` / `formatDateTime` (`src/utils/dates.ts`) and send `toISOString()`.
- `ExpenseHistory` is an audit log. Never edit or delete its rows.
- Schema changes: new columns are added by the `ensure_*_schema` helpers in `app/__init__.py`, so existing databases upgrade on start-up. Add a helper for any new column.

## Before you open a pull request

```bash
# Backend (from Splitmate-Web, with the venv active)
python -m unittest discover -s tests

# App (from Splitmate-App)
npm run typecheck
```

Both must pass. Then:

- Update the README or `docs/API.md` if behaviour or setup changed.
- Add a line under **Unreleased** in the relevant `CHANGELOG.md`.
- Check `git diff --cached` for secrets, `.env`, databases, `node_modules/` or `venv/`.

## Pull requests

- Fill in the pull request template.
- Keep pull requests small and focused. Split large work into several.
- Include screenshots or a short recording for UI changes (web or app).
- Get at least one review before merging. Squash-merge with a Conventional Commit title.

## Code style

- Formatting rules are in `.editorconfig`: 4 spaces for Python, 2 spaces for TypeScript, JSON, HTML and CSS.
- Python: follow PEP 8 and match the surrounding code.
- TypeScript: strict mode is on. Use the `@/` import alias for `src/`, `AppText` instead of React Native's `Text`, and colours from `@/theme/colors`.
