export const colors = {
  ink: '#0f172a',
  text: '#0f172a',
  secondary: '#475569',
  muted: '#94a3b8',
  primary: '#2563eb',
  primaryDark: '#1d4ed8',
  primaryStrong: '#1d4ed8',
  primarySoft: '#eff6ff',
  primaryFocus: 'rgba(37, 99, 235, 0.14)',
  primaryBorder: 'rgba(37, 99, 235, 0.22)',
  accent: '#2563eb',
  accentSoft: '#eff6ff',
  success: '#16a34a',
  successSoft: '#f0fdf4',
  danger: '#e11d48',
  dangerDark: '#be123c',
  dangerSoft: '#fff1f3',
  warning: '#d97706',
  warningSoft: '#fffbeb',
  bg: '#fafbfc',
  surface: '#ffffff',
  surfaceGlass: 'rgba(255, 255, 255, 0.92)',
  surfaceBlue: '#f1f5f9',
  surfaceAlt: '#f1f5f9',
  hoverSurface: '#f1f5f9',
  border: '#eef0f4',
  borderStrong: '#e2e8f0',
  input: '#ffffff',
  placeholder: '#cbd5e1',
  pageTint: '#eef2ff',
  white: '#ffffff'
};

export type ThemeMode = 'system' | 'light' | 'dark';
export type AccentKey = 'blue' | 'indigo' | 'green' | 'rose';

/** color/dark/soft are the light-mode shades; night/nightLight are used in dark mode. */
export const ACCENT_PRESETS: Record<AccentKey, { label: string; color: string; dark: string; soft: string; night: string; nightLight: string }> = {
  blue: { label: 'Blue', color: '#2563eb', dark: '#1d4ed8', soft: '#eff6ff', night: '#3b82f6', nightLight: '#93c5fd' },
  indigo: { label: 'Indigo', color: '#4f46e5', dark: '#4338ca', soft: '#eef2ff', night: '#6366f1', nightLight: '#a5b4fc' },
  green: { label: 'Green', color: '#16a34a', dark: '#15803d', soft: '#f0fdf4', night: '#22c55e', nightLight: '#86efac' },
  rose: { label: 'Rose', color: '#e11d48', dark: '#be123c', soft: '#fff1f3', night: '#f43f5e', nightLight: '#fda4af' }
};

const darkNeutrals: Partial<typeof colors> = {
  ink: '#f1f5f9',
  text: '#e2e8f0',
  secondary: '#cbd5e1',
  muted: '#94a3b8',
  success: '#22c55e',
  successSoft: 'rgba(34, 197, 94, 0.16)',
  danger: '#fb7185',
  dangerDark: '#f43f5e',
  dangerSoft: 'rgba(251, 113, 133, 0.16)',
  warning: '#f59e0b',
  warningSoft: 'rgba(245, 158, 11, 0.16)',
  bg: '#0b1120',
  surface: '#111827',
  surfaceGlass: 'rgba(17, 24, 39, 0.94)',
  surfaceBlue: '#1e293b',
  surfaceAlt: '#1e293b',
  hoverSurface: '#1e293b',
  border: '#1f2937',
  borderStrong: '#334155',
  input: '#0f172a',
  placeholder: '#64748b',
  pageTint: '#111827'
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
  const preset = ACCENT_PRESETS[accent] || ACCENT_PRESETS.blue;
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
  sm: 8,
  md: 12,
  lg: 16,
  pill: 999
};

export const fonts = {
  regular: 'Inter_400Regular',
  medium: 'Inter_500Medium',
  semiBold: 'Inter_600SemiBold',
  bold: 'Inter_700Bold',
  extraBold: 'Inter_800ExtraBold'
};
