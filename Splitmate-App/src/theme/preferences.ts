import * as SecureStore from 'expo-secure-store';
import { Appearance, Platform } from 'react-native';

import { ACCENT_PRESETS, AccentKey, ThemeMode } from '@/theme/colors';

export const THEME_ACCENT_KEY = 'splitmate.mobile.theme-accent';
export const THEME_MODE_KEY = 'splitmate.mobile.theme-mode';
export const TASK_NOTIFICATIONS_KEY = 'splitmate.mobile.task-notifications';

type WebStorage = {
  getItem: (key: string) => string | null;
  setItem: (key: string, value: string) => void;
};

function webStorage() {
  if (Platform.OS !== 'web') {
    return null;
  }
  return (globalThis as unknown as { localStorage?: WebStorage }).localStorage || null;
}

/** Synchronous read, so the theme can be applied before any screen loads. */
export function readPreference(key: string): string | null {
  try {
    const storage = webStorage();
    if (storage) {
      return storage.getItem(key);
    }
    return Platform.OS === 'web' ? null : SecureStore.getItem(key);
  } catch {
    return null;
  }
}

export async function writePreference(key: string, value: string) {
  const storage = webStorage();
  if (storage) {
    storage.setItem(key, value);
    return;
  }
  if (Platform.OS !== 'web') {
    await SecureStore.setItemAsync(key, value);
  }
}

export function storedAccent(): AccentKey {
  const saved = readPreference(THEME_ACCENT_KEY);
  return saved && saved in ACCENT_PRESETS ? (saved as AccentKey) : 'blue';
}

export function storedThemeMode(): ThemeMode {
  const saved = readPreference(THEME_MODE_KEY);
  return saved === 'light' || saved === 'dark' || saved === 'system' ? saved : 'system';
}

/** Like the website: follow the device until the person picks a theme. */
export function resolveScheme(mode: ThemeMode): 'light' | 'dark' {
  if (mode === 'system') {
    return Appearance.getColorScheme() === 'dark' ? 'dark' : 'light';
  }
  return mode;
}

export function storedTaskNotificationsEnabled() {
  return readPreference(TASK_NOTIFICATIONS_KEY) !== 'off';
}
