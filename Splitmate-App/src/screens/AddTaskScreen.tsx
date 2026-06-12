import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useState } from 'react';
import { Alert, StyleSheet, Text } from 'react-native';

import { api } from '@/api/client';
import { AppButton } from '@/components/AppButton';
import { Card } from '@/components/Card';
import { Screen } from '@/components/Screen';
import { TextField } from '@/components/TextField';
import { colors, spacing } from '@/theme/colors';
import type { RootStackParamList } from '@/types';

type Props = NativeStackScreenProps<RootStackParamList, 'AddTask'>;

function toIsoLocal(value: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    return '';
  }
  const date = new Date(trimmed);
  return Number.isNaN(date.getTime()) ? trimmed : date.toISOString();
}

export function AddTaskScreen({ navigation, route }: Props) {
  const { groupId } = route.params;
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [reminderTime, setReminderTime] = useState('');
  const [assignedToId, setAssignedToId] = useState('');
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      await api.addTask(groupId, {
        title,
        description,
        due_date: toIsoLocal(dueDate),
        reminder_time: reminderTime ? toIsoLocal(reminderTime) : null,
        assigned_to_id: assignedToId ? Number(assignedToId) : null
      });
      navigation.goBack();
    } catch (error) {
      Alert.alert('Could not add task', error instanceof Error ? error.message : 'Try again.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <Screen>
      <Card>
        <TextField label="Title" value={title} onChangeText={setTitle} placeholder="Buy supplies" />
        <TextField label="Description" value={description} onChangeText={setDescription} multiline />
        <TextField label="Due date" value={dueDate} onChangeText={setDueDate} placeholder="2026-06-15 18:00" />
        <TextField label="Reminder time" value={reminderTime} onChangeText={setReminderTime} placeholder="2026-06-15 17:30" />
        <TextField label="Assign to member ID" value={assignedToId} onChangeText={setAssignedToId} keyboardType="number-pad" />
        <Text style={styles.help}>Dates accept formats your phone can parse, like 2026-06-15 18:00.</Text>
        <AppButton loading={saving} onPress={save}>Add Task</AppButton>
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  help: {
    color: colors.muted,
    fontWeight: '700',
    marginVertical: spacing.sm
  }
});
