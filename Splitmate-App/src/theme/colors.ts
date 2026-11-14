export const colors = {
  ink: '#1f2023',
  text: '#1f2023',
  secondary: '#4a4d55',
  muted: '#8b8f98',
  primary: '#2b2d31',
  primaryDark: '#1f2023',
  primaryStrong: '#1f2023',
  primarySoft: '#fff6d6',
  primaryFocus: 'rgba(43, 45, 49, 0.14)',
  primaryBorder: 'rgba(43, 45, 49, 0.22)',
  accent: '#2b2d31',
  accentSoft: '#fff6d6',
  // Teal: money owed to you and settled amounts, the second colour of the logo.
  success: '#0d9488',
  successSoft: '#ccfbf1',
  danger: '#e11d48',
  dangerDark: '#be123c',
  dangerSoft: '#fff1f3',
  warning: '#d97706',
  warningSoft: '#fffbeb',
  bg: '#f7f7f5',
  surface: '#ffffff',
  surfaceGlass: 'rgba(255, 255, 255, 0.92)',
  surfaceBlue: '#f1f1ef',
  surfaceAlt: '#f1f1ef',
  hoverSurface: '#f1f1ef',
  border: '#ececea',
  borderStrong: '#dcdcd8',
  input: '#ffffff',
  placeholder: '#b9bcc2',
  pageTint: '#fff9e6',
  white: '#ffffff',
  // Sunshine yellow for main buttons and the balance card, with graphite text on it.
  highlight: '#ffc83d',
  onHighlight: '#1f2023',
  // Text and icons drawn on a primary-coloured fill.
  onPrimary: '#ffffff'
};

export type ThemeMode = 'system' | 'light' | 'dark';
export type AccentKey = 'indigo' | 'blue' | 'green' | 'rose';

/** color/dark/soft are the light-mode shades; night/nightLight are used in dark mode. */
export const ACCENT_PRESETS: Record<AccentKey, { label: string; color: string; dark: string; soft: string; night: string; nightLight: string }> = {
  indigo: { label: 'Sunshine', color: '#2b2d31', dark: '#1f2023', soft: '#fff6d6', night: '#ffc83d', nightLight: '#ffe08a' },
  blue: { label: 'Blue', color: '#2563eb', dark: '#1d4ed8', soft: '#eff6ff', night: '#3b82f6', nightLight: '#93c5fd' },
  green: { label: 'Green', color: '#16a34a', dark: '#15803d', soft: '#f0fdf4', night: '#22c55e', nightLight: '#86efac' },
  rose: { label: 'Rose', color: '#e11d48', dark: '#be123c', soft: '#fff1f3', night: '#f43f5e', nightLight: '#fda4af' }
};

const darkNeutrals: Partial<typeof colors> = {
  ink: '#f4f4f2',
  text: '#ececea',
  secondary: '#c4c6cb',
  muted: '#8b8f98',
  success: '#2dd4bf',
  successSoft: 'rgba(45, 212, 191, 0.16)',
  danger: '#fb7185',
  dangerDark: '#f43f5e',
  dangerSoft: 'rgba(251, 113, 133, 0.16)',
  warning: '#f59e0b',
  warningSoft: 'rgba(245, 158, 11, 0.16)',
  bg: '#18191c',
  surface: '#222327',
  surfaceGlass: 'rgba(34, 35, 39, 0.94)',
  surfaceBlue: '#2c2e33',
  surfaceAlt: '#2c2e33',
  hoverSurface: '#2c2e33',
  border: '#2f3136',
  borderStrong: '#3d4046',
  input: '#1d1e21',
  placeholder: '#6b6f78',
  pageTint: '#222327'
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
      onPrimary: accent === 'indigo' ? '#1f2023' : '#ffffff'
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

/** The yellow gradient of the balance card on Home. */
export const gradients = {
  balance: ['#ffd65c', '#ffc83d', '#ffb81f']
} as const;
