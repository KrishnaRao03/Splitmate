import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { AppText as Text } from '@/components/AppText';
import { colors, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import { HistoryPeriod, HistorySort, PERIOD_OPTIONS, SORT_OPTIONS } from '@/utils/history';

type Props = {
  sort: HistorySort;
  period: HistoryPeriod;
  onSort: (sort: HistorySort) => void;
  onPeriod: (period: HistoryPeriod) => void;
};

/** Two quiet rows of small pills: when, and in what order. */
export function HistoryFilters({ sort, period, onSort, onPeriod }: Props) {
  return (
    <View style={styles.wrap}>
      <Pills options={PERIOD_OPTIONS} value={period} onChange={onPeriod} />
      <Pills options={SORT_OPTIONS} value={sort} onChange={onSort} />
    </View>
  );
}

function Pills<T extends string>({ options, value, onChange }: { options: Array<{ label: string; value: T }>; value: T; onChange: (value: T) => void }) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.row}>
      {options.map(option => {
        const selected = option.value === value;
        return (
          <Pressable
            key={option.value}
            accessibilityRole="button"
            accessibilityState={{ selected }}
            onPress={() => onChange(option.value)}
            style={[styles.pill, selected && styles.pillOn]}
          >
            <Text style={[styles.text, selected && styles.textOn]}>{option.label}</Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  wrap: {
    gap: spacing.xs
  },
  row: {
    gap: spacing.xs
  },
  pill: {
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border
  },
  pillOn: {
    backgroundColor: colors.primary,
    borderColor: colors.primary
  },
  text: {
    color: colors.secondary,
    ...typography.caption
  },
  textOn: {
    color: colors.onPrimary
  }
});
