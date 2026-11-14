import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useFocusEffect } from '@react-navigation/native';
import { useCallback, useRef, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { api } from '@/api/client';
import { AppButton } from '@/components/AppButton';
import { AppText as Text } from '@/components/AppText';
import { Card } from '@/components/Card';
import { Screen } from '@/components/Screen';
import { EmptyState, ErrorState, LoadingState } from '@/components/States';
import { colors, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import type { Group, RootStackParamList } from '@/types';

type Props = NativeStackScreenProps<RootStackParamList, 'Groups'>;

export function GroupsScreen({ navigation }: Props) {
  const [groups, setGroups] = useState<Group[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const hasLoaded = useRef(false);

  const load = useCallback(async () => {
    try {
      const data = await api.groups();
      setGroups(data);
      hasLoaded.current = true;
      setLoadError(null);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : 'Try again.');
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

  if (loading && !hasLoaded.current) {
    return <LoadingState label="Loading your groups..." />;
  }
  if (loadError && !hasLoaded.current) {
    return <ErrorState message={loadError} onRetry={() => { setLoading(true); load(); }} />;
  }

  return (
    <Screen onRefresh={refresh} refreshing={refreshing}>
      <AppButton icon="add-outline" onPress={() => navigation.navigate('CreateGroup')}>Create Group</AppButton>
      <AppButton icon="mail-open-outline" variant="outline" onPress={() => navigation.navigate('Invites')}>Join with an invite</AppButton>

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
    </Screen>
  );
}

const styles = StyleSheet.create({
  sectionTitle: {
    ...typography.h2,
    color: colors.ink
  },
  groupCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.md
  },
  groupIcon: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.md,
    backgroundColor: colors.primary
  },
  groupIconText: {
    ...typography.bodyStrong,
    color: colors.onPrimary
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
    ...typography.body,
    color: colors.muted
  }
});
