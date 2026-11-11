import { useFocusEffect, useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useCallback, useMemo, useRef, useState } from 'react';
import { Alert, Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { api } from '@/api/client';
import { AppButton } from '@/components/AppButton';
import { AppText as Text } from '@/components/AppText';
import { Card } from '@/components/Card';
import { ChoiceChips } from '@/components/ChoiceChips';
import { Screen } from '@/components/Screen';
import { EmptyState, ErrorState, LoadingState } from '@/components/States';
import { TextField } from '@/components/TextField';
import { colors, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import { formatDateTime } from '@/utils/dates';
import type { RootStackParamList, Task } from '@/types';

const REPEAT_LABELS: Record<Task['recurrence'], string> = { none: '', daily: 'Repeats daily', weekly: 'Repeats weekly', monthly: 'Repeats monthly' };

export function TasksScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const addTask = () => navigation.navigate('AddTask');
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const hasLoaded = useRef(false);
  const [search, setSearch] = useState('');
  const [groupFilter, setGroupFilter] = useState<number | 'all'>('all');
  const [showCompleted, setShowCompleted] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await api.allTasks();
      setTasks(data);
      hasLoaded.current = true;
      setLoadError(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Try again.';
      setLoadError(message);
      if (hasLoaded.current) {
        Alert.alert('Could not refresh Tasks', message);
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

  async function toggleTask(task: Task) {
    // Optimistic update so the row flips instantly; reconciled by a refetch
    // so is_completed/is_overdue stay correct if the server disagrees.
    setTasks(current => current.map(item => (item.id === task.id ? { ...item, is_completed: !item.is_completed } : item)));
    try {
      await api.toggleTask(task.id);
      await load();
    } catch (error) {
      setTasks(current => current.map(item => (item.id === task.id ? { ...item, is_completed: task.is_completed } : item)));
      Alert.alert('Could not update task', error instanceof Error ? error.message : 'Try again.');
    }
  }

  async function deleteTask(task: Task) {
    try {
      await api.deleteTask(task.id);
      await load();
    } catch (error) {
      Alert.alert('Could not delete task', error instanceof Error ? error.message : 'Try again.');
    }
  }

  function confirmDeleteTask(task: Task) {
    Alert.alert('Delete task?', task.title, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: () => deleteTask(task) }
    ]);
  }

  const groupOptions = useMemo(() => {
    const seen = new Map<number, string>();
    tasks.forEach(task => {
      if (!seen.has(task.group_id)) {
        seen.set(task.group_id, task.group_name);
      }
    });
    return [{ label: 'All groups', value: 'all' as const }, ...Array.from(seen.entries()).map(([id, name]) => ({ label: name, value: id }))];
  }, [tasks]);

  const filteredTasks = useMemo(() => {
    const query = search.trim().toLowerCase();
    return tasks
      .filter(task => {
        if (!showCompleted && task.is_completed) {
          return false;
        }
        if (groupFilter !== 'all' && task.group_id !== groupFilter) {
          return false;
        }
        if (!query) {
          return true;
        }
        return task.title.toLowerCase().includes(query);
      })
      .sort((a, b) => {
        const aTime = a.due_date ? new Date(a.due_date).getTime() : Infinity;
        const bTime = b.due_date ? new Date(b.due_date).getTime() : Infinity;
        return aTime - bTime;
      });
  }, [tasks, groupFilter, search, showCompleted]);

  if (loading && !hasLoaded.current) {
    return <LoadingState label="Loading your tasks..." />;
  }
  if (loadError && !hasLoaded.current) {
    return <ErrorState message={loadError} onRetry={() => { setLoading(true); load(); }} />;
  }

  return (
    <View style={styles.page}>
    <Screen onRefresh={refresh} refreshing={refreshing}>
      <View style={styles.headerRow}>
        <Text style={styles.sectionTitle}>Tasks</Text>
        <AppButton icon="add-outline" onPress={addTask}>Add Task</AppButton>
      </View>

      {tasks.length ? (
        <Card style={styles.filterCard}>
          <TextField
            label="Search"
            placeholder="Search tasks"
            value={search}
            onChangeText={setSearch}
          />
          {groupOptions.length > 2 ? (
            <ChoiceChips
              label="Group"
              options={groupOptions}
              value={groupFilter}
              onChange={setGroupFilter}
            />
          ) : null}
          <Pressable accessibilityRole="button" onPress={() => setShowCompleted(current => !current)} style={styles.completedToggle}>
            <Ionicons name={showCompleted ? 'checkbox' : 'square-outline'} size={20} color={colors.primary} />
            <Text style={styles.completedToggleLabel}>Show completed</Text>
          </Pressable>
        </Card>
      ) : null}

      {tasks.length === 0 ? (
        <Card style={styles.filterCard}>
          <EmptyState label="No tasks yet. Add chores, bills or reminders for your group." />
          <AppButton icon="add-outline" onPress={addTask}>Add Your First Task</AppButton>
        </Card>
      ) : filteredTasks.length === 0 ? (
        <EmptyState label="No tasks match your filters." />
      ) : filteredTasks.map(task => (
        <Card key={task.id} style={styles.taskCard}>
          <View style={styles.rowBetween}>
            <Pressable onPress={() => toggleTask(task)} style={styles.taskMain}>
              <Ionicons name={task.is_completed ? 'checkbox' : 'square-outline'} size={22} color={colors.primary} />
              <View style={styles.headerText}>
                <Text style={[styles.title, task.is_completed && styles.completed]}>{task.title}</Text>
                <Text style={styles.muted}>{task.group_name}</Text>
              </View>
            </Pressable>
            {task.can_delete ? (
              <Pressable accessibilityLabel={`Delete ${task.title}`} onPress={() => confirmDeleteTask(task)} style={styles.iconButton}>
                <Ionicons name="trash-outline" size={20} color={colors.danger} />
              </Pressable>
            ) : null}
          </View>
          {task.description ? <Text style={styles.description}>{task.description}</Text> : null}
          <Text style={[styles.dueDate, task.is_overdue && styles.overdue]}>
            {task.due_date ? `Due ${formatDateTime(task.due_date)}` : 'No due date'}
          </Text>
          {task.reminder_time ? <Text style={styles.muted}>Reminder: {formatDateTime(task.reminder_time)}</Text> : null}
          <Text style={styles.muted}>
            {task.priority.toUpperCase()}{task.assigned_to ? ` - Assigned to ${task.assigned_to}` : ' - Anyone'}
            {REPEAT_LABELS[task.recurrence] ? ` - ${REPEAT_LABELS[task.recurrence]}` : ''}
          </Text>
        </Card>
      ))}
    </Screen>
      <Pressable style={styles.fab} onPress={addTask} accessibilityRole="button" accessibilityLabel="Add task">
        <Ionicons name="add" size={30} color={colors.surface} />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  page: {
    flex: 1
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.md
  },
  fab: {
    position: 'absolute',
    right: spacing.lg,
    bottom: spacing.lg,
    width: 58,
    height: 58,
    borderRadius: 29,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primary,
    elevation: 6,
    shadowColor: colors.ink,
    shadowOpacity: 0.2,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 }
  },
  sectionTitle: {
    ...typography.h2,
    color: colors.ink
  },
  filterCard: {
    gap: spacing.md
  },
  completedToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm
  },
  completedToggleLabel: {
    ...typography.bodyStrong,
    color: colors.ink
  },
  taskCard: {
    gap: spacing.sm
  },
  rowBetween: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm
  },
  taskMain: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm
  },
  headerText: {
    flex: 1
  },
  title: {
    ...typography.h3,
    color: colors.ink
  },
  completed: {
    color: colors.muted,
    textDecorationLine: 'line-through'
  },
  description: {
    ...typography.body,
    color: colors.text
  },
  dueDate: {
    ...typography.bodyStrong,
    color: colors.secondary
  },
  overdue: {
    color: colors.danger
  },
  muted: {
    ...typography.caption,
    color: colors.muted
  },
  iconButton: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceAlt
  }
});
