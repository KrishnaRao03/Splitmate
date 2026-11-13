import { useEffect, useState } from 'react';
import { Alert, Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { AppButton } from '@/components/AppButton';
import { AppText as Text } from '@/components/AppText';
import { ChoiceChips } from '@/components/ChoiceChips';
import { colors, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import { CANADIAN_BANKS, copyText, getPreferredBankId, openBank, setPreferredBankId } from '@/utils/banks';

type Props = {
  /** 'pay': send an e-Transfer to `email`. 'request': send an Interac "Request money" to `email`. */
  mode: 'pay' | 'request';
  person: string;
  email: string;
  /** Shown instead of the full email; Copy still uses the full one. */
  masked?: string;
  amountText: string;
  amountLabel: string;
  note: string;
};

/**
 * Interac has no universal "pay this person" link, so this copies the details and opens the user's own
 * banking app. Splitmate never touches the money.
 */
export function InteracShortcut({ mode, person, email, masked, amountText, amountLabel, note }: Props) {
  const [bankId, setBankId] = useState<string | null>(null);
  const bank = CANADIAN_BANKS.find(item => item.id === bankId) ?? null;

  useEffect(() => {
    getPreferredBankId().then(setBankId);
  }, []);

  async function copy(value: string, what: string) {
    await copyText(value);
    Alert.alert('Copied', `${what} copied. Paste it in your banking app.`);
  }

  async function openMyBank() {
    if (!bank) {
      Alert.alert('Choose your bank', 'Pick your bank once and Splitmate will open it next time.');
      return;
    }
    // The email is the field people mistype, so it goes on the clipboard before the bank opens.
    await copyText(email);
    try {
      await openBank(bank);
    } catch {
      Alert.alert('Could not open your bank', `Open the ${bank.name} app yourself; the email is copied.`);
    }
  }

  const rows: Array<[string, string, string]> = [
    ['Email', masked || email, 'Email'],
    ['Amount', amountLabel, 'Amount'],
    ['Message', note, 'Message'],
  ];

  return (
    <View style={styles.box}>
      <Text style={styles.title}>{mode === 'pay' ? `Send ${person} an Interac e-Transfer` : `Request money from ${person}`}</Text>
      {rows.map(([label, shown, what]) => (
        <Pressable
          key={label}
          style={styles.row}
          accessibilityLabel={`Copy ${what.toLowerCase()}`}
          onPress={() => copy(label === 'Amount' ? amountText : label === 'Email' ? email : shown, what)}
        >
          <View style={styles.rowText}>
            <Text style={styles.label}>{label}</Text>
            <Text style={styles.value} selectable={label !== 'Email'}>{shown}</Text>
          </View>
          <Ionicons name="copy-outline" size={18} color={colors.primary} />
        </Pressable>
      ))}
      <ChoiceChips<string>
        label="My bank"
        value={bankId}
        onChange={value => {
          setBankId(value);
          setPreferredBankId(value);
        }}
        options={CANADIAN_BANKS.map(item => ({ label: item.name, value: item.id }))}
      />
      <AppButton icon="open-outline" onPress={openMyBank}>
        {bank ? `Copy Email & Open ${bank.name}` : 'Copy Email & Open My Bank'}
      </AppButton>
      <Text style={styles.hint}>
        {mode === 'pay'
          ? 'In your bank: Send Interac e-Transfer, paste the email, enter the amount and message. Then come back and tap "I\'ve Paid".'
          : `In your bank: Request money, paste the email and enter the amount. ${person} accepts it in their bank, then marks it paid here.`}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  box: {
    gap: spacing.sm,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md
  },
  title: {
    color: colors.ink,
    ...typography.bodyStrong
  },
  row: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm
  },
  rowText: {
    flex: 1
  },
  label: {
    color: colors.muted,
    ...typography.caption
  },
  value: {
    color: colors.text,
    ...typography.body
  },
  hint: {
    color: colors.muted,
    ...typography.caption
  }
});
