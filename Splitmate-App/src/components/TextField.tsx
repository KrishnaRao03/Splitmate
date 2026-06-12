import { ReactNode } from 'react';
import { StyleSheet, Text, TextInput, TextInputProps, View } from 'react-native';

import { colors, radius, spacing } from '@/theme/colors';

type Props = TextInputProps & {
  label: string;
  error?: string;
  right?: ReactNode;
};

export function TextField({ label, error, right, style, ...props }: Props) {
  return (
    <View style={styles.wrap}>
      <Text style={styles.label}>{label}</Text>
      <View style={[styles.inputWrap, Boolean(error) && styles.invalid]}>
        <TextInput
          placeholderTextColor="#8aa0af"
          style={[styles.input, style]}
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
    fontSize: 13,
    fontWeight: '800'
  },
  inputWrap: {
    minHeight: 48,
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    backgroundColor: colors.input,
    paddingHorizontal: spacing.sm
  },
  invalid: {
    borderColor: colors.danger
  },
  input: {
    flex: 1,
    color: colors.text,
    fontSize: 15,
    paddingVertical: 11
  },
  error: {
    color: colors.danger,
    fontSize: 12,
    fontWeight: '700'
  }
});
