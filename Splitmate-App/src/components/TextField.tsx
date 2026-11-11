import { ReactNode, useState } from 'react';
import { StyleSheet, TextInput, TextInputProps, View } from 'react-native';

import { AppText as Text } from '@/components/AppText';
import { colors, fonts, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';

type Props = TextInputProps & {
  label: string;
  error?: string;
  right?: ReactNode;
};

export function TextField({ label, error, right, style, onFocus, onBlur, ...props }: Props) {
  const [focused, setFocused] = useState(false);

  return (
    <View style={styles.wrap}>
      <Text style={styles.label}>{label}</Text>
      <View
        style={[
          styles.inputWrap,
          focused && styles.focused,
          Boolean(error) && styles.invalid
        ]}
      >
        <TextInput
          placeholderTextColor={colors.placeholder}
          style={[styles.input, style]}
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
      {error ? <Text style={styles.error}>{error}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    gap: 7
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
    fontSize: 15,
    fontFamily: fonts.regular,
    fontWeight: 'normal',
    paddingVertical: 11
  },
  error: {
    color: colors.danger,
    fontSize: 12,
    fontWeight: '700'
  }
});
