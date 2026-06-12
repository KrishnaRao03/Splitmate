import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useFocusEffect } from '@react-navigation/native';
import { useCallback, useState } from 'react';
import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { api } from '@/api/client';
import { AppButton } from '@/components/AppButton';
import { Card } from '@/components/Card';
import { Screen } from '@/components/Screen';
import { SegmentedControl } from '@/components/SegmentedControl';
import { EmptyState, LoadingState } from '@/components/States';
import { TextField } from '@/components/TextField';
import { colors, spacing } from '@/theme/colors';
import type { GroupDetail, RootStackParamList } from '@/types';

type Props = NativeStackScreenProps<RootStackParamList, 'GroupDetail'>;
type Tab = 'overview' | 'expenses' | 'tasks' | 'notes' | 'pay';

export function GroupDetailScreen({ navigation, route }: Props) {
  const { groupId } = route.params;
  const [detail, setDetail] = useState<GroupDetail | null>(null);
  const [tab, setTab] = useState<Tab>('overview');
  const [loading, setLoading] = useState(true);
  const [memberEmail, setMemberEmail] = useState('');
  const [noteTitle, setNoteTitle] = useState('');
  const [noteDescription, setNoteDescription] = useState('');
  const [receiverId, setReceiverId] = useState('');
  const [paymentAmount, setPaymentAmount] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setDetail(await api.groupDetail(groupId));
    } catch (error) {
      Alert.alert('Could not load group', error instanceof Error ? error.message : 'Try again.');
    } finally {
      setLoading(false);
    }
  }, [groupId]);

  useFocusEffect(useCallback(() => {
    load();
  }, [load]));

  async function addMember() {
    try {
      await api.addMember(groupId, memberEmail);
      setMemberEmail('');
      await load();
    } catch (error) {
      Alert.alert('Could not add member', error instanceof Error ? error.message : 'Try again.');
    }
  }

  async function addNote() {
    try {
      await api.addNote(groupId, { title: noteTitle, description: noteDescription });
      setNoteTitle('');
      setNoteDescription('');
      await load();
    } catch (error) {
      Alert.alert('Could not add note', error instanceof Error ? error.message : 'Try again.');
    }
  }

  async function recordPayment() {
    try {
      await api.recordPayment(groupId, Number(receiverId), paymentAmount);
      setPaymentAmount('');
      await load();
    } catch (error) {
      Alert.alert('Could not record payment', error instanceof Error ? error.message : 'Try again.');
    }
  }

  async function settleSplit(splitId: number) {
    try {
      await api.settleSplit(splitId);
      await load();
    } catch (error) {
      Alert.alert('Could not settle split', error instanceof Error ? error.message : 'Try again.');
    }
  }

  async function toggleTask(taskId: number) {
    await api.toggleTask(taskId);
    await load();
  }

  async function toggleNote(noteId: number) {
    await api.toggleNote(noteId);
    await load();
  }

  if (loading || !detail) {
    return <LoadingState label="Loading group..." />;
  }

  const outstanding = detail.summaries.filter(item => !item.is_settled);

  return (
    <Screen>
      <Card>
        <View style={styles.headerRow}>
          <View>
            <Text style={styles.title}>{detail.group.name}</Text>
            <Text style={styles.muted}>{detail.group.members.length} members</Text>
          </View>
          <AppButton variant="outline" onPress={() => navigation.navigate('AddExpense', { groupId, members: detail.group.members })}>
            Expense
          </AppButton>
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
                  {balance.net >= 0 ? '+' : ''}{balance.net.toFixed(2)}
                </Text>
              </View>
              <Text style={styles.muted}>Paid {balance.paid.toFixed(2)} • Owes {balance.owes.toFixed(2)}</Text>
            </Card>
          ))}
          <Text style={styles.sectionTitle}>Members</Text>
          <Card>
            {detail.group.members.map(member => (
              <Text key={member.id} style={styles.memberLine}>{member.name} • {member.email}</Text>
            ))}
            <View style={styles.formGap}>
              <TextField label="Add member by email" value={memberEmail} onChangeText={setMemberEmail} keyboardType="email-address" autoCapitalize="none" />
              <AppButton variant="outline" onPress={addMember}>Add Member</AppButton>
            </View>
          </Card>
        </>
      ) : null}

      {tab === 'expenses' ? (
        <>
          <AppButton onPress={() => navigation.navigate('AddExpense', { groupId, members: detail.group.members })}>Add Expense</AppButton>
          {detail.expenses.length ? detail.expenses.map(expense => (
            <Card key={expense.id}>
              <View style={styles.rowBetween}>
                <Text style={styles.itemTitle}>{expense.description}</Text>
                <Text style={styles.amount}>{expense.amount.toFixed(2)}</Text>
              </View>
              <Text style={styles.muted}>Paid by {expense.paid_by}</Text>
              {expense.splits.map(split => (
                <Text key={split.id} style={styles.memberLine}>
                  {split.user}: {split.amount.toFixed(2)} {split.is_settled ? 'Settled' : 'Outstanding'}
                </Text>
              ))}
            </Card>
          )) : <EmptyState label="No expenses yet." />}
        </>
      ) : null}

      {tab === 'tasks' ? (
        <>
          <AppButton onPress={() => navigation.navigate('AddTask', { groupId, members: detail.group.members })}>Add Task</AppButton>
          {detail.tasks.length ? detail.tasks.map(task => (
            <Card key={task.id}>
              <Pressable onPress={() => toggleTask(task.id)} style={styles.rowBetween}>
                <View style={styles.row}>
                  <Ionicons name={task.is_completed ? 'checkbox' : 'square-outline'} size={22} color={colors.primary} />
                  <Text style={styles.itemTitle}>{task.title}</Text>
                </View>
                <Text style={styles.muted}>{task.due_date ? new Date(task.due_date).toLocaleDateString() : ''}</Text>
              </Pressable>
              {task.description ? <Text style={styles.muted}>{task.description}</Text> : null}
              {task.reminder_time ? <Text style={styles.memberLine}>Reminder: {new Date(task.reminder_time).toLocaleString()}</Text> : null}
            </Card>
          )) : <EmptyState label="No tasks yet." />}
        </>
      ) : null}

      {tab === 'notes' ? (
        <>
          <Card>
            <Text style={styles.cardLabel}>New Note</Text>
            <TextField label="Title" value={noteTitle} onChangeText={setNoteTitle} />
            <TextField label="Description" value={noteDescription} onChangeText={setNoteDescription} multiline />
            <AppButton onPress={addNote}>Add Note</AppButton>
          </Card>
          {detail.notes.length ? detail.notes.map(note => (
            <Card key={note.id}>
              <Pressable onPress={() => toggleNote(note.id)} style={styles.rowBetween}>
                <Text style={styles.itemTitle}>{note.title}</Text>
                <Ionicons name={note.is_completed ? 'checkmark-circle' : 'ellipse-outline'} size={22} color={colors.primary} />
              </Pressable>
              {note.description ? <Text style={styles.muted}>{note.description}</Text> : null}
              <Text style={styles.memberLine}>By {note.created_by}</Text>
            </Card>
          )) : <EmptyState label="No notes yet." />}
        </>
      ) : null}

      {tab === 'pay' ? (
        <>
          <Text style={styles.sectionTitle}>Outstanding</Text>
          {outstanding.length ? outstanding.map(item => (
            <Card key={item.split_id}>
              <View style={styles.rowBetween}>
                <Text style={styles.itemTitle}>{item.owed_by} owes {item.payer}</Text>
                <Text style={styles.amount}>{item.amount_owed.toFixed(2)}</Text>
              </View>
              <Text style={styles.muted}>{item.expense}</Text>
              <AppButton variant="outline" onPress={() => settleSplit(item.split_id)}>Mark Settled</AppButton>
            </Card>
          )) : <EmptyState label="No outstanding balances." />}
          <Card>
            <Text style={styles.cardLabel}>Record Payment</Text>
            <TextField label="Receiver ID" value={receiverId} onChangeText={setReceiverId} keyboardType="number-pad" placeholder="Member ID from list" />
            <TextField label="Amount" value={paymentAmount} onChangeText={setPaymentAmount} keyboardType="decimal-pad" />
            <AppButton onPress={recordPayment}>Record Payment</AppButton>
          </Card>
          {detail.payments.map(payment => (
            <Card key={payment.id}>
              <Text style={styles.itemTitle}>{payment.payer} paid {payment.receiver}</Text>
              <Text style={styles.muted}>{payment.amount.toFixed(2)} • {payment.status}</Text>
            </Card>
          ))}
        </>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: spacing.md,
    alignItems: 'center'
  },
  title: {
    color: colors.ink,
    fontSize: 26,
    fontWeight: '900'
  },
  sectionTitle: {
    color: colors.ink,
    fontSize: 18,
    fontWeight: '900'
  },
  muted: {
    color: colors.muted,
    fontWeight: '700'
  },
  rowBetween: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: spacing.md
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    flex: 1
  },
  itemTitle: {
    color: colors.ink,
    fontSize: 16,
    fontWeight: '900'
  },
  amount: {
    color: colors.primary,
    fontWeight: '900'
  },
  net: {
    fontWeight: '900'
  },
  positive: {
    color: colors.success
  },
  negative: {
    color: colors.danger
  },
  memberLine: {
    color: colors.text,
    fontWeight: '700',
    marginTop: 6
  },
  formGap: {
    gap: spacing.sm,
    marginTop: spacing.md
  },
  cardLabel: {
    color: colors.ink,
    fontWeight: '900',
    marginBottom: spacing.sm
  }
});
