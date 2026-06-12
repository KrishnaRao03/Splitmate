import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useMemo, useState } from 'react';
import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { api } from '@/api/client';
import { AppButton } from '@/components/AppButton';
import { Card } from '@/components/Card';
import { Screen } from '@/components/Screen';
import { SegmentedControl } from '@/components/SegmentedControl';
import { TextField } from '@/components/TextField';
import { colors, spacing } from '@/theme/colors';
import type { GroupMember, RootStackParamList } from '@/types';

type Props = NativeStackScreenProps<RootStackParamList, 'AddExpense'>;
type SplitType = 'equal' | 'selected' | 'exact' | 'percentage';

export function AddExpenseScreen({ navigation, route }: Props) {
  const { groupId, members } = route.params;
  const [description, setDescription] = useState('');
  const [amount, setAmount] = useState('');
  const [splitType, setSplitType] = useState<SplitType>('equal');
  const [selectedIds, setSelectedIds] = useState(() => new Set(members.map(member => member.id)));
  const [values, setValues] = useState<Record<number, string>>({});
  const [saving, setSaving] = useState(false);

  const activeMembers = useMemo(() => {
    if (splitType === 'selected') {
      return members.filter(member => selectedIds.has(member.id));
    }
    return members;
  }, [members, selectedIds, splitType]);

  function toggleMember(member: GroupMember) {
    const next = new Set(selectedIds);
    if (next.has(member.id)) {
      next.delete(member.id);
    } else {
      next.add(member.id);
    }
    setSelectedIds(next);
  }

  async function save() {
    if (!description.trim() || !amount.trim()) {
      Alert.alert('Missing details', 'Description and amount are required.');
      return;
    }
    if (splitType === 'selected' && !activeMembers.length) {
      Alert.alert('Choose people', 'Select at least one person to split with.');
      return;
    }

    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        description,
        amount,
        split_type: splitType
      };
      if (splitType === 'selected') {
        payload.split_user_ids = activeMembers.map(member => member.id);
      }
      if (splitType === 'exact') {
        payload.exact_amounts = Object.fromEntries(members.map(member => [member.id, values[member.id] || '0']));
      }
      if (splitType === 'percentage') {
        payload.percentages = Object.fromEntries(members.map(member => [member.id, values[member.id] || '0']));
      }

      await api.addExpense(groupId, payload);
      navigation.goBack();
    } catch (error) {
      Alert.alert('Could not add expense', error instanceof Error ? error.message : 'Try again.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <Screen>
      <Card>
        <TextField label="Description" value={description} onChangeText={setDescription} placeholder="Dinner, rent, groceries" />
        <TextField label="Amount" value={amount} onChangeText={setAmount} keyboardType="decimal-pad" placeholder="0.00" />
        <SegmentedControl<SplitType>
          value={splitType}
          onChange={setSplitType}
          options={[
            { label: 'Equal', value: 'equal' },
            { label: 'Selected', value: 'selected' },
            { label: 'Exact', value: 'exact' },
            { label: 'Percent', value: 'percentage' }
          ]}
        />
      </Card>

      {splitType === 'selected' ? (
        <Card>
          <Text style={styles.title}>Split With</Text>
          {members.map(member => (
            <Pressable key={member.id} onPress={() => toggleMember(member)} style={styles.memberRow}>
              <Ionicons name={selectedIds.has(member.id) ? 'checkbox' : 'square-outline'} size={22} color={colors.primary} />
              <Text style={styles.memberName}>{member.name}</Text>
            </Pressable>
          ))}
        </Card>
      ) : null}

      {(splitType === 'exact' || splitType === 'percentage') ? (
        <Card>
          <Text style={styles.title}>{splitType === 'exact' ? 'Exact Amounts' : 'Percentages'}</Text>
          {members.map(member => (
            <TextField
              key={member.id}
              label={member.name}
              value={values[member.id] || ''}
              onChangeText={text => setValues(current => ({ ...current, [member.id]: text }))}
              keyboardType="decimal-pad"
              placeholder={splitType === 'exact' ? '0.00' : '0'}
            />
          ))}
        </Card>
      ) : null}

      <Card>
        <Text style={styles.helper}>
          {splitType === 'equal'
            ? `The amount will be split between all ${members.length} group members.`
            : splitType === 'selected'
              ? `The amount will be split between ${activeMembers.length} selected people.`
              : splitType === 'exact'
                ? 'Exact amounts must add up to the total expense.'
                : 'Percentages must add up to 100.'}
        </Text>
        <AppButton loading={saving} onPress={save}>Add Expense</AppButton>
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  title: {
    color: colors.ink,
    fontSize: 17,
    fontWeight: '900',
    marginBottom: spacing.sm
  },
  memberRow: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm
  },
  memberName: {
    color: colors.text,
    fontWeight: '800'
  },
  helper: {
    color: colors.muted,
    fontWeight: '700',
    marginBottom: spacing.md
  }
});
