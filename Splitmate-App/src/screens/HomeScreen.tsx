import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { BottomTabScreenProps } from '@react-navigation/bottom-tabs';
import { CompositeScreenProps, useFocusEffect } from '@react-navigation/native';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, Pressable, StyleSheet, View } from 'react-native';
import { Icon, IconName } from '@/components/Icon';

import { api } from '@/api/client';
import { AppText as Text } from '@/components/AppText';
import { BarList, MonthBars } from '@/components/Charts';
import { Screen } from '@/components/Screen';
import { ErrorState, LoadingState } from '@/components/States';
import { configureNotifications, scheduleTaskReminders } from '@/services/notifications';
import { useAuth } from '@/state/AuthContext';
import { colors, fonts, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import { formatDateTime } from '@/utils/dates';
import { formatMoney } from '@/utils/money';
import type { Dashboard, Group, MainTabParamList, MyInvite, PersonBalance, RootStackParamList, Task } from '@/types';

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
  const [people, setPeople] = useState<PersonBalance[]>([]);
  const [opening, setOpening] = useState(false);
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
      api.peopleBalances().then(setPeople).catch(() => setPeople([]));
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

  // With one group the expense form opens straight away; with several, the Split tab asks which group.
  async function openExpenseForm() {
    if (groups.length !== 1) {
      navigation.navigate('Split');
      return;
    }
    setOpening(true);
    try {
      const detail = await api.groupDetail(groups[0].id);
      navigation.navigate('AddExpense', {
        groupId: groups[0].id,
        members: detail.group.members,
        currentUserId: detail.current_user_id,
        categories: detail.expense_categories,
        defaultSplit: detail.default_split
      });
    } catch (error) {
      Alert.alert('Could not open the expense form', error instanceof Error ? error.message : 'Try again.');
    } finally {
      setOpening(false);
    }
  }

  function settleUp() {
    if (groups.length === 1) {
      navigation.navigate('GroupDetail', { groupId: groups[0].id, groupName: groups[0].name });
    } else {
      navigation.navigate('Split');
    }
  }

  if (loading && !dashboard) {
    return <LoadingState label="Loading your groups..." />;
  }
  if (!dashboard) {
    return <ErrorState message={loadError || 'Could not load Splitmate.'} onRetry={() => { setLoading(true); load(); }} />;
  }

  const insights = dashboard.spending_insights;
  const net = dashboard.total_owed_to_user - dashboard.total_user_owes;
  const firstName = (user?.name || '').split(' ')[0] || 'there';
  const owing = people.filter(person => person.net !== 0).slice(0, 6);

  return (
    <Screen onRefresh={refresh} refreshing={refreshing} flush background={SHEET.bg}>
      <View style={styles.header}>
        <Text style={styles.greeting}>{greeting()}, {firstName}</Text>
        <Text style={styles.balance}>{net < 0 ? '-' : net > 0 ? '+' : ''}{money(Math.abs(net))}</Text>
        <View style={styles.pills}>
          <View style={[styles.pill, styles.pillDark]}><Text style={styles.pillDarkText}>Owed {money(dashboard.total_owed_to_user)}</Text></View>
          <View style={[styles.pill, styles.pillSoft]}><Text style={styles.pillSoftText}>You owe {money(dashboard.total_user_owes)}</Text></View>
        </View>
      </View>

      <View style={styles.sheet}>
        <View style={styles.actions}>
          <Action icon="add-outline" label="Add expense" onPress={openExpenseForm} disabled={opening} />
          <Action icon="flash-outline" label="Quick split" onPress={() => navigation.navigate('QuickSplit')} />
          <Action icon="scan-outline" label="Scan receipt" onPress={openExpenseForm} disabled={opening} />
          <Action icon="swap-horizontal-outline" label="Settle up" onPress={settleUp} />
        </View>

        {invites.length ? (
          <Pressable accessibilityRole="button" onPress={() => navigation.navigate('Invites')} style={[styles.darkCard, styles.rowCard]}>
            <View style={[styles.tile, { backgroundColor: TINTS[0].bg }]}><Icon name="mail-unread-outline" size={20} color={TINTS[0].fg} /></View>
            <View style={styles.flex}>
              <Text style={styles.rowTitle}>
                {invites.length === 1 ? `You're invited to ${invites[0].group_name}` : `You have ${invites.length} group invites`}
              </Text>
              <Text style={styles.rowMeta}>Tap to review and join.</Text>
            </View>
            <Icon name="chevron-forward" size={16} color={SHEET.muted} />
          </Pressable>
        ) : null}

        <View style={styles.section}>
          <SectionTitle title="People" action={groups.length ? 'Groups' : undefined} onAction={() => navigation.navigate('Groups')} />
          <View style={styles.people}>
            {owing.map(person => (
              <Pressable key={person.user_id} accessibilityRole="button" style={styles.person} onPress={() => navigation.navigate('Split')}>
                <View style={[styles.avatar, { backgroundColor: tint(person.name).bg }]}>
                  <Text style={[styles.avatarText, { color: tint(person.name).fg }]}>{initials(person.name)}</Text>
                </View>
                <Text style={styles.personName} numberOfLines={1}>{person.name.split(' ')[0]}</Text>
                <Text style={[styles.personAmount, { color: person.net > 0 ? SHEET.positive : SHEET.negative }]} numberOfLines={1}>
                  {person.net > 0 ? '+' : '-'}{money(Math.abs(person.net))}
                </Text>
              </Pressable>
            ))}
            <Pressable accessibilityRole="button" style={styles.person} onPress={() => navigation.navigate(groups.length ? 'Groups' : 'CreateGroup')}>
              <View style={[styles.avatar, styles.inviteAvatar]}><Icon name="add" size={20} color={SHEET.muted} /></View>
              <Text style={[styles.personName, { color: SHEET.muted }]}>{groups.length ? 'Invite' : 'New group'}</Text>
            </Pressable>
          </View>
        </View>

        <View style={styles.section}>
          <SectionTitle title="Recent activity" />
          {dashboard.recent_expenses.length ? (
            <View style={styles.darkCard}>
              {dashboard.recent_expenses.slice(0, 8).map((expense, index, list) => (
                <View key={expense.id} style={[styles.activityRow, index < list.length - 1 && styles.divider]}>
                  <View style={[styles.tile, { backgroundColor: categoryStyle(expense.category).bg }]}>
                    <Icon name={categoryStyle(expense.category).icon} size={20} color={categoryStyle(expense.category).fg} />
                  </View>
                  <View style={styles.flex}>
                    <Text style={styles.rowTitle} numberOfLines={1}>{expense.description}</Text>
                    <Text style={styles.rowMeta} numberOfLines={1}>{expense.group_name} · {expense.category}</Text>
                  </View>
                  <Text style={styles.rowAmount}>{money(expense.amount)}</Text>
                </View>
              ))}
            </View>
          ) : <EmptyDark icon="receipt-outline" label="No expenses yet. Add one to see it here." />}
        </View>

        <View style={styles.section}>
          <SectionTitle title="This month" />
          {dashboard.monthly_spending.length ? (
            <View style={styles.darkCard}>
              {dashboard.monthly_spending.map((item, index, list) => (
                <Pressable key={item.group_id} accessibilityRole="button" onPress={() => navigation.navigate('GroupDetail', { groupId: item.group_id, groupName: item.group })} style={[styles.activityRow, index < list.length - 1 && styles.divider]}>
                  <View style={[styles.tile, { backgroundColor: tint(item.group).bg }]}><Icon name="people-outline" size={20} color={tint(item.group).fg} /></View>
                  <Text style={[styles.rowTitle, styles.flex]} numberOfLines={1}>{item.group}</Text>
                  <Text style={styles.rowAmount}>{money(item.total)}</Text>
                </Pressable>
              ))}
            </View>
          ) : <EmptyDark icon="calendar-outline" label="No spending recorded this month." />}
        </View>

        <View style={styles.section}>
          <SectionTitle title="Spending insights" />
          {insights.count ? (
            <>
              <View style={styles.statsGrid}>
                <Stat label="Total spent" value={money(insights.total)} />
                <Stat label="Expenses" value={String(insights.count)} />
                <Stat label="Average" value={money(insights.average ?? insights.total / insights.count)} />
                <Stat label="Top category" value={insights.top_category || 'None'} />
              </View>
              <View style={[styles.darkCard, styles.chartCard]}>
                <Text style={styles.cardTitle}>By category</Text>
                <BarList dark rows={insights.category_totals.map(row => ({ label: row.category, total: row.total }))} format={money} emptyLabel="No categories yet." />
              </View>
              <View style={[styles.darkCard, styles.chartCard]}>
                <Text style={styles.cardTitle}>By group</Text>
                <BarList dark rows={(insights.group_totals || []).map(row => ({ label: row.name, total: row.total }))} format={money} emptyLabel="No group spending yet." />
              </View>
              {insights.monthly_totals?.length ? (
                <View style={[styles.darkCard, styles.chartCard]}>
                  <Text style={styles.cardTitle}>Monthly trend</Text>
                  <MonthBars dark rows={insights.monthly_totals} />
                </View>
              ) : null}
              <View style={[styles.darkCard, styles.chartCard]}>
                <Text style={styles.cardTitle}>Paid by</Text>
                <BarList dark rows={insights.payer_totals.map(row => ({ label: row.name, total: row.total }))} format={money} emptyLabel="No payers yet." />
              </View>
            </>
          ) : <EmptyDark icon="analytics-outline" label="Add an expense to see spending insights." />}
        </View>

        <View style={styles.section}>
          <SectionTitle title="Upcoming reminders" />
          {reminders.length ? (
            <View style={styles.darkCard}>
              {reminders.slice(0, 5).map((task, index, list) => (
                <View key={task.id} style={[styles.activityRow, index < list.length - 1 && styles.divider]}>
                  <View style={[styles.tile, { backgroundColor: TINTS[1].bg }]}><Icon name="alarm-outline" size={20} color={TINTS[1].fg} /></View>
                  <View style={styles.flex}>
                    <Text style={styles.rowTitle} numberOfLines={1}>{task.title}</Text>
                    <Text style={styles.rowMeta} numberOfLines={1}>{task.group_name} · {formatDateTime(task.reminder_time, 'No reminder')}</Text>
                  </View>
                </View>
              ))}
            </View>
          ) : <EmptyDark icon="notifications-outline" label="No upcoming reminders. Task reminders will appear here." />}
        </View>
      </View>
    </Screen>
  );
}

/** The lower part of Home is always black, whatever the app theme, with yellow and soft tints on it. */
const SHEET = {
  bg: '#000000',
  card: '#1F1F1F',
  line: '#272727',
  text: '#ffffff',
  muted: '#9b9b9b',
  positive: '#7ee2a8',
  negative: '#ff9bb3'
};

/** Soft colour pairs for icons and avatars: [background, foreground]. */
const TINTS = [
  { bg: '#3a3420', fg: '#ffc83d' },
  { bg: '#1e3a2b', fg: '#7ee2a8' },
  { bg: '#3d2a1f', fg: '#ffb38a' },
  { bg: '#2c2848', fg: '#b4a8ff' },
  { bg: '#1d3046', fg: '#8cc8ff' },
  { bg: '#40222d', fg: '#ff9bb3' }
];

const CATEGORY: Record<string, { icon: IconName; tint: number }> = {
  Groceries: { icon: 'cart-outline', tint: 1 },
  Dining: { icon: 'restaurant-outline', tint: 2 },
  Rent: { icon: 'home-outline', tint: 3 },
  Utilities: { icon: 'wifi-outline', tint: 4 },
  Transport: { icon: 'car-outline', tint: 4 },
  Travel: { icon: 'airplane-outline', tint: 3 },
  Entertainment: { icon: 'film-outline', tint: 5 },
  Shopping: { icon: 'pricetags-outline', tint: 0 },
  Health: { icon: 'medkit-outline', tint: 5 }
};

function categoryStyle(category: string) {
  const match = CATEGORY[category] || { icon: 'receipt-outline' as IconName, tint: 0 };
  return { icon: match.icon, ...TINTS[match.tint] };
}

function tint(name: string) {
  let hash = 0;
  for (const char of name || '?') {
    hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  }
  return TINTS[hash % TINTS.length];
}

function initials(name: string) {
  return name.split(' ').filter(Boolean).slice(0, 2).map(part => part[0].toUpperCase()).join('') || '?';
}

function greeting() {
  const hour = new Date().getHours();
  return hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
}

function Action({ icon, label, onPress, disabled }: { icon: IconName; label: string; onPress: () => void; disabled?: boolean }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} disabled={disabled} onPress={onPress} style={({ pressed }) => [styles.action, pressed && styles.pressed]}>
      <View style={styles.actionCircle}><Icon name={icon} size={24} color="#1f2023" /></View>
      <Text style={styles.actionLabel}>{label}</Text>
    </Pressable>
  );
}

function SectionTitle({ title, action, onAction }: { title: string; action?: string; onAction?: () => void }) {
  return (
    <View style={styles.sectionHead}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {action ? <Pressable accessibilityRole="button" onPress={onAction}><Text style={styles.sectionAction}>{action}</Text></Pressable> : null}
    </View>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <View style={[styles.darkCard, styles.stat]}>
      <Text style={styles.rowMeta}>{label}</Text>
      <Text style={styles.statValue} numberOfLines={1}>{value}</Text>
    </View>
  );
}

function EmptyDark({ icon, label }: { icon: IconName; label: string }) {
  return (
    <View style={[styles.darkCard, styles.empty]}>
      <View style={[styles.tile, { backgroundColor: TINTS[0].bg }]}><Icon name={icon} size={20} color={TINTS[0].fg} /></View>
      <Text style={[styles.rowMeta, styles.flex]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.xxl,
    backgroundColor: colors.highlight
  },
  greeting: {
    ...typography.h3,
    color: colors.onHighlight
  },
  balance: {
    fontFamily: fonts.semiBold,
    fontSize: 48,
    lineHeight: 56,
    color: colors.onHighlight
  },
  pills: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm
  },
  pill: {
    borderRadius: 9999,
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.md
  },
  pillDark: {
    backgroundColor: '#1f2023'
  },
  pillDarkText: {
    ...typography.caption,
    color: '#ffffff'
  },
  pillSoft: {
    backgroundColor: 'rgba(31, 32, 35, 0.12)'
  },
  pillSoftText: {
    ...typography.caption,
    color: colors.onHighlight
  },
  sheet: {
    flexGrow: 1,
    gap: spacing.xl,
    marginTop: -spacing.xl,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.xl,
    paddingBottom: spacing.xxl,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    backgroundColor: SHEET.bg
  },
  actions: {
    flexDirection: 'row',
    justifyContent: 'space-between'
  },
  action: {
    width: 72,
    alignItems: 'center',
    gap: spacing.sm
  },
  pressed: {
    transform: [{ scale: 0.96 }],
    opacity: 0.85
  },
  actionCircle: {
    width: 56,
    height: 56,
    borderRadius: 9999,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#ffffff'
  },
  actionLabel: {
    ...typography.caption,
    color: SHEET.text,
    textAlign: 'center'
  },
  section: {
    gap: spacing.md
  },
  sectionHead: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between'
  },
  sectionTitle: {
    ...typography.h2,
    color: SHEET.text
  },
  sectionAction: {
    ...typography.label,
    color: colors.highlight
  },
  people: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.md
  },
  person: {
    width: 72,
    alignItems: 'center',
    gap: spacing.xs
  },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 9999,
    alignItems: 'center',
    justifyContent: 'center'
  },
  avatarText: {
    ...typography.bodyStrong
  },
  inviteAvatar: {
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: SHEET.muted
  },
  personName: {
    ...typography.caption,
    color: SHEET.text
  },
  personAmount: {
    ...typography.caption
  },
  darkCard: {
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: SHEET.line,
    backgroundColor: SHEET.card
  },
  rowCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    padding: spacing.md
  },
  activityRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg
  },
  divider: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: SHEET.line
  },
  tile: {
    width: 40,
    height: 40,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center'
  },
  flex: {
    flex: 1
  },
  rowTitle: {
    ...typography.h3,
    color: SHEET.text
  },
  rowMeta: {
    ...typography.caption,
    color: SHEET.muted
  },
  rowAmount: {
    ...typography.bodyStrong,
    color: SHEET.text
  },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.md
  },
  stat: {
    flexBasis: '47%',
    flexGrow: 1,
    gap: spacing.xs,
    padding: spacing.lg
  },
  statValue: {
    ...typography.h2,
    color: SHEET.text
  },
  chartCard: {
    gap: spacing.md,
    padding: spacing.lg
  },
  cardTitle: {
    ...typography.h3,
    color: SHEET.text
  },
  empty: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    padding: spacing.lg
  }
});
