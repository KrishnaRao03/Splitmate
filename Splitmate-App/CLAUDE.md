# Splitmate – shared project brief (read by every agent)

Splitmate is a bill-splitting + group tasks/notes app.
- **Mobile app** (this folder): Expo SDK 55 / React Native / TypeScript. Source in `src/`.
- **Backend** (sibling folder `../Splitmate-Web`): Flask + SQLAlchemy, mobile API in `app/routes/mobile_api.py` (blueprint prefix `/api/mobile`). Start Claude Code from this folder with `claude --add-dir ..\Splitmate-Web` so agents can see both.

## Commands (Windows PowerShell)
- App typecheck: `npm run typecheck` (run in this folder)
- App dev server: `npm run start`
- Backend tests: `..\Splitmate-Web\venv\Scripts\python.exe -m unittest tests.test_mobile_api -v` (run in `..\Splitmate-Web`)
- Backend server: `..\Splitmate-Web\venv\Scripts\python.exe run.py`

## Conventions
- Path alias `@/` = `src/`. Use `AppText` (not RN `Text`), theme tokens from `@/theme/colors`, shared components in `src/components`.
- Money: format with `formatMoney`, parse with `parseAmount` (`src/utils/money.ts`). Never do money maths on strings. Server uses `Decimal` + cents.
- Dates: server sends naive UTC ISO strings. Always read them with `parseServerDate` / `formatDateTime` (`src/utils/dates.ts`); send UTC (`toISOString()`).
- Every API call goes through `src/api/client.ts`; its methods must match routes in `mobile_api.py`. Change both sides together and keep `src/types.ts` in sync.
- `ExpenseHistory` is an immutable audit log: never edit or delete its rows.
- Backend changes need a test in `../Splitmate-Web/tests/test_mobile_api.py`.
- Never read, print, or commit `.env` files or secrets.

## Team workflow (the main session orchestrates; subagents cannot spawn each other)
1. `product-lead` turns a goal into a small ordered plan in `docs/ROADMAP.md`.
2. `backend-dev` and/or `mobile-dev` implement one plan item each.
3. `qa-tester` runs typecheck + tests and reports pass/fail with exact errors.
4. `reviewer` reviews the diff. Fix anything it flags, then re-run QA.
5. `release-manager` prepares changelog / version / build notes.
Loop steps 2–4 until QA passes and review is clean, then summarise to the human.

## Autonomy rules
Agents MAY, without asking: edit source and tests, run typecheck/tests, update docs/ROADMAP.md and CHANGELOG.md.
Agents MUST ask the human first before: deleting files or data, changing the database schema or running migrations, touching auth/payments (Stripe), changing dependencies, running `eas build`/`eas submit`, pushing to git remotes, sending emails/notifications to real users, or editing production config.
