import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { BottomTabScreenProps } from '@react-navigation/bottom-tabs';
import { CompositeScreenProps, useFocusEffect } from '@react-navigation/native';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { api } from '@/api/client';
import { AppButton } from '@/components/AppButton';
import { AppText as Text } from '@/components/AppText';
import { BrandMark } from '@/components/BrandMark';
import { GradientView } from '@/components/GradientView';
import { Card } from '@/components/Card';
import { BarList, MonthBars } from '@/components/Charts';
import { Screen } from '@/components/Screen';
import { EmptyState, ErrorState, LoadingState } from '@/components/States';
import { configureNotifications, scheduleTaskReminders } from '@/services/notifications';
import { useAuth } from '@/state/AuthContext';
import { colors, fonts, gradients, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import { formatDateTime } from '@/utils/dates';
import { formatMoney } from '@/utils/money';
import type { Dashboard, Group, MainTabParamList, MyInvite, RootStackParamList, Task } from '@/types';

type Props = CompositeScreenProps<
  BottomTabScreenProps<MainTabParamList, 'Home'>,
  NativeStackScreenProps<RootStackParamList>
>;

export function HomeScreen({ navigation }: Props) {
  const { user, currencyCode } = useAuth();
  const [groups, setGroups] = useState<Group[]>([]);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [reminders, setReminders] = useState<Task[]>([]);
  const [invites, setInvites] = useState<MyInvite[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const hasLoaded = useRef(false);
  const money = (value: number) => formatMoney(value, currencyCode);

  // Only the very first load shows a full-screen spinner; later reloads (on focus,
  // pull-to-refresh) keep the current content visible.
  const load = useCallback(async () => {
    try {
      const [dashboardData, reminderData] = await Promise.all([
        api.dashboard(),
        api.upcomingReminders()
      ]);
      setDashboard(dashboardData);
      setGroups(dashboardData.groups);
      setReminders(reminderData);
      hasLoaded.current = true;
      // Invites are a nice-to-have on Home; an older server without the route shouldn't break it.
      api.myInvites().then(setInvites).catch(() => setInvites([]));
      setLoadError(null);
      await scheduleTaskReminders(reminderData).catch(() => undefined);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Try again.';
      setLoadError(message);
      if (hasLoaded.current) {
        Alert.alert('Could not refresh Splitmate', message);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }, [load]);

  useEffect(() => {
    configureNotifications().catch(() => undefined);
  }, []);

  useFocusEffect(useCallback(() => {
    load();
  }, [load]));

  if (loading && !dashboard) {
    return <LoadingState label="Loading your groups..." />;
  }
  if (!dashboard) {
    return <ErrorState message={loadError || 'Could not load Splitmate.'} onRetry={() => { setLoading(true); load(); }} />;
  }

  const insights = dashboard.spending_insights;
  const net = dashboard.total_owed_to_user - dashboard.total_user_owes;
  const firstName = (user?.name || '').split(' ')[0] || 'there';

  return (
    <Screen onRefresh={refresh} refreshing={refreshing}>
      <GradientView colors={gradients.balance} style={styles.hero}>
        <View style={styles.heroShape} />
        <Text style={styles.heroLabel}>Hi {firstName}, your balance</Text>
        <Text style={styles.heroAmount}>{net < 0 ? '-' : net > 0 ? '+' : ''}{money(Math.abs(net))}</Text>
        <Text style={styles.heroMeta}>{net > 0 ? 'You are owed overall' : net < 0 ? 'You owe overall' : 'All settled up'}</Text>
      </GradientView>

      {invites.length ? (
        <Pressable accessibilityRole="button" onPress={() => navigation.navigate('Invites')}>
          <Card style={styles.inviteBanner}>
            <Ionicons name="mail-unread-outline" size={22} color={colors.primary} />
            <View style={styles.groupMain}>
              <Text style={styles.groupName}>
                {invites.length === 1 ? `You're invited to ${invites[0].group_name}` : `You have ${invites.length} group invites`}
              </Text>
              <Text style={styles.muted}>Tap to review and join.</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={colors.muted} />
          </Card>
        </Pressable>
      ) : null}

      <Card style={styles.summaryCard}>
        <SummaryRow icon="arrow-down-outline" label="Owed to you" value={`+${money(dashboard.total_owed_to_user)}`} color={colors.success} />
        <SummaryRow icon="arrow-up-outline" label="You owe" value={`-${money(dashboard.total_user_owes)}`} color={colors.danger} />
        <Pressable accessibilityRole="button" onPress={() => navigation.navigate('Groups')}>
          <SummaryRow icon="people-outline" label="Groups" value={String(groups.length)} chevron />
        </Pressable>
        <SummaryRow icon="alarm-outline" label="Reminders" value={String(reminders.length)} last />
      </Card>

      <View style={styles.homeActions}>
        <AppButton icon="flash-outline" style={styles.homeAction} onPress={() => navigation.navigate('QuickSplit')}>Quick split</AppButton>
        <AppButton icon="add-outline" variant="outline" style={styles.homeAction} onPress={() => navigation.navigate('CreateGroup')}>Create Group</AppButton>
      </View>

      <Text style={styles.sectionTitle}>This Month</Text>
      {dashboard?.monthly_spending.length ? dashboard.monthly_spending.map(item => (
        <Card key={item.group_id} style={styles.spendingRow}>
          <View style={styles.groupMain}>
            <Text style={styles.groupName}>{item.group}</Text>
            <Text style={styles.muted}>Recorded workspace spending</Text>
          </View>
          <Text style={styles.spendingAmount}>{money(item.total)}</Text>
        </Card>
      )) : <EmptyState label="No spending recorded this month." />}

      <Text style={styles.sectionTitle}>Recent Expenses</Text>
      {dashboard?.recent_expenses.length ? dashboard.recent_expenses.slice(0, 10).map(expense => (
        <Card key={expense.id}>
          <View style={styles.spendingRow}>
            <View style={styles.groupMain}>
              <Text style={styles.groupName}>{expense.description}</Text>
              <Text style={styles.muted}>{expense.group_name} - {expense.category}</Text>
            </View>
            <Text style={styles.spendingAmount}>{money(expense.amount)}</Text>
          </View>
        </Card>
      )) : <EmptyState label="No recent expenses." />}

      <Text style={styles.sectionTitle}>Spending Insights</Text>
      {insights.count ? (
        <>
          <View style={styles.statsGrid}>
            <View style={styles.statTile}>
              <Text style={styles.statLabel}>Total spent</Text>
              <Text style={styles.statValue}>{money(insights.total)}</Text>
            </View>
            <View style={styles.statTile}>
              <Text style={styles.statLabel}>Expenses</Text>
              <Text style={styles.statValue}>{insights.count}</Text>
            </View>
          </View>
          <View style={styles.statsGrid}>
            <View style={styles.statTile}>
              <Text style={styles.statLabel}>Average</Text>
              <Text style={styles.statValue}>{money(insights.average ?? insights.total / insights.count)}</Text>
            </View>
            <View style={styles.statTile}>
              <Text style={styles.statLabel}>Top category</Text>
              <Text style={styles.statValue} numberOfLines={1}>{insights.top_category || 'None'}</Text>
            </View>
          </View>
          <Card style={styles.insightCard}>
            <Text style={styles.cardTitle}>By Category</Text>
            <BarList rows={insights.category_totals.map(row => ({ label: row.category, total: row.total }))} format={money} emptyLabel="No categories yet." />
          </Card>
          <Card style={styles.insightCard}>
            <Text style={styles.cardTitle}>By Group</Text>
            <BarList rows={(insights.group_totals || []).map(row => ({ label: row.name, total: row.total }))} format={money} emptyLabel="No group spending yet." />
          </Card>
          {insights.monthly_totals?.length ? (
            <Card style={styles.insightCard}>
              <Text style={styles.cardTitle}>Monthly Trend</Text>
              <MonthBars rows={insights.monthly_totals} />
            </Card>
          ) : null}
          <Card style={styles.insightCard}>
            <Text style={styles.cardTitle}>Paid By</Text>
            <BarList rows={insights.payer_totals.map(row => ({ label: row.name, total: row.total }))} format={money} emptyLabel="No payers yet." />
          </Card>
        </>
      ) : <EmptyState label="Add an expense to see spending insights." />}

      <Text style={styles.sectionTitle}>Upcoming Reminders</Text>
      {reminders.length ? reminders.slice(0, 5).map(task => (
        <Card key={task.id}>
          <Text style={styles.groupName}>{task.title}</Text>
          <Text style={styles.muted}>{task.group_name} - {formatDateTime(task.reminder_time, 'No reminder')}</Text>
        </Card>
      )) : <EmptyState label="No upcoming reminders. Task reminders will appear here." />}
    </Screen>
  );
}

/** One line of the summary card: a small icon, a label, and the value on the right. */
function SummaryRow({ icon, label, value, color, chevron, last }: {
  icon: keyof typeof Ionicons.glyphMap; label: string; value: string; color?: string; chevron?: boolean; last?: boolean;
}) {
  return (
    <View style={[styles.summaryRow, !last && styles.summaryDivider]}>
      <View style={styles.summaryIcon}><Ionicons name={icon} size={16} color={colors.primary} /></View>
      <Text style={styles.summaryLabel}>{label}</Text>
      <Text style={[styles.summaryValue, color ? { color } : null]}>{value}</Text>
      {chevron ? <Ionicons name="chevron-forward" size={16} color={colors.muted} /> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  hero: {
    alignItems: 'center',
    gap: spacing.xs,
    paddingVertical: spacing.xl,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.lg,
    overflow: 'hidden'
  },
  heroShape: {
    position: 'absolute',
    width: 220,
    height: 220,
    right: -90,
    top: -40,
    transform: [{ rotate: '45deg' }],
    backgroundColor: 'rgba(255, 255, 255, 0.22)'
  },
  heroLabel: {
    ...typography.label,
    color: colors.onHighlight
  },
  heroAmount: {
    fontFamily: fonts.medium,
    fontSize: 38,
    lineHeight: 46,
    color: colors.onHighlight
  },
  heroMeta: {
    ...typography.caption,
    color: 'rgba(31, 32, 35, 0.7)'
  },
  summaryCard: {
    paddingVertical: spacing.xs
  },
  summaryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingVertical: spacing.md
  },
  summaryDivider: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.borderStrong
  },
  summaryIcon: {
    width: 30,
    height: 30,
    borderRadius: 9,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primarySoft
  },
  summaryLabel: {
    ...typography.body,
    flex: 1,
    color: colors.secondary
  },
  summaryValue: {
    ...typography.body,
    fontFamily: fonts.semiBold,
    color: colors.text
  },
  homeActions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm
  },
  homeAction: {
    flexGrow: 1,
    flexBasis: 140
  },
  muted: {
    ...typography.body,
    color: colors.muted
  },
  statsGrid: {
    flexDirection: 'row',
    gap: spacing.sm
  },
  statTile: {
    flex: 1,
    gap: spacing.xs,
    padding: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.surfaceAlt
  },
  statLabel: {
    ...typography.caption,
    color: colors.secondary,
    textTransform: 'uppercase'
  },
  statValue: {
    ...typography.h2,
    color: colors.ink
  },
  sectionTitle: {
    ...typography.h2,
    color: colors.ink
  },
  inviteBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.primarySoft
  },
  insightCard: {
    gap: spacing.sm
  },
  cardTitle: {
    ...typography.h3,
    color: colors.ink
  },
  groupMain: {
    flex: 1,
    gap: 2
  },
  groupName: {
    ...typography.bodyStrong,
    color: colors.ink
  },
  spendingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm
  },
  spendingAmount: {
    ...typography.bodyStrong,
    color: colors.primary
  }
});
