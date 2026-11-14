import { StyleSheet, View } from 'react-native';

import { AppText as Text } from '@/components/AppText';
import { colors, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';

type BarRow = { label: string; total: number };

/** Colours for charts drawn on a black surface (the Home screen's lower sheet). */
const DARK = { text: '#ffffff', amount: '#ffc83d', track: '#272727', bar: '#ffc83d' };

/** Horizontal bars scaled to the largest row, like the website's insight lists. */
export function BarList({ rows, format, emptyLabel, dark = false }: { rows: BarRow[]; format: (value: number) => string; emptyLabel: string; dark?: boolean }) {
  if (!rows.length) {
    return <Text style={styles.empty}>{emptyLabel}</Text>;
  }
  const max = Math.max(...rows.map(row => row.total), 0) || 1;
  return (
    <View style={styles.list}>
      {rows.map(row => (
        <View key={row.label} style={styles.barBlock}>
          <View style={styles.rowBetween}>
            <Text style={[styles.barLabel, dark && { color: DARK.text }]} numberOfLines={1}>{row.label}</Text>
            <Text style={[styles.amount, dark && { color: DARK.amount }]}>{format(row.total)}</Text>
          </View>
          <View style={[styles.track, dark && { backgroundColor: DARK.track }]}>
            <View style={[styles.bar, dark && { backgroundColor: DARK.bar }, { width: `${Math.max(4, (row.total / max) * 100)}%` }]} />
          </View>
        </View>
      ))}
    </View>
  );
}

/** Vertical month columns; empty months stay empty instead of showing a sliver. */
export function MonthBars({ rows, dark = false }: { rows: Array<{ month: string; label: string; total: number }>; dark?: boolean }) {
  const max = Math.max(...rows.map(row => row.total), 0) || 1;
  return (
    <View style={styles.monthRow}>
      {rows.map(row => (
        <View key={row.month} style={styles.monthColumn}>
          <View style={[styles.monthTrack, dark && { backgroundColor: DARK.track }]}>
            <View style={[styles.monthBar, dark && { backgroundColor: DARK.bar }, { height: row.total ? `${Math.max(6, (row.total / max) * 100)}%` : 0 }]} />
          </View>
          <Text style={styles.monthLabel}>{row.label}</Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  list: {
    gap: spacing.sm
  },
  empty: {
    color: colors.muted,
    ...typography.body
  },
  barBlock: {
    gap: spacing.xs
  },
  rowBetween: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: spacing.sm
  },
  barLabel: {
    flex: 1,
    color: colors.text,
    ...typography.bodyStrong
  },
  amount: {
    color: colors.primary,
    ...typography.bodyStrong
  },
  track: {
    height: 8,
    overflow: 'hidden',
    borderRadius: radius.pill,
    backgroundColor: colors.primarySoft
  },
  bar: {
    height: 8,
    borderRadius: radius.pill,
    backgroundColor: colors.primary
  },
  monthRow: {
    height: 150,
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: spacing.xs
  },
  monthColumn: {
    flex: 1,
    alignItems: 'center',
    gap: spacing.xs
  },
  monthTrack: {
    width: '70%',
    height: 120,
    justifyContent: 'flex-end',
    borderRadius: radius.sm,
    overflow: 'hidden',
    backgroundColor: colors.primarySoft
  },
  monthBar: {
    width: '100%',
    backgroundColor: colors.primary
  },
  monthLabel: {
    color: colors.muted,
    ...typography.caption
  }
});
