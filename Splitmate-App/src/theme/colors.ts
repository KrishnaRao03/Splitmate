import { Platform } from 'react-native';

export const colors = {
  // Navy, mint and off white (picked by Krishna on 2026-11-15), plus one red for warnings.
  ink: '#1a2340',
  text: '#1a2340',
  secondary: '#46506e',
  muted: '#646c88',
  primary: '#1a2340',
  primaryDark: '#0d1222',
  primaryStrong: '#0d1222',
  primarySoft: '#e3f7ee',
  primaryFocus: 'rgba(26, 35, 64, 0.14)',
  primaryBorder: 'rgba(26, 35, 64, 0.22)',
  accent: '#1a2340',
  accentSoft: '#e3f7ee',
  // Money owed to you and settled amounts: a deeper mint so it reads on white.
  success: '#1b7f5a',
  successSoft: '#ddf5ea',
  danger: '#c93c4a',
  dangerDark: '#a82f3c',
  dangerSoft: '#fdecee',
  warning: '#c93c4a',
  warningSoft: '#fdecee',
  bg: '#f1f3f8',
  surface: '#ffffff',
  surfaceGlass: 'rgba(241, 243, 248, 0.94)',
  surfaceBlue: '#e8ebf3',
  surfaceAlt: '#e8ebf3',
  hoverSurface: '#e8ebf3',
  border: '#e1e5ee',
  borderStrong: '#c9cfdd',
  input: '#ffffff',
  placeholder: '#9aa1b8',
  pageTint: '#f1f3f8',
  white: '#ffffff',
  // Mint for main buttons, with navy text on it.
  highlight: '#7fe0b5',
  onHighlight: '#1a2340',
  // The receipt style balance card on Home.
  receipt: '#1a2340',
  onReceipt: '#f1f3f8',
  receiptLine: '#46506e',
  // Text and icons drawn on a primary-coloured fill.
  onPrimary: '#ffffff'
};

export type ThemeMode = 'system' | 'light' | 'dark';
export type AccentKey = 'indigo' | 'blue' | 'green' | 'rose';

/** color/dark/soft are the light-mode shades; night/nightLight are used in dark mode. */
export const ACCENT_PRESETS: Record<AccentKey, { label: string; color: string; dark: string; soft: string; night: string; nightLight: string }> = {
  indigo: { label: 'Navy', color: '#1a2340', dark: '#0d1222', soft: '#e3f7ee', night: '#7fe0b5', nightLight: '#a8edcf' },
  blue: { label: 'Blue', color: '#2563eb', dark: '#1d4ed8', soft: '#eff6ff', night: '#3b82f6', nightLight: '#93c5fd' },
  green: { label: 'Green', color: '#16a34a', dark: '#15803d', soft: '#f0fdf4', night: '#22c55e', nightLight: '#86efac' },
  rose: { label: 'Rose', color: '#e11d48', dark: '#be123c', soft: '#fff1f3', night: '#f43f5e', nightLight: '#fda4af' }
};

const darkNeutrals: Partial<typeof colors> = {
  ink: '#f1f3f8',
  text: '#e6e9f2',
  secondary: '#b9c0d6',
  muted: '#8c94b0',
  success: '#7fe0b5',
  successSoft: 'rgba(127, 224, 181, 0.16)',
  danger: '#ff8a8a',
  dangerDark: '#ff6b6b',
  dangerSoft: 'rgba(255, 138, 138, 0.16)',
  warning: '#ff8a8a',
  warningSoft: 'rgba(255, 138, 138, 0.16)',
  bg: '#0d1222',
  surface: '#161d36',
  surfaceGlass: 'rgba(13, 18, 34, 0.94)',
  surfaceBlue: '#1c2645',
  surfaceAlt: '#1c2645',
  hoverSurface: '#1c2645',
  border: '#263055',
  borderStrong: '#2f3a5e',
  input: '#0d1222',
  placeholder: '#5e6788',
  pageTint: '#161d36',
  onHighlight: '#0d1222',
  receipt: '#1c2645',
  onReceipt: '#f1f3f8',
  receiptLine: '#3b4770'
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
      accentSoft: hexToRgba(preset.night, 0.18),
      onPrimary: accent === 'indigo' ? '#0d1222' : '#ffffff'
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
    accentSoft: preset.soft,
    onPrimary: '#ffffff'
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
  regular: 'Manrope_400Regular',
  medium: 'Manrope_500Medium',
  semiBold: 'Manrope_600SemiBold',
  bold: 'Manrope_700Bold',
  // The design guide caps weight at bold, so the heaviest style is bold too.
  extraBold: 'Manrope_700Bold',
  // Amounts on the receipt style card; the system monospace, so no extra font download.
  mono: Platform.select({ ios: 'Menlo', android: 'monospace', default: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace' }) as string
};

