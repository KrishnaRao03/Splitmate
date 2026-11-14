import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { api } from '@/api/client';
import { AppButton } from '@/components/AppButton';
import { AppText as Text } from '@/components/AppText';
import { Card } from '@/components/Card';
import { Icon } from '@/components/Icon';
import { Screen } from '@/components/Screen';
import { ErrorState, LoadingState } from '@/components/States';
import { notify } from '@/state/UndoToast';
import { colors, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import type { FriendPreview, Group, RootStackParamList } from '@/types';

type Props = NativeStackScreenProps<RootStackParamList, 'AddFriend'>;

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]?.toUpperCase()).join('') || '?';
}

/** Where scanning a friend's profile QR lands: who they are, and what you can do together. */
export function AddFriendScreen({ navigation, route }: Props) {
  const [friend, setFriend] = useState<FriendPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [groups, setGroups] = useState<Group[]>([]);
  const [picking, setPicking] = useState(false);
  const [inviting, setInviting] = useState<number | null>(null);
  const [invitedTo, setInvitedTo] = useState<string | null>(null);

  function load() {
    setError(null);
    api.friendPreview(route.params.code).then(setFriend).catch(cause => setError(cause instanceof Error ? cause.message : 'Could not read this QR code.'));
    api.groups().then(setGroups).catch(() => setGroups([]));
  }

  useEffect(load, [route.params.code]);

  if (!friend) {
    return error ? <ErrorState message={error} onRetry={load} /> : <LoadingState label="Reading QR code..." />;
  }

  const firstName = friend.name.split(/\s+/)[0] || friend.name;
  const sharedIds = new Set(friend.shared_groups.map(group => group.id));
  const invitable = groups.filter(group => !sharedIds.has(group.id));

  async function invite(group: Group) {
    if (!friend) {
      return;
    }
    setInviting(group.id);
    try {
      await api.inviteToGroup(group.id, friend.email);
      setInvitedTo(group.name);
      setPicking(false);
    } catch (cause) {
      notify('Could not send invite', cause instanceof Error ? cause.message : 'Try again.');
    } finally {
      setInviting(null);
    }
  }

  return (
    <Screen contentStyle={styles.content}>
      <Card style={styles.card}>
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>{initials(friend.name)}</Text>
        </View>
        <Text style={styles.title}>{friend.is_self ? 'This is your QR code' : friend.name}</Text>
        <Text style={styles.body}>
          {friend.is_self
            ? 'Friends scan it with their camera to add you on Splitmate.'
            : friend.shared_groups.length
              ? `You're already together in ${friend.shared_groups.map(group => group.name).join(', ')}.`
              : `Add ${firstName} to split bills and share tasks.`}
        </Text>

        {invitedTo ? (
          <View style={styles.done}>
            <Icon name="checkmark-circle" size={20} color={colors.success} />
            <Text style={styles.doneText}>Invite sent. {firstName} joins {invitedTo} once they accept.</Text>
          </View>
        ) : null}

        {friend.is_self ? (
          <AppButton onPress={() => navigation.goBack()}>Done</AppButton>
        ) : (
          <>
            <AppButton icon="flash-outline" onPress={() => navigation.replace('QuickSplit', { contacts: [friend.email] })}>
              {`Split a bill with ${firstName}`}
            </AppButton>
            {invitable.length ? (
              <AppButton icon="people-outline" variant="outline" onPress={() => setPicking(value => !value)}>
                {`Invite ${firstName} to a group`}
              </AppButton>
            ) : null}
            {picking ? (
              <View style={styles.groupList}>
                {invitable.map(group => (
                  <Pressable
                    key={group.id}
                    accessibilityRole="button"
                    disabled={inviting !== null}
                    onPress={() => invite(group)}
                    style={({ pressed }) => [styles.groupRow, pressed && styles.pressed]}
                  >
                    <Text style={styles.groupName}>{group.name}</Text>
                    <Text style={styles.groupAction}>{inviting === group.id ? 'Sending...' : 'Invite'}</Text>
                  </Pressable>
                ))}
              </View>
            ) : null}
            {friend.shared_groups.length ? (
              <AppButton
                variant="ghost"
                onPress={() => navigation.replace('GroupDetail', { groupId: friend.shared_groups[0].id, groupName: friend.shared_groups[0].name })}
              >
                {`Open ${friend.shared_groups[0].name}`}
              </AppButton>
            ) : null}
          </>
        )}
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: {
    maxWidth: 520,
    justifyContent: 'center',
    flexGrow: 1
  },
  card: {
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.xl
  },
  avatar: {
    width: 72,
    height: 72,
    borderRadius: 9999,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.highlight
  },
  avatarText: {
    ...typography.h2,
    color: colors.onHighlight
  },
  title: {
    ...typography.h2,
    color: colors.ink,
    textAlign: 'center'
  },
  body: {
    ...typography.body,
    color: colors.secondary,
    textAlign: 'center'
  },
  done: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    alignSelf: 'stretch',
    padding: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.successSoft
  },
  doneText: {
    ...typography.body,
    color: colors.ink,
    flex: 1
  },
  groupList: {
    alignSelf: 'stretch',
    gap: spacing.sm
  },
  groupRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: spacing.md,
    borderRadius: radius.md,
    borderCurve: 'continuous',
    backgroundColor: colors.surfaceAlt
  },
  pressed: {
    opacity: 0.85
  },
  groupName: {
    ...typography.bodyStrong,
    color: colors.ink
  },
  groupAction: {
    ...typography.bodyStrong,
    color: colors.primary
  }
});
