export const colors = {
  ink: '#0f172a',
  text: '#0f172a',
  secondary: '#475569',
  muted: '#94a3b8',
  primary: '#4f46e5',
  primaryDark: '#4338ca',
  primaryStrong: '#4338ca',
  primarySoft: '#eef2ff',
  primaryFocus: 'rgba(79, 70, 229, 0.14)',
  primaryBorder: 'rgba(79, 70, 229, 0.22)',
  accent: '#4f46e5',
  accentSoft: '#eef2ff',
  // Teal: money owed to you and settled amounts, the second colour of the logo.
  success: '#0d9488',
  successSoft: '#ccfbf1',
  danger: '#e11d48',
  dangerDark: '#be123c',
  dangerSoft: '#fff1f3',
  warning: '#d97706',
  warningSoft: '#fffbeb',
  bg: '#f6f7fb',
  surface: '#ffffff',
  surfaceGlass: 'rgba(255, 255, 255, 0.92)',
  surfaceBlue: '#f1f2fa',
  surfaceAlt: '#f1f2fa',
  hoverSurface: '#f1f2fa',
  border: '#eceef5',
  borderStrong: '#dfe2ee',
  input: '#ffffff',
  placeholder: '#cbd5e1',
  pageTint: '#eef0ff',
  white: '#ffffff'
};

export type ThemeMode = 'system' | 'light' | 'dark';
export type AccentKey = 'indigo' | 'blue' | 'green' | 'rose';

/** color/dark/soft are the light-mode shades; night/nightLight are used in dark mode. */
export const ACCENT_PRESETS: Record<AccentKey, { label: string; color: string; dark: string; soft: string; night: string; nightLight: string }> = {
  indigo: { label: 'Indigo', color: '#4f46e5', dark: '#4338ca', soft: '#eef2ff', night: '#6366f1', nightLight: '#a5b4fc' },
  blue: { label: 'Blue', color: '#2563eb', dark: '#1d4ed8', soft: '#eff6ff', night: '#3b82f6', nightLight: '#93c5fd' },
  green: { label: 'Green', color: '#16a34a', dark: '#15803d', soft: '#f0fdf4', night: '#22c55e', nightLight: '#86efac' },
  rose: { label: 'Rose', color: '#e11d48', dark: '#be123c', soft: '#fff1f3', night: '#f43f5e', nightLight: '#fda4af' }
};

const darkNeutrals: Partial<typeof colors> = {
  ink: '#f1f5f9',
  text: '#e2e8f0',
  secondary: '#cbd5e1',
  muted: '#94a3b8',
  success: '#2dd4bf',
  successSoft: 'rgba(45, 212, 191, 0.16)',
  danger: '#fb7185',
  dangerDark: '#f43f5e',
  dangerSoft: 'rgba(251, 113, 133, 0.16)',
  warning: '#f59e0b',
  warningSoft: 'rgba(245, 158, 11, 0.16)',
  bg: '#0c0e1a',
  surface: '#151829',
  surfaceGlass: 'rgba(21, 24, 41, 0.94)',
  surfaceBlue: '#1f2338',
  surfaceAlt: '#1f2338',
  hoverSurface: '#1f2338',
  border: '#24283d',
  borderStrong: '#3a405c',
  input: '#10131f',
  placeholder: '#64748b',
  pageTint: '#151829'
};

let activeScheme: 'light' | 'dark' = 'light';

/** The scheme applied at startup (screens read `colors` once, when they load). */
export function activeColorScheme() {
  return activeScheme;
}

/**
 * Rewrites the shared `colors` object in place. Screens build their StyleSheets
 * from `colors` when their module loads, so this must run before App is imported
 * (see src/theme/bootstrap.ts); later changes apply on the next app start.
 */
export function applyTheme(scheme: 'light' | 'dark', accent: AccentKey) {
  const preset = ACCENT_PRESETS[accent] || ACCENT_PRESETS.indigo;
  activeScheme = scheme;
  if (scheme === 'dark') {
    Object.assign(colors, darkNeutrals, {
      primary: preset.night,
      primaryDark: preset.nightLight,
      primaryStrong: preset.nightLight,
      primarySoft: hexToRgba(preset.night, 0.18),
      primaryFocus: hexToRgba(preset.night, 0.24),
      primaryBorder: hexToRgba(preset.night, 0.4),
      accent: preset.night,
      accentSoft: hexToRgba(preset.night, 0.18)
    });
    return;
  }
  Object.assign(colors, {
    primary: preset.color,
    primaryDark: preset.dark,
    primaryStrong: preset.dark,
    primarySoft: preset.soft,
    primaryFocus: hexToRgba(preset.color, 0.14),
    primaryBorder: hexToRgba(preset.color, 0.22),
    accent: preset.color,
    accentSoft: preset.soft
  });
}

function hexToRgba(hex: string, alpha: number) {
  const value = hex.replace('#', '');
  const r = parseInt(value.slice(0, 2), 16);
  const g = parseInt(value.slice(2, 4), 16);
  const b = parseInt(value.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32
};

export const radius = {
  sm: 10,
  md: 16,
  lg: 20,
  pill: 999
};

export const fonts = {
  regular: 'Inter_400Regular',
  medium: 'Inter_500Medium',
  semiBold: 'Inter_600SemiBold',
  bold: 'Inter_700Bold',
  extraBold: 'Inter_800ExtraBold'
};

/** Bright gradients for hero cards and stat tiles: [from, to]. */
export const gradients = {
  brand: ['#4f46e5', '#7c3aed', '#14b8a6'],
  owed: ['#0d9488', '#10b981'],
  owe: ['#e11d48', '#f97316'],
  violet: ['#7c3aed', '#a855f7'],
  amber: ['#f59e0b', '#f97316'],
  sky: ['#0284c7', '#06b6d4']
} as const;

/** Colours for category and group badges, picked by name so each stays the same everywhere. */
export const badgePalette = ['#6366f1', '#14b8a6', '#f97316', '#e11d48', '#a855f7', '#0ea5e9', '#f59e0b', '#10b981'];

export function badgeColor(name: string) {
  let hash = 0;
  for (const char of name || '?') {
    hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  }
  return badgePalette[hash % badgePalette.length];
}
