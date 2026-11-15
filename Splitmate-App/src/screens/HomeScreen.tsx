import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { BottomTabScreenProps } from '@react-navigation/bottom-tabs';
import { CompositeScreenProps, useFocusEffect } from '@react-navigation/native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
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
import { confirm, notify, useUndo } from '@/state/UndoToast';
import { pickReceiptImage, type ReceiptFile } from '@/utils/receiptPicker';
import { takeLaunchLink } from '@/utils/launchLinks';
import type { Dashboard, Group, MainTabParamList, MyInvite, PersonBalance, RootStackParamList, Task } from '@/types';
import { tourSeenKey } from '@/screens/WelcomeScreen';
import { parseServerDate } from '@/utils/dates';

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
  const cacheKey = `splitmate.cache.dashboard.${user?.id ?? 'guest'}`;
  // Clearing Recent activity only hides it on this device; group history is untouched.
  // Expense ids only grow, so anything newer than the last cleared id shows again.
  const clearedKey = `splitmate.activity.cleared.${user?.id ?? 'guest'}`;
  const [clearedThrough, setClearedThrough] = useState(0);
  const showUndo = useUndo();

  // Only the very first load shows a full-screen spinner; later reloads (on focus,
  // pull-to-refresh) keep the current content visible.
  const load = useCallback(async () => {
    try {
      const [dashboardData, reminderData] = await Promise.all([
        api.dashboard(),
        api.upcomingReminders()
      ]);
      setDashboard(dashboardData);
      AsyncStorage.setItem(cacheKey, JSON.stringify(dashboardData)).catch(() => undefined);
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
        notify('Could not refresh Splitmate', message);
      }
    } finally {
      setLoading(false);
    }
  }, [cacheKey]);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }, [load]);

  useEffect(() => {
    configureNotifications().catch(() => undefined);
  }, []);

  // New accounts (joined in the last week) see the quick tour once on this device.
  useEffect(() => {
    const joined = user?.created_at ? parseServerDate(user.created_at) : null;
    if (!user || !joined || Date.now() - joined.getTime() > 7 * 24 * 3600 * 1000) {
      return;
    }
    AsyncStorage.getItem(tourSeenKey(user.id)).then(seen => {
      if (!seen) {
        navigation.navigate('Welcome', { userId: user.id });
      }
    }).catch(() => undefined);
  }, [navigation, user]);

  useEffect(() => {
    AsyncStorage.getItem(clearedKey).then(value => setClearedThrough(Number(value) || 0)).catch(() => undefined);
  }, [clearedKey]);

  function clearActivity() {
    const newest = Math.max(0, ...(dashboard?.recent_expenses ?? []).map(expense => expense.id));
    const previous = clearedThrough;
    setClearedThrough(newest);
    showUndo('Recent activity cleared', {
      commit: () => { AsyncStorage.setItem(clearedKey, String(newest)).catch(() => undefined); },
      undo: () => setClearedThrough(previous)
    });
  }

  // Links the app was opened with (Stripe checkout return, group invite email), acted on once
  // Home has data so a sign-in restore that remounts the screens can't swallow them.
  useEffect(() => {
    if (!dashboard) {
      return;
    }
    const membership = takeLaunchLink('membership');
    if (membership === 'success') {
      navigation.navigate('MembershipWelcome');
    } else if (membership === 'cancelled') {
      notify('Checkout cancelled', 'You were not charged.');
    }
    const add = takeLaunchLink('add');
    if (add) {
      navigation.navigate('AddFriend', { code: add });
    }
    const invite = takeLaunchLink('invite');
    if (invite) {
      api.acceptInviteLink(invite)
        .then(result => {
          notify('You joined a group', result.message);
          navigation.navigate('GroupDetail', { groupId: result.group.id, groupName: result.group.name });
        })
        .catch(error => notify('Could not join the group', error instanceof Error ? error.message : 'Open Group invites to try again.'));
    }
  }, [dashboard, navigation]);

  // Stale-while-revalidate: show the last dashboard straight away, then the fresh one replaces it.
  useEffect(() => {
    AsyncStorage.getItem(cacheKey).then(cached => {
      if (cached && !hasLoaded.current) {
        const data = JSON.parse(cached) as Dashboard;
        setDashboard(data);
        setGroups(data.groups);
        setLoading(false);
      }
    }).catch(() => undefined);
  }, [cacheKey]);

  useFocusEffect(useCallback(() => {
    load();
  }, [load]));

  // With one group the expense form opens straight away; with several, the Split tab asks which group.
  async function openExpenseForm() {
    if (groups.length !== 1) {
      navigation.navigate('Split');
      return;
    }
    await openExpenseFor(groups[0].id);
  }

  async function openExpenseFor(groupId: number, scanImage?: ReceiptFile) {
    setOpening(true);
    try {
      const detail = await api.groupDetail(groupId);
      navigation.navigate('AddExpense', {
        groupId,
        members: detail.group.members,
        groupName: detail.group.name,
        currentUserId: detail.current_user_id,
        categories: detail.expense_categories,
        defaultSplit: detail.default_split,
        scanImage
      });
    } catch (error) {
      notify('Could not open the expense form', error instanceof Error ? error.message : 'Try again.');
    } finally {
      setOpening(false);
    }
  }

  // Scan receipt opens the camera (or the photo picker on the web build) first, then the
  // expense form with the receipt already being read.
  async function scanReceipt() {
    if (!groups.length) {
      notify('Create a group first', 'Receipts are split with a group.');
      return;
    }
    const image = await pickReceiptImage('camera');
    if (!image) {
      return;
    }
    if (groups.length === 1) {
      await openExpenseFor(groups[0].id, image);
      return;
    }
    confirm('Which group is this receipt for?', undefined, [
      ...groups.slice(0, 6).map(group => ({ text: group.name, onPress: () => { void openExpenseFor(group.id, image); } })),
      { text: 'Cancel', style: 'cancel' as const }
    ]);
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
  const recentActivity = dashboard.recent_expenses.filter(expense => expense.id > clearedThrough);
  // My balance in each group, from the per-person balances (positive: they owe me).
  const groupNet = new Map<number, number>();
  people.forEach(person => person.groups.forEach(item => groupNet.set(item.group_id, (groupNet.get(item.group_id) ?? 0) + item.net)));
  const plain = (value: number) => formatMoney(Math.abs(value), currencyCode).replace(/[^0-9.,]/g, '');
  const signed = (value: number) => `${value > 0 ? '+' : value < 0 ? '-' : ''}${plain(value)}`;

  return (
    <Screen onRefresh={refresh} refreshing={refreshing}>
      <Text style={styles.greeting}>{greeting()}, {firstName}</Text>

      <View style={styles.receipt}>
        <View style={styles.receiptTop}>
          <Text style={styles.receiptLabel}>BALANCE</Text>
          <Text style={styles.receiptBalance} accessibilityLabel={`Balance ${money(net)}`}>{signed(net)}</Text>
          <Text style={styles.receiptMeta}>{currencyCode} across {groups.length} {groups.length === 1 ? 'group' : 'groups'}</Text>
        </View>
        <View style={styles.tear} />
        <View style={styles.receiptBottom}>
          <View style={styles.receiptRow}><Text style={styles.receiptMono}>OWED TO YOU</Text><Text style={styles.receiptMono}>{plain(dashboard.total_owed_to_user)}</Text></View>
          <View style={styles.receiptRow}><Text style={styles.receiptMono}>YOU OWE</Text><Text style={styles.receiptMono}>{plain(dashboard.total_user_owes)}</Text></View>
        </View>
      </View>

      <View style={styles.actions}>
        <Action label="Split a bill" icon="add-outline" filled onPress={openExpenseForm} disabled={opening} />
        <Action label="Scan receipt" icon="scan-outline" onPress={scanReceipt} disabled={opening} />
        <Action label="Settle up" icon="swap-horizontal-outline" onPress={settleUp} />
        <Action label="Quick split" icon="flash-outline" onPress={() => navigation.navigate('QuickSplit')} />
      </View>

      {invites.length ? (
        <Pressable accessibilityRole="button" onPress={() => navigation.navigate('Invites')} style={styles.notice}>
          <Icon name="mail-unread-outline" size={20} color={colors.ink} />
          <View style={styles.flex}>
            <Text style={styles.rowTitle}>
              {invites.length === 1 ? `You're invited to ${invites[0].group_name}` : `You have ${invites.length} group invites`}
            </Text>
            <Text style={styles.rowMeta}>Tap to review and join.</Text>
          </View>
          <Icon name="chevron-forward" size={16} color={colors.muted} />
        </Pressable>
      ) : null}

      <View style={styles.section}>
        <SectionTitle title="People" />
        <View style={styles.people}>
          {owing.map(person => (
            <Pressable key={person.user_id} accessibilityRole="button" style={styles.person} onPress={() => navigation.navigate('Split')}>
              <View style={[styles.avatar, person.net < 0 && styles.avatarOwe]}>
                <Text style={[styles.avatarText, person.net < 0 && styles.avatarOweText]}>{initials(person.name)}</Text>
              </View>
              <Text style={styles.personName} numberOfLines={1}>{person.name.split(' ')[0]}</Text>
              <Text style={styles.personAmount} numberOfLines={1}>{signed(person.net)}</Text>
            </Pressable>
          ))}
          <Pressable accessibilityRole="button" style={styles.person} onPress={() => navigation.navigate(groups.length ? 'Groups' : 'CreateGroup')}>
            <View style={[styles.avatar, styles.addAvatar]}><Icon name="add" size={20} color={colors.ink} /></View>
            <Text style={styles.personName}>{groups.length ? 'Invite' : 'New group'}</Text>
          </Pressable>
        </View>
      </View>

      <View style={styles.section}>
        <SectionTitle title="Groups" action={groups.length ? 'See all' : 'New group'} onAction={() => navigation.navigate(groups.length ? 'Groups' : 'CreateGroup')} />
        {groups.length ? (
          <View>
            {groups.slice(0, 6).map(group => (
              <Pressable key={group.id} accessibilityRole="button" onPress={() => navigation.navigate('GroupDetail', { groupId: group.id, groupName: group.name })} style={styles.line}>
                <Text style={[styles.lineTitle, styles.flex]} numberOfLines={1}>{group.name}</Text>
                <Text style={styles.lineAmount}>{signed(groupNet.get(group.id) ?? 0)}</Text>
              </Pressable>
            ))}
          </View>
        ) : <Text style={styles.rowMeta}>No groups yet. Create one to start splitting.</Text>}
      </View>

      <View style={styles.section}>
        <SectionTitle title="Recent activity" action={recentActivity.length ? 'Clear' : undefined} onAction={clearActivity} />
        {recentActivity.length ? (
          <View>
            {recentActivity.slice(0, 8).map(expense => (
              <View key={expense.id} style={styles.line}>
                <Icon name={categoryIcon(expense.category)} size={20} color={colors.ink} />
                <View style={styles.flex}>
                  <Text style={styles.rowTitle} numberOfLines={1}>{expense.description}</Text>
                  <Text style={styles.rowMeta} numberOfLines={1}>{expense.group_name} · {expense.category}</Text>
                </View>
                <Text style={styles.lineAmount}>{plain(expense.amount)}</Text>
              </View>
            ))}
          </View>
        ) : <Text style={styles.rowMeta}>{clearedThrough ? 'All caught up. New expenses will show here.' : 'No expenses yet. Add one to see it here.'}</Text>}
      </View>

      <View style={styles.section}>
        <SectionTitle title="This month" />
        {dashboard.monthly_spending.length ? (
          <View>
            {dashboard.monthly_spending.map(item => (
              <Pressable key={item.group_id} accessibilityRole="button" onPress={() => navigation.navigate('GroupDetail', { groupId: item.group_id, groupName: item.group })} style={styles.line}>
                <Text style={[styles.lineTitle, styles.flex]} numberOfLines={1}>{item.group}</Text>
                <Text style={styles.lineAmount}>{plain(item.total)}</Text>
              </Pressable>
            ))}
          </View>
        ) : <Text style={styles.rowMeta}>No spending recorded this month.</Text>}
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
            <View style={styles.panel}>
              <Text style={styles.cardTitle}>By category</Text>
              <BarList rows={insights.category_totals.map(row => ({ label: row.category, total: row.total }))} format={money} emptyLabel="No categories yet." />
            </View>
            <View style={styles.panel}>
              <Text style={styles.cardTitle}>By group</Text>
              <BarList rows={(insights.group_totals || []).map(row => ({ label: row.name, total: row.total }))} format={money} emptyLabel="No group spending yet." />
            </View>
            {insights.monthly_totals?.length ? (
              <View style={styles.panel}>
                <Text style={styles.cardTitle}>Monthly trend</Text>
                <MonthBars rows={insights.monthly_totals} />
              </View>
            ) : null}
            <View style={styles.panel}>
              <Text style={styles.cardTitle}>Paid by</Text>
              <BarList rows={insights.payer_totals.map(row => ({ label: row.name, total: row.total }))} format={money} emptyLabel="No payers yet." />
            </View>
          </>
        ) : <Text style={styles.rowMeta}>Add an expense to see spending insights.</Text>}
      </View>

      <View style={styles.section}>
        <SectionTitle title="Upcoming reminders" />
        {reminders.length ? (
          <View>
            {reminders.slice(0, 5).map(task => (
              <View key={task.id} style={styles.line}>
                <Icon name="alarm-outline" size={20} color={colors.ink} />
                <View style={styles.flex}>
                  <Text style={styles.rowTitle} numberOfLines={1}>{task.title}</Text>
                  <Text style={styles.rowMeta} numberOfLines={1}>{task.group_name} · {formatDateTime(task.reminder_time, 'No reminder')}</Text>
                </View>
              </View>
            ))}
          </View>
        ) : <Text style={styles.rowMeta}>No upcoming reminders. Task reminders will appear here.</Text>}
      </View>
    </Screen>
  );
}

const CATEGORY_ICONS: Record<string, IconName> = {
  Groceries: 'cart-outline',
  Dining: 'restaurant-outline',
  Rent: 'home-outline',
  Utilities: 'wifi-outline',
  Transport: 'car-outline',
  Travel: 'airplane-outline',
  Entertainment: 'film-outline',
  Shopping: 'pricetags-outline',
  Health: 'medkit-outline'
};

function categoryIcon(category: string): IconName {
  return CATEGORY_ICONS[category] || 'receipt-outline';
}

function initials(name: string) {
  return name.split(' ').filter(Boolean).slice(0, 2).map(part => part[0].toUpperCase()).join('') || '?';
}

function greeting() {
  const hour = new Date().getHours();
  return hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
}

function Action({ icon, label, onPress, disabled, filled }: { icon: IconName; label: string; onPress: () => void; disabled?: boolean; filled?: boolean }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} disabled={disabled} onPress={onPress} style={({ pressed }) => [styles.action, filled && styles.actionFilled, pressed && styles.pressed]}>
      <Icon name={icon} size={18} color={filled ? colors.onHighlight : colors.ink} />
      <Text style={[styles.actionLabel, filled && styles.actionLabelFilled]}>{label}</Text>
    </Pressable>
  );
}

function SectionTitle({ title, action, onAction }: { title: string; action?: string; onAction?: () => void }) {
  return (
    <View style={styles.sectionHead}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {action ? <Pressable accessibilityRole="button" hitSlop={8} onPress={onAction}><Text style={styles.sectionAction}>{action}</Text></Pressable> : null}
    </View>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <View style={[styles.panel, styles.stat]}>
      <Text style={styles.rowMeta}>{label}</Text>
      <Text style={styles.statValue} numberOfLines={1}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  greeting: {
    ...typography.h1,
    color: colors.ink
  },
  receipt: {
    borderRadius: 20,
    borderCurve: 'continuous',
    backgroundColor: colors.receipt
  },
  receiptTop: {
    gap: spacing.xs,
    padding: spacing.xl
  },
  receiptLabel: {
    ...typography.caption,
    letterSpacing: 1.5,
    color: colors.highlight
  },
  receiptBalance: {
    fontFamily: fonts.mono,
    fontSize: 40,
    lineHeight: 48,
    fontWeight: '700',
    color: colors.onReceipt
  },
  receiptMeta: {
    ...typography.body,
    color: colors.onReceipt
  },
  tear: {
    marginHorizontal: spacing.lg,
    borderTopWidth: 2,
    borderStyle: 'dashed',
    borderColor: colors.receiptLine
  },
  receiptBottom: {
    gap: spacing.sm,
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.md,
    paddingBottom: spacing.lg
  },
  receiptRow: {
    flexDirection: 'row',
    justifyContent: 'space-between'
  },
  receiptMono: {
    fontFamily: fonts.mono,
    fontSize: 14,
    lineHeight: 20,
    color: colors.onReceipt
  },
  actions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm
  },
  action: {
    flexBasis: '47%',
    flexGrow: 1,
    minHeight: 52,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    borderRadius: 14,
    borderCurve: 'continuous',
    borderWidth: 1.5,
    borderColor: colors.ink
  },
  actionFilled: {
    borderColor: colors.highlight,
    backgroundColor: colors.highlight
  },
  actionLabel: {
    ...typography.button,
    color: colors.ink
  },
  actionLabelFilled: {
    color: colors.onHighlight
  },
  pressed: {
    opacity: 0.8
  },
  notice: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    padding: spacing.lg,
    borderRadius: 14,
    borderCurve: 'continuous',
    backgroundColor: colors.primarySoft
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
    color: colors.ink
  },
  sectionAction: {
    ...typography.label,
    color: colors.ink,
    textDecorationLine: 'underline'
  },
  people: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.md
  },
  person: {
    width: 64,
    alignItems: 'center',
    gap: spacing.xs
  },
  avatar: {
    width: 56,
    height: 56,
    borderRadius: 9999,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: colors.ink
  },
  avatarOwe: {
    borderColor: colors.highlight,
    backgroundColor: colors.highlight
  },
  addAvatar: {
    borderStyle: 'dashed'
  },
  avatarText: {
    ...typography.h3,
    fontFamily: fonts.bold,
    color: colors.ink
  },
  avatarOweText: {
    color: colors.onHighlight
  },
  personName: {
    ...typography.caption,
    color: colors.ink
  },
  personAmount: {
    fontFamily: fonts.mono,
    fontSize: 12,
    lineHeight: 16,
    color: colors.ink
  },
  line: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.md,
    borderTopWidth: 1.5,
    borderTopColor: colors.borderStrong
  },
  lineTitle: {
    ...typography.h3,
    fontFamily: fonts.semiBold,
    color: colors.ink
  },
  lineAmount: {
    fontFamily: fonts.mono,
    fontSize: 15,
    lineHeight: 20,
    color: colors.ink
  },
  flex: {
    flex: 1
  },
  rowTitle: {
    ...typography.h3,
    color: colors.ink
  },
  rowMeta: {
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
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.md
  },
  stat: {
    flexBasis: '47%',
    flexGrow: 1,
    gap: spacing.xs
  },
  statValue: {
    ...typography.h2,
    color: colors.ink
  },
  cardTitle: {
    ...typography.h3,
    color: colors.ink
  }
});
