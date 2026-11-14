import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useFocusEffect } from '@react-navigation/native';
import { useCallback, useState } from 'react';
import { Alert, Pressable, Share, StyleSheet, View } from 'react-native';
import { Icon } from '@/components/Icon';

import { api } from '@/api/client';
import { AppButton } from '@/components/AppButton';
import { AppText as Text } from '@/components/AppText';
import { Card } from '@/components/Card';
import { ChoiceChips } from '@/components/ChoiceChips';
import { QrCode } from '@/components/QrCode';
import { Screen } from '@/components/Screen';
import { LoadingState } from '@/components/States';
import { TextField } from '@/components/TextField';
import { colors, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import { formatDate } from '@/utils/dates';
import type { DefaultSplit, GroupDetail, GroupMember, RootStackParamList } from '@/types';

type Props = NativeStackScreenProps<RootStackParamList, 'GroupSettings'>;
type SplitType = DefaultSplit['type'];

type LastInvite = { email: string; url: string; qrRows: string[] };

export function GroupSettingsScreen({ navigation, route }: Props) {
  const { groupId } = route.params;
  const [detail, setDetail] = useState<GroupDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [inviteEmail, setInviteEmail] = useState('');
  const [lastInvite, setLastInvite] = useState<LastInvite | null>(null);
  const [groupName, setGroupName] = useState('');
  const [nicknames, setNicknames] = useState<Record<number, string>>({});
  const [splitType, setSplitType] = useState<SplitType>('equal');
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [percentages, setPercentages] = useState<Record<number, string>>({});
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const next = await api.groupDetail(groupId);
      setDetail(next);
      setGroupName(next.group.name);
      setNicknames(Object.fromEntries(next.group.members.map(member => [member.id, member.nickname])));
      setSplitType(next.default_split.type);
      setSelectedIds(new Set(next.default_split.member_ids.map(Number)));
      setPercentages(Object.fromEntries(
        Object.entries(next.default_split.percentages).map(([memberId, value]) => [Number(memberId), value])
      ));
    } catch (error) {
      Alert.alert('Could not load group settings', error instanceof Error ? error.message : 'Try again.');
    } finally {
      setLoading(false);
    }
  }, [groupId]);

  useFocusEffect(useCallback(() => {
    load();
  }, [load]));

  function toggleMember(member: GroupMember) {
    const next = new Set(selectedIds);
    if (next.has(member.id)) {
      next.delete(member.id);
    } else {
      next.add(member.id);
    }
    setSelectedIds(next);
  }

  // One invite flow for everyone: new or existing accounts both get an invite they accept to join.
  async function inviteMember() {
    try {
      const result = await api.inviteToGroup(groupId, inviteEmail);
      setInviteEmail('');
      setLastInvite(result.invite_url ? { email: result.email, url: result.invite_url, qrRows: result.qr_rows || [] } : null);
      await load();
    } catch (error) {
      Alert.alert('Could not create invite', error instanceof Error ? error.message : 'Try again.');
    }
  }

  async function shareInvite() {
    if (!lastInvite) {
      return;
    }
    try {
      await Share.share({ message: `Join ${detail?.group.name} on Splitmate: ${lastInvite.url}` });
    } catch {
      // The share sheet was dismissed; nothing to undo.
    }
  }

  async function saveGroupName() {
    try {
      await api.renameGroup(groupId, groupName);
      navigation.setOptions({ title: `${groupName.trim()} Settings` });
      await load();
      Alert.alert('Group renamed', `This group is now called "${groupName.trim()}".`);
    } catch (error) {
      Alert.alert('Could not rename group', error instanceof Error ? error.message : 'Try again.');
    }
  }

  function makeAdmin(member: GroupMember) {
    Alert.alert(
      `Make ${member.full_name} the admin?`,
      'They will be able to rename the group, invite and remove people, and delete it. You will become a regular member.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Make admin',
          onPress: async () => {
            try {
              await api.transferAdmin(groupId, member.id);
              setLastInvite(null);
              await load();
              Alert.alert('Admin changed', `${member.full_name} is now the group admin.`);
            } catch (error) {
              Alert.alert('Could not change admin', error instanceof Error ? error.message : 'Try again.');
            }
          }
        }
      ]
    );
  }

  function leaveGroup() {
    Alert.alert('Leave this group?', 'You will lose access to its expenses, tasks and notes.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Leave',
        style: 'destructive',
        onPress: async () => {
          try {
            await api.leaveGroup(groupId);
            navigation.popToTop();
          } catch (error) {
            Alert.alert('Could not leave group', error instanceof Error ? error.message : 'Try again.');
          }
        }
      }
    ]);
  }

  function deleteGroup() {
    const soloAdmin = detail?.group.members.length === 1;
    const warning = soloAdmin
      ? 'This deletes all expenses, payments, notes and tasks in this group, and cancels its pending invites. It cannot be undone.'
      : 'This permanently deletes the group, its tasks and notes. It cannot be undone.';
    Alert.alert('Delete this group?', warning, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            await api.deleteGroup(groupId);
            navigation.popToTop();
          } catch (error) {
            Alert.alert('Could not delete group', error instanceof Error ? error.message : 'Try again.');
          }
        }
      }
    ]);
  }

  async function saveNickname(memberId: number) {
    try {
      await api.updateMemberNickname(groupId, memberId, nicknames[memberId] || '');
      await load();
    } catch (error) {
      Alert.alert('Could not update nickname', error instanceof Error ? error.message : 'Try again.');
    }
  }

  function removeMember(member: GroupMember) {
    Alert.alert('Remove member?', `${member.full_name} will lose access to this group.`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Remove',
        style: 'destructive',
        onPress: async () => {
          try {
            await api.removeMember(groupId, member.id);
            await load();
          } catch (error) {
            Alert.alert('Could not remove member', error instanceof Error ? error.message : 'Try again.');
          }
        }
      }
    ]);
  }

  async function saveDefaultSplit() {
    if (!detail) {
      return;
    }
    setSaving(true);
    try {
      await api.saveDefaultSplit(groupId, {
        type: splitType,
        member_ids: splitType === 'selected' ? Array.from(selectedIds).map(String) : detail.group.members.map(member => String(member.id)),
        percentages: splitType === 'percentage'
          ? Object.fromEntries(detail.group.members.map(member => [String(member.id), percentages[member.id] || '0']))
          : {}
      });
      Alert.alert('Default saved', 'New expenses will start with this split.');
      await load();
    } catch (error) {
      Alert.alert('Could not save default', error instanceof Error ? error.message : 'Try again.');
    } finally {
      setSaving(false);
    }
  }

  if (loading || !detail) {
    return <LoadingState label="Loading group settings..." />;
  }

  const isAdmin = detail.group.admin_id === detail.current_user_id;
  const adminName = detail.group.members.find(member => member.id === detail.group.admin_id)?.full_name ?? 'the admin';

  return (
    <Screen>
      <Card>
        <Text style={styles.sectionTitle}>Group</Text>
        {isAdmin ? (
          <>
            <TextField label="Group name" value={groupName} onChangeText={setGroupName} />
            <AppButton icon="save-outline" variant="outline" onPress={saveGroupName} disabled={!groupName.trim() || groupName.trim() === detail.group.name}>
              Rename Group
            </AppButton>
          </>
        ) : (
          <>
            <Text style={styles.memberName}>{detail.group.name}</Text>
            <Text style={styles.help}>{adminName} is the admin. Only they can rename the group, invite people or remove members.</Text>
          </>
        )}
      </Card>

      {isAdmin ? (
        <Card>
          <Text style={styles.sectionTitle}>Invite people</Text>
          <TextField label="Their email" value={inviteEmail} onChangeText={setInviteEmail} keyboardType="email-address" autoCapitalize="none" />
          <AppButton icon="mail-outline" onPress={inviteMember} disabled={!inviteEmail.trim()}>Send invite</AppButton>
          <Text style={styles.help}>Works for new and existing Splitmate accounts. They join once they accept.</Text>
          {lastInvite ? (
            <View style={styles.invitePanel}>
              <Text style={styles.memberName}>Invite for {lastInvite.email}</Text>
              <Text style={styles.help}>Show this QR code, or share the link, so they can join right away.</Text>
              {lastInvite.qrRows.length ? <View style={styles.qrWrap}><QrCode rows={lastInvite.qrRows} size={180} /></View> : null}
              <Text style={styles.help} selectable>{lastInvite.url}</Text>
              <AppButton icon="share-social-outline" variant="outline" onPress={shareInvite}>Share invite link</AppButton>
            </View>
          ) : null}
        </Card>
      ) : null}

      <Card>
        <Text style={styles.sectionTitle}>Members ({detail.group.members.length})</Text>
        {detail.group.members.map(member => (
          <View key={member.id} style={styles.memberBlock}>
            <View style={styles.rowBetween}>
              <View style={styles.memberMain}>
                <Text style={styles.memberName}>{member.full_name}{member.id === detail.current_user_id ? ' (you)' : ''}</Text>
                <Text style={styles.help}>{member.email}</Text>
              </View>
              {member.id === detail.group.admin_id ? (
                <Text style={styles.adminLabel}>Admin</Text>
              ) : isAdmin ? (
                <Pressable accessibilityLabel={`Remove ${member.full_name}`} onPress={() => removeMember(member)} style={styles.iconButton}>
                  <Icon name="trash-outline" size={20} color={colors.danger} />
                </Pressable>
              ) : null}
            </View>
            {isAdmin ? (
              <View style={styles.nicknameRow}>
                <View style={styles.memberMain}>
                  <TextField
                    label="Group nickname"
                    value={nicknames[member.id] || ''}
                    onChangeText={value => setNicknames(current => ({ ...current, [member.id]: value }))}
                  />
                </View>
                <AppButton icon="save-outline" variant="outline" onPress={() => saveNickname(member.id)}>Save</AppButton>
              </View>
            ) : null}
            {isAdmin && member.id !== detail.group.admin_id ? (
              <AppButton icon="shield-checkmark-outline" variant="ghost" onPress={() => makeAdmin(member)}>Make admin</AppButton>
            ) : null}
          </View>
        ))}
        {isAdmin ? <Text style={styles.help}>Members who still owe or are owed money can't be removed until they settle up.</Text> : null}
      </Card>

      {isAdmin && detail.pending_invites.length ? (
        <Card>
          <Text style={styles.sectionTitle}>Pending invites</Text>
          {detail.pending_invites.map(invite => (
            <View key={invite.id} style={styles.inviteRow}>
              <View style={styles.memberMain}>
                <Text style={styles.memberName}>{invite.email}</Text>
                <Text style={styles.help}>Expires {formatDate(invite.expires_at, 'soon')}</Text>
              </View>
              <AppButton icon="close-outline" variant="danger" onPress={async () => {
                await api.revokeGroupInvite(groupId, invite.id);
                await load();
              }}>Revoke</AppButton>
            </View>
          ))}
        </Card>
      ) : null}

      {isAdmin ? (
      <Card>
        <Text style={styles.sectionTitle}>Default expense split</Text>
        <ChoiceChips<SplitType>
          value={splitType}
          onChange={setSplitType}
          options={[
            { label: 'Equal', value: 'equal' },
            { label: 'Selected people', value: 'selected' },
            { label: 'Percentage', value: 'percentage' }
          ]}
        />
        {splitType === 'selected' ? detail.group.members.map(member => (
          <Pressable key={member.id} onPress={() => toggleMember(member)} style={styles.selectRow}>
            <Icon name={selectedIds.has(member.id) ? 'checkbox' : 'square-outline'} size={22} color={colors.primary} />
            <Text style={styles.memberName}>{member.name}</Text>
          </Pressable>
        )) : null}
        {splitType === 'percentage' ? detail.group.members.map(member => (
          <TextField
            key={member.id}
            label={`${member.name} percentage`}
            value={percentages[member.id] || ''}
            onChangeText={value => setPercentages(current => ({ ...current, [member.id]: value }))}
            keyboardType="decimal-pad"
          />
        )) : null}
        <AppButton icon="save-outline" loading={saving} onPress={saveDefaultSplit}>Save default</AppButton>
        <AppButton icon="refresh-outline" variant="outline" onPress={async () => {
          await api.clearDefaultSplit(groupId);
          await load();
        }}>Reset to Equal</AppButton>
      </Card>
      ) : null}

      <Card>
        <Text style={styles.sectionTitle}>{isAdmin ? 'Delete group' : 'Leave group'}</Text>
        {isAdmin ? (
          <>
            <Text style={styles.help}>
              {detail.group.members.length === 1
                ? "You're the only member, so you can delete this group along with all its expenses, payments, notes and tasks."
                : 'While other members are here, a group with expenses or payments can\'t be deleted, so nobody\'s history is lost. Once everyone else has settled up and left, you can delete it. Want to leave instead? Tap "Make Admin" on another member first.'}
            </Text>
            <AppButton icon="trash-outline" variant="danger" onPress={deleteGroup}>Delete group</AppButton>
          </>
        ) : (
          <>
            <Text style={styles.help}>You can leave once you've settled up everything you owe or are owed here.</Text>
            <AppButton icon="exit-outline" variant="danger" onPress={leaveGroup}>Leave group</AppButton>
          </>
        )}
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  sectionTitle: {
    color: colors.ink,
    ...typography.h2,
    marginBottom: spacing.sm
  },
  help: {
    color: colors.muted,
    ...typography.caption
  },
  memberBlock: {
    gap: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    paddingVertical: spacing.sm
  },
  memberName: {
    color: colors.ink,
    ...typography.bodyStrong
  },
  memberMain: {
    flex: 1
  },
  rowBetween: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm
  },
  nicknameRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: spacing.sm
  },
  iconButton: {
    width: 42,
    height: 42,
    alignItems: 'center',
    justifyContent: 'center'
  },
  invitePanel: {
    gap: spacing.sm,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border
  },
  qrWrap: {
    alignItems: 'center',
    paddingVertical: spacing.sm
  },
  adminLabel: {
    color: colors.primary,
    ...typography.label
  },
  inviteRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    paddingVertical: spacing.sm
  },
  selectRow: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border
  }
});
