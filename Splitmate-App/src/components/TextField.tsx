import { ReactNode, useState } from 'react';
import { Platform, StyleSheet, TextInput, TextInputProps, View } from 'react-native';

import { AppText as Text } from '@/components/AppText';
import { colors, fonts, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';

type Props = TextInputProps & {
  label: string;
  error?: string;
  right?: ReactNode;
  /** Overrides the border colour, e.g. to show password strength. */
  borderColor?: string;
  /** Shown under the field, above any error. */
  footer?: ReactNode;
};

export function TextField({ label, error, right, borderColor, footer, style, onFocus, onBlur, ...props }: Props) {
  const [focused, setFocused] = useState(false);

  return (
    <View style={styles.wrap}>
      <Text style={styles.label}>{label}</Text>
      <View
        style={[
          styles.inputWrap,
          focused && styles.focused,
          Boolean(error) && styles.invalid,
          borderColor ? { borderColor } : null
        ]}
      >
        <TextInput
          placeholderTextColor={colors.placeholder}
          style={[styles.input, Platform.OS === 'web' && WEB_NO_OUTLINE, style]}
          onFocus={(event) => {
            setFocused(true);
            onFocus?.(event);
          }}
          onBlur={(event) => {
            setFocused(false);
            onBlur?.(event);
          }}
          {...props}
        />
        {right}
      </View>
      {footer}
      {error ? <Text style={styles.error}>{error}</Text> : null}
    </View>
  );
}

// The coloured border already shows focus; the browser's own black focus box would sit inside it.
const WEB_NO_OUTLINE = { outlineStyle: 'none' } as unknown as TextInputProps['style'];

const styles = StyleSheet.create({
  wrap: {
    gap: spacing.sm
  },
  label: {
    color: colors.ink,
    ...typography.label
  },
  inputWrap: {
    minHeight: 48,
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.borderStrong,
    borderRadius: radius.md,
    backgroundColor: colors.input,
    paddingHorizontal: spacing.sm
  },
  focused: {
    borderColor: colors.primary
  },
  invalid: {
    borderColor: colors.danger
  },
  input: {
    flex: 1,
    color: colors.text,
    fontSize: 16,
    lineHeight: 24,
    fontFamily: fonts.regular,
    fontWeight: 'normal',
    paddingVertical: spacing.md
  },
  error: {
    color: colors.danger,
    ...typography.caption
  }
});
