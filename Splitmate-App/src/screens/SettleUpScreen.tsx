import AsyncStorage from '@react-native-async-storage/async-storage';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useFocusEffect } from '@react-navigation/native';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Linking, Pressable, StyleSheet, View } from 'react-native';

import { api } from '@/api/client';
import { AppButton } from '@/components/AppButton';
import { AppText as Text } from '@/components/AppText';
import { Card } from '@/components/Card';
import { HistoryFilters } from '@/components/HistoryFilters';
import { Icon } from '@/components/Icon';
import { InteracShortcut } from '@/components/InteracShortcut';
import { Screen } from '@/components/Screen';
import { EmptyState, ErrorState, LoadingState } from '@/components/States';
import { TextField } from '@/components/TextField';
import { useAuth } from '@/state/AuthContext';
import { confirm, notify } from '@/state/UndoToast';
import { colors, fonts, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import type { Group, GroupDetail, Payment, RootStackParamList, SettlePerson, UnsettledItem } from '@/types';
import { formatDate, parseServerDate } from '@/utils/dates';
import { HISTORY_PAGE, HistoryPeriod, HistorySort, filterHistory } from '@/utils/history';
import { formatMoney, parseAmount } from '@/utils/money';
import { SETTLE_POINTS_NOTE } from '@/utils/points';

type Props = NativeStackScreenProps<RootStackParamList, 'SettleUp'>;

/** Settle up on its own page: who owes whom, settle with a person in one go, and the payment history. */
export function SettleUpScreen({ navigation, route }: Props) {
  const groupId = route.params?.groupId;
  if (!groupId) {
    return <GroupChooser onChoose={group => navigation.replace('SettleUp', { groupId: group.id, groupName: group.name })} />;
  }
  return <GroupSettleUp groupId={groupId} />;
}

function GroupChooser({ onChoose }: { onChoose: (group: Group) => void }) {
  const [groups, setGroups] = useState<Group[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => {
    api.groups().then(list => {
      setGroups(list);
      if (list.length === 1) {
        onChoose(list[0]);
      }
    }).catch(cause => setError(cause instanceof Error ? cause.message : 'Try again.'));
  }, [onChoose]);
  useEffect(load, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (error) {
    return <ErrorState message={error} onRetry={load} />;
  }
  if (!groups) {
    return <LoadingState label="Loading your groups..." />;
  }
  return (
    <Screen>
      <Text style={styles.label}>Which group?</Text>
      <Card style={styles.flush}>
        {groups.length ? groups.map((group, index) => (
          <Pressable key={group.id} accessibilityRole="button" onPress={() => onChoose(group)} style={[styles.chooseRow, index > 0 && styles.divider]}>
            <Text style={styles.name}>{group.name}</Text>
            <Icon name="chevron-forward" size={18} color={colors.muted} />
          </Pressable>
        )) : <EmptyState label="You're not in any groups yet." />}
      </Card>
    </Screen>
  );
}

function GroupSettleUp({ groupId }: { groupId: number }) {
  const { currencyCode } = useAuth();
  const [detail, setDetail] = useState<GroupDetail | null>(null);
  const [people, setPeople] = useState<SettlePerson[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [openPerson, setOpenPerson] = useState<number | null>(null);
  const [payingTo, setPayingTo] = useState<number | null>(null);
  const [payAmount, setPayAmount] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [sort, setSort] = useState<HistorySort>('newest');
  const [period, setPeriod] = useState<HistoryPeriod>('all');
  const [shown, setShown] = useState(HISTORY_PAGE);
  const [clearedAt, setClearedAt] = useState(0);
  const clearedKey = `splitmate.payments.cleared.${groupId}`;
  const money = useCallback((value: number) => formatMoney(value, detail?.group.currency || currencyCode), [currencyCode, detail]);

  const load = useCallback(async () => {
    try {
      const [nextDetail, summary] = await Promise.all([api.groupDetail(groupId), api.settleSummary(groupId)]);
      setDetail(nextDetail);
      setPeople(summary.people);
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Try again.');
    }
  }, [groupId]);
  useFocusEffect(useCallback(() => { load(); }, [load]));
  useEffect(() => {
    AsyncStorage.getItem(clearedKey).then(value => setClearedAt(Number(value) || 0)).catch(() => undefined);
  }, [clearedKey]);

  async function run(key: string, action: () => Promise<unknown>, failTitle: string, done?: string) {
    setBusy(key);
    try {
      await action();
      await load();
      if (done) {
        notify(done);
      }
    } catch (cause) {
      notify(failTitle, cause instanceof Error ? cause.message : 'Try again.');
    } finally {
      setBusy(null);
    }
  }

  function settleWith(person: SettlePerson) {
    confirm(`Settle up with ${person.name}?`, `This marks all ${money(person.they_owe)} they owe you in this group as paid.`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Mark as settled', onPress: () => run(`settle-${person.user_id}`, () => api.settlePerson(groupId, person.user_id), 'Could not settle up', `Settled with ${person.name}`) }
    ]);
  }

  function startPay(person: SettlePerson) {
    const option = detail?.payment_options.find(item => item.receiver_id === person.user_id);
    setPayingTo(current => (current === person.user_id ? null : person.user_id));
    setPayAmount((option?.max_amount ?? person.you_owe).toFixed(2));
  }

  async function recordPayment(person: SettlePerson) {
    const amount = parseAmount(payAmount);
    const option = detail?.payment_options.find(item => item.receiver_id === person.user_id);
    if (amount === null || amount <= 0) {
      notify('Enter an amount', 'Enter how much you sent.');
      return;
    }
    if (option && amount > option.max_amount + 0.005) {
      notify('Amount too high', `You can record up to ${money(option.max_amount)} right now.`);
      return;
    }
    await run(`pay-${person.user_id}`, () => api.recordPayment(groupId, person.user_id, amount.toFixed(2)), 'Could not record payment',
      `${person.name} will confirm it arrived`);
    setPayingTo(null);
  }

  function clearHistory() {
    confirm('Clear payment history?', 'Payments so far are hidden on this device. Balances don\'t change.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Clear',
        style: 'destructive',
        onPress: () => {
          const now = Date.now();
          setClearedAt(now);
          AsyncStorage.setItem(clearedKey, String(now)).catch(() => undefined);
          notify('Payment history cleared', 'Only on this device. Balances are the same.');
        }
      }
    ]);
  }

  const history = useMemo(() => {
    const visible = (detail?.payments ?? []).filter(payment => (parseServerDate(payment.date)?.getTime() ?? 0) > clearedAt);
    return filterHistory(visible, sort, period);
  }, [clearedAt, detail, period, sort]);

  if (error && !detail) {
    return <ErrorState message={error} onRetry={load} />;
  }
  if (!detail || !people) {
    return <LoadingState label="Loading settle up..." />;
  }

  const toConfirm = detail.payments.filter(payment => payment.can_confirm);
  const open = people.filter(person => person.they_owe > 0 || person.you_owe > 0);
  const square = people.filter(person => person.they_owe === 0 && person.you_owe === 0);

  return (
    <Screen onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false); }} refreshing={refreshing}>
      {toConfirm.map(payment => (
        <Card key={`confirm-${payment.id}`} style={styles.alert}>
          <Text style={styles.name}>{payment.payer} says they paid you {money(payment.amount)}</Text>
          <Text style={styles.muted}>Check it arrived before you confirm.</Text>
          <View style={styles.buttons}>
            <AppButton style={styles.grow} loading={busy === `c-${payment.id}`} onPress={() => run(`c-${payment.id}`, () => api.confirmPayment(payment.id), 'Could not confirm', 'Payment confirmed')}>Got it</AppButton>
            <AppButton style={styles.grow} variant="outline" onPress={() => run(`d-${payment.id}`, () => api.declinePayment(payment.id), 'Could not decline', `We told ${payment.payer} it hasn't arrived`)}>Not received</AppButton>
          </View>
        </Card>
      ))}

      {detail.requests_for_me.map(item => (
        <Card key={`ask-${item.id}`} style={styles.alert}>
          <Text style={styles.name}>{item.requester} asked you for {money(item.amount)}</Text>
          <View style={styles.buttons}>
            <AppButton style={styles.grow} variant="outline" onPress={() => run(`ap-${item.id}`, () => api.answerMoneyRequest(item.id, 'approve'), 'Could not approve', `${item.requester} can now see your email`)}>Share my email</AppButton>
            <AppButton style={styles.grow} variant="ghost" onPress={() => run(`de-${item.id}`, () => api.answerMoneyRequest(item.id, 'decline'), 'Could not decline', 'Request declined')}>Decline</AppButton>
          </View>
        </Card>
      ))}

      <Text style={styles.label}>People</Text>
      {open.length ? open.map(person => {
        const expanded = openPerson === person.user_id;
        const option = detail.payment_options.find(item => item.receiver_id === person.user_id);
        const request = detail.money_requests.find(item => item.payer_id === person.user_id);
        const items = [...person.they_owe_items.map(item => ({ ...item, theyOwe: true })), ...person.you_owe_items.map(item => ({ ...item, theyOwe: false }))];
        return (
          <Card key={person.user_id} style={styles.person}>
            <Pressable accessibilityRole="button" onPress={() => setOpenPerson(expanded ? null : person.user_id)} style={styles.personTop}>
              <View style={styles.avatar}><Text style={styles.avatarText}>{initials(person.name)}</Text></View>
              <View style={styles.grow}>
                <Text style={styles.name}>{person.name}</Text>
                <Text style={styles.muted}>
                  {person.last_settled_at ? `Last settled ${formatDate(person.last_settled_at)}` : 'Not settled yet'} · {items.length} unsettled
                </Text>
              </View>
              <View style={styles.amountBox}>
                <Text style={[styles.amount, person.net >= 0 ? styles.positive : styles.negative]}>{money(Math.abs(person.net))}</Text>
                <Text style={styles.muted}>{person.net >= 0 ? 'owes you' : 'you owe'}</Text>
              </View>
            </Pressable>

            {expanded ? (
              <View style={styles.items}>
                {items.map(item => <ItemRow key={`${item.theyOwe}-${item.split_id}`} item={item} theyOwe={item.theyOwe} name={person.name} money={money} />)}
              </View>
            ) : (
              <Pressable onPress={() => setOpenPerson(person.user_id)}><Text style={styles.link}>Show what's unsettled</Text></Pressable>
            )}

            <View style={[styles.buttons, person.they_owe > 0 && person.you_owe > 0 && styles.stacked]}>
              {person.they_owe > 0 ? (
                <AppButton style={styles.grow} icon="checkmark-outline" loading={busy === `settle-${person.user_id}`} onPress={() => settleWith(person)}>
                  Mark as settled
                </AppButton>
              ) : null}
              {person.you_owe > 0 && option && option.max_amount > 0 ? (
                <AppButton style={styles.grow} icon="cash-outline" variant={person.they_owe > 0 ? 'outline' : 'primary'} onPress={() => startPay(person)}>
                  Pay
                </AppButton>
              ) : null}
            </View>
            {option && option.pending_amount > 0 ? <Text style={styles.muted}>{money(option.pending_amount)} sent, waiting for {person.name} to confirm.</Text> : null}

            {person.they_owe > 0 && request ? (
              request.request_status === 'approved' && request.email ? (
                <InteracShortcut mode="request" person={person.name} email={request.email} masked={request.masked_email || undefined}
                  amountText={request.amount.toFixed(2)} amountLabel={money(request.amount)} note={`Splitmate - ${detail.group.name}`} />
              ) : request.request_status === 'pending' ? (
                <Text style={styles.muted}>You asked {person.name} to pay. Waiting for them.</Text>
              ) : (
                <Pressable onPress={() => run(`req-${person.user_id}`, () => api.requestMoney(groupId, person.user_id), 'Could not send request', `Asked ${person.name} to pay`)}>
                  <Text style={styles.link}>{`Ask ${person.name} to pay ${money(request.amount)}`}</Text>
                </Pressable>
              )
            ) : null}

            {payingTo === person.user_id && option ? (
              <View style={styles.payPanel}>
                <Text style={styles.muted}>1. Send it with {person.name}'s details. Splitmate never holds the money.</Text>
                {option.payment_methods.length ? option.payment_methods.map(method => (
                  method.type === 'interac' ? (
                    <InteracShortcut key={method.type} mode="pay" person={person.name} email={method.handle} masked={method.masked}
                      amountText={(parseAmount(payAmount) ?? option.max_amount).toFixed(2)} amountLabel={money(parseAmount(payAmount) ?? option.max_amount)}
                      note={`Splitmate - ${detail.group.name}`} />
                  ) : method.url ? (
                    <AppButton key={method.type} icon="open-outline" variant="outline" onPress={() => openPaymentLink(method.url as string)}>
                      {`Pay with ${method.label}`}
                    </AppButton>
                  ) : null
                )) : <Text style={styles.muted}>{person.name} hasn't added PayPal or UPI yet. Pay them however you agreed.</Text>}
                <Text style={styles.muted}>2. Then tell {person.name}. {SETTLE_POINTS_NOTE}</Text>
                <TextField label="Amount sent" value={payAmount} onChangeText={setPayAmount} keyboardType="decimal-pad" />
                <AppButton icon="checkmark-circle-outline" loading={busy === `pay-${person.user_id}`} onPress={() => recordPayment(person)}>I've paid</AppButton>
              </View>
            ) : null}
          </Card>
        );
      }) : <EmptyState label="Everyone is settled up in this group." />}

      {square.length ? (
        <Text style={styles.muted}>
          All square with {square.map(person => person.name).join(', ')}.
        </Text>
      ) : null}

      <View style={styles.historyHead}>
        <Text style={styles.label}>Payment history</Text>
        {history.length ? <Pressable accessibilityRole="button" onPress={clearHistory} hitSlop={8}><Text style={styles.link}>Clear</Text></Pressable> : null}
      </View>
      <HistoryFilters sort={sort} period={period} onSort={value => { setSort(value); setShown(HISTORY_PAGE); }} onPeriod={value => { setPeriod(value); setShown(HISTORY_PAGE); }} />
      <Card style={styles.flush}>
        {history.length ? history.slice(0, shown).map((payment, index) => (
          <PaymentRow key={payment.id} payment={payment} money={money} divider={index > 0}
            onCancel={payment.can_decline && !payment.can_confirm ? () => run(`x-${payment.id}`, () => api.declinePayment(payment.id), 'Could not cancel payment', 'Payment cancelled') : undefined} />
        )) : <Text style={[styles.muted, styles.emptyLine]}>No payments here.</Text>}
      </Card>
      {history.length > shown ? <AppButton variant="ghost" onPress={() => setShown(count => count + HISTORY_PAGE)}>Show more</AppButton> : null}
    </Screen>
  );
}

function ItemRow({ item, theyOwe, name, money }: { item: UnsettledItem; theyOwe: boolean; name: string; money: (value: number) => string }) {
  return (
    <View style={styles.itemRow}>
      <View style={styles.grow}>
        <Text style={styles.itemTitle}>{item.description}</Text>
        <Text style={styles.muted}>
          {formatDate(item.date)}{item.date ? ' · ' : ''}{money(item.total)} ÷ {item.people} · {theyOwe ? `${name} owes you` : `you owe ${name}`}
        </Text>
      </View>
      <Text style={[styles.itemAmount, theyOwe ? styles.positive : styles.negative]}>{money(item.share)}</Text>
    </View>
  );
}

function PaymentRow({ payment, money, divider, onCancel }: { payment: Payment; money: (value: number) => string; divider: boolean; onCancel?: () => void }) {
  return (
    <View style={[styles.itemRow, divider && styles.divider]}>
      <View style={styles.grow}>
        <Text style={styles.itemTitle}>{payment.payer} paid {payment.receiver}</Text>
        <Text style={styles.muted}>{formatDate(payment.date)} · {payment.status_label}{payment.reward_points_awarded ? ` · +${payment.reward_points_awarded} pts` : ''}</Text>
        {onCancel ? <Pressable onPress={onCancel}><Text style={styles.link}>Cancel</Text></Pressable> : null}
      </View>
      <Text style={styles.itemAmount}>{money(payment.amount)}</Text>
    </View>
  );
}

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]?.toUpperCase()).join('');
}

async function openPaymentLink(url: string) {
  // Only the server-built PayPal (https) and UPI links are opened; nothing else.
  if (!/^(https:\/\/paypal\.me\/|upi:\/\/pay\?)/.test(url)) {
    return;
  }
  try {
    await Linking.openURL(url);
  } catch {
    notify('Could not open payment app', 'Make sure the app for this payment method is installed.');
  }
}

const styles = StyleSheet.create({
  label: {
    color: colors.muted,
    ...typography.caption,
    marginTop: spacing.sm
  },
  flush: {
    paddingVertical: 0
  },
  chooseRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.md
  },
  divider: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border
  },
  alert: {
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.highlight
  },
  stacked: {
    flexDirection: 'column',
    flexWrap: 'nowrap'
  },
  buttons: {
    flexDirection: 'row',
    gap: spacing.sm,
    flexWrap: 'wrap'
  },
  grow: {
    flex: 1
  },
  person: {
    gap: spacing.sm
  },
  personTop: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md
  },
  avatar: {
    width: 44,
    height: 44,
    borderRadius: radius.pill,
    borderWidth: 1.5,
    borderColor: colors.ink,
    alignItems: 'center',
    justifyContent: 'center'
  },
  avatarText: {
    color: colors.ink,
    ...typography.bodyStrong
  },
  name: {
    color: colors.ink,
    ...typography.bodyStrong
  },
  muted: {
    color: colors.secondary,
    ...typography.caption
  },
  amountBox: {
    alignItems: 'flex-end'
  },
  amount: {
    fontFamily: fonts.mono,
    fontSize: 18,
    fontWeight: '700'
  },
  positive: {
    color: colors.success
  },
  negative: {
    color: colors.danger
  },
  link: {
    color: colors.primary,
    ...typography.caption,
    textDecorationLine: 'underline'
  },
  items: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border
  },
  itemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.sm
  },
  itemTitle: {
    color: colors.ink,
    ...typography.body
  },
  itemAmount: {
    color: colors.ink,
    fontFamily: fonts.mono,
    fontSize: 15
  },
  payPanel: {
    gap: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border
  },
  historyHead: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between'
  },
  emptyLine: {
    paddingVertical: spacing.md
  }
});
