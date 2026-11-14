import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useEffect, useMemo, useState } from 'react';
import { StyleSheet } from 'react-native';

import { api } from '@/api/client';
import { AppButton } from '@/components/AppButton';
import { AppText as Text } from '@/components/AppText';
import { Card } from '@/components/Card';
import { ChoiceChips } from '@/components/ChoiceChips';
import { DateTimeField } from '@/components/DateTimeField';
import { Screen } from '@/components/Screen';
import { LoadingState } from '@/components/States';
import { TextField } from '@/components/TextField';
import { colors, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import { notify } from '@/state/UndoToast';
import type { Group, GroupMember, RootStackParamList, Task } from '@/types';

type Props = NativeStackScreenProps<RootStackParamList, 'AddTask'>;
type ReminderChoice = 'none' | 'due' | 'hour' | 'day' | 'custom';
const ANYONE = 0;

/** Tomorrow at 9:00, a sensible default due time. */
function defaultDue() {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  date.setHours(9, 0, 0, 0);
  return date;
}

export function AddTaskScreen({ navigation, route }: Props) {
  // Opened from a group, the group is fixed; opened from the Tasks tab, the user picks one.
  const fixedGroupId = route.params?.groupId ?? null;
  const [groups, setGroups] = useState<Group[] | null>(null);
  const [groupId, setGroupId] = useState<number | null>(fixedGroupId);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [due, setDue] = useState<Date | null>(defaultDue());
  const [reminderChoice, setReminderChoice] = useState<ReminderChoice>('none');
  const [customReminder, setCustomReminder] = useState<Date | null>(null);
  const [priority, setPriority] = useState<Task['priority']>('medium');
  const [recurrence, setRecurrence] = useState<Task['recurrence']>('none');
  const [assignedToId, setAssignedToId] = useState<number>(ANYONE);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (fixedGroupId) {
      return;
    }
    api.groups()
      .then(list => {
        setGroups(list);
        if (list.length === 1) {
          setGroupId(list[0].id);
        }
      })
      .catch(error => notify('Could not load your groups', error instanceof Error ? error.message : 'Try again.'));
  }, [fixedGroupId]);

  const members: GroupMember[] = useMemo(() => {
    if (fixedGroupId) {
      return route.params?.members ?? [];
    }
    return groups?.find(group => group.id === groupId)?.members ?? [];
  }, [fixedGroupId, groupId, groups, route.params?.members]);

  const reminder: Date | null = useMemo(() => {
    if (!due) {
      return null;
    }
    switch (reminderChoice) {
      case 'due':
        return due;
      case 'hour':
        return new Date(due.getTime() - 60 * 60 * 1000);
      case 'day':
        return new Date(due.getTime() - 24 * 60 * 60 * 1000);
      case 'custom':
        return customReminder;
      default:
        return null;
    }
  }, [customReminder, due, reminderChoice]);

  async function save() {
    if (!groupId) {
      notify('Choose a group', 'Pick which group this task belongs to.');
      return;
    }
    if (!title.trim()) {
      notify('Missing title', 'Give the task a title.');
      return;
    }
    if (!due) {
      notify('Pick a due date', 'Choose when the task is due.');
      return;
    }
    if (reminderChoice === 'custom' && !customReminder) {
      notify('Pick a reminder time', 'Choose when to be reminded, or pick another reminder option.');
      return;
    }

    setSaving(true);
    try {
      await api.addTask(groupId, {
        title: title.trim(),
        description: description.trim(),
        // Sent as UTC; the server stores UTC and the app converts back for display.
        due_date: due.toISOString(),
        reminder_time: reminder ? reminder.toISOString() : null,
        priority,
        recurrence,
        assigned_to_id: assignedToId === ANYONE ? null : assignedToId
      });
      navigation.goBack();
    } catch (error) {
      notify('Could not add task', error instanceof Error ? error.message : 'Try again.');
    } finally {
      setSaving(false);
    }
  }

  if (!fixedGroupId && !groups) {
    return <LoadingState label="Loading your groups..." />;
  }

  if (!fixedGroupId && groups && !groups.length) {
    return (
      <Screen>
        <Card>
          <Text style={styles.help}>Tasks belong to a group. Create a group first, then add tasks to it.</Text>
          <AppButton icon="people-outline" onPress={() => navigation.replace('CreateGroup')}>Create a Group</AppButton>
        </Card>
      </Screen>
    );
  }

  return (
    <Screen>
      <Card style={styles.section}>
        {!fixedGroupId && groups ? (
          <ChoiceChips<number>
            label="Group"
            value={groupId}
            onChange={value => {
              setGroupId(value);
              setAssignedToId(ANYONE);
            }}
            options={groups.map(group => ({ label: group.name, value: group.id }))}
          />
        ) : null}
        <TextField label="Task" value={title} onChangeText={setTitle} placeholder="Take out the bins" />
        <TextField label="Details (optional)" value={description} onChangeText={setDescription} multiline />
        <DateTimeField label="Due" value={due} onChange={setDue} />
      </Card>

      <Card style={styles.section}>
        <ChoiceChips<number>
          label="Assign to"
          value={assignedToId}
          onChange={setAssignedToId}
          options={[{ label: 'Anyone', value: ANYONE }, ...members.map(member => ({ label: member.name, value: member.id }))]}
        />
        <ChoiceChips<Task['priority']>
          label="Priority"
          value={priority}
          onChange={setPriority}
          options={[
            { label: 'Low', value: 'low' },
            { label: 'Medium', value: 'medium' },
            { label: 'High', value: 'high' }
          ]}
        />
        <ChoiceChips<Task['recurrence']>
          label="Repeat"
          value={recurrence}
          onChange={setRecurrence}
          options={[
            { label: 'Never', value: 'none' },
            { label: 'Daily', value: 'daily' },
            { label: 'Weekly', value: 'weekly' },
            { label: 'Monthly', value: 'monthly' }
          ]}
        />
        {recurrence !== 'none' ? (
          <Text style={styles.help}>When it's marked done, the next one is created automatically.</Text>
        ) : null}
        <ChoiceChips<ReminderChoice>
          label="Remind me"
          value={reminderChoice}
          onChange={setReminderChoice}
          options={[
            { label: 'No reminder', value: 'none' },
            { label: 'At due time', value: 'due' },
            { label: '1 hour before', value: 'hour' },
            { label: '1 day before', value: 'day' },
            { label: 'Pick a time', value: 'custom' }
          ]}
        />
        {reminderChoice === 'custom' ? (
          <DateTimeField label="Reminder" value={customReminder} onChange={setCustomReminder} />
        ) : null}
      </Card>

      <AppButton icon="add-outline" loading={saving} onPress={save}>Add task</AppButton>
    </Screen>
  );
}

const styles = StyleSheet.create({
  section: {
    gap: spacing.md
  },
  help: {
    color: colors.muted,
    ...typography.caption
  }
});
