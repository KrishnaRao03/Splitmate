# Splitmate security audit — 2026-11-09

Scope: the whole Flask backend (`Splitmate-Web/app`, web pages and `/api/mobile`), the Expo app (`Splitmate-App/src`), configuration and dependencies.
Items marked **[confirmed]** were exploited against an in-memory test database, not real data.

## Critical — fix before anyone else uses the app

1. **Log in as anyone with only their email** [confirmed]
   `POST /api/mobile/auth/verify-email` with `{"email": "<any verified user>"}` returns a valid login token, with no OTP or password needed (`app/routes/mobile_api.py:466-467`, the `if user.is_email_verified: return jsonify(auth_payload(user))` branch).
   Fix: return `{"already_verified": true}` without a token, so the user signs in normally.

2. **Debug server open to the whole network**
   `run.py` defaults to `debug=True` on `0.0.0.0`. The Werkzeug debugger is reachable by anyone on the same Wi-Fi or hotspot, and Werkzeug 3.0.1 has a known debugger remote-code-execution bug (CVE-2024-34069).
   Fix: default `FLASK_DEBUG` to false, and upgrade Werkzeug (see 15). Never run debug mode on a public network.

## High

3. **A debtor can clear their own debt without paying** [confirmed]
   `POST /groups/<id>/payments` (mobile) and `/split/pay` (web) settle the payer's splits immediately; the person owed never confirms. (Marking a split settled *is* restricted to the payee, so this bypasses that rule.)
   Fix: record manual payments as `pending` until the receiver confirms them, or only let the receiver record them.

4. **Any group member can delete every expense in the group** [confirmed]
   `DELETE /api/mobile/groups/<id>/expenses` has no admin check (`mobile_api.py:1263`). The web version (`split.clear_recent`) correctly requires the admin.
   Fix: require `group.admin_id == request.mobile_user.id`.

5. **Stored XSS on the web Tasks page** [confirmed: the payload is accepted]
   `templates/tasks.html:184` puts member names into `innerHTML` unescaped. A member who sets their name or nickname to `<img src=x onerror=...>` runs script in every other member's browser session.
   Fix: `escapeHtml(m.name)`. Also reject `<` and `>` in names and nicknames on the server.

6. **No rate limiting anywhere** [confirmed for login]
   - Login: unlimited password guesses.
   - OTP: a 6-digit code with unlimited guesses for 10 minutes.
   - Forgot password, register, group invites and "invite to Splitmate" each send an email from your Gmail for every request, so anyone can use the server to spam people. That can get the Gmail account blocked.
   Fix: add Flask-Limiter (for example 5 per minute per IP and per email on auth and email-sending routes), plus a lockout after about 5 wrong OTPs.

7. **Stripe settlements land in your account, not the person owed**
   The Checkout sessions have no `transfer_data` or Connect account, so the money goes to the platform's Stripe account (`split.py:494`, `mobile_api.py:1557`). Holding other people's money brings legal and financial obligations.
   Fix: use Stripe Connect (each receiver onboards, then pay with `transfer_data.destination`), or remove Stripe and link out to Interac, PayPal or UPI.

## Medium

8. **Logins are never revoked** [confirmed]
   Mobile tokens last 30 days and stay valid after a password change, a password reset or a logout. Password-reset links can also be reused for 30 minutes.
   Fix: include a per-user `token_version` (or the password-hash fingerprint) in tokens and reset links, and bump it on password change, reset and "log out everywhere".

9. **Email can be changed without the password**
   `PATCH /api/mobile/me` and the web profile change the account email without asking for the current password. A stolen token therefore becomes a full account takeover.
   Fix: require `current_password` when the email changes.

10. **`javascript:` receipt links** [confirmed: accepted]
    `receipt_url` accepts any string, and the web page uses it as a link (`templates/split.html:320`). Clicking "View Receipt" runs the script.
    Fix: only accept `http://` or `https://` URLs on the server.

11. **Removing a member who owes money breaks the group** [confirmed: 500 error]
    `balances_for` raises a `KeyError` for splits whose user has left (`mobile_api.py:248-249`). After that, nobody can open the group.
    Fix: block removal while the member has open balances, or include former members in the balances.

12. **Account lookup and name leaks**
    - `/invite-splitmate` reveals the account name behind any email.
    - Adding a member by email returns that user's email and points, and adds them without asking.
    - Register (409) and resend-OTP (404) reveal whether an email is registered.
    Fix: return generic messages, and send invites (needing acceptance) instead of adding people directly.

13. **Uploads**
    - There is no request size limit (`MAX_CONTENT_LENGTH`), so large uploads can exhaust memory or disk.
    - Receipts are saved under `/static/uploads/receipts/` and anyone with the link can open them, with no login.
    Fix: set `MAX_CONTENT_LENGTH = 10 * 1024 * 1024`, and serve receipts through a route that checks group membership.

14. **Plain HTTP in production builds**
    The `withCleartextTraffic` plugin enables HTTP for every Android build, including production. Passwords and tokens would travel unencrypted. Session cookies also aren't marked `Secure`.
    Fix: deploy the server behind HTTPS. Enable cleartext only in development builds, and set `SESSION_COOKIE_SECURE`, `REMEMBER_COOKIE_SECURE` and `SESSION_COOKIE_SAMESITE='Lax'` in production.

15. **Outdated Flask and Werkzeug**
    Werkzeug 3.0.1 has known issues: CVE-2024-34069 (debugger RCE), CVE-2024-49767 (multipart memory DoS) and CVE-2024-49766 (`safe_join` on Windows).
    Fix: upgrade to current Flask 3.1.x and Werkzeug 3.1.x, then re-run the tests.

## Low

16. CSV export does no formula escaping: descriptions starting with `=`, `+`, `-` or `@` run as formulas in Excel. Prefix them with `'`.
17. The minimum password length is 6 characters. Raise it to at least 8.
18. Logout uses GET on both web and admin, so another site can log you out. Make it POST.
19. `npm audit` reports 9 issues (1 critical, 1 high), all in Expo build tooling (shell-quote, browserslist, glob), not code shipped in the app. Update Expo patch versions.
20. Money is stored as `Float`, which can drift by cents. Moving to `Numeric(12, 2)` needs a migration.
21. Any member can delete any task or note. Limit deletion to the creator or the admin if that matters.

## Fix status (2026-11-09)

Each fix has a test in `tests/test_security_fixes.py` (25 tests). The whole backend suite passes: 49 tests. Re-running the original proof-of-concept against the fixed code reproduced none of the 8 confirmed issues.

| # | Status | What changed |
|---|---|---|
| 1 | Fixed | `/auth/verify-email` returns `already_verified` with no token. |
| 2 | Fixed | Debug mode is opt-in (`FLASK_DEBUG=true`). Werkzeug is now 3.1.9, and `/console` returns 404. |
| 3 | Fixed | Manual payments start as `pending`. Only the receiver can confirm them (`/payments/<id>/confirm`, web and app), and either side can decline. The payer can't record more than is still owed, after subtracting payments already pending. |
| 4 | Fixed | Clearing every expense from the app is admin-only. |
| 5 | Fixed | The Tasks page escapes names. The server rejects `<` and `>` in names, nicknames and group names. |
| 6 | Fixed | Flask-Limiter applies per-IP limits, plus per-email limits on sign-in, reset and code emails. A code stops working after 5 wrong guesses. |
| 7 | Fixed | In-app Stripe collection is removed. Each member can add an Interac email, PayPal.Me username and UPI ID, and payers get "Pay with…" links (PayPal, UPI) or the Interac email to send to. Splitmate never touches the money. **Points:** earning is paused (`rewards.POINTS_EARNING_PAUSED`). Confirmed manual payments can't safely earn gift-card points, because two friends could confirm fake payments to each other. Existing balances and history are kept. |
| 8 | Fixed | Users have a `token_version`. A password change or reset, and the new "Sign out of all devices" (`/me/logout-all`), revoke every app token and web session. Reset links work once. |
| 9 | Fixed | Changing the email needs the current password, in the app and on the web. |
| 10 | Fixed | Receipt links must be `http(s)://` or a local path, checked on the server and again on the web page. |
| 11 | Fixed | Removing a member with open balances is blocked (409). Balances also no longer crash for members who left before this fix. |
| 12 | Fixed | "Invite to Splitmate" gives the same reply for any email. "Add member" now sends an invite instead of adding the person directly. Resend-code and forgot-password replies are generic. |
| 13 | Fixed | 10 MB upload cap (413). New receipts are stored in `instance/receipts/` and served by `/receipts/<file>` only to group members or through a one-hour signed link. |
| 14 | Fixed | Production EAS builds turn plain HTTP off (`SPLITMATE_ALLOW_CLEARTEXT=false`; checked with `expo config --type introspect`). Cookies are SameSite=Lax and HttpOnly, with `Secure` controlled by `SECURE_COOKIES`. |
| 15 | Fixed | Flask 3.1.3, Werkzeug 3.1.9 (SQLAlchemy stays at 2.0.49). |
| 16 | Fixed | CSV cells starting with `=`, `+`, `-` or `@` get a leading `'` (web and app exports). |
| 17 | Fixed | New passwords need 8+ characters. Existing 6–7 character passwords still sign in. |
| 18 | Fixed | Web and admin logout are POST-only, with CSRF. |
| 19 | Partly | `npm audit fix` cleared the critical (shell-quote) and high (browserslist) issues. 5 moderate ones remain in Expo's build tooling (glob/minimatch). npm's only "fix" for them downgrades Expo to SDK 53, which would break the app. They'll go away with a later Expo update. |
| 20 | Not done | Money is still stored as `Float`. The real fix is integer cents (or `NUMERIC`) plus a data migration and changes to every calculation. That's a schema migration on your live data, so it needs its own planned change. All amounts are already rounded to cents with `Decimal` before they're saved. |
| 21 | Fixed | Only the creator or the group admin can delete a task or note (web and app). |

### Still to do (for you)
- **When you deploy behind HTTPS:** set `SECURE_COOKIES=true` in the server `.env`.
- **Receipts uploaded before this fix** are still under `app/static/uploads/receipts/` and still public to anyone with the link. Move them into `instance/receipts/` and update their `receipt_url` values when convenient. That's a data change, so I didn't do it.
- **Rate-limit storage** is in-memory, which is fine for one server process. If you run several workers, point Flask-Limiter at Redis (`RATELIMIT_STORAGE_URI`).
- **Stripe settings:** `STRIPE_SECRET_KEY` and `STRIPE_PUBLISHABLE_KEY` are no longer used and can be removed from `.env`. `STRIPE_CURRENCY` is still the app's display currency. The `stripe` package is no longer in `requirements.txt`.
- **Register** still says "Email already registered" (409). Hiding that would need a "check your inbox" sign-up flow, which is a product decision.

## Already done well

- Tokens are stored in SecureStore on the phone.
- CSRF protection is on for web forms.
- All database queries are parameterized; no SQL injection was found.
- Group membership checks are present on almost every route.
- The secret key is random.
- Invite tokens are long and random.
- Redirect targets are checked (no open redirect).
- Only the payee can mark a split settled.
- Receipt files get random names.
- Most web templates use `escapeHtml`.
