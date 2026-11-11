import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { BottomTabScreenProps } from '@react-navigation/bottom-tabs';
import { CompositeScreenProps, useFocusEffect } from '@react-navigation/native';
import { useCallback, useRef, useState } from 'react';
import { Alert, Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { api } from '@/api/client';
import { AppButton } from '@/components/AppButton';
import { AppText as Text } from '@/components/AppText';
import { Card } from '@/components/Card';
import { ChoiceChips } from '@/components/ChoiceChips';
import { Screen } from '@/components/Screen';
import { EmptyState, ErrorState, LoadingState } from '@/components/States';
import { useAuth } from '@/state/AuthContext';
import { colors, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import { formatMoney } from '@/utils/money';
import type { Dashboard, MainTabParamList, PersonBalance, RootStackParamList } from '@/types';

type Props = CompositeScreenProps<
  BottomTabScreenProps<MainTabParamList, 'Split'>,
  NativeStackScreenProps<RootStackParamList>
>;

export function SplitScreen({ navigation }: Props) {
  const { currencyCode } = useAuth();
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [people, setPeople] = useState<PersonBalance[]>([]);
  const [expandedUserId, setExpandedUserId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const hasLoaded = useRef(false);
  const [expenseGroupId, setExpenseGroupId] = useState<number | null>(null);
  const [openingExpense, setOpeningExpense] = useState(false);
  const money = (value: number) => formatMoney(value, currencyCode);

  const load = useCallback(async () => {
    try {
      const [dashboardData, peopleData] = await Promise.all([
        api.dashboard(),
        api.peopleBalances()
      ]);
      setDashboard(dashboardData);
      setPeople(peopleData);
      hasLoaded.current = true;
      setLoadError(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Try again.';
      setLoadError(message);
      if (hasLoaded.current) {
        Alert.alert('Could not refresh Split', message);
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

  useFocusEffect(useCallback(() => {
    load();
  }, [load]));

  // The expense form needs the group's members, categories and default split.
  async function startExpense() {
    const groups = dashboard?.groups || [];
    const groupId = expenseGroupId ?? (groups.length === 1 ? groups[0].id : null);
    if (!groupId) {
      Alert.alert('Choose a group', 'Pick which group this expense belongs to.');
      return;
    }
    setOpeningExpense(true);
    try {
      const detail = await api.groupDetail(groupId);
      navigation.navigate('AddExpense', {
        groupId,
        members: detail.group.members,
        currentUserId: detail.current_user_id,
        categories: detail.expense_categories,
        defaultSplit: detail.default_split
      });
    } catch (error) {
      Alert.alert('Could not open the expense form', error instanceof Error ? error.message : 'Try again.');
    } finally {
      setOpeningExpense(false);
    }
  }

  function openGroup(groupId: number, groupName: string) {
    navigation.navigate('GroupDetail', { groupId, groupName });
  }

  function handlePersonPress(person: PersonBalance) {
    if (person.groups.length === 1) {
      const [group] = person.groups;
      openGroup(group.group_id, group.group_name);
      return;
    }
    setExpandedUserId(current => (current === person.user_id ? null : person.user_id));
  }

  if (loading && !dashboard) {
    return <LoadingState label="Loading your spending..." />;
  }
  if (!dashboard) {
    return <ErrorState message={loadError || 'Could not load Split.'} onRetry={() => { setLoading(true); load(); }} />;
  }

  const activePeople = people.filter(person => person.net !== 0);
  const settledPeople = people.filter(person => person.net === 0);

  return (
    <Screen onRefresh={refresh} refreshing={refreshing}>
      <View style={styles.statsGrid}>
        <View style={styles.statTile}>
          <Text style={styles.statLabel}>Owed to you</Text>
          <Text style={[styles.statValue, { color: colors.success }]}>{money(dashboard.total_owed_to_user)}</Text>
        </View>
        <View style={styles.statTile}>
          <Text style={styles.statLabel}>You owe</Text>
          <Text style={[styles.statValue, { color: colors.danger }]}>{money(dashboard.total_user_owes)}</Text>
        </View>
      </View>

      <Card style={styles.addCard}>
        <Text style={styles.addTitle}>Add Expense</Text>
        {dashboard.groups.length ? (
          <>
            {dashboard.groups.length > 1 ? (
              <ChoiceChips<number>
                label="Group"
                value={expenseGroupId}
                onChange={setExpenseGroupId}
                options={dashboard.groups.map(group => ({ label: group.name, value: group.id }))}
              />
            ) : (
              <Text style={styles.addHelp}>For {dashboard.groups[0].name}</Text>
            )}
            <AppButton icon="add-outline" loading={openingExpense} onPress={startExpense}>Add Expense</AppButton>
          </>
        ) : (
          <>
            <Text style={styles.addHelp}>Create a group first, then you can split expenses with it.</Text>
            <AppButton icon="people-outline" onPress={() => navigation.navigate('CreateGroup')}>Create Group</AppButton>
          </>
        )}
      </Card>

      <Text style={styles.sectionTitle}>Who Owes Who</Text>
      {activePeople.length ? activePeople.map(person => {
        const isExpanded = expandedUserId === person.user_id;
        const isMultiGroup = person.groups.length > 1;
        const positive = person.net > 0;
        return (
          <Card key={person.user_id} style={styles.personCard}>
            <Pressable style={styles.personRow} onPress={() => handlePersonPress(person)}>
              <View style={styles.personAvatar}>
                <Text style={styles.personAvatarText}>{person.name.slice(0, 1).toUpperCase()}</Text>
              </View>
              <View style={styles.groupMain}>
                <Text style={styles.personName}>{person.name}</Text>
                <Text style={styles.muted}>
                  {positive ? 'owes you' : 'you owe'} - {person.groups.length} group{person.groups.length === 1 ? '' : 's'}
                </Text>
              </View>
              <Text style={[styles.personNet, { color: positive ? colors.success : colors.danger }]}>
                {money(Math.abs(person.net))}
              </Text>
              {isMultiGroup ? (
                <Ionicons
                  name={isExpanded ? 'chevron-up' : 'chevron-down'}
                  size={18}
                  color={colors.muted}
                  style={styles.chevron}
                />
              ) : (
                <Ionicons name="chevron-forward" size={18} color={colors.muted} style={styles.chevron} />
              )}
            </Pressable>
            {isMultiGroup && isExpanded ? (
              <View style={styles.breakdown}>
                {person.groups.map(group => (
                  <Pressable
                    key={group.group_id}
                    style={styles.breakdownRow}
                    onPress={() => openGroup(group.group_id, group.group_name)}
                  >
                    <Text style={styles.breakdownName}>{group.group_name}</Text>
                    <Text style={[styles.breakdownNet, { color: group.net === 0 ? colors.muted : group.net > 0 ? colors.success : colors.danger }]}>
                      {group.net === 0 ? money(0) : money(Math.abs(group.net))}
                    </Text>
                  </Pressable>
                ))}
              </View>
            ) : null}
          </Card>
        );
      }) : <EmptyState label="No outstanding balances. You're all settled up." />}
      {settledPeople.length ? (
        <Text style={styles.settledHint}>
          {settledPeople.length} {settledPeople.length === 1 ? 'person' : 'people'} settled up
        </Text>
      ) : null}

      <Text style={styles.sectionTitle}>This Month</Text>
      {dashboard.monthly_spending.length ? dashboard.monthly_spending.map(item => (
        <Card key={item.group_id} style={styles.spendingRow}>
          <View style={styles.groupMain}>
            <Text style={styles.groupName}>{item.group}</Text>
            <Text style={styles.muted}>Recorded workspace spending</Text>
          </View>
          <Text style={styles.spendingAmount}>{money(item.total)}</Text>
        </Card>
      )) : <EmptyState label="No spending recorded this month." />}

      <Text style={styles.sectionTitle}>Recent Expenses</Text>
      {dashboard.recent_expenses.length ? dashboard.recent_expenses.map(expense => (
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
    </Screen>
  );
}

const styles = StyleSheet.create({
  addCard: {
    gap: spacing.sm
  },
  addTitle: {
    ...typography.h3,
    color: colors.ink
  },
  addHelp: {
    ...typography.body,
    color: colors.secondary
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
    ...typography.h2
  },
  sectionTitle: {
    ...typography.h2,
    color: colors.ink
  },
  personCard: {
    gap: spacing.sm
  },
  personRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm
  },
  personAvatar: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.md,
    backgroundColor: colors.primary
  },
  personAvatarText: {
    ...typography.bodyStrong,
    color: colors.white
  },
  personName: {
    ...typography.bodyStrong,
    color: colors.ink
  },
  personNet: {
    ...typography.bodyStrong
  },
  chevron: {
    marginLeft: spacing.xs
  },
  breakdown: {
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: spacing.sm,
    gap: spacing.xs
  },
  breakdownRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.xs
  },
  breakdownName: {
    ...typography.body,
    color: colors.secondary
  },
  breakdownNet: {
    ...typography.bodyStrong
  },
  settledHint: {
    ...typography.caption,
    color: colors.muted
  },
  groupMain: {
    flex: 1,
    gap: 2
  },
  groupName: {
    ...typography.bodyStrong,
    color: colors.ink
  },
  muted: {
    ...typography.caption,
    color: colors.muted
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
