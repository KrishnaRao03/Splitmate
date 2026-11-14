import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useFocusEffect } from '@react-navigation/native';
import { useCallback, useMemo, useState } from 'react';
import { Alert, Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { api } from '@/api/client';
import { AppText as Text } from '@/components/AppText';
import { Card } from '@/components/Card';
import { Screen } from '@/components/Screen';
import { EmptyState, LoadingState } from '@/components/States';
import { colors, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import { formatDateTime, parseServerDate } from '@/utils/dates';
import type { RootStackParamList, Task } from '@/types';

type Props = NativeStackScreenProps<RootStackParamList, 'TaskCalendar'>;

export function TaskCalendarScreen({ route }: Props) {
  const { groupId } = route.params;
  const [tasks, setTasks] = useState<Task[]>([]);
  const [month, setMonth] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setTasks((await api.groupDetail(groupId)).tasks);
    } catch (error) {
      Alert.alert('Could not load calendar', error instanceof Error ? error.message : 'Try again.');
    } finally {
      setLoading(false);
    }
  }, [groupId]);

  useFocusEffect(useCallback(() => {
    load();
  }, [load]));

  const calendar = useMemo(() => {
    const year = month.getFullYear();
    const monthIndex = month.getMonth();
    const firstDay = new Date(year, monthIndex, 1).getDay();
    const daysInMonth = new Date(year, monthIndex + 1, 0).getDate();
    const cells: Array<{ key: string; day?: number; tasks: Task[] }> = [];
    for (let index = 0; index < firstDay; index += 1) {
      cells.push({ key: `blank-${index}`, tasks: [] });
    }
    for (let day = 1; day <= daysInMonth; day += 1) {
      const dayTasks = tasks.filter(task => {
        if (!task.due_date) {
          return false;
        }
        const due = parseServerDate(task.due_date);
        return !!due && due.getFullYear() === year && due.getMonth() === monthIndex && due.getDate() === day;
      });
      cells.push({ key: `day-${day}`, day, tasks: dayTasks });
    }
    while (cells.length % 7) {
      cells.push({ key: `tail-${cells.length}`, tasks: [] });
    }
    return cells;
  }, [month, tasks]);

  const monthTasks = tasks
    .filter(task => {
      const due = parseServerDate(task.due_date);
      return !!due && due.getFullYear() === month.getFullYear() && due.getMonth() === month.getMonth();
    })
    .sort((left, right) => (parseServerDate(left.due_date)?.getTime() ?? 0) - (parseServerDate(right.due_date)?.getTime() ?? 0));

  if (loading) {
    return <LoadingState label="Loading task calendar..." />;
  }

  return (
    <Screen>
      <Card>
        <View style={styles.calendarHeader}>
          <Pressable accessibilityLabel="Previous month" onPress={() => setMonth(current => new Date(current.getFullYear(), current.getMonth() - 1, 1))} style={styles.iconButton}>
            <Ionicons name="chevron-back" size={22} color={colors.primaryDark} />
          </Pressable>
          <Text style={styles.monthTitle}>{month.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })}</Text>
          <Pressable accessibilityLabel="Next month" onPress={() => setMonth(current => new Date(current.getFullYear(), current.getMonth() + 1, 1))} style={styles.iconButton}>
            <Ionicons name="chevron-forward" size={22} color={colors.primaryDark} />
          </Pressable>
        </View>
        <View style={styles.calendarGrid}>
          {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(label => (
            <View key={label} style={styles.dayCell}><Text style={styles.dayLabel}>{label}</Text></View>
          ))}
          {calendar.map(cell => {
            const overdue = cell.tasks.some(task => task.is_overdue);
            return (
              <View key={cell.key} style={[styles.dayCell, styles.dateCell, cell.tasks.length ? styles.hasTasks : null, overdue ? styles.overdue : null]}>
                {cell.day ? <Text style={styles.dayNumber}>{cell.day}</Text> : null}
                {cell.tasks.length ? <Text style={styles.taskCount}>{cell.tasks.length}</Text> : null}
              </View>
            );
          })}
        </View>
      </Card>

      <Text style={styles.sectionTitle}>Tasks This Month</Text>
      {monthTasks.length ? monthTasks.map(task => (
        <Card key={task.id}>
          <View style={styles.rowBetween}>
            <Text style={styles.taskTitle}>{task.title}</Text>
            <Text style={[styles.priority, task.priority === 'high' ? styles.high : task.priority === 'low' ? styles.low : null]}>{task.priority}</Text>
          </View>
          <Text style={styles.meta}>{formatDateTime(task.due_date)}</Text>
          <Text style={styles.meta}>{task.assigned_to ? `Assigned to ${task.assigned_to}` : 'Anyone'}{task.recurrence !== 'none' ? ` - Repeats ${task.recurrence}` : ''}</Text>
        </Card>
      )) : <EmptyState label="No tasks in this month." />}
    </Screen>
  );
}

const styles = StyleSheet.create({
  calendarHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.sm
  },
  iconButton: {
    width: 42,
    height: 42,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceAlt
  },
  monthTitle: {
    color: colors.ink,
    ...typography.h2
  },
  calendarGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap'
  },
  dayCell: {
    width: '14.285%',
    minHeight: 34,
    alignItems: 'center',
    justifyContent: 'center'
  },
  dateCell: {
    minHeight: 56,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface
  },
  hasTasks: {
    backgroundColor: colors.primarySoft
  },
  overdue: {
    borderColor: colors.danger
  },
  dayLabel: {
    color: colors.muted,
    ...typography.caption
  },
  dayNumber: {
    color: colors.ink,
    ...typography.bodyStrong
  },
  taskCount: {
    minWidth: 18,
    textAlign: 'center',
    color: colors.onPrimary,
    fontSize: 10,
    fontWeight: '700',
    backgroundColor: colors.primary
  },
  sectionTitle: {
    color: colors.ink,
    ...typography.h2
  },
  rowBetween: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm
  },
  taskTitle: {
    flex: 1,
    color: colors.ink,
    ...typography.h3
  },
  priority: {
    color: colors.primaryDark,
    ...typography.label,
    textTransform: 'uppercase'
  },
  high: {
    color: colors.danger
  },
  low: {
    color: colors.success
  },
  meta: {
    color: colors.muted,
    ...typography.caption,
    marginTop: spacing.xs
  }
});
