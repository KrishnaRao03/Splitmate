import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useFocusEffect } from '@react-navigation/native';
import { useCallback, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, Linking, Pressable, Share, StyleSheet, TextInput, View } from 'react-native';
import { Icon } from '@/components/Icon';

import { api } from '@/api/client';
import { AppButton } from '@/components/AppButton';
import { AppText as Text } from '@/components/AppText';
import { BrandMark } from '@/components/BrandMark';
import { Card } from '@/components/Card';
import { Screen } from '@/components/Screen';
import { SegmentedControl } from '@/components/SegmentedControl';
import { EmptyState, ErrorState, LoadingState } from '@/components/States';
import { useAuth } from '@/state/AuthContext';
import { colors, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import { formatDate } from '@/utils/dates';
import { formatMoney } from '@/utils/money';
import { confirm, notify, useUndo } from '@/state/UndoToast';
import type { Expense, ExpenseSearchResult, Group, GroupDetail, RootStackParamList } from '@/types';
import { HistoryFilters } from '@/components/HistoryFilters';
import { HISTORY_PAGE, HistoryPeriod, HistorySort, filterHistory } from '@/utils/history';

type Props = NativeStackScreenProps<RootStackParamList, 'GroupDetail'>;
type Tab = 'overview' | 'expenses';

export function GroupDetailScreen({ navigation, route }: Props) {
  const { groupId } = route.params;
  const { currencyCode } = useAuth();
  const [removed, setRemoved] = useState<string[]>([]);
  const showUndo = useUndo();
  const [detail, setDetail] = useState<GroupDetail | null>(null);
  const groupCurrency = detail?.group.currency || currencyCode;
  const money = useCallback((value: number) => formatMoney(value, groupCurrency), [groupCurrency]);
  const [tab, setTab] = useState<Tab>('overview');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const hasLoaded = useRef(false);
  const [sort, setSort] = useState<HistorySort>('newest');
  const [period, setPeriod] = useState<HistoryPeriod>('all');
  const [shown, setShown] = useState(HISTORY_PAGE);
  const [expenseSearch, setExpenseSearch] = useState('');
  const [searchResults, setSearchResults] = useState<ExpenseSearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [exportingCsv, setExportingCsv] = useState(false);

  // Reloads quietly: the screen keeps showing its current data instead of
  // flashing a full-screen spinner after every action.
  const load = useCallback(async () => {
    try {
      const next = await api.groupDetail(groupId);
      setDetail(next);
      hasLoaded.current = true;
      setLoadError(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Try again.';
      setLoadError(message);
      if (hasLoaded.current) {
        notify('Could not refresh group', message);
      }
    } finally {
      setLoading(false);
    }
  }, [groupId]);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }, [load]);

  useFocusEffect(useCallback(() => {
    load();
  }, [load]));

  const groupName = detail?.group.name ?? route.params.groupName;
  const openManage = useCallback(() => {
    navigation.navigate('GroupSettings', { groupId, groupName });
  }, [groupId, groupName, navigation]);

  // A Manage button in the header, so group settings are always one tap away from any tab.
  useLayoutEffect(() => {
    navigation.setOptions({
      title: groupName,
      headerRight: () => (
        <Pressable onPress={openManage} accessibilityRole="button" accessibilityLabel="Manage group" hitSlop={8} style={styles.headerButton}>
          <Icon name="settings-outline" size={20} color={colors.primary} />
          <Text style={styles.headerButtonText}>Manage</Text>
        </Pressable>
      )
    });
  }, [groupName, navigation, openManage]);

  async function runAction(action: () => Promise<unknown>, title: string, done?: [string, string?]) {
    try {
      await action();
      if (done) {
        notify(...done);
      }
      await load();
    } catch (error) {
      notify(title, error instanceof Error ? error.message : 'Try again.');
      // Undo any optimistic change by showing what the server really has.
      load().catch(() => undefined);
    }
  }

  // Deletes hide the item at once and show an Undo toast; the server delete runs when it times out.
  function removeWithUndo(key: string, message: string, remove: () => Promise<unknown>, failTitle: string) {
    setRemoved(keys => [...keys, key]);
    const restore = () => setRemoved(keys => keys.filter(item => item !== key));
    showUndo(message, {
      commit: () => { runAction(remove, failTitle).finally(restore); },
      undo: restore
    });
  }

  function editExpense(expense: Expense) {
    if (!detail) {
      return;
    }
    if (expense.splits.some(split => split.is_settled && split.user_id !== expense.paid_by_id)) {
      notify('Cannot edit this expense', 'Part of it has already been settled. Delete it and add a corrected expense instead.');
      return;
    }
    navigation.navigate('AddExpense', {
      groupId,
      members: detail.group.members,
      groupName: detail.group.name,
      currentUserId: detail.current_user_id,
      categories: detail.expense_categories,
      defaultSplit: detail.default_split,
      currency: detail.group.currency,
      expense
    });
  }

  async function moveExpense(expense: Expense) {
    if (expense.splits.some(split => split.is_settled && split.user_id !== expense.paid_by_id)) {
      notify('Cannot move this expense', 'Part of it has already been settled.');
      return;
    }
    let groups: Group[];
    try {
      groups = (await api.groups()).filter(group => group.id !== groupId);
    } catch (error) {
      notify('Could not load your groups', error instanceof Error ? error.message : 'Try again.');
      return;
    }
    if (!groups.length) {
      notify('No other groups', 'Join or create another group to move expenses there.');
      return;
    }
    confirm(`Move ${expense.description} to`, 'It is split the way that group splits by default.', [
      ...groups.map(group => ({
        text: group.name,
        onPress: () => runAction(async () => {
          await api.moveExpense(expense.id, group.id);
          notify('Expense moved', `${expense.description} is now in ${group.name}.`);
        }, 'Could not move expense')
      })),
      { text: 'Cancel', style: 'cancel' as const }
    ]);
  }

  function confirmDeleteExpense(expense: Expense) {
    removeWithUndo(`expense:${expense.id}`, `${expense.description} deleted`, () => api.deleteExpense(expense.id), 'Could not delete expense');
  }

  function clearRecentExpenses() {
    confirm('Clear recent expenses?', 'Balances from active expenses will be cleared, but transaction history stays available.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Clear', style: 'destructive', onPress: () => runAction(() => api.clearExpenses(groupId), 'Could not clear expenses', ['Expenses cleared', 'Transaction history still has them.']) }
    ]);
  }

  async function runExpenseSearch() {
    const query = expenseSearch.trim();
    if (!query) {
      setSearchResults(null);
      setSearchError(null);
      return;
    }
    setSearching(true);
    setSearchError(null);
    try {
      const results = await api.searchExpenses(groupId, { q: query });
      setSearchResults(results);
    } catch (error) {
      setSearchError(error instanceof Error ? error.message : 'Try again.');
    } finally {
      setSearching(false);
    }
  }

  function clearExpenseSearch() {
    setExpenseSearch('');
    setSearchResults(null);
    setSearchError(null);
  }

  async function shareActivityCsv() {
    setExportingCsv(true);
    try {
      const csv = await api.exportActivityCsv(groupId);
      await Share.share({ message: csv });
    } catch (error) {
      notify('Could not export activity', error instanceof Error ? error.message : 'Try again.');
    } finally {
      setExportingCsv(false);
    }
  }


  const history = useMemo(
    () => filterHistory((detail?.expenses ?? []).filter(expense => !removed.includes(`expense:${expense.id}`)), sort, period),
    [detail, period, removed, sort]
  );
  const openSettleUp = () => navigation.navigate('SettleUp', { groupId, groupName });

  if (loading && !detail) {
    return <LoadingState label="Loading group..." />;
  }
  if (!detail) {
    return <ErrorState message={loadError || 'Could not load this group.'} onRetry={() => { setLoading(true); load(); }} />;
  }

  const isAdmin = detail.group.admin_id === detail.current_user_id;
  const navigateToExpense = () => navigation.navigate('AddExpense', {
    groupId,
    members: detail.group.members,
    groupName: detail.group.name,
    currentUserId: detail.current_user_id,
    categories: detail.expense_categories,
    defaultSplit: detail.default_split,
    currency: detail.group.currency
  });

  return (
    <Screen onRefresh={refresh} refreshing={refreshing}>
      <Card style={styles.pageHeader}>
        <View style={styles.headerRow}>
          <View style={styles.brandRow}>
            <BrandMark size={40} />
            <View style={styles.headerText}>
              <Text style={styles.title}>{detail.group.name}</Text>
              <Text style={styles.muted}>{detail.group.members.length} members</Text>
            </View>
          </View>
        </View>
        <View style={styles.actionRow}>
          <AppButton icon="add-outline" style={styles.actionButton} onPress={navigateToExpense}>Add expense</AppButton>
          <AppButton icon="swap-horizontal-outline" variant="outline" style={styles.actionButton} onPress={openSettleUp}>Settle up</AppButton>
        </View>
        <View style={styles.actionRow}>
          <AppButton icon="analytics-outline" variant="ghost" style={styles.actionButton} onPress={() => navigation.navigate('Insights', {
            groupId,
            groupName: detail.group.name,
            members: detail.group.members,
            categories: detail.expense_categories
          })}>Insights</AppButton>
          <AppButton icon="settings-outline" variant="ghost" style={styles.actionButton} onPress={openManage}>Manage</AppButton>
        </View>
      </Card>

      <SegmentedControl<Tab>
        value={tab}
        onChange={setTab}
        options={[
          { label: 'Overview', value: 'overview' },
          { label: 'Expenses', value: 'expenses' }
        ]}
      />

      {tab === 'overview' ? (
        <>
          <Text style={styles.sectionTitle}>Balances</Text>
          {detail.balances.map(balance => (
            <Card key={balance.id}>
              <View style={styles.rowBetween}>
                <Text style={styles.itemTitle}>{balance.name}</Text>
                <Text style={[styles.net, balance.net >= 0 ? styles.positive : styles.negative]}>
                  {balance.net >= 0 ? '+' : ''}{money(balance.net)}
                </Text>
              </View>
              <Text style={styles.muted}>Paid {money(balance.paid)} · Owes {money(balance.owes)}</Text>
            </Card>
          ))}
          <Text style={styles.sectionTitle}>Members</Text>
          <Card>
            {detail.group.members.map(member => (
              <View key={member.id} style={styles.memberRow}>
                <View style={styles.avatar}><Text style={styles.avatarText}>{member.name.slice(0, 1).toUpperCase()}</Text></View>
                <View style={styles.headerText}>
                  <Text style={styles.itemTitle}>{member.name}</Text>
                  <Text style={styles.muted}>{member.email}</Text>
                </View>
                {member.id === detail.group.admin_id ? (
                  <View style={styles.adminPill}><Text style={styles.adminLabel}>Admin</Text></View>
                ) : null}
              </View>
            ))}
            <AppButton icon="settings-outline" variant="outline" onPress={openManage}>
              {isAdmin ? 'Manage group' : 'Group info & leave'}
            </AppButton>
          </Card>
        </>
      ) : null}

      {tab === 'expenses' ? (
        <>
          <View style={styles.searchRow}>
            <Icon name="search-outline" size={18} color={colors.muted} />
            <TextInput
              style={styles.searchInput}
              placeholder="Search expenses"
              placeholderTextColor={colors.muted}
              value={expenseSearch}
              onChangeText={text => { setExpenseSearch(text); if (!text.trim()) { clearExpenseSearch(); } }}
              onSubmitEditing={runExpenseSearch}
              returnKeyType="search"
            />
            {searching ? <ActivityIndicator color={colors.primary} /> : expenseSearch ? (
              <Pressable accessibilityLabel="Clear search" hitSlop={8} onPress={clearExpenseSearch}><Icon name="close-outline" size={18} color={colors.muted} /></Pressable>
            ) : null}
          </View>

          {searchResults !== null ? (
            <Card style={styles.flushCard}>
              {searchError ? (
                <ErrorState message={searchError} onRetry={runExpenseSearch} />
              ) : searchResults.length ? searchResults.map((result, index) => (
                <View key={result.id} style={[styles.historyRow, index > 0 && styles.divider]}>
                  <View style={styles.headerText}>
                    <Text style={styles.itemTitle}>{result.description}</Text>
                    <Text style={styles.muted}>{result.paid_by}{result.date ? ` · ${formatDate(result.date)}` : ''} · {result.category}</Text>
                  </View>
                  <Text style={styles.amountNeutral}>{money(result.amount)}</Text>
                </View>
              )) : <Text style={[styles.muted, styles.emptyLine]}>Nothing matches "{expenseSearch.trim()}".</Text>}
            </Card>
          ) : (
            <>
              <HistoryFilters sort={sort} period={period} onSort={value => { setSort(value); setShown(HISTORY_PAGE); }} onPeriod={value => { setPeriod(value); setShown(HISTORY_PAGE); }} />
              {history.length ? history.slice(0, shown).map(expense => (
                <Card key={expense.id}>
                  <View style={styles.rowBetween}>
                    <View style={styles.headerText}>
                      <Text style={styles.itemTitle}>{expense.description}</Text>
                      <Text style={styles.muted}>
                        {expense.paid_by} paid{expense.date ? ` · ${formatDate(expense.date)}` : ''} · ÷ {new Set([...expense.splits.map(split => split.user_id), expense.paid_by_id]).size}
                      </Text>
                    </View>
                    <Text style={styles.amountNeutral}>{money(expense.amount)}</Text>
                  </View>
                  {expense.splits.map(split => (
                    <Text key={split.id} style={styles.memberLine}>
                      {split.user}: {money(split.amount)} {split.is_settled ? '· settled' : ''}
                    </Text>
                  ))}
                  <View style={styles.iconActionRow}>
                    {expense.receipt_url ? (
                      <Pressable hitSlop={8} accessibilityLabel="Open receipt" onPress={() => Linking.openURL(api.resolveUrl(expense.receipt_url || ''))} style={styles.iconButton}><Icon name="receipt-outline" size={20} color={colors.primaryDark} /></Pressable>
                    ) : null}
                    {expense.paid_by_id === detail.current_user_id || isAdmin ? (
                      <>
                        <Pressable hitSlop={8} accessibilityLabel={`Edit ${expense.description}`} onPress={() => editExpense(expense)} style={styles.iconButton}><Icon name="pencil-outline" size={20} color={colors.primaryDark} /></Pressable>
                        <Pressable hitSlop={8} accessibilityLabel={`Move ${expense.description} to another group`} onPress={() => moveExpense(expense)} style={styles.iconButton}><Icon name="swap-horizontal-outline" size={20} color={colors.primaryDark} /></Pressable>
                        <Pressable hitSlop={8} accessibilityLabel={`Delete ${expense.description}`} onPress={() => confirmDeleteExpense(expense)} style={styles.iconButton}><Icon name="trash-outline" size={20} color={colors.danger} /></Pressable>
                      </>
                    ) : null}
                  </View>
                </Card>
              )) : <EmptyState label={detail.expenses.length ? 'No expenses in this period.' : 'No expenses yet. Add one to get started.'} />}
              {history.length > shown ? <AppButton variant="ghost" onPress={() => setShown(count => count + HISTORY_PAGE)}>Show more</AppButton> : null}
            </>
          )}

          <View style={styles.footerLinks}>
            <Pressable onPress={shareActivityCsv} disabled={exportingCsv}><Text style={styles.link}>{exportingCsv ? 'Preparing...' : 'Share as CSV'}</Text></Pressable>
            {isAdmin ? <Pressable onPress={clearRecentExpenses}><Text style={[styles.link, styles.dangerLink]}>Clear recent</Text></Pressable> : null}
          </View>
        </>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  searchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.md,
    minHeight: 44,
    backgroundColor: colors.surface
  },
  searchInput: {
    flex: 1,
    color: colors.ink,
    ...typography.body,
    paddingVertical: spacing.sm
  },
  flushCard: {
    paddingVertical: 0
  },
  historyRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.md
  },
  divider: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border
  },
  emptyLine: {
    paddingVertical: spacing.md
  },
  footerLinks: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: spacing.xl,
    paddingVertical: spacing.sm
  },
  link: {
    color: colors.primary,
    ...typography.caption,
    textDecorationLine: 'underline'
  },
  dangerLink: {
    color: colors.danger
  },
  headerButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    paddingHorizontal: spacing.sm,
    minHeight: 40
  },
  headerButtonText: {
    color: colors.primary,
    ...typography.bodyStrong
  },
  pageHeader: {
    backgroundColor: colors.surface,
    gap: spacing.md
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: spacing.md,
    alignItems: 'center'
  },
  brandRow: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm
  },
  headerText: {
    flex: 1
  },
  title: {
    ...typography.h1,
    color: colors.ink
  },
  sectionTitle: {
    ...typography.h3,
    color: colors.ink
  },
  muted: {
    ...typography.caption,
    color: colors.muted
  },
  rowBetween: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: spacing.md
  },
  actionRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm
  },
  actionButton: {
    flexGrow: 1,
    flexBasis: 150
  },
  iconActionRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: spacing.xs
  },
  iconButton: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceAlt
  },
  itemTitle: {
    ...typography.bodyStrong,
    color: colors.ink
  },
  amountNeutral: {
    ...typography.bodyStrong,
    color: colors.ink
  },
  net: {
    ...typography.bodyStrong
  },
  positive: {
    color: colors.success
  },
  negative: {
    color: colors.danger
  },
  memberLine: {
    ...typography.caption,
    color: colors.secondary
  },
  memberRow: {
    minHeight: 58,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border
  },
  avatar: {
    width: 38,
    height: 38,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.pill,
    backgroundColor: colors.primary
  },
  avatarText: {
    ...typography.bodyStrong,
    color: colors.onPrimary
  },
  adminPill: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: radius.pill,
    backgroundColor: colors.primarySoft
  },
  adminLabel: {
    ...typography.caption,
    color: colors.primaryDark
  }
});
