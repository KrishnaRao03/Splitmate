# Splitmate Roadmap: minimal auth + 4-tab bottom nav

Ordered so each item is one backend-dev or mobile-dev step and ships independently.

## 1. Backend: aggregate notes endpoint + test — DONE
- Outcome: `GET /api/mobile/notes` returns all notes across the current user's groups (newest first), each with `group_id`/`group_name`, matching the existing `Note` shape.
- Files: `../Splitmate/app/routes/mobile_api.py` (new route near the `/reminders/upcoming` handler; reuse `note_payload` at line 205 and the `Group.members.contains(request.mobile_user)` filter pattern from `upcoming_reminders`); test in `../Splitmate/tests/test_mobile_api.py`.
- Acceptance: new unit test proves a user sees notes from all their groups and none from groups they are not in; `python -m unittest tests.test_mobile_api -v` passes.
- Risk: Low. Read-only endpoint; main risk is leaking notes across membership — the test must assert isolation.

## 2. App: client + types for aggregate notes — DONE
- Outcome: `api.allNotes()` calling `GET /notes`, returning `Note[]`.
- Files: `src/api/client.ts`, `src/types.ts` (reuse existing `Note`).
- Acceptance: `npm run typecheck` passes; method path matches the route from item 1.
- Risk: Low. Keep names in sync with backend (repo convention).

## 3. App: add bottom-tabs dependency (human-approved) — DONE
- Outcome: `@react-navigation/bottom-tabs` installed and importable.
- Files: `package.json` / lockfile.
- Acceptance: `npm run typecheck` passes; package resolves.
- Risk: Low. Dependency change is normally "must ask"; human pre-approved. Version must match Expo SDK 55 / installed React Navigation.

## 4. App: TabNavigator (Home/Split/Tasks/Notes) + top-left profile button — DONE
- Outcome: Authenticated side uses a bottom tab navigator with 4 tabs; each tab header shows a top-left profile button (navigate to `Profile`). Existing stack screens (GroupDetail, AddExpense, etc.) remain reachable.
- Files: `src/navigation/AppNavigator.tsx`, new `src/navigation/TabNavigator.tsx`, `src/types.ts` (tab param list), `src/components` (optional shared header-left button).
- Acceptance: Login shows a 4-tab bar; profile button top-left opens Profile; all existing stack navigations still work; `npm run typecheck` passes.
- Risk: Medium. Nesting stack + tabs and header wiring can break existing `navigation.navigate` calls; keep `RootStackParamList` routes intact.

## 5. App: Home screen cleanup (remove fake nav) — DONE
- Outcome: Remove decorative Home/Split/Tasks/Notes pills (HomeScreen.tsx:156-173) and in-page profile/settings header buttons (112-119) now that the tab bar + top-left profile own navigation. Keep stats, groups, create-group, spending, reminders.
- Files: `src/screens/HomeScreen.tsx`.
- Acceptance: Home renders without the pill row; profile reachable via top-left button; `npm run typecheck` passes.
- Risk: Low. Pure removal; drop orphaned styles.

## 6. App: Split aggregate screen — DONE
- Outcome: Split tab shows an across-all-groups view reusing dashboard data (`recent_expenses`, `monthly_spending`, owed totals) — no new fetch endpoint.
- Files: new `src/screens/SplitScreen.tsx`; wired in item 4.
- Acceptance: Split tab lists expenses/spending across groups; empty state when none; `npm run typecheck` passes.
- Risk: Low-Medium. Avoid duplicate dashboard fetches — share/refetch consistently with Home.

## 7. App: Tasks aggregate screen — DONE
- Outcome: Tasks tab shows upcoming tasks across all groups via `api.upcomingReminders()`.
- Files: new `src/screens/TasksScreen.tsx`.
- Acceptance: Tasks tab lists reminders across groups; empty state; `npm run typecheck` passes.
- Risk: Low. Endpoint returns only future, incomplete reminders — confirm that is the intended "Tasks" scope (see open questions).

## 8. App: Notes aggregate screen — DONE
- Outcome: Notes tab lists all notes across groups via `api.allNotes()` (item 2).
- Files: new `src/screens/NotesScreen.tsx`.
- Acceptance: Notes tab lists notes across groups with group label; empty state; `npm run typecheck` passes.
- Risk: Low. Read-only; toggle/edit can be deferred.

## 9. App: minimal AuthScreen redesign — DONE
- Outcome: Single calmer card — compact brand, Login/Register tabs, fields, OTP/forgot flows, and API URL override moved behind a collapsible "Connection"/"Advanced" disclosure instead of an always-visible card. All existing behavior kept.
- Files: `src/screens/AuthScreen.tsx` (optionally a small reusable disclosure in `src/components`).
- Acceptance: All four modes (login/register/verify/forgot) still work; API URL still editable via the disclosure; visibly less clutter; `npm run typecheck` passes.
- Risk: Low-Medium. Do not hide the API URL so deeply that device QA can't find it.

## Must-ask / flags
- Item 3 (new dependency) is normally "must ask the human" — treated as pre-approved per the goal.
- No schema change, no auth/payments change, no migrations in this plan.

---

# Phase 2: Full redesign (clean/minimal fintech)

Goal: visual overhaul of every screen plus the audited feature gaps. Each item is one mobile-dev step (or backend-dev where a new/changed endpoint is noted) and ships independently. Design tokens come from item P2-1; later items assume those tokens exist. Gap audit and design tokens are summarised in the two reference sections at the bottom of this file.

## P2-1. Design system refresh (tokens + shared components) — foundation for everything below — DONE
- Outcome: Evolve `src/theme/colors.ts` to the fintech palette/scales in "Design tokens" below (one accent, softer neutrals, extended spacing/radius, a named `type` scale). Update shared components to match: `Card` drops the 1px border and uses a softer shadow + more padding; `AppButton` is taller, less saturated, `fontWeight` 600-700 not 800; `TextField` gets the larger radius and calmer border; `AppText` keeps weight-to-font mapping but add a `variant` helper or exported text styles so screens stop hand-rolling `fontSize/fontWeight` everywhere.
- Files: `src/theme/colors.ts`, `src/components/Card.tsx`, `src/components/AppButton.tsx`, `src/components/TextField.tsx`, `src/components/AppText.tsx`, `src/components/States.tsx`, optionally new `src/theme/typography.ts`.
- Acceptance: `npm run typecheck` passes; every screen still renders (tokens are additive/renamed-with-shims so nothing references a deleted key); Card shows no hard border; buttons visibly taller/softer. QA spot-checks Home, GroupDetail, Auth.
- Risk: Medium. Renaming/removing a color key breaks many screens. Keep old keys as aliases, or do a repo-wide rename in this same item. No new deps.

## P2-2. Backend: per-person net balance across all groups (+ test) — DONE
- Outcome: New `GET /api/mobile/balances/people` returning each counterparty the user shares groups with and the net the user owes them / they owe the user, summed across groups (reuse the `balances_for`/split logic at `mobile_api.py` ~221 and the dashboard owed/owes math at ~668). Shape e.g. `[{ user_id, name, net, groups: [{group_id, group_name, net}] }]`.
- Files: `../Splitmate/app/routes/mobile_api.py` (new route near `all_notes`), test in `../Splitmate/tests/test_mobile_api.py`.
- Acceptance: unit test proves a two-group shared debt nets correctly and users in no shared group are excluded; `python -m unittest tests.test_mobile_api -v` passes.
- Risk: Medium. Correctness of netting across groups; the test must cover mutual debts that partly cancel. No schema change.

## P2-3. App: client + types for per-person balances — DONE
- Outcome: `api.peopleBalances()` -> `PersonBalance[]`; add `PersonBalance` to `src/types.ts`. No UI yet.
- Files: `src/api/client.ts`, `src/types.ts`.
- Acceptance: `npm run typecheck` passes; path matches P2-2's route.
- Risk: Low. Keep names in sync with backend per convention.

## P2-4. App: Split tab redesign + settle-up surfaced — DONE
- Outcome: Redesign Split with the new tokens; add a "Who owes who" section driven by `api.peopleBalances()` (P2-3) showing per-person net with a tap-through to that group's Pay flow; keep owed/owe summary and recent expenses. Makes settle-up discoverable without digging into a group.
- Files: `src/screens/SplitScreen.tsx`.
- Acceptance: Split shows per-person balances across groups with empty state; tapping a person navigates to the relevant `GroupDetail`; `npm run typecheck` passes.
- Risk: Low-Medium. A person may owe across several groups — decide single-group deep-link vs. list (see open questions).

## P2-5. App: Tasks tab redesign + make it actionable — DONE
- Outcome: Redesign with new tokens; let users toggle-complete (`api.toggleTask`) and delete (`api.deleteTask`) from the aggregate list, and add group filter + text search. Backend note: `upcomingReminders()` hides tasks without a reminder time and all overdue/completed ones — switch the Tasks source to a fuller task feed so the tab isn't misleadingly empty (needs P2-6).
- Files: `src/screens/TasksScreen.tsx` (and depends on P2-6).
- Acceptance: tasks across groups listed incl. overdue; toggle/delete update optimistically and persist on refresh; search/filter work; `npm run typecheck` passes.
- Risk: Medium. Depends on P2-6; optimistic update must reconcile with `is_overdue`/`is_completed`.

## P2-6. Backend: aggregate tasks endpoint (+ test) — DONE
- Outcome: `GET /api/mobile/tasks` returning all tasks across the user's groups (not just future-with-reminder), newest/soonest first, reusing `task_payload`. Keeps `/reminders/upcoming` intact for notifications.
- Files: `../Splitmate/app/routes/mobile_api.py` (near `upcoming_reminders`/`all_notes`), test in `../Splitmate/tests/test_mobile_api.py`.
- Acceptance: test proves a user sees tasks with no reminder_time and overdue tasks, and none from non-member groups; unittest passes. (Pairs with a `api.allTasks()` client method — fold into P2-3 or add here.)
- Risk: Low-Medium. Membership isolation like `all_notes`; confirm ordering. No schema change.

## P2-7. App: Notes tab redesign + inline edit/toggle/delete — DONE
- Outcome: Redesign with new tokens; wire the already-existing `api.toggleNote`/`api.updateNote`/`api.deleteNote` so notes are editable from the aggregate tab (removes the read-only limitation from Phase 1 item 8, which the redesign goal now treats as a gap); add group filter + search.
- Files: `src/screens/NotesScreen.tsx`.
- Acceptance: toggle/edit/delete work from the Notes tab and persist; search/filter work; empty state; `npm run typecheck` passes.
- Risk: Low. All endpoints already exist and are in the client.

## P2-8. App: Home screen redesign — DONE
- Outcome: Apply new tokens; rework the stat grid into a single calmer balance header (owed/owe), tighten group list rows, keep create-group, spending, recent expenses, reminders. Consistent card spacing per design tokens.
- Files: `src/screens/HomeScreen.tsx`.
- Acceptance: Home renders with new look, all existing data/sections present, create-group still works; `npm run typecheck` passes.
- Risk: Low. Pure visual; reuse existing data.

## P2-9. App: GroupDetail redesign — DONE
- Outcome: Apply new tokens across all five tabs (overview/expenses/tasks/notes/pay); restyle balances, segmented control, settle-up and expense/task/note cards; no behavior change. Largest screen — keep logic intact.
- Files: `src/screens/GroupDetailScreen.tsx`.
- Acceptance: all five tabs render and every existing action (add/edit/delete expense, toggle task/note, record/stripe payment, settle split) still works; `npm run typecheck` passes.
- Risk: Medium. Big file; risk of touching logic while restyling. Visual-only diff.

## P2-10. App: Auth screen redesign — DONE
- Outcome: Apply new tokens to the login/register/verify/forgot card and the Connection disclosure from Phase 1 item 9; keep all four modes and the API URL override.
- Files: `src/screens/AuthScreen.tsx`.
- Acceptance: all four modes work; API URL still reachable; `npm run typecheck` passes.
- Risk: Low-Medium. Do not hide API URL from device QA.

## P2-11. App: Profile + Settings redesign — DONE
- Outcome: Apply new tokens; group Profile cards (identity/details/password/invite/actions) with the new spacing; restyle Settings. No behavior change. Optional: add "Leave group" entry point for non-admins is a separate low-priority gap, not in this item.
- Files: `src/screens/ProfileScreen.tsx`, `src/screens/SettingsScreen.tsx`.
- Acceptance: save details/password/invite/sign-out still work; `npm run typecheck` passes.
- Risk: Low.

## P2-12. App: secondary screens redesign (AddExpense, AddTask, GroupSettings, Insights, TaskCalendar) — DONE
- Outcome: Apply new tokens to the remaining stack screens for consistency. No behavior change; can be split per-screen if too large for one step.
- Files: `src/screens/AddExpenseScreen.tsx`, `src/screens/AddTaskScreen.tsx`, `src/screens/GroupSettingsScreen.tsx`, `src/screens/InsightsScreen.tsx`, `src/screens/TaskCalendarScreen.tsx`.
- Acceptance: each screen's existing flows work; `npm run typecheck` passes.
- Risk: Low-Medium. Insights may rely on specific color keys — check during P2-1 rename. Confirmed: every `colors.*` key used in `InsightsScreen.tsx` (`muted`, `ink`, `primary`, `text`, `primarySoft`, `accent`, `success`, `danger`, `white`) still exists in `src/theme/colors.ts`.

## Phase 2 must-ask / flags
- No new dependencies planned. If a redesign item wants an icon set, chart lib, or bottom-sheet lib, that is "must ask the human" — raise it before adding.
- P2-2 and P2-6 are new backend endpoints only (read-only, membership-isolated). No schema change, no migration, no auth/payments change — within autonomy rules, each still needs a test per CLAUDE.md.
- Nothing here touches auth/payments logic (Stripe pay flow in GroupDetail is restyled, not rewired).

---

## Phase 2 reference: feature gap audit (prioritised)

HIGH
- Tasks tab is misleading: `upcomingReminders()` (`mobile_api.py:1624`) returns only future tasks that have a `reminder_time` and are incomplete, so tasks with no reminder and all overdue tasks never appear — the tab looks empty when work exists. (P2-5/P2-6)
- No way to complete or delete a task from the aggregate Tasks tab — toggle/delete only exist inside `GroupDetailScreen`, even though `api.toggleTask`/`api.deleteTask` already exist. (P2-5)
- No per-person net balance across groups — `Dashboard` only has `total_owed_to_user`/`total_user_owes` scalars; per-person `balances` live only inside each `GroupDetail`. A core Splitwise-style "who owes who overall" view is missing. (P2-2/P2-3/P2-4)
- Settle-up is buried in GroupDetail's "Pay" tab and not reachable from the Split tab, so marking a debt paid is hard to discover. (P2-4)

MEDIUM
- Notes tab is read-only; `api.toggleNote`/`updateNote`/`deleteNote` exist and are used in GroupDetail but not the aggregate tab — now a gap given the redesign goal. (P2-7)
- No search/filter on any list screen (groups, expenses, notes, tasks); fine today but breaks down as lists grow. (P2-4/P2-5/P2-7)

LOW
- Non-admins have no "Leave group" action; `GroupSettings` is admin-only (removeMember exists but there's no self-leave surface). Not scheduled in Phase 2 — flag for the human.
- Empty/loading/refresh states are actually consistent across the newer tab screens (all use `Screen`/`States`), so no gap there — noted so it isn't re-investigated.
- No dead-end backend routes of note: every substantive route is called from `client.ts`. (`rewards_summary` at `mobile_api.py:1458` has no client method — confirm whether a rewards feature is intended before building UI; flag for the human, not scheduled.)

## Phase 2 reference: design tokens (clean/minimal fintech)

Colors (replace/extend `src/theme/colors.ts`):
- primary `#4f46e5` (indigo, single accent), primaryDark `#4338ca`, primarySoft `#eef2ff`, primaryBorder `rgba(79,70,229,0.22)`
- ink/text `#0f172a`, secondary `#475569`, muted `#94a3b8`, placeholder `#cbd5e1`
- bg `#fafbfc`, surface `#ffffff`, surfaceAlt `#f1f5f9`, border `#eef0f4`, borderStrong `#e2e8f0`
- success `#16a34a`, successSoft `#f0fdf4`, danger `#e11d48`, dangerSoft `#fff1f3`, warning `#d97706`, warningSoft `#fffbeb`
- Keep it to one accent (indigo); use success/danger only for money direction, not for decorative icon tiles. Retire the multi-colored stat-icon tiles (blue/accent/green/red) from Home/Split in favour of neutral tiles with colored numbers.

Spacing scale (4pt base): xs 4, sm 8, md 12, lg 16, xl 24, xxl 32. Screen horizontal padding `lg` (16), card internal padding `lg` (16), gap between cards `md` (12).

Radius: sm 8, md 12, lg 16, pill 999. Cards use `md` (12); buttons/inputs use `md` (12); avatars/tiles use `md`.

Type scale (sizes / weight): display 30/700, h1 24/700, h2 20/700, h3 17/600, body 15/400, bodyStrong 15/600, label 13/600 (not uppercase-900), caption 12/500. Expose as exported styles in `src/theme/typography.ts` so screens stop hand-rolling `fontSize`+`fontWeight 900`. Drop the current `fontWeight: '900'` everywhere — it reads heavy for fintech; headings max at 700.

Component-level changes:
1. Card: remove the 1px border, use shadow only (`shadowOpacity ~0.06`, `shadowRadius 12`, `offset {0,6}`, `elevation 2`), padding `lg` (16), radius `md` (12).
2. AppButton: `minHeight 52`, radius `md`, primary uses indigo at full but text `fontWeight 600`; outline becomes a hairline `borderStrong` on `surface` (not the current filled `primarySoft`); ghost unchanged.
3. Stat/summary blocks: replace saturated colored icon tiles with neutral `surfaceAlt` tiles + an indigo or success/danger colored value, so the one-accent rule holds and money direction stays legible.
4. TextField: radius `md` (12), border `borderStrong`, focus border `primary`; label `label` style (13/600, not 800).
