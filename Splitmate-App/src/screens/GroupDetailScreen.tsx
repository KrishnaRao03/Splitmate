import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useFocusEffect } from '@react-navigation/native';
import { useCallback, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Alert, Linking, Pressable, Share, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { api } from '@/api/client';
import { AppButton } from '@/components/AppButton';
import { AppText as Text } from '@/components/AppText';
import { BrandMark } from '@/components/BrandMark';
import { Card } from '@/components/Card';
import { ChoiceChips } from '@/components/ChoiceChips';
import { Screen } from '@/components/Screen';
import { SegmentedControl } from '@/components/SegmentedControl';
import { GroceryComparisonView } from '@/components/GroceryComparisonView';
import { InteracShortcut } from '@/components/InteracShortcut';
import { EmptyState, ErrorState, LoadingState } from '@/components/States';
import { TextField } from '@/components/TextField';
import { useAuth } from '@/state/AuthContext';
import { colors, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import { formatDate, formatDateTime } from '@/utils/dates';
import { formatMoney, parseAmount, suggestSettlements } from '@/utils/money';
import type { Expense, ExpenseSearchResult, GroceryComparison, GroupDetail, Note, RootStackParamList } from '@/types';

type Props = NativeStackScreenProps<RootStackParamList, 'GroupDetail'>;
type Tab = 'overview' | 'expenses' | 'tasks' | 'notes' | 'pay';

export function GroupDetailScreen({ navigation, route }: Props) {
  const { groupId } = route.params;
  const { currencyCode, user } = useAuth();
  const money = useCallback((value: number) => formatMoney(value, currencyCode), [currencyCode]);
  const [detail, setDetail] = useState<GroupDetail | null>(null);
  const [tab, setTab] = useState<Tab>('overview');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const hasLoaded = useRef(false);
  const [noteTitle, setNoteTitle] = useState('');
  const [noteDescription, setNoteDescription] = useState('');
  const [editingNoteId, setEditingNoteId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [comparisons, setComparisons] = useState<Record<number, GroceryComparison>>({});
  const [receiverId, setReceiverId] = useState<number | null>(null);
  const [paymentAmount, setPaymentAmount] = useState('');
  const [requestPayerId, setRequestPayerId] = useState<number | null>(null);
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
      setReceiverId(current => {
        if (current && !next.payment_options.some(option => option.receiver_id === current)) {
          setPaymentAmount('');
          return null;
        }
        return current;
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Try again.';
      setLoadError(message);
      if (hasLoaded.current) {
        Alert.alert('Could not refresh group', message);
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
          <Ionicons name="settings-outline" size={20} color={colors.primary} />
          <Text style={styles.headerButtonText}>Manage</Text>
        </Pressable>
      )
    });
  }, [groupName, navigation, openManage]);

  async function runAction(action: () => Promise<unknown>, title: string) {
    try {
      await action();
      await load();
    } catch (error) {
      Alert.alert(title, error instanceof Error ? error.message : 'Try again.');
    }
  }

  async function addNote() {
    await runAction(async () => {
      await api.addNote(groupId, { title: noteTitle, description: noteDescription });
      setNoteTitle('');
      setNoteDescription('');
    }, 'Could not add note');
  }

  async function recordPayment() {
    if (!receiverId) {
      Alert.alert('Choose a receiver', 'Select the person you are paying.');
      return;
    }
    const amount = parseAmount(paymentAmount);
    if (amount === null || amount <= 0) {
      Alert.alert('Enter an amount', 'Enter a payment amount greater than zero.');
      return;
    }
    const option = detail?.payment_options.find(item => item.receiver_id === receiverId);
    if (option && amount > option.max_amount + 0.005) {
      Alert.alert('Amount too high', `You can record up to ${money(option.max_amount)} for this person right now.`);
      return;
    }
    try {
      await api.recordPayment(groupId, receiverId, amount.toFixed(2));
      setPaymentAmount('');
      setReceiverId(null);
      await load();
      Alert.alert('Payment recorded', `${option?.receiver ?? 'They'} will be asked to confirm it. Your balance updates once they do.`);
    } catch (error) {
      Alert.alert('Could not record payment', error instanceof Error ? error.message : 'Try again.');
    }
  }

  async function openPaymentLink(url: string) {
    // Only the server-built PayPal (https) and UPI links are opened; nothing else.
    if (!/^(https:\/\/paypal\.me\/|upi:\/\/pay\?)/.test(url)) {
      return;
    }
    try {
      await Linking.openURL(url);
    } catch {
      Alert.alert('Could not open payment app', 'Make sure the app for this payment method is installed.');
    }
  }

  function confirmDeleteTask(taskId: number, title: string) {
    Alert.alert('Delete task?', title, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: () => runAction(() => api.deleteTask(taskId), 'Could not delete task') }
    ]);
  }

  function editExpense(expense: Expense) {
    if (!detail) {
      return;
    }
    if (expense.splits.some(split => split.is_settled && split.user_id !== expense.paid_by_id)) {
      Alert.alert('Cannot edit this expense', 'Part of it has already been settled. Delete it and add a corrected expense instead.');
      return;
    }
    navigation.navigate('AddExpense', {
      groupId,
      members: detail.group.members,
      currentUserId: detail.current_user_id,
      categories: detail.expense_categories,
      defaultSplit: detail.default_split,
      expense
    });
  }

  function confirmDeleteExpense(expense: Expense) {
    Alert.alert('Delete expense?', `${expense.description} (${money(expense.amount)}) will be removed and balances recalculated. Transaction history keeps its record.`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: () => runAction(() => api.deleteExpense(expense.id), 'Could not delete expense') }
    ]);
  }

  function confirmDeleteNote(note: Note) {
    Alert.alert('Delete note?', note.title, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: () => runAction(() => api.deleteNote(note.id), 'Could not delete note') }
    ]);
  }

  function beginEditNote(note: Note) {
    setEditingNoteId(note.id);
    setEditTitle(note.title);
    setEditDescription(note.description);
  }

  async function saveNote(noteId: number) {
    await runAction(async () => {
      await api.updateNote(noteId, editTitle, editDescription);
      setEditingNoteId(null);
    }, 'Could not update note');
  }

  async function compareNote(noteId: number) {
    try {
      const comparison = await api.compareGroceries(noteId);
      setComparisons(current => ({ ...current, [noteId]: comparison }));
    } catch (error) {
      Alert.alert('Could not compare groceries', error instanceof Error ? error.message : 'Try again.');
    }
  }

  function clearRecentExpenses() {
    Alert.alert('Clear recent expenses?', 'Balances from active expenses will be cleared, but transaction history stays available.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Clear', style: 'destructive', onPress: () => runAction(() => api.clearExpenses(groupId), 'Could not clear expenses') }
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
      Alert.alert('Could not export activity', error instanceof Error ? error.message : 'Try again.');
    } finally {
      setExportingCsv(false);
    }
  }

  const settlements = useMemo(() => suggestSettlements(detail?.balances ?? []), [detail?.balances]);

  if (loading && !detail) {
    return <LoadingState label="Loading group..." />;
  }
  if (!detail) {
    return <ErrorState message={loadError || 'Could not load this group.'} onRetry={() => { setLoading(true); load(); }} />;
  }

  function payFromSuggestion(receiver: number, amount: number) {
    const option = detail?.payment_options.find(item => item.receiver_id === receiver);
    setReceiverId(receiver);
    setPaymentAmount(Math.min(amount, option?.max_amount ?? amount).toFixed(2));
    setTab('pay');
  }

  const settleUpCard = (
    <Card>
      <Text style={styles.cardLabel}>Settle up</Text>
      {settlements.length ? settlements.map(item => {
        const mine = item.fromId === detail.current_user_id;
        const canPay = mine && detail.payment_options.some(option => option.receiver_id === item.toId);
        return (
          <View key={`${item.fromId}-${item.toId}`} style={styles.settleRow}>
            <View style={styles.headerText}>
              <Text style={styles.itemTitle}>{mine ? 'You' : item.from} pay{mine ? '' : 's'} {item.toId === detail.current_user_id ? 'you' : item.to}</Text>
              <Text style={styles.amountNeutral}>{money(item.amount)}</Text>
            </View>
            {canPay ? <AppButton icon="cash-outline" variant="outline" onPress={() => payFromSuggestion(item.toId, item.amount)}>Settle</AppButton> : null}
          </View>
        );
      }) : <Text style={styles.muted}>Everyone is settled up.</Text>}
      {settlements.length ? <Text style={styles.hint}>Fewest payments needed to clear every balance.</Text> : null}
    </Card>
  );

  const outstanding = detail.summaries.filter(item => !item.is_settled);
  const isAdmin = detail.group.admin_id === detail.current_user_id;
  const navigateToExpense = () => navigation.navigate('AddExpense', {
    groupId,
    members: detail.group.members,
    currentUserId: detail.current_user_id,
    categories: detail.expense_categories,
    defaultSplit: detail.default_split
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
          <AppButton icon="add-outline" variant="outline" onPress={navigateToExpense}>Expense</AppButton>
          <AppButton icon="checkbox-outline" variant="outline" onPress={() => navigation.navigate('AddTask', { groupId, members: detail.group.members })}>Task</AppButton>
          <AppButton icon="document-text-outline" variant="outline" onPress={() => setTab('notes')}>Note</AppButton>
        </View>
        <View style={styles.actionRow}>
          <AppButton icon="analytics-outline" variant="ghost" style={styles.actionButton} onPress={() => navigation.navigate('Insights', {
            groupId,
            groupName: detail.group.name,
            members: detail.group.members,
            categories: detail.expense_categories
          })}>Insights</AppButton>
          <AppButton icon="calendar-outline" variant="ghost" style={styles.actionButton} onPress={() => navigation.navigate('TaskCalendar', { groupId, groupName: detail.group.name })}>Calendar</AppButton>
          <AppButton icon="settings-outline" variant="ghost" style={styles.actionButton} onPress={openManage}>Manage</AppButton>
        </View>
      </Card>

      <SegmentedControl<Tab>
        value={tab}
        onChange={setTab}
        options={[
          { label: 'Overview', value: 'overview' },
          { label: 'Expenses', value: 'expenses' },
          { label: 'Tasks', value: 'tasks' },
          { label: 'Notes', value: 'notes' },
          { label: 'Pay', value: 'pay' }
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
              <Text style={styles.muted}>Paid {money(balance.paid)} - Owes {money(balance.owes)}</Text>
            </Card>
          ))}
          {settleUpCard}
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
              {isAdmin ? 'Manage Group' : 'Group Info & Leave'}
            </AppButton>
          </Card>
        </>
      ) : null}

      {tab === 'expenses' ? (
        <>
          <View style={styles.actionRow}>
            <AppButton icon="add-outline" style={styles.actionButton} onPress={navigateToExpense}>Add Expense</AppButton>
            <AppButton icon="share-outline" variant="outline" style={styles.actionButton} loading={exportingCsv} onPress={shareActivityCsv}>Share Activity CSV</AppButton>
            <AppButton icon="trash-outline" variant="danger" style={styles.actionButton} onPress={clearRecentExpenses}>Clear Recent</AppButton>
          </View>

          <Card>
            <Text style={styles.cardLabel}>Search All Expenses</Text>
            <TextField
              label="Search"
              placeholder="Search by description"
              value={expenseSearch}
              onChangeText={setExpenseSearch}
              onSubmitEditing={runExpenseSearch}
              returnKeyType="search"
            />
            <View style={styles.actionRow}>
              <AppButton icon="search-outline" style={styles.actionButton} loading={searching} onPress={runExpenseSearch}>Search</AppButton>
              {searchResults !== null ? (
                <AppButton icon="close-outline" variant="outline" style={styles.actionButton} onPress={clearExpenseSearch}>Clear search</AppButton>
              ) : null}
            </View>
          </Card>

          {searchResults !== null ? (
            <>
              <Text style={styles.sectionTitle}>Search Results</Text>
              {searchError ? (
                <ErrorState message={searchError} onRetry={runExpenseSearch} />
              ) : searchResults.length ? searchResults.map(result => (
                <Card key={result.id}>
                  <View style={styles.rowBetween}>
                    <View style={styles.headerText}>
                      <Text style={styles.itemTitle}>{result.description}</Text>
                      <View style={styles.categoryPill}><Text style={styles.category}>{result.category}</Text></View>
                    </View>
                    <Text style={styles.amountNeutral}>{money(result.amount)}</Text>
                  </View>
                  <Text style={styles.muted}>Paid by {result.paid_by}{result.date ? ` - ${formatDate(result.date)}` : ''}</Text>
                </Card>
              )) : <EmptyState label="No expenses match your search." />}
            </>
          ) : (
            detail.expenses.length ? detail.expenses.map(expense => (
              <Card key={expense.id}>
                <View style={styles.rowBetween}>
                  <View style={styles.headerText}>
                    <Text style={styles.itemTitle}>{expense.description}</Text>
                    <View style={styles.categoryPill}><Text style={styles.category}>{expense.category}</Text></View>
                  </View>
                  <Text style={styles.amountNeutral}>{money(expense.amount)}</Text>
                </View>
                <Text style={styles.muted}>Paid by {expense.paid_by}{expense.date ? ` - ${formatDate(expense.date)}` : ''}</Text>
                {expense.splits.map(split => (
                  <Text key={split.id} style={styles.memberLine}>
                    {split.user}: {money(split.amount)} {split.is_settled ? 'Settled' : 'Outstanding'}
                  </Text>
                ))}
                {expense.receipt_url ? <AppButton icon="receipt-outline" variant="ghost" onPress={() => Linking.openURL(api.resolveUrl(expense.receipt_url || ''))}>Open Receipt</AppButton> : null}
                {expense.paid_by_id === detail.current_user_id || isAdmin ? (
                  <View style={styles.iconActionRow}>
                    <Pressable accessibilityLabel={`Edit ${expense.description}`} onPress={() => editExpense(expense)} style={styles.iconButton}><Ionicons name="pencil-outline" size={20} color={colors.primaryDark} /></Pressable>
                    <Pressable accessibilityLabel={`Delete ${expense.description}`} onPress={() => confirmDeleteExpense(expense)} style={styles.iconButton}><Ionicons name="trash-outline" size={20} color={colors.danger} /></Pressable>
                  </View>
                ) : null}
              </Card>
            )) : <EmptyState label="No active expenses. Transaction history remains available in Insights." />
          )}
        </>
      ) : null}

      {tab === 'tasks' ? (
        <>
          <View style={styles.actionRow}>
            <AppButton icon="add-outline" style={styles.actionButton} onPress={() => navigation.navigate('AddTask', { groupId, members: detail.group.members })}>Add Task</AppButton>
            <AppButton icon="calendar-outline" variant="outline" style={styles.actionButton} onPress={() => navigation.navigate('TaskCalendar', { groupId, groupName: detail.group.name })}>Calendar</AppButton>
          </View>
          {detail.tasks.length ? detail.tasks.map(task => (
            <Card key={task.id}>
              <View style={styles.rowBetween}>
                <Pressable onPress={() => runAction(() => api.toggleTask(task.id), 'Could not update task')} style={styles.taskMain}>
                  <Ionicons name={task.is_completed ? 'checkbox' : 'square-outline'} size={22} color={colors.primary} />
                  <View style={styles.headerText}>
                    <Text style={[styles.itemTitle, task.is_completed && styles.completed]}>{task.title}</Text>
                    <Text style={styles.muted}>{formatDateTime(task.due_date)}</Text>
                  </View>
                </Pressable>
                {task.can_delete ? (
                  <Pressable accessibilityLabel={`Delete ${task.title}`} onPress={() => confirmDeleteTask(task.id, task.title)} style={styles.iconButton}>
                    <Ionicons name="trash-outline" size={20} color={colors.danger} />
                  </Pressable>
                ) : null}
              </View>
              {task.description ? <Text style={styles.muted}>{task.description}</Text> : null}
              <Text style={styles.memberLine}>{task.priority.toUpperCase()}{task.assigned_to ? ` - Assigned to ${task.assigned_to}` : ' - Anyone'}{task.recurrence !== 'none' ? ` - Repeats ${task.recurrence}` : ''}</Text>
              {task.reminder_time ? <Text style={styles.memberLine}>Reminder: {formatDateTime(task.reminder_time)}</Text> : null}
            </Card>
          )) : (
            <Card>
              <EmptyState label="No tasks yet. Add chores, bills or reminders for this group." />
              <AppButton icon="add-outline" onPress={() => navigation.navigate('AddTask', { groupId, members: detail.group.members })}>Add the First Task</AppButton>
            </Card>
          )}
        </>
      ) : null}

      {tab === 'notes' ? (
        <>
          <Card>
            <Text style={styles.cardLabel}>New Note</Text>
            <TextField label="Title" value={noteTitle} onChangeText={setNoteTitle} />
            <TextField label="Description" value={noteDescription} onChangeText={setNoteDescription} multiline />
            <AppButton icon="add-outline" onPress={addNote}>Add Note</AppButton>
          </Card>
          {detail.notes.length ? detail.notes.map(note => (
            <Card key={note.id}>
              {editingNoteId === note.id ? (
                <>
                  <TextField label="Title" value={editTitle} onChangeText={setEditTitle} />
                  <TextField label="Description" value={editDescription} onChangeText={setEditDescription} multiline />
                  <View style={styles.actionRow}>
                    <AppButton icon="save-outline" style={styles.actionButton} onPress={() => saveNote(note.id)}>Save</AppButton>
                    <AppButton icon="close-outline" variant="outline" style={styles.actionButton} onPress={() => setEditingNoteId(null)}>Cancel</AppButton>
                  </View>
                </>
              ) : (
                <>
                  <Pressable onPress={() => runAction(() => api.toggleNote(note.id), 'Could not update note')} style={styles.rowBetween}>
                    <Text style={[styles.itemTitle, note.is_completed && styles.completed]}>{note.title}</Text>
                    <Ionicons name={note.is_completed ? 'checkmark-circle' : 'ellipse-outline'} size={22} color={colors.primary} />
                  </Pressable>
                  {note.description ? <Text style={styles.muted}>{note.description}</Text> : null}
                  <Text style={styles.memberLine}>By {note.created_by}</Text>
                  <View style={styles.iconActionRow}>
                    {note.can_compare_prices !== false ? (
                      <Pressable accessibilityLabel={`Compare ${note.title} grocery prices`} onPress={() => compareNote(note.id)} style={styles.iconButton}><Ionicons name="cart-outline" size={20} color={colors.primaryDark} /></Pressable>
                    ) : null}
                    <Pressable accessibilityLabel={`Edit ${note.title}`} onPress={() => beginEditNote(note)} style={styles.iconButton}><Ionicons name="pencil-outline" size={20} color={colors.primaryDark} /></Pressable>
                    {note.can_delete ? (
                      <Pressable accessibilityLabel={`Delete ${note.title}`} onPress={() => confirmDeleteNote(note)} style={styles.iconButton}><Ionicons name="trash-outline" size={20} color={colors.danger} /></Pressable>
                    ) : null}
                  </View>
                </>
              )}
              {comparisons[note.id] ? <GroceryComparisonView comparison={comparisons[note.id]} /> : null}
            </Card>
          )) : <EmptyState label="No notes yet." />}
        </>
      ) : null}

      {tab === 'pay' ? (
        <>
          {settleUpCard}
          <Text style={styles.sectionTitle}>Outstanding Splits</Text>
          {outstanding.length ? outstanding.map(item => (
            <Card key={item.split_id}>
              <View style={styles.rowBetween}>
                <Text style={styles.itemTitle}>{item.owed_by} owes {item.payer}</Text>
                <Text style={styles.amountNeutral}>{money(item.amount_owed)}</Text>
              </View>
              <Text style={styles.muted}>{item.expense}</Text>
              {/* Only the person who is owed can confirm a split was paid. */}
              {item.payer_id === user?.id ? (
                <AppButton icon="checkmark-outline" variant="outline" onPress={() => runAction(() => api.settleSplit(item.split_id), 'Could not settle split')}>Mark Settled</AppButton>
              ) : null}
            </Card>
          )) : <EmptyState label="No outstanding balances." />}
          {detail.payments.some(payment => payment.can_confirm) ? (
            <>
              <Text style={styles.sectionTitle}>Waiting for You to Confirm</Text>
              {detail.payments.filter(payment => payment.can_confirm).map(payment => (
                <Card key={`confirm-${payment.id}`}>
                  <Text style={styles.itemTitle}>{payment.payer} says they paid you {money(payment.amount)}</Text>
                  <Text style={styles.muted}>Check that the money arrived before confirming. Balances only change once you do.</Text>
                  <AppButton icon="checkmark-circle-outline" onPress={() => runAction(() => api.confirmPayment(payment.id), 'Could not confirm payment')}>Confirm Received</AppButton>
                  <AppButton icon="close-circle-outline" variant="outline" onPress={() => runAction(() => api.declinePayment(payment.id), 'Could not decline payment')}>Not Received</AppButton>
                </Card>
              ))}
            </>
          ) : null}
          <Card>
            <Text style={styles.cardLabel}>Pay Someone</Text>
            {detail.payment_options.length ? (
              <>
                <ChoiceChips<number>
                  label="Pay"
                  value={receiverId}
                  onChange={value => {
                    setReceiverId(value);
                    const option = detail.payment_options.find(item => item.receiver_id === value);
                    setPaymentAmount(option ? option.max_amount.toFixed(2) : '');
                  }}
                  options={detail.payment_options.map(option => ({ label: option.receiver, value: option.receiver_id, detail: `Owe ${money(option.owed)}` }))}
                />
                {(() => {
                  const option = detail.payment_options.find(item => item.receiver_id === receiverId);
                  if (!option) {
                    return null;
                  }
                  return (
                    <>
                      {option.pending_amount > 0 ? (
                        <Text style={styles.muted}>{money(option.pending_amount)} is already waiting for {option.receiver} to confirm.</Text>
                      ) : null}
                      <Text style={styles.hint}>1. Send the money with one of {option.receiver}'s payment methods. Splitmate never handles it.</Text>
                      {option.payment_methods.length ? option.payment_methods.map(method => (
                        method.type === 'interac' ? (
                          <InteracShortcut
                            key={method.type}
                            mode="pay"
                            person={option.receiver}
                            email={method.handle}
                            amountText={(parseAmount(paymentAmount) ?? option.max_amount).toFixed(2)}
                            amountLabel={money(parseAmount(paymentAmount) ?? option.max_amount)}
                            note={`Splitmate - ${detail.group.name}`}
                          />
                        ) : method.url ? (
                          <AppButton key={method.type} icon="open-outline" variant="outline" onPress={() => openPaymentLink(method.url as string)}>
                            {`Pay with ${method.label} (${method.handle})`}
                          </AppButton>
                        ) : null
                      )) : (
                        <Text style={styles.muted}>{option.receiver} hasn't added Interac, PayPal or UPI details yet. Pay them however you agreed.</Text>
                      )}
                      <Text style={styles.hint}>2. Then record it, and {option.receiver} confirms it arrived.</Text>
                    </>
                  );
                })()}
                <TextField label="Amount" value={paymentAmount} onChangeText={setPaymentAmount} keyboardType="decimal-pad" />
                <AppButton icon="checkmark-circle-outline" onPress={recordPayment}>I've Paid - Ask Them to Confirm</AppButton>
              </>
            ) : <Text style={styles.muted}>You do not currently owe another member in this group.</Text>}
          </Card>
          {detail.money_requests.length ? (
            <Card>
              <Text style={styles.cardLabel}>Request Money</Text>
              <Text style={styles.muted}>Ask someone who owes you to pay, with an Interac request from your own bank.</Text>
              <ChoiceChips<number>
                label="Request from"
                value={requestPayerId}
                onChange={setRequestPayerId}
                options={detail.money_requests.map(item => ({ label: item.payer, value: item.payer_id, detail: money(item.amount) }))}
              />
              {(() => {
                const request = detail.money_requests.find(item => item.payer_id === requestPayerId);
                return request ? (
                  <InteracShortcut
                    mode="request"
                    person={request.payer}
                    email={request.email}
                    amountText={request.amount.toFixed(2)}
                    amountLabel={money(request.amount)}
                    note={`Splitmate - ${detail.group.name}`}
                  />
                ) : null;
              })()}
            </Card>
          ) : null}
          <Text style={styles.sectionTitle}>Payment History</Text>
          {detail.payments.length ? detail.payments.map(payment => (
            <Card key={payment.id}>
              <Text style={styles.itemTitle}>{payment.payer} paid {payment.receiver}</Text>
              <Text style={styles.muted}>
                {money(payment.amount)} - {payment.method === 'stripe' ? 'Stripe' : 'Manual'} - {payment.status_label}
                {payment.reward_points_awarded ? ` - +${payment.reward_points_awarded} pts` : ''}
              </Text>
              <Text style={styles.memberLine}>{formatDateTime(payment.date)}</Text>
              {payment.can_decline && !payment.can_confirm ? (
                <AppButton icon="close-outline" variant="ghost" onPress={() => runAction(() => api.declinePayment(payment.id), 'Could not cancel payment')}>Cancel</AppButton>
              ) : null}
            </Card>
          )) : <EmptyState label="No payments recorded." />}
        </>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
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
  completed: {
    color: colors.muted,
    textDecorationLine: 'line-through'
  },
  amountNeutral: {
    ...typography.bodyStrong,
    color: colors.ink
  },
  categoryPill: {
    alignSelf: 'flex-start',
    marginTop: spacing.xs,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt
  },
  category: {
    ...typography.caption,
    color: colors.secondary
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
    color: colors.secondary,
    marginTop: spacing.xs
  },
  cardLabel: {
    ...typography.label,
    color: colors.ink,
    marginBottom: spacing.sm
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
    color: colors.white
  },
  adminPill: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    borderRadius: radius.pill,
    backgroundColor: colors.primarySoft
  },
  adminLabel: {
    ...typography.caption,
    color: colors.primaryDark
  },
  settleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.md,
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border
  },
  hint: {
    ...typography.caption,
    color: colors.muted,
    marginTop: spacing.sm
  },
  taskMain: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm
  }
});
