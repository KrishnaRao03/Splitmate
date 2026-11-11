import { ReactNode } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, ViewStyle } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { AppText as Text } from '@/components/AppText';
import { useTheme } from '@/state/ThemeContext';
import { colors, radius, spacing } from '@/theme/colors';

type Props = {
  children: ReactNode;
  disabled?: boolean;
  icon?: keyof typeof Ionicons.glyphMap;
  loading?: boolean;
  variant?: 'primary' | 'outline' | 'ghost' | 'danger';
  onPress?: () => void;
  style?: ViewStyle;
};

export function AppButton({ children, disabled, icon, loading, onPress, style, variant = 'primary' }: Props) {
  const { accentColor } = useTheme();
  const foreground = variant === 'primary'
    ? colors.white
    : variant === 'danger'
      ? colors.white
      : accentColor;

  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled || loading}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        styles[variant],
        variant === 'primary' && { backgroundColor: accentColor },
        (pressed || disabled) && styles.dimmed,
        style
      ]}
    >
      {loading ? (
        <ActivityIndicator color={foreground} />
      ) : (
        <>
          {icon ? <Ionicons name={icon} size={18} color={foreground} /> : null}
          <Text style={[styles.text, { color: foreground }]}>{children}</Text>
        </>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    minHeight: 52,
    flexDirection: 'row',
    gap: spacing.xs,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.md,
    paddingHorizontal: spacing.md
  },
  primary: {
    backgroundColor: colors.primary
  },
  outline: {
    borderWidth: 1,
    borderColor: colors.borderStrong,
    backgroundColor: colors.surface
  },
  ghost: {
    backgroundColor: 'transparent'
  },
  danger: {
    backgroundColor: colors.danger
  },
  dimmed: {
    opacity: 0.72
  },
  text: {
    fontWeight: '600'
  }
});
