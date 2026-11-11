# Splitmate-App

The Splitmate mobile app for iOS and Android, built with Expo and React Native. It talks to the Flask backend in [`../Splitmate-Web`](../Splitmate-Web/README.md) through the mobile API documented in [`../Splitmate-Web/docs/API.md`](../Splitmate-Web/docs/API.md).

## Features

- Sign up, verify email with a code, sign in, reset password; the login token is stored in the device's secure storage
- Four tabs: **Home** (dashboard), **Split** (groups and balances), **Tasks**, **Notes**
- Groups: create, rename, invite by email, link or QR code, accept invites, member nicknames, admin hand-over, leave or delete
- Expenses: equal, selected-members, exact and percentage splits, categories, a default split per group, receipt photos, and **receipt scanning** that fills in the form
- Settle up: record payments, confirm or decline incoming ones, per-person balances, and "Open my bank" / Interac shortcuts for Canadian banks
- Tasks with due dates, reminders, assignees, priority and recurrence, plus a task calendar; reminders arrive as local notifications
- Notes and grocery lists with a store price comparison
- Insights charts, rewards and membership, profile with payment handles and QR code, data export
- In-app help chat (offline FAQ), light/dark/system theme, and an API URL setting for pointing at any backend

## Tech stack

| Area | Choice |
| --- | --- |
| Framework | Expo SDK 58, React Native 0.88, React 19 |
| Language | TypeScript (strict) |
| Navigation | React Navigation 7 (native stack + bottom tabs) |
| Storage | `expo-secure-store` for the token and preferences |
| Device features | `expo-notifications`, `expo-image-picker`, `expo-document-picker`, `expo-clipboard`, `expo-intent-launcher`, `@react-native-community/datetimepicker` |
| Fonts and icons | `@expo-google-fonts/inter`, `@expo/vector-icons` |
| Builds | EAS Build (`eas.json`), `expo-dev-client` |

## Folder structure

```text
Splitmate-App/
├── App.tsx                 Providers (theme, auth, navigation) and font loading
├── index.ts                Entry point
├── app.json                Expo config: name, bundle IDs, permissions, plugins, EAS project
├── eas.json                EAS build profiles: development, preview (APK), production
├── plugins/
│   ├── withCleartextTraffic.js   Allows plain HTTP on Android for local testing (off in production builds)
│   └── withBankAppQueries.js     Lets Android see installed bank apps for "Open my bank"
├── src/
│   ├── api/client.ts       SplitmateApi: every call to /api/mobile lives here
│   ├── types.ts            Types for every API response (kept in sync with the server)
│   ├── navigation/         AppNavigator (auth vs signed-in stack) and TabNavigator (4 tabs)
│   ├── screens/            One file per screen
│   ├── components/         Shared UI: AppText, AppButton, Card, TextField, Charts, QrCode, ...
│   ├── state/              AuthContext (session, API URL) and ThemeContext
│   ├── services/           notifications.ts (permissions, push token, local reminders)
│   ├── theme/              Colours, typography and saved theme preference
│   └── utils/              money, dates, banks (canadian-banks.json)
├── docs/ROADMAP.md         Planned and finished work items
└── CLAUDE.md               Project brief and conventions for AI assistants
```

The `@/` import alias points at `src/`.

## Prerequisites

- Node.js 22 and npm
- The backend running (see [`../Splitmate-Web/README.md`](../Splitmate-Web/README.md))
- One of:
  - **Expo Go** on your phone (App Store / Google Play), on the same Wi-Fi as your computer
  - an Android emulator (Android Studio)
  - the iOS Simulator (Xcode, macOS only)

## Setup

### Windows (PowerShell)

```powershell
cd Splitmate-App
npm install
Copy-Item .env.example .env
notepad .env
```

### macOS / Linux

```bash
cd Splitmate-App
npm install
cp .env.example .env
```

Set the backend address in `.env`:

```text
EXPO_PUBLIC_SPLITMATE_API_URL=http://192.168.1.50:5000/api/mobile
```

Use your computer's LAN IP (Windows: `ipconfig`; macOS: `ipconfig getifaddr en0`), not `localhost`. A phone's `localhost` is the phone itself.

## Running

```bash
npm run start            # Expo dev server (uses the development build if one is installed)
npx expo start --go      # force Expo Go
npx expo start --clear   # after changing .env: clears the cache so the new URL is picked up
```

Then scan the QR code with the camera (iOS) or the Expo Go app (Android), or press `a` for the Android emulator or `i` for the iOS simulator.

### How the app finds the backend

`defaultApiBaseUrl()` in `src/api/client.ts` picks the first of:

1. `EXPO_PUBLIC_SPLITMATE_API_URL` (inlined at bundle time, so restart with `--clear` after changing it)
2. `expo.extra.apiBaseUrl` in `app.json`
3. `http://<the Expo dev server's host>:5000/api/mobile`. This works automatically when the backend runs on the same computer as Expo.

You can also change the URL inside the app: on the sign-in screen, or in **Settings**. The value is saved on the device.

### Environment variables

| Variable | Where | Purpose |
| --- | --- | --- |
| `EXPO_PUBLIC_SPLITMATE_API_URL` | `.env` | Backend mobile API base URL |
| `SPLITMATE_ALLOW_CLEARTEXT` | build environment | Set to `false` to stop allowing plain HTTP on Android. The `production` EAS profile already sets it. |

## Checks

```bash
npm run typecheck
```

There are no app unit tests yet. The backend's `tests/test_mobile_api.py` covers the API the app uses.

## Building

Builds use [EAS](https://docs.expo.dev/build/introduction/) (project `rk011s-team/splimate`):

```bash
npx eas build --profile development --platform android   # dev client
npx eas build --profile preview --platform android       # installable APK for testers
npx eas build --profile production --platform all        # store builds (HTTPS only)
```

Production builds need a backend served over **HTTPS**.

## Notifications

After sign-in the app asks for notification permission, registers its Expo push token with `POST /api/mobile/devices`, and schedules local notifications for upcoming task reminders (`GET /api/mobile/reminders/upcoming`). Push notifications don't work in Expo Go on Android; use a development build.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| "Network request failed" / can't sign in | Check the API URL (sign-in screen or Settings). Open `http://<ip>:5000/api/mobile/health` in the phone's browser; it should show `{"ok": true}`. Allow Python through the Windows Firewall on private networks. |
| Changed `.env` but the app uses the old URL | Restart with `npx expo start --clear`. |
| Expo Go says the project is incompatible | This project uses SDK 58. Update Expo Go, or use a development build. |
| Phone can't load the bundle at all | The phone and computer must be on the same network. Otherwise use `npx expo start --tunnel`. |
| Android release build can't reach `http://` | Expected: production builds require HTTPS. |
| Typecheck errors after pulling | Run `npm install`; dependencies may have changed. |
