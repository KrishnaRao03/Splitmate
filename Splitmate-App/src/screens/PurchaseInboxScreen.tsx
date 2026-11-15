import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useFocusEffect } from '@react-navigation/native';
import * as Clipboard from 'expo-clipboard';
import { useCallback, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { api } from '@/api/client';
import { AppButton } from '@/components/AppButton';
import { AppText as Text } from '@/components/AppText';
import { Card } from '@/components/Card';
import { Screen } from '@/components/Screen';
import { EmptyState, ErrorState, LoadingState } from '@/components/States';
import { TextField } from '@/components/TextField';
import { colors, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import { formatDate } from '@/utils/dates';
import { formatMoney } from '@/utils/money';
import { confirm, notify } from '@/state/UndoToast';
import type { InboxPurchase, PurchaseInbox, RootStackParamList } from '@/types';

type Props = NativeStackScreenProps<RootStackParamList, 'PurchaseInbox'>;

export function PurchaseInboxScreen({ navigation }: Props) {
  const [inbox, setInbox] = useState<PurchaseInbox | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [pasteText, setPasteText] = useState('');
  const [busy, setBusy] = useState<number | 'paste' | 'default' | null>(null);

  const load = useCallback(async () => {
    try {
      setInbox(await api.purchaseInbox());
      setLoadError(null);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : 'Could not load your purchases.');
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

  async function chooseDefault(groupId: number | null) {
    setBusy('default');
    try {
      setInbox(await api.setDefaultGroup(groupId));
    } catch (error) {
      notify('Could not save default group', error instanceof Error ? error.message : 'Try again.');
    } finally {
      setBusy(null);
    }
  }

  async function copyAddress() {
    if (!inbox?.address) {
      return;
    }
    await Clipboard.setStringAsync(inbox.address);
    notify('Address copied', 'Paste it as the forwarding address in your email settings.');
  }

  async function paste() {
    if (!pasteText.trim()) {
      notify('Paste an alert', 'Copy the purchase alert from your bank app or email, then paste it here.');
      return;
    }
    setBusy('paste');
    try {
      const purchase = await api.pastePurchase(pasteText);
      setPasteText('');
      setInbox(current => current ? { ...current, purchases: [purchase, ...current.purchases] } : current);
    } catch (error) {
      notify('Could not read that alert', error instanceof Error ? error.message : 'Try again.');
    } finally {
      setBusy(null);
    }
  }

  function removeFromList(purchase: InboxPurchase) {
    setInbox(current => current ? { ...current, purchases: current.purchases.filter(item => item.id !== purchase.id) } : current);
  }

  async function share(purchase: InboxPurchase, groupId: number) {
    setBusy(purchase.id);
    try {
      const result = await api.sharePurchase(purchase.id, groupId);
      removeFromList(purchase);
      confirm('Shared', `${purchase.merchant} was added to ${result.group.name}.`, [
        { text: 'Done', style: 'cancel' },
        { text: 'Open group', onPress: () => navigation.navigate('GroupDetail', { groupId: result.group.id, groupName: result.group.name }) }
      ]);
    } catch (error) {
      notify('Could not share purchase', error instanceof Error ? error.message : 'Try again.');
    } finally {
      setBusy(null);
    }
  }

  function chooseGroupAndShare(purchase: InboxPurchase) {
    const groups = inbox?.groups || [];
    if (!groups.length) {
      notify('No groups yet', 'Create or join a group first, then share purchases with it.');
      return;
    }
    confirm(`Share ${purchase.merchant} with`, undefined, [
      ...groups.map(group => ({ text: group.name, onPress: () => share(purchase, group.id) })),
      { text: 'Cancel', style: 'cancel' as const }
    ]);
  }

  async function markPersonal(purchase: InboxPurchase) {
    setBusy(purchase.id);
    try {
      await api.markPurchasePersonal(purchase.id);
      removeFromList(purchase);
    } catch (error) {
      notify('Could not update purchase', error instanceof Error ? error.message : 'Try again.');
    } finally {
      setBusy(null);
    }
  }

  if (!inbox && !loadError) {
    return <LoadingState label="Loading purchases..." />;
  }
  if (!inbox) {
    return <ErrorState message={loadError || 'Could not load your purchases.'} onRetry={load} />;
  }

  const defaultGroup = inbox.groups.find(group => group.id === inbox.default_group_id);

  return (
    <Screen onRefresh={refresh} refreshing={refreshing}>
      <Text style={styles.sectionTitle}>To sort</Text>
      <Text style={styles.muted}>Card purchases wait here. Share each one with a group, or keep it personal. Nothing is shared until you tap.</Text>
      {inbox.purchases.length ? inbox.purchases.map(purchase => (
        <Card key={purchase.id} style={styles.card}>
          <View style={styles.row}>
            <Text style={styles.merchant}>{purchase.merchant}</Text>
            <Text style={styles.amount}>{formatMoney(purchase.amount, defaultGroup?.currency)}</Text>
          </View>
          <Text style={styles.muted}>
            {purchase.purchased_at ? formatDate(purchase.purchased_at) : ''}{purchase.source === 'email' ? ' · from forwarded alert' : ' · pasted'}
          </Text>
          {defaultGroup ? (
            <AppButton icon="people-outline" loading={busy === purchase.id} onPress={() => share(purchase, defaultGroup.id)}>
              Share with {defaultGroup.name}
            </AppButton>
          ) : null}
          <View style={styles.actions}>
            <View style={styles.action}>
              <AppButton icon="swap-horizontal-outline" variant="outline" disabled={busy === purchase.id} onPress={() => chooseGroupAndShare(purchase)}>
                {defaultGroup ? 'Other group' : 'Share'}
              </AppButton>
            </View>
            <View style={styles.action}>
              <AppButton icon="person-outline" variant="ghost" disabled={busy === purchase.id} onPress={() => markPersonal(purchase)}>Personal</AppButton>
            </View>
          </View>
        </Card>
      )) : <EmptyState label="Nothing to sort. New card purchases show up here." />}

      <Card style={styles.card}>
        <Text style={styles.cardTitle}>Default group</Text>
        <Text style={styles.muted}>Purchases offer this group first. You can still pick another group for any purchase, or move an expense later.</Text>
        <View style={styles.chips}>
          {inbox.groups.map(group => {
            const selected = group.id === inbox.default_group_id;
            return (
              <Pressable
                key={group.id}
                accessibilityRole="button"
                accessibilityState={{ selected }}
                disabled={busy === 'default'}
                onPress={() => chooseDefault(selected ? null : group.id)}
                style={[styles.chip, selected && styles.chipSelected]}
              >
                <Text style={[styles.chipText, selected && styles.chipTextSelected]}>{group.name}</Text>
              </Pressable>
            );
          })}
        </View>
        {!inbox.groups.length ? <Text style={styles.muted}>Join or create a group to pick a default.</Text> : null}
      </Card>

      <Card style={styles.card}>
        <Text style={styles.cardTitle}>Get purchases automatically</Text>
        {inbox.address ? (
          <>
            <Text style={styles.muted}>1. In your bank app, turn on email alerts for card purchases.</Text>
            <Text style={styles.muted}>2. In your email settings, forward those alerts to your private Splitmate address:</Text>
            <Text style={styles.address} selectable>{inbox.address}</Text>
            <AppButton icon="copy-outline" variant="outline" onPress={copyAddress}>Copy address</AppButton>
            <Text style={styles.muted}>If your email asks you to confirm forwarding, we email you the code. Splitmate only reads the amount and the store. It never connects to your bank or touches your money.</Text>
          </>
        ) : (
          <Text style={styles.muted}>Automatic forwarding is not switched on yet. You can paste alerts below in the meantime.</Text>
        )}
      </Card>

      <Card style={styles.card}>
        <Text style={styles.cardTitle}>Paste an alert</Text>
        <Text style={styles.muted}>Copy a purchase alert from your bank app or email and paste it here.</Text>
        <TextField label="Alert text" value={pasteText} onChangeText={setPasteText} multiline placeholder="A purchase of $24.50 was made at ..." />
        <AppButton icon="add-outline" variant="outline" loading={busy === 'paste'} onPress={paste}>Add purchase</AppButton>
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
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: spacing.sm
  },
  merchant: {
    flex: 1,
    color: colors.ink,
    ...typography.h3
  },
  amount: {
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
  },
  address: {
    color: colors.ink,
    ...typography.bodyStrong
  },
  actions: {
    flexDirection: 'row',
    gap: spacing.sm
  },
  action: {
    flex: 1
  },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm
  },
  chip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm
  },
  chipSelected: {
    backgroundColor: colors.highlight,
    borderColor: colors.highlight
  },
  chipText: {
    color: colors.ink,
    ...typography.body
  },
  chipTextSelected: {
    color: colors.onHighlight
  }
});
