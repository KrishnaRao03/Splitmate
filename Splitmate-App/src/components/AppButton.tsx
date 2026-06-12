import { ReactNode } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, ViewStyle } from 'react-native';

import { colors, radius, spacing } from '@/theme/colors';

type Props = {
  children: ReactNode;
  disabled?: boolean;
  loading?: boolean;
  variant?: 'primary' | 'outline' | 'ghost' | 'danger';
  onPress?: () => void;
  style?: ViewStyle;
};

export function AppButton({ children, disabled, loading, onPress, style, variant = 'primary' }: Props) {
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled || loading}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        styles[variant],
        (pressed || disabled) && styles.dimmed,
        style
      ]}
    >
      {loading ? (
        <ActivityIndicator color={variant === 'primary' ? colors.white : colors.primary} />
      ) : (
        <Text style={[styles.text, variant !== 'primary' && styles.textAlt]}>{children}</Text>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    minHeight: 48,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.sm,
    paddingHorizontal: spacing.md
  },
  primary: {
    backgroundColor: colors.primary
  },
  outline: {
    borderWidth: 1,
    borderColor: colors.border,
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
    color: colors.white,
    fontWeight: '800'
  },
  textAlt: {
    color: colors.primary
  }
});
