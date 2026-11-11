import { Pressable, StyleSheet, View } from 'react-native';

import { AppText as Text } from '@/components/AppText';
import { colors, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';

type Option<T extends string | number> = {
  label: string;
  value: T;
  detail?: string;
};

type Props<T extends string | number> = {
  label?: string;
  options: Option<T>[];
  value: T | null;
  onChange: (value: T) => void;
};

export function ChoiceChips<T extends string | number>({ label, options, value, onChange }: Props<T>) {
  return (
    <View style={styles.container}>
      {label ? <Text style={styles.label}>{label}</Text> : null}
      <View style={styles.row}>
        {options.map(option => {
          const selected = option.value === value;
          return (
            <Pressable
              accessibilityRole="button"
              key={String(option.value)}
              onPress={() => onChange(option.value)}
              style={[styles.chip, selected && styles.selected]}
            >
              <Text style={[styles.text, selected && styles.selectedText]}>{option.label}</Text>
              {option.detail ? <Text style={[styles.detail, selected && styles.selectedDetail]}>{option.detail}</Text> : null}
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing.xs
  },
  label: {
    ...typography.label,
    color: colors.ink
  },
  row: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs
  },
  chip: {
    minHeight: 42,
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceAlt,
    paddingHorizontal: spacing.sm,
    paddingVertical: 8
  },
  selected: {
    borderColor: colors.primary,
    backgroundColor: colors.primary
  },
  text: {
    ...typography.bodyStrong,
    color: colors.primaryDark
  },
  selectedText: {
    color: colors.white
  },
  detail: {
    ...typography.caption,
    color: colors.muted
  },
  selectedDetail: {
    color: colors.white
  }
});
