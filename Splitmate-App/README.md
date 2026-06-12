# Splitmate Mobile App

Cross-platform iOS and Android app for Splitmate, built with Expo and React Native.

## What Is Included

- Email/password login against the Splitmate Flask backend
- Mobile token authentication through `/api/mobile`
- Group list and group dashboard
- Add groups and group members
- Add expenses with equal, selected-user, exact amount, and percentage splits
- View balances, expenses, outstanding splits, payments, tasks, and notes
- Add tasks with reminder times
- Add and complete notes
- Local task reminder notifications
- Expo push-token registration endpoint for future server push notifications

## Run The Flask Backend

From the parent Splitmate folder:

```powershell
.\venv\Scripts\python.exe run.py
```

The backend should be available at:

```text
http://127.0.0.1:5000
```

## Configure The Mobile API URL

The mobile app talks to:

```text
/api/mobile
```

For Expo Go on a physical phone, use your computer's LAN IP:

```text
http://YOUR_COMPUTER_IP:5000/api/mobile
```

You can set it in the app's Settings screen, or create `.env` from `.env.example`:

```powershell
Copy-Item .env.example .env
```

Then edit:

```text
EXPO_PUBLIC_SPLITMATE_API_URL=http://YOUR_COMPUTER_IP:5000/api/mobile
```

## Install And Run

```powershell
cd Splitmate-App
npm install
npm run start
```

Then press:

- `a` for Android emulator
- `i` for iOS simulator on macOS
- scan the QR code with Expo Go for a real phone

## Notifications

The app asks for notification permission after login. It schedules local notifications for task reminders returned by the backend. It also registers the Expo push token with `/api/mobile/devices`, so the backend can send push notifications later.

## Build Native Apps

Use EAS Build when you are ready for store builds:

```powershell
npx eas build --platform android
npx eas build --platform ios
```
