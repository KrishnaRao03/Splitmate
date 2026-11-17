import { Linking, Platform, Share } from 'react-native';

function isApple() {
  if (Platform.OS === 'ios') {
    return true;
  }
  if (Platform.OS !== 'web' || typeof navigator === 'undefined') {
    return false;
  }
  return /iPhone|iPad|iPod|Macintosh/.test(navigator.userAgent);
}

/**
 * Opens the phone's own Messages app with the invite already typed, so texting is free and needs no SMS service.
 * Falls back to the share sheet when there is no Messages app (a desktop browser, say).
 */
export async function sendTextInvite(phone: string, message: string) {
  // iPhones read the body after '&', Android after '?'.
  const url = `sms:${phone}${isApple() ? '&' : '?'}body=${encodeURIComponent(message)}`;
  try {
    if (Platform.OS === 'web') {
      const mobileBrowser = typeof navigator !== 'undefined' && /iPhone|iPad|iPod|Android/.test(navigator.userAgent);
      if (mobileBrowser) {
        window.location.href = url;
        return;
      }
    } else if (await Linking.canOpenURL(url)) {
      await Linking.openURL(url);
      return;
    }
  } catch {
    // Fall through to the share sheet.
  }
  try {
    await Share.share({ message });
  } catch {
    // The share sheet was dismissed; nothing to undo.
  }
}
