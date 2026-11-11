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
import { Card } from '@/components/Card';
import { BarList, MonthBars } from '@/components/Charts';
import { Screen } from '@/components/Screen';
import { EmptyState, ErrorState, LoadingState } from '@/components/States';
import { configureNotifications, scheduleTaskReminders } from '@/services/notifications';
import { useAuth } from '@/state/AuthContext';
import { colors, radius, spacing } from '@/theme/colors';
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

  return (
    <Screen onRefresh={refresh} refreshing={refreshing}>
      <Card style={styles.pageHeader}>
        <View style={styles.brandRow}>
          <BrandMark size={40} />
          <View>
            <Text style={styles.eyebrow}>Welcome back</Text>
            <Text style={styles.title}>{user?.name || 'Splitmate'}</Text>
          </View>
        </View>
        <Text style={styles.muted}>{currencyCode} workspace</Text>
      </Card>

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

      <Card style={styles.balanceCard}>
        <View style={styles.balanceHalf}>
          <Text style={styles.balanceLabel}>Owed to you</Text>
          <Text style={[styles.balanceValue, { color: colors.success }]}>{money(dashboard.total_owed_to_user)}</Text>
        </View>
        <View style={styles.balanceDivider} />
        <View style={styles.balanceHalf}>
          <Text style={styles.balanceLabel}>You owe</Text>
          <Text style={[styles.balanceValue, { color: colors.danger }]}>{money(dashboard.total_user_owes)}</Text>
        </View>
      </Card>

      <View style={styles.statsGrid}>
        <Pressable style={styles.statTile} onPress={() => navigation.navigate('Groups')}>
          <Ionicons name="people-outline" size={18} color={colors.secondary} />
          <Text style={styles.statLabel}>Groups</Text>
          <Text style={styles.statValue}>{groups.length}</Text>
        </Pressable>
        <View style={styles.statTile}>
          <Ionicons name="alarm-outline" size={18} color={colors.secondary} />
          <Text style={styles.statLabel}>Reminders</Text>
          <Text style={styles.statValue}>{reminders.length}</Text>
        </View>
      </View>

      <AppButton icon="add-outline" onPress={() => navigation.navigate('CreateGroup')}>Create Group</AppButton>

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

const styles = StyleSheet.create({
  pageHeader: {
    gap: spacing.xs,
    backgroundColor: colors.surfaceGlass
  },
  brandRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm
  },
  eyebrow: {
    ...typography.label,
    color: colors.primary,
    textTransform: 'uppercase'
  },
  title: {
    ...typography.display,
    color: colors.ink
  },
  muted: {
    ...typography.body,
    color: colors.muted
  },
  balanceCard: {
    flexDirection: 'row',
    alignItems: 'center'
  },
  balanceHalf: {
    flex: 1,
    gap: spacing.xs,
    alignItems: 'center'
  },
  balanceDivider: {
    width: 1,
    alignSelf: 'stretch',
    backgroundColor: colors.border,
    marginHorizontal: spacing.sm
  },
  balanceLabel: {
    ...typography.label,
    color: colors.muted
  },
  balanceValue: {
    ...typography.h1
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
