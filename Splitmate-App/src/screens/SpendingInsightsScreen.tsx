import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useFocusEffect } from '@react-navigation/native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { api } from '@/api/client';
import { AppText as Text } from '@/components/AppText';
import { BarList, MonthBars } from '@/components/Charts';
import { Screen } from '@/components/Screen';
import { EmptyState, ErrorState, LoadingState } from '@/components/States';
import { useAuth } from '@/state/AuthContext';
import { colors, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import { formatMoney } from '@/utils/money';
import type { Dashboard, RootStackParamList } from '@/types';

type Props = NativeStackScreenProps<RootStackParamList, 'SpendingInsights'>;
type Insights = Dashboard['spending_insights'];

/** Every spending breakdown across all your groups, opened from Home's "View all". */
export function SpendingInsightsScreen(_props: Props) {
  const { user, currencyCode } = useAuth();
  const money = (value: number) => formatMoney(value, currencyCode);
  const [insights, setInsights] = useState<Insights | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  // Home caches the dashboard, so the page can draw straight away while it refreshes.
  useEffect(() => {
    AsyncStorage.getItem(`splitmate.cache.dashboard.${user?.id ?? 'guest'}`).then(cached => {
      if (cached) {
        setInsights(current => current ?? (JSON.parse(cached) as Dashboard).spending_insights);
      }
    }).catch(() => undefined);
  }, [user?.id]);

  const load = useCallback(async () => {
    try {
      const dashboard = await api.dashboard();
      setInsights(dashboard.spending_insights);
      setError(null);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Try again.');
    }
  }, []);

  useFocusEffect(useCallback(() => {
    load();
  }, [load]));

  const refresh = useCallback(async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }, [load]);

  if (!insights) {
    return error ? <ErrorState message={error} onRetry={load} /> : <LoadingState label="Loading your spending..." />;
  }

  if (!insights.count) {
    return (
      <Screen onRefresh={refresh} refreshing={refreshing}>
        <EmptyState label="Add an expense to see spending insights." icon="analytics-outline" />
      </Screen>
    );
  }

  return (
    <Screen onRefresh={refresh} refreshing={refreshing}>
      <View style={styles.summary}>
        <Text style={styles.total}>{money(insights.total)}</Text>
        <Text style={styles.meta}>
          Spent across {insights.count} {insights.count === 1 ? 'expense' : 'expenses'} in all your groups
        </Text>
      </View>

      <View style={styles.panel}>
        <Text style={styles.cardTitle}>By category</Text>
        <BarList rows={insights.category_totals.map(row => ({ label: row.category, total: row.total }))} format={money} emptyLabel="No categories yet." />
      </View>
      <View style={styles.panel}>
        <Text style={styles.cardTitle}>By group</Text>
        <BarList rows={(insights.group_totals || []).map(row => ({ label: row.name, total: row.total }))} format={money} emptyLabel="No group spending yet." />
      </View>
      <View style={styles.panel}>
        <Text style={styles.cardTitle}>Paid by</Text>
        <BarList rows={insights.payer_totals.map(row => ({ label: row.name, total: row.total }))} format={money} emptyLabel="No payers yet." />
      </View>
      {insights.monthly_totals?.length ? (
        <View style={styles.panel}>
          <Text style={styles.cardTitle}>Monthly trend</Text>
          <MonthBars rows={insights.monthly_totals} />
        </View>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  summary: {
    gap: spacing.xs
  },
  total: {
    ...typography.h1,
    color: colors.ink
  },
  meta: {
    ...typography.caption,
    color: colors.muted
  },
  panel: {
    gap: spacing.md,
    padding: spacing.lg,
    borderRadius: 14,
    borderCurve: 'continuous',
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border
  },
  cardTitle: {
    ...typography.h3,
    color: colors.ink
  }
});
