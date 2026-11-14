import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useFocusEffect } from '@react-navigation/native';
import { useCallback, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { api } from '@/api/client';
import { AppButton } from '@/components/AppButton';
import { AppText as Text } from '@/components/AppText';
import { Card } from '@/components/Card';
import { ChoiceChips } from '@/components/ChoiceChips';
import { Screen } from '@/components/Screen';
import { EmptyState, LoadingState } from '@/components/States';
import { TextField } from '@/components/TextField';
import { useAuth } from '@/state/AuthContext';
import { colors, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import { formatDateTime } from '@/utils/dates';
import { formatMoney } from '@/utils/money';
import { notify } from '@/state/UndoToast';
import type { GroupActivity, RootStackParamList } from '@/types';

type Props = NativeStackScreenProps<RootStackParamList, 'Insights'>;

export function InsightsScreen({ route }: Props) {
  const { groupId, members, categories } = route.params;
  const { currencyCode } = useAuth();
  const money = (value: number) => formatMoney(value, currencyCode);
  const [activity, setActivity] = useState<GroupActivity | null>(null);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('');
  const [payerId, setPayerId] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [minAmount, setMinAmount] = useState('');
  const [maxAmount, setMaxAmount] = useState('');

  const load = useCallback(async (applyFilters = false) => {
    setLoading(true);
    try {
      setActivity(await api.groupActivity(groupId, applyFilters ? {
        q: query,
        category,
        payer_id: payerId,
        start_date: startDate,
        end_date: endDate,
        min_amount: minAmount,
        max_amount: maxAmount
      } : {}));
    } catch (error) {
      notify('Could not load activity', error instanceof Error ? error.message : 'Try again.');
    } finally {
      setLoading(false);
    }
  }, [category, endDate, groupId, maxAmount, minAmount, payerId, query, startDate]);

  useFocusEffect(useCallback(() => {
    load(false);
  }, [groupId]));

  function resetFilters() {
    setQuery('');
    setCategory('');
    setPayerId('');
    setStartDate('');
    setEndDate('');
    setMinAmount('');
    setMaxAmount('');
    setTimeout(() => load(false), 0);
  }

  if (loading && !activity) {
    return <LoadingState label="Loading spending insights..." />;
  }

  const analytics = activity?.analytics;
  const maxCategory = Math.max(...(analytics?.category_totals.map(item => item.total) || [0]), 1);
  const maxMonth = Math.max(...(analytics?.monthly_totals.map(item => item.total) || [0]), 1);

  return (
    <Screen>
      <View style={styles.statsRow}>
        <Card style={styles.statCard}>
          <Text style={styles.statLabel}>Recorded spend</Text>
          <Text style={styles.statValue}>{money(analytics?.total ?? 0)}</Text>
        </Card>
        <Card style={styles.statCard}>
          <Text style={styles.statLabel}>Transactions</Text>
          <Text style={styles.statValue}>{analytics?.count || 0}</Text>
        </Card>
        <Card style={styles.statCard}>
          <Text style={styles.statLabel}>Top category</Text>
          <Text style={styles.statText}>{analytics?.top_category || 'None'}</Text>
        </Card>
      </View>

      <Card>
        <Text style={styles.sectionTitle}>Search history</Text>
        <TextField label="Description" value={query} onChangeText={setQuery} placeholder="Rent, dinner, groceries" />
        <ChoiceChips
          label="Category"
          value={category}
          onChange={setCategory}
          options={[{ label: 'All', value: '' }, ...categories.map(item => ({ label: item, value: item }))]}
        />
        <ChoiceChips
          label="Paid by"
          value={payerId}
          onChange={setPayerId}
          options={[{ label: 'Anyone', value: '' }, ...members.map(member => ({ label: member.name, value: String(member.id) }))]}
        />
        <View style={styles.twoColumns}>
          <View style={styles.field}><TextField label="Start date" value={startDate} onChangeText={setStartDate} placeholder="YYYY-MM-DD" /></View>
          <View style={styles.field}><TextField label="End date" value={endDate} onChangeText={setEndDate} placeholder="YYYY-MM-DD" /></View>
        </View>
        <View style={styles.twoColumns}>
          <View style={styles.field}><TextField label="Minimum" value={minAmount} onChangeText={setMinAmount} keyboardType="decimal-pad" /></View>
          <View style={styles.field}><TextField label="Maximum" value={maxAmount} onChangeText={setMaxAmount} keyboardType="decimal-pad" /></View>
        </View>
        <AppButton icon="search-outline" loading={loading} onPress={() => load(true)}>Search</AppButton>
        <AppButton icon="refresh-outline" variant="outline" onPress={resetFilters}>Reset filters</AppButton>
      </Card>

      <Card>
        <Text style={styles.sectionTitle}>By category</Text>
        {analytics?.category_totals.length ? analytics.category_totals.map(item => (
          <View key={item.category} style={styles.barBlock}>
            <View style={styles.rowBetween}><Text style={styles.barLabel}>{item.category}</Text><Text style={styles.amount}>{money(item.total)}</Text></View>
            <View style={styles.track}><View style={[styles.bar, { width: `${Math.max(4, item.total / maxCategory * 100)}%` }]} /></View>
          </View>
        )) : <EmptyState label="No category history yet." />}
      </Card>

      <Card>
        <Text style={styles.sectionTitle}>Last six months</Text>
        <View style={styles.monthRow}>
          {analytics?.monthly_totals.map(item => (
            <View key={item.month} style={styles.monthColumn}>
              <View style={styles.monthTrack}>
                <View style={[styles.monthBar, { height: `${Math.max(5, item.total / maxMonth * 100)}%` }]} />
              </View>
              <Text style={styles.monthLabel}>{item.label}</Text>
            </View>
          ))}
        </View>
      </Card>

      <Text style={styles.sectionTitle}>Transaction history</Text>
      {activity?.transactions.length ? activity.transactions.map((item, index) => (
        <Card key={`${item.type}-${item.id}-${index}`}>
          <View style={styles.rowBetween}>
            <Text style={styles.transactionTitle}>{item.description}</Text>
            <Text style={styles.amount}>{money(item.amount)}</Text>
          </View>
          <Text style={styles.meta}>
            {item.type === 'expense'
              ? `${item.category || 'General'} · Paid by ${item.paid_by}`
              : `${item.payer} paid ${item.receiver} · ${item.status}`}
          </Text>
          <Text style={styles.meta}>{formatDateTime(item.date)}</Text>
        </Card>
      )) : <EmptyState label="No matching transactions." />}
    </Screen>
  );
}

const styles = StyleSheet.create({
  statsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm
  },
  statCard: {
    flexGrow: 1,
    flexBasis: 160
  },
  statLabel: {
    color: colors.muted,
    ...typography.label
  },
  statValue: {
    color: colors.ink,
    ...typography.h1
  },
  statText: {
    color: colors.primary,
    ...typography.h3
  },
  sectionTitle: {
    color: colors.ink,
    ...typography.h2,
    marginBottom: spacing.sm
  },
  twoColumns: {
    flexDirection: 'row',
    gap: spacing.sm
  },
  field: {
    flex: 1
  },
  rowBetween: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: spacing.sm
  },
  barBlock: {
    gap: spacing.xs,
    marginBottom: spacing.sm
  },
  barLabel: {
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
    borderRadius: 4,
    backgroundColor: colors.primarySoft
  },
  bar: {
    height: 8,
    backgroundColor: colors.primary
  },
  monthRow: {
    height: 170,
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
    width: '75%',
    height: 130,
    justifyContent: 'flex-end',
    backgroundColor: colors.primarySoft
  },
  monthBar: {
    width: '100%',
    backgroundColor: colors.accent
  },
  monthLabel: {
    color: colors.muted,
    ...typography.caption
  },
  transactionTitle: {
    flex: 1,
    color: colors.ink,
    ...typography.bodyStrong
  },
  meta: {
    color: colors.muted,
    ...typography.caption,
    marginTop: spacing.xs
  }
});
