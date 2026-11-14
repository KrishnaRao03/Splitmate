import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useFocusEffect } from '@react-navigation/native';
import { useCallback, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { api } from '@/api/client';
import { AppButton } from '@/components/AppButton';
import { AppText as Text } from '@/components/AppText';
import { Card } from '@/components/Card';
import { Screen } from '@/components/Screen';
import { EmptyState, ErrorState, LoadingState } from '@/components/States';
import { TextField } from '@/components/TextField';
import { colors, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import { formatDate } from '@/utils/dates';
import { confirm, notify } from '@/state/UndoToast';
import type { Group, MyInvite, RootStackParamList } from '@/types';

type Props = NativeStackScreenProps<RootStackParamList, 'Invites'>;

export function InvitesScreen({ navigation }: Props) {
  const [invites, setInvites] = useState<MyInvite[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [link, setLink] = useState('');
  const [acceptingId, setAcceptingId] = useState<number | 'link' | null>(null);

  const load = useCallback(async () => {
    try {
      setInvites(await api.myInvites());
      setLoadError(null);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : 'Could not load your invites.');
    }
  }, []);

  useFocusEffect(useCallback(() => {
    load();
  }, [load]));

  async function refresh() {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }

  function joined(result: { message: string; group: Group }) {
    confirm('Joined group', result.message, [
      { text: 'Later', style: 'cancel' },
      { text: 'Open group', onPress: () => navigation.replace('GroupDetail', { groupId: result.group.id, groupName: result.group.name }) }
    ]);
  }

  async function accept(invite: MyInvite) {
    setAcceptingId(invite.id);
    try {
      const result = await api.acceptInvite(invite.id);
      setInvites(current => (current || []).filter(item => item.id !== invite.id));
      joined(result);
    } catch (error) {
      notify('Could not accept invite', error instanceof Error ? error.message : 'Try again.');
      load();
    } finally {
      setAcceptingId(null);
    }
  }

  async function acceptLink() {
    if (!link.trim()) {
      notify('Paste a link', 'Paste the invite link from your email, like https://.../invite/abc123.');
      return;
    }
    setAcceptingId('link');
    try {
      const result = await api.acceptInviteLink(link);
      setLink('');
      load();
      joined(result);
    } catch (error) {
      notify('Could not accept invite', error instanceof Error ? error.message : 'Try again.');
    } finally {
      setAcceptingId(null);
    }
  }

  if (!invites && !loadError) {
    return <LoadingState label="Loading invites..." />;
  }

  return (
    <Screen onRefresh={refresh} refreshing={refreshing}>
      <Text style={styles.sectionTitle}>Invites for you</Text>
      {loadError && !invites ? <ErrorState message={loadError} onRetry={load} /> : null}
      {invites?.length ? invites.map(invite => (
        <Card key={invite.id} style={styles.card}>
          <Text style={styles.groupName}>{invite.group_name}</Text>
          <Text style={styles.muted}>
            {invite.invited_by ? `${invite.invited_by} invited you` : 'You were invited'}
            {invite.expires_at ? ` - expires ${formatDate(invite.expires_at)}` : ''}
          </Text>
          <AppButton icon="enter-outline" loading={acceptingId === invite.id} onPress={() => accept(invite)}>Join group</AppButton>
        </Card>
      )) : invites ? <EmptyState label="No open invites. When a group admin invites your email, it shows up here." /> : null}

      <Card style={styles.card}>
        <Text style={styles.cardTitle}>Have an invite link?</Text>
        <Text style={styles.muted}>Paste the link from your invite email. It only works for the email it was sent to.</Text>
        <View>
          <TextField label="Invite link" value={link} onChangeText={setLink} autoCapitalize="none" autoCorrect={false} placeholder="https://.../invite/..." />
        </View>
        <AppButton icon="link-outline" variant="outline" loading={acceptingId === 'link'} onPress={acceptLink}>Accept invite</AppButton>
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  sectionTitle: {
    color: colors.ink,
    ...typography.h2
  },
  card: {
    gap: spacing.sm
  },
  groupName: {
    color: colors.ink,
    ...typography.h3
  },
  cardTitle: {
    color: colors.ink,
    ...typography.h3
  },
  muted: {
    color: colors.secondary,
    ...typography.body
  }
});
