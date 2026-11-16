import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useFocusEffect } from '@react-navigation/native';
import { useCallback, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, View } from 'react-native';

import { api } from '@/api/client';
import { AppText as Text } from '@/components/AppText';
import { Card } from '@/components/Card';
import { Icon, IconName } from '@/components/Icon';
import { Screen } from '@/components/Screen';
import { ErrorState, LoadingState } from '@/components/States';
import { notify } from '@/state/UndoToast';
import { colors, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import type { Group, RootStackParamList } from '@/types';

type Props = NativeStackScreenProps<RootStackParamList, 'SplitPicker'>;

/** "Split a bill" from Home: split with a contact right away, or add it to one of your groups. */
export function SplitPickerScreen({ navigation }: Props) {
  const [groups, setGroups] = useState<Group[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [opening, setOpening] = useState<number | null>(null);

  const load = useCallback(() => {
    api.groups().then(list => { setGroups(list); setError(null); })
      .catch(cause => setError(cause instanceof Error ? cause.message : 'Try again.'));
  }, []);
  useFocusEffect(load);

  async function openGroup(group: Group) {
    setOpening(group.id);
    try {
      const detail = await api.groupDetail(group.id);
      navigation.replace('AddExpense', {
        groupId: group.id,
        members: detail.group.members,
        groupName: detail.group.name,
        currentUserId: detail.current_user_id,
        categories: detail.expense_categories,
        defaultSplit: detail.default_split,
        currency: detail.group.currency
      });
    } catch (cause) {
      notify('Could not open the expense form', cause instanceof Error ? cause.message : 'Try again.');
      setOpening(null);
    }
  }

  if (error && !groups) {
    return <ErrorState message={error} onRetry={load} />;
  }
  if (!groups) {
    return <LoadingState label="Loading your groups..." />;
  }

  return (
    <Screen>
      <Text style={styles.label}>With someone</Text>
      <Card style={styles.list}>
        <Row icon="flash-outline" title="Quick split with a contact" detail="Pick people by email or phone. No group needed." onPress={() => navigation.replace('QuickSplit')} />
      </Card>

      <Text style={styles.label}>In a group</Text>
      <Card style={styles.list}>
        {groups.map((group, index) => (
          <Row
            key={group.id}
            icon="people-outline"
            title={group.name}
            detail={`${group.members.length} ${group.members.length === 1 ? 'person' : 'people'}`}
            busy={opening === group.id}
            divider={index > 0}
            onPress={() => openGroup(group)}
          />
        ))}
        <Row icon="add-outline" title="New group" detail="For a home, trip or team" divider={groups.length > 0} onPress={() => navigation.replace('CreateGroup')} />
      </Card>
    </Screen>
  );
}

function Row({ icon, title, detail, onPress, busy, divider }: { icon: IconName; title: string; detail: string; onPress: () => void; busy?: boolean; divider?: boolean }) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress} disabled={busy} style={[styles.row, divider && styles.divider]}>
      <View style={styles.icon}><Icon name={icon} size={20} color={colors.ink} /></View>
      <View style={styles.text}>
        <Text style={styles.title}>{title}</Text>
        <Text style={styles.detail}>{detail}</Text>
      </View>
      {busy ? <ActivityIndicator color={colors.primary} /> : <Icon name="chevron-forward" size={18} color={colors.muted} />}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  label: {
    color: colors.muted,
    ...typography.caption,
    marginTop: spacing.sm
  },
  list: {
    paddingVertical: 0
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.md
  },
  divider: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border
  },
  icon: {
    width: 40,
    height: 40,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    alignItems: 'center',
    justifyContent: 'center'
  },
  text: {
    flex: 1,
    gap: 2
  },
  title: {
    color: colors.ink,
    ...typography.bodyStrong
  },
  detail: {
    color: colors.secondary,
    ...typography.caption
  }
});
