import React, { createContext, useContext, useMemo, useState } from 'react';

import { ACCENT_PRESETS, AccentKey, ThemeMode, activeColorScheme } from '@/theme/colors';
import {
  THEME_ACCENT_KEY,
  THEME_MODE_KEY,
  resolveScheme,
  storedAccent,
  storedThemeMode,
  writePreference
} from '@/theme/preferences';

export { ACCENT_PRESETS };
export type { AccentKey, ThemeMode };

type ThemeState = {
  accent: AccentKey;
  accentColor: string;
  accentColorDark: string;
  accentColorSoft: string;
  setAccent: (accent: AccentKey) => void;
  mode: ThemeMode;
  setMode: (mode: ThemeMode) => void;
  /** The scheme the screens were built with at startup. */
  scheme: 'light' | 'dark';
  /** True when the saved theme differs from what is on screen until the app restarts. */
  restartNeeded: boolean;
};

const ThemeContext = createContext<ThemeState | null>(null);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  // Read synchronously so the first render already matches what bootstrap applied.
  const [accent, setAccentState] = useState<AccentKey>(storedAccent);
  const [mode, setModeState] = useState<ThemeMode>(storedThemeMode);
  const [bootAccent] = useState<AccentKey>(storedAccent);
  const scheme = activeColorScheme();

  const value = useMemo<ThemeState>(() => {
    const preset = ACCENT_PRESETS[accent];
    const dark = scheme === 'dark';
    return {
      accent,
      accentColor: dark ? preset.night : preset.color,
      accentColorDark: dark ? preset.nightLight : preset.dark,
      accentColorSoft: preset.soft,
      setAccent: (next: AccentKey) => {
        setAccentState(next);
        writePreference(THEME_ACCENT_KEY, next).catch(() => undefined);
      },
      mode,
      setMode: (next: ThemeMode) => {
        setModeState(next);
        writePreference(THEME_MODE_KEY, next).catch(() => undefined);
      },
      scheme,
      restartNeeded: resolveScheme(mode) !== scheme || accent !== bootAccent
    };
  }, [accent, mode, scheme, bootAccent]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used inside ThemeProvider');
  }
  return context;
}
