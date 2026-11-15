# Splitmate on the App Store and Google Play

Everything the stores ask for, with the answers filled in. The code side is done; the parts marked **You** need your accounts.

## 1. What's ready in the app

| Store rule | Where it is |
| --- | --- |
| Delete account inside the app (Apple 5.1.1(v), Google Play) | Settings, then Delete account (needs password). Server: `POST /api/mobile/me/delete` |
| Account deletion web link (Google Play) | `https://splitmate-web.onrender.com/delete-account` |
| Privacy policy link | `https://splitmate-web.onrender.com/privacy`, linked in Settings and on sign up |
| Terms | `https://splitmate-web.onrender.com/terms` |
| No test or developer screens | Connection and API URL fields only show in development builds |
| Subscriptions inside store apps must use store billing (Apple 3.1.1, Google Play billing) | iPhone and Android builds don't sell Pro with Stripe. Pro bought on the web still works, and points buy Pro time. See section 6 |
| Points have no cash value | Terms, Points section |
| iOS icon without transparency | `assets/images/icon.png` (1024, no alpha) |
| Android adaptive icon | `assets/images/adaptive-icon.png` on navy `#1a2340` |
| Splash in light and dark | `app.json` splash |
| Encryption export question | `ITSAppUsesNonExemptEncryption: false` (only standard HTTPS) |
| Apple privacy manifest | `ios.privacyManifests` in `app.json` (no tracking) |
| Permissions | Camera and photos for receipt scans only. Microphone and location are blocked on Android |
| First-run tour | 4 step tour for new accounts, replay from Settings |

## 2. Accounts you need (**You**)

1. Apple Developer Program, US$99 a year: https://developer.apple.com/programs/enroll/
2. Google Play Console, US$25 once: https://play.google.com/console/signup
   New personal accounts must run a closed test with at least 12 testers for 14 days before going public.
3. Set `SUPPORT_EMAIL` on Render (splitmate-web) to the email you want shown in the privacy policy. Until then it shows the email that sends Splitmate's emails.
4. Deploy the latest code on Render so the privacy, terms and delete account pages are live before you submit.

## 3. Build and submit (**You**, from Splitmate-App)

```
npm install -g eas-cli
eas login
eas build --platform ios --profile production
eas build --platform android --profile production
eas submit --platform ios --latest
eas submit --platform android --latest
```

Before the first iOS submit, create the app in App Store Connect (bundle ID `com.splitmate.mobile`) and put its Apple ID number in `eas.json` under `submit.production.ios.ascAppId`.
For Android, the first upload must be done by hand in Play Console (upload the `.aab` from the build page); after that `eas submit` works with a service account key.

The production build must point at the live server. Set `EXPO_PUBLIC_SPLITMATE_API_URL=https://splitmate-web.onrender.com/api/mobile` in the EAS production environment (expo.dev, Project, Environment variables).

Note: the Expo project slug is `splimate` (missing a "t"). It only shows in Expo URLs; renaming it means relinking the EAS project, so leave it unless it bothers you.

## 4. Store listing text

**Name:** Splitmate
**Subtitle (Apple, 30 chars):** Split bills, settle up directly
**Short description (Google, 80 chars):** Split bills with friends and housemates, then pay each other directly.

**Description:**

Splitmate keeps shared money simple for housemates, trips and friends.

- Make a group and invite people by email or QR code
- Add a bill and Splitmate works out who owes what, equally or your own way
- Scan a receipt to fill in the items
- Settle up directly with Interac e-Transfer, PayPal or UPI. Splitmate never holds your money
- The person you paid confirms it arrived, so balances stay right
- Share tasks with reminders and group notes
- Compare grocery prices near you
- Earn points for inviting friends and settling up, and spend them on free Pro time

Splitmate Pro gives unlimited receipt scans and grocery price comparisons.

**Keywords (Apple, 100 chars):** split,bills,expenses,roommates,housemates,trip,friends,group,owe,settle,interac,receipt,shared

**Category:** Finance (secondary: Productivity)
**Age rating:** 4+ (Apple) / Everyone (Google). No user-to-user chat, no gambling, no mature content.
**Support URL:** https://splitmate-web.onrender.com
**Marketing URL:** https://splitmate-app.onrender.com

## 5. Privacy answers

### Apple App Privacy ("nutrition label")

Tracking: **No**. Data linked to the user, used for App Functionality only:

| Data type | Collected | Why |
| --- | --- | --- |
| Name, Email address | Yes | Account |
| Phone number | Yes (optional) | Find friends |
| Other financial info (Interac email, PayPal.Me, UPI ID, expense amounts) | Yes | Paying friends, splitting |
| Photos | Yes (receipts you choose) | Receipt scans |
| Other user content (notes, tasks, group names) | Yes | App functionality |
| Purchase history | Yes (Pro status) | App functionality |
| User ID, Device ID (push token) | Yes | Notifications, sign in |
| Coarse location | No (web only, typed or rounded, not stored) | |
| Diagnostics, Usage data for analytics, Advertising data | No | |

### Google Play Data safety

- Data shared with third parties: **No** (providers that process data for us, like hosting and email, don't count as sharing).
- Data encrypted in transit: **Yes**.
- Users can request deletion: **Yes**, in the app and at the delete account link.
- Collected: Personal info (name, email, phone optional), Financial info (payment handles, purchase history), Photos (receipts), App activity (in-app content), Device IDs (push token). All for App functionality and Account management, none for ads or analytics. Phone and photos are optional.

## 6. Pro inside the store apps (decision for later)

Apple and Google require their own billing for subscriptions sold inside an app. Right now the store builds don't sell Pro; people can buy it on the website or earn Pro time with points. When you want Pro for sale inside the iPhone and Android apps, the usual route is RevenueCat (free under US$2.5k a month) with App Store and Play subscriptions, and the server marks Pro from RevenueCat's webhook the same way it does from Stripe's today.

## 7. Review notes to paste (both stores)

> Splitmate never processes payments between users; members pay each other outside the app (Interac, PayPal, UPI) and record it. Demo account: reviewer@splitmate.app / (password you set). It already belongs to a sample group with expenses.

Create that demo account on the live site before submitting and add a group with a few expenses.

## 8. Screenshots to take

iPhone 6.9" (1320 x 2868) and Android phone, light mode:
1. Home with the receipt balance card
2. A group with expenses
3. Split a bill
4. Settle up with the Interac button
5. Receipt scan result
6. Profile with points and rewards
