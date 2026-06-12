import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useFocusEffect } from '@react-navigation/native';
import { useCallback, useEffect, useState } from 'react';
import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { api } from '@/api/client';
import { AppButton } from '@/components/AppButton';
import { Card } from '@/components/Card';
import { Screen } from '@/components/Screen';
import { EmptyState, LoadingState } from '@/components/States';
import { TextField } from '@/components/TextField';
import { configureNotifications, scheduleTaskReminders } from '@/services/notifications';
import { useAuth } from '@/state/AuthContext';
import { colors, spacing } from '@/theme/colors';
import type { Group, RootStackParamList, Task } from '@/types';

type Props = NativeStackScreenProps<RootStackParamList, 'Home'>;

export function HomeScreen({ navigation }: Props) {
  const { user, currencyCode } = useAuth();
  const [groups, setGroups] = useState<Group[]>([]);
  const [reminders, setReminders] = useState<Task[]>([]);
  const [newGroup, setNewGroup] = useState('');
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [groupData, reminderData] = await Promise.all([
        api.groups(),
        api.upcomingReminders()
      ]);
      setGroups(groupData);
      setReminders(reminderData);
      await scheduleTaskReminders(reminderData);
    } catch (error) {
      Alert.alert('Could not load Splitmate', error instanceof Error ? error.message : 'Try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    configureNotifications().catch(() => undefined);
  }, []);

  useFocusEffect(useCallback(() => {
    load();
  }, [load]));

  async function createGroup() {
    if (!newGroup.trim()) {
      return;
    }
    setCreating(true);
    try {
      const created = await api.createGroup(newGroup.trim());
      setNewGroup('');
      setGroups(current => [created, ...current]);
    } catch (error) {
      Alert.alert('Could not create group', error instanceof Error ? error.message : 'Try again.');
    } finally {
      setCreating(false);
    }
  }

  if (loading) {
    return <LoadingState label="Loading your groups..." />;
  }

  return (
    <Screen>
      <View style={styles.header}>
        <View>
          <Text style={styles.eyebrow}>Welcome back</Text>
          <Text style={styles.title}>{user?.name || 'Splitmate'}</Text>
          <Text style={styles.muted}>{currencyCode} workspace</Text>
        </View>
        <Pressable style={styles.iconButton} onPress={() => navigation.navigate('Settings')}>
          <Ionicons name="settings-outline" size={22} color={colors.primaryDark} />
        </Pressable>
      </View>

      <Card>
        <Text style={styles.cardTitle}>Create Group</Text>
        <TextField label="Group name" value={newGroup} onChangeText={setNewGroup} placeholder="Apartment, Trip, Project" />
        <AppButton loading={creating} onPress={createGroup}>Create Group</AppButton>
      </Card>

      <Text style={styles.sectionTitle}>Your Groups</Text>
      {groups.length ? groups.map(group => (
        <Pressable
          key={group.id}
          onPress={() => navigation.navigate('GroupDetail', { groupId: group.id, groupName: group.name })}
        >
          <Card style={styles.groupCard}>
            <View style={styles.groupIcon}>
              <Text style={styles.groupIconText}>{group.name.slice(0, 1).toUpperCase()}</Text>
            </View>
            <View style={styles.groupMain}>
              <Text style={styles.groupName}>{group.name}</Text>
              <Text style={styles.muted}>{group.members.length} members</Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color={colors.muted} />
          </Card>
        </Pressable>
      )) : <EmptyState label="No groups yet. Create your first group above." />}

      <Text style={styles.sectionTitle}>Upcoming Reminders</Text>
      {reminders.length ? reminders.slice(0, 5).map(task => (
        <Card key={task.id}>
          <Text style={styles.groupName}>{task.title}</Text>
          <Text style={styles.muted}>{task.group_name} • {task.reminder_time ? new Date(task.reminder_time).toLocaleString() : 'No reminder'}</Text>
        </Card>
      )) : <EmptyState label="No upcoming reminders. Task reminders will appear here." />}
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between'
  },
  eyebrow: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: '900',
    textTransform: 'uppercase'
  },
  title: {
    color: colors.ink,
    fontSize: 30,
    fontWeight: '900'
  },
  muted: {
    color: colors.muted,
    fontWeight: '700'
  },
  iconButton: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 12,
    backgroundColor: colors.surfaceBlue
  },
  cardTitle: {
    color: colors.ink,
    fontSize: 18,
    fontWeight: '900',
    marginBottom: spacing.sm
  },
  sectionTitle: {
    color: colors.ink,
    fontSize: 19,
    fontWeight: '900'
  },
  groupCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md
  },
  groupIcon: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 12,
    backgroundColor: colors.primary
  },
  groupIconText: {
    color: colors.white,
    fontWeight: '900',
    fontSize: 18
  },
  groupMain: {
    flex: 1
  },
  groupName: {
    color: colors.ink,
    fontSize: 16,
    fontWeight: '900'
  }
});
