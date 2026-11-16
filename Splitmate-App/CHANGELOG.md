# Changelog: Splitmate-App

All notable changes to the mobile app. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Group settings: type an email or a mobile number. For a number, "Text invite" opens Messages with the invite and link ready to send, and "Text it again" re-opens it. Pending invites show the number with most digits hidden.
- Quick split: friends whose number isn't on Splitmate get a "Text an invite" button instead of being asked for an email.
- Group settings lists "Friends from your other groups" with a one-tap Invite button.

### Changed
- Expenses you didn't pay and aren't part of no longer show anywhere in the app.

## [0.1.0] - 2026-11-11

First documented release.

### Added
- Bottom-tab navigation: Home, Split, Tasks, Notes.
- Sign-up with email verification code, sign-in, password reset. The token is kept in secure storage.
- Groups: create, rename, invites by email, link and QR code, nicknames, admin hand-over, leave and delete.
- Expenses with equal, selected, exact and percentage splits, categories, a default split, receipt photos and receipt scanning.
- Payments: record, confirm or decline; per-person balances; bank and Interac shortcuts.
- Tasks with reminders, recurrence and a calendar; local reminder notifications and push-token registration.
- Notes with grocery price comparison.
- Insights charts, rewards and membership, profile QR code and payment handles, data export, help chat.
- Light, dark and system themes; in-app API URL setting.
- EAS build profiles and the `expo-dev-client` development build.

### Changed
- Upgraded to Expo SDK 58 / React Native 0.88.
