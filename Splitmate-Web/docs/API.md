# Splitmate Mobile API

The JSON API the Expo app (`Splitmate-App`) uses. Source: [`app/routes/mobile_api.py`](../app/routes/mobile_api.py). App client: `Splitmate-App/src/api/client.ts`. Response types: `Splitmate-App/src/types.ts`.

## Basics

- **Base URL:** `http://<server>:5000/api/mobile`
- **Format:** JSON request and response bodies (`Content-Type: application/json`), except file uploads, which use `multipart/form-data`.
- **Auth:** every route except `/health` and `/auth/*` needs `Authorization: Bearer <token>`. Missing or invalid tokens get `401`.
- **Errors:** failures return `{"error": "<message for the user>"}` with a 4xx/5xx status:
  - `400` invalid input
  - `401` not signed in
  - `403` not allowed (not a group member, not the group admin, account suspended or unverified)
  - `404` not found
  - `413` upload too large (limit 10 MB)
  - `429` rate limited
  - `503` receipt scanning not configured
- **Dates:** naive UTC ISO 8601 strings (`2026-11-11T14:00:00`). Send UTC.
- **Money:** amounts are decimals rounded to cents. `currency_code` (from `STRIPE_CURRENCY`) is returned on sign-in.
- **CSRF:** not used. The blueprint is CSRF-exempt because it uses bearer tokens, not cookies.
- **CORS:** only origins listed in `MOBILE_API_CORS_ORIGINS` (Expo web). Native apps don't need CORS.

### Tokens

`token` is signed with `SECRET_KEY` and carries the user id and a `token_version`. It expires after `MOBILE_TOKEN_EXPIRY_DAYS` (default 30). Changing the password or calling `POST /me/logout-all` bumps `token_version`, which revokes every existing token.

### Rate limits

| Route | Limit |
| --- | --- |
| `POST /auth/login` | 10/minute and 50/hour per IP, and 10 per 15 minutes per email |
| `POST /auth/register` | 5/hour per IP |
| `POST /auth/verify-email` | 10/minute per IP |
| `POST /auth/resend-otp` | 3 per 10 minutes per email |
| `POST /auth/forgot-password` | 3/hour per email |
| `POST /groups/<id>/invites`, `POST /groups/<id>/members` | 30/hour |

## Endpoints

`<id>` values are integers. "Admin" means the group admin unless stated otherwise.

### Health and auth

| Method | Path | Body | Notes |
| --- | --- | --- | --- |
| GET | `/health` | | `{"ok": true, "service": "Splitmate mobile API"}`. No auth. |
| POST | `/auth/login` | `email`, `password` | Returns `{token, user, currency_code}`. `403` if the email is unverified or the account is suspended. |
| POST | `/auth/register` | `name`, `email`, `password`, `confirm_password` | Saves the sign-up as pending and emails a verification code. No account exists until the code is verified; registering the same email again replaces the pending sign-up. Returns `{user: {email, name}, verification_required, otp_sent}` with `201`. |
| POST | `/auth/verify-email` | `email`, `otp` | Verifies the code, creates the account (for a pending sign-up) and returns `{token, user, currency_code}`. An already-verified email gets `{already_verified: true, message}` and no token; sign in normally. Too many wrong codes return `429`. |
| POST | `/auth/resend-otp` | `email` | Sends a new code (cooldown `OTP_RESEND_COOLDOWN_SECONDS`). |
| POST | `/auth/forgot-password` | `email` | Emails a reset link. The response is the same whether or not the account exists. |

`user` object: `id`, `name`, `email`, `is_email_verified`, `reward_points`, `membership_plan`, `membership_status`, `created_at`, `interac_email`, `paypal_username`, `upi_id`.

### Account

| Method | Path | Body | Notes |
| --- | --- | --- | --- |
| GET | `/me` | | Current user |
| PATCH | `/me` | `name`, `email`, `interac_email`, `paypal_username`, `upi_id`, `current_password` | `current_password` is required only when changing `email`. |
| POST | `/me/password` | `current_password`, `new_password`, `confirm_password` | Revokes all other tokens. |
| POST | `/me/logout-all` | | Revokes every token, including this one. |
| GET | `/me/qr` | | Profile QR code: `{payload, size, rows}` (a boolean matrix to draw). |
| GET | `/export` | | All of the user's data as JSON (profile, groups, expenses, payments, notes, tasks). |
| POST | `/devices` | `expo_push_token`, `platform` | Registers the device for push notifications. |
| GET | `/rewards` | | Reward points, membership and history |

### Dashboard and insights

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/dashboard` | Groups, recent expenses, monthly spending, and insight totals by category, payer, group and month |
| GET | `/balances/people` | Net balance with each person across all groups |
| GET | `/reminders/upcoming` | Upcoming task reminders, used to schedule local notifications |
| GET | `/tasks` | Tasks across all of the user's groups |
| GET | `/notes` | Notes across all of the user's groups, newest first |

### Groups and members

| Method | Path | Body | Notes |
| --- | --- | --- | --- |
| GET | `/groups` | | Groups the user belongs to |
| POST | `/groups` | `name` | Creates a group. The creator becomes admin. |
| GET | `/groups/<id>` | | Group detail: `group`, `balances`, `summaries`, `expenses`, `tasks`, `notes`, `payments`, `payment_options`, `money_requests`, `default_split`, `expense_categories`, and `pending_invites` (admin only) |
| PATCH | `/groups/<id>` | `name` | Rename. Admin only. |
| DELETE | `/groups/<id>` | | Admin only. Allowed only when no other member has expense history. |
| POST | `/groups/<id>/admin` | `user_id` | Hand the admin role to another member |
| POST | `/groups/<id>/leave` | | Only once your balance is settled. The admin must hand over first. |
| POST | `/groups/<id>/members` | `email` | Admin only. Sends an invite; the person joins only after accepting. Returns `{invited, already_member, message}`. |
| PATCH | `/groups/<id>/members/<user_id>` | `nickname` | Admin only |
| DELETE | `/groups/<id>/members/<user_id>` | | Admin only. Refused while the member has an open balance. |
| GET | `/groups/<id>/default-split` | | The group's default split |
| PUT | `/groups/<id>/default-split` | `type` (`equal`/`exact`/`percentage`), `member_ids`, `percentages` | Set the default split |
| DELETE | `/groups/<id>/default-split` | | Reset to equal |

### Invites

| Method | Path | Body | Notes |
| --- | --- | --- | --- |
| GET | `/groups/<id>/invites` | | Pending invites for the group |
| POST | `/groups/<id>/invites` | `email` | Creates an invite and returns its link and QR code. Expires after `GROUP_INVITE_EXPIRY_DAYS`. |
| DELETE | `/groups/<id>/invites/<invite_id>` | | Revoke |
| GET | `/invites` | | Invites addressed to the current user |
| POST | `/invites/<invite_id>/accept` | | Join the group |
| POST | `/invites/accept-link` | `link` | Join from a pasted or scanned invite link |
| POST | `/invite-splitmate` | `email` | Email someone an invitation to join Splitmate |

### Expenses

| Method | Path | Body / query | Notes |
| --- | --- | --- | --- |
| GET | `/groups/<id>/expenses` | `?q=&category=&payer_id=` | List with filters |
| POST | `/groups/<id>/expenses` | see below | Create. Returns the expense, `201`. |
| DELETE | `/groups/<id>/expenses` | | Clear all expenses. Admin only. |
| PUT | `/expenses/<expense_id>` | see below | Edit. Only the payer or the admin. |
| DELETE | `/expenses/<expense_id>` | | Delete. Only the payer or the admin. |
| GET | `/groups/<id>/expenses/search` | `?q=&category=&paid_by_id=&min_amount=&max_amount=&date_from=&date_to=` | Search |
| GET | `/groups/<id>/activity` | `?q=&category=&payer_id=&min_amount=&max_amount=&start_date=&end_date=` | Expense and payment history |
| GET | `/groups/<id>/activity.csv` | same filters | CSV download |
| POST | `/receipts/scan` | multipart file field `receipt` (JPEG/PNG/WebP/GIF) | Reads a receipt with Gemini and returns the extracted fields. `503` if `GEMINI_API_KEY` is not set. |

Expense body fields (JSON, or multipart with a `payload` JSON field plus an optional receipt image):

| Field | Type | Notes |
| --- | --- | --- |
| `description` | string | Required |
| `amount` | number | Required, greater than 0 |
| `paid_by_id` | int | Defaults to the current user |
| `category` | string | Built-in or a group custom category |
| `split_type` | `equal`, `selected`, `exact`, `percentage` | `selected` means equal among `split_user_ids` |
| `split_user_ids` | int[] | Members sharing the expense |
| `exact_amounts` | `{user_id: amount}` | For `exact`. Must add up to `amount`. |
| `percentages` | `{user_id: percent}` | For `percentage`. Must add up to 100. |
| `receipt_url` | string | Existing receipt to keep when editing |

### Payments and settling

| Method | Path | Body | Notes |
| --- | --- | --- | --- |
| POST | `/groups/<id>/payments` | `receiver_id`, `amount` | Record a payment to another member. It waits for the receiver to confirm. |
| POST | `/payments/<payment_id>/confirm` | | Receiver confirms |
| POST | `/payments/<payment_id>/decline` | | Receiver declines |
| POST | `/splits/<split_id>/settle` | | Mark one split as paid. Only the person who paid for the expense can do this. |

### Tasks

| Method | Path | Body | Notes |
| --- | --- | --- | --- |
| POST | `/groups/<id>/tasks` | `title`, `description`, `due_date`, `reminder_time`, `assigned_to_id`, `priority`, `recurrence` | Create |
| POST | `/tasks/<task_id>/toggle` | | Complete / reopen. Completing a recurring task schedules the next one. |
| DELETE | `/tasks/<task_id>` | | Delete |

### Notes

| Method | Path | Body | Notes |
| --- | --- | --- | --- |
| POST | `/groups/<id>/notes` | `title`, `description` | Create |
| PATCH | `/notes/<note_id>` | `title`, `description` | Edit |
| DELETE | `/notes/<note_id>` | | Delete |
| POST | `/notes/<note_id>/toggle` | | Mark done / not done |
| GET | `/notes/<note_id>/grocery-comparison` | | Compares the note's items across grocery stores (`GROCERY_PRICE_SOURCE`) |

## Example

```bash
# Sign in
curl -s -X POST http://127.0.0.1:5000/api/mobile/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"your-password"}'

# Use the returned token
curl -s http://127.0.0.1:5000/api/mobile/groups -H "Authorization: Bearer <token>"
```

## Changing the API

Change the route, `src/api/client.ts`, `src/types.ts`, this file and `tests/test_mobile_api.py` together, in one pull request.
