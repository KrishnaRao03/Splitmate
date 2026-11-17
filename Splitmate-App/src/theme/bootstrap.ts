// Imported first from index.ts: applies the saved theme and accent to the shared
// `colors` object before any screen module builds its StyleSheet.
import { applyTheme } from '@/theme/colors';
import { resolveScheme, storedAccent, storedThemeMode } from '@/theme/preferences';

applyTheme(resolveScheme(storedThemeMode()), storedAccent());
