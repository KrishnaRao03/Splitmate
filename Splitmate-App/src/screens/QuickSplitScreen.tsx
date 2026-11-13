import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { api, type ApiError } from '@/api/client';
import { AppButton } from '@/components/AppButton';
import { AppText as Text } from '@/components/AppText';
import { Card } from '@/components/Card';
import { Screen } from '@/components/Screen';
import { TextField } from '@/components/TextField';
import { useAuth } from '@/state/AuthContext';
import { colors, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import type { RootStackParamList } from '@/types';
import { formatMoney, parseAmount } from '@/utils/money';

type Props = NativeStackScreenProps<RootStackParamList, 'QuickSplit'>;

/** Split one bill equally with friends by email or phone, without making a group first. */
export function QuickSplitScreen({ navigation }: Props) {
  const auth = useAuth();
  const [contact, setContact] = useState('');
  const [contacts, setContacts] = useState<string[]>([]);
  const [description, setDescription] = useState('');
  const [amountText, setAmountText] = useState('');
  const [error, setError] = useState('');
  const [notFound, setNotFound] = useState<string[]>([]);
  const [notice, setNotice] = useState('');
  const [saving, setSaving] = useState(false);

  const amount = parseAmount(amountText);
  const people = contacts.length + 1;
  const share = amount ? Math.floor((amount / people) * 100) / 100 : null;

  function addContact() {
    const parts = contact.split(/[,;\n]+/).map(part => part.trim()).filter(Boolean);
    if (!parts.length) {
      return;
    }
    setContacts(current => [...current, ...parts.filter(part => !current.includes(part))]);
    setContact('');
    setError('');
  }

  async function invite(email: string) {
    try {
      const result = await api.inviteSplitmate(email);
      setNotice(result.message);
    } catch (inviteError) {
      setError(inviteError instanceof Error ? inviteError.message : 'Could not send the invite.');
    }
  }

  async function split() {
    const all = contact.trim() ? [...contacts, ...contact.split(/[,;\n]+/).map(part => part.trim()).filter(Boolean)] : contacts;
    setNotFound([]);
    setNotice('');
    if (!all.length) {
      setError('Add at least one friend by email or phone number.');
      return;
    }
    if (!description.trim()) {
      setError('Say what it was for, like "Dinner".');
      return;
    }
    if (!amount || amount <= 0) {
      setError('Enter the total amount.');
      return;
    }
    setError('');
    setSaving(true);
    try {
      const result = await api.quickSplit(all, description.trim(), amount);
      navigation.replace('GroupDetail', { groupId: result.group.id, groupName: result.group.name });
    } catch (splitError) {
      const apiError = splitError as ApiError;
      setError(apiError.message || 'Could not split this. Try again.');
      const missing = apiError.data?.not_found;
      setNotFound(Array.isArray(missing) ? missing.map(String) : []);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Screen>
      <Card>
        <Text style={styles.title}>Quick split</Text>
        <Text style={styles.muted}>Split one bill equally with friends. No group needed; the same friends share one running balance.</Text>

        <TextField
          label="Friends (email or phone)"
          value={contact}
          onChangeText={setContact}
          onSubmitEditing={addContact}
          autoCapitalize="none"
          keyboardType="email-address"
          placeholder="sam@email.com or 416 555 0123"
        />
        <AppButton icon="person-add-outline" variant="outline" onPress={addContact}>Add friend</AppButton>
        {contacts.length ? (
          <View style={styles.chips}>
            {contacts.map(item => (
              <Pressable
                key={item}
                accessibilityRole="button"
                accessibilityLabel={`Remove ${item}`}
                onPress={() => setContacts(current => current.filter(value => value !== item))}
                style={styles.chip}
              >
                <Text style={styles.chipText}>{item}</Text>
                <Ionicons name="close" size={14} color={colors.primaryDark} />
              </Pressable>
            ))}
          </View>
        ) : null}

        <TextField label="What was it for?" value={description} onChangeText={setDescription} placeholder="Dinner, Uber, Movie tickets" />
        <TextField label="Total amount" value={amountText} onChangeText={setAmountText} keyboardType="decimal-pad" placeholder="60.00" />

        {share ? (
          <Text style={styles.summary}>
            {people} people · about {formatMoney(share, auth.currencyCode)} each. You paid, so they'll owe you.
          </Text>
        ) : null}
        {error ? <Text style={styles.error}>{error}</Text> : null}
        {notice ? <Text style={styles.notice}>{notice}</Text> : null}
        {notFound.filter(item => item.includes('@')).map(email => (
          <AppButton key={email} icon="mail-outline" variant="outline" onPress={() => invite(email)}>{`Invite ${email} to Splitmate`}</AppButton>
        ))}

        <AppButton icon="flash-outline" loading={saving} onPress={split}>Split it</AppButton>
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  title: {
    ...typography.h3,
    color: colors.ink
  },
  muted: {
    ...typography.body,
    color: colors.muted
  },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: radius.pill,
    backgroundColor: colors.primarySoft,
    borderWidth: 1,
    borderColor: colors.border
  },
  chipText: {
    ...typography.label,
    color: colors.primaryDark
  },
  summary: {
    ...typography.body,
    color: colors.ink
  },
  error: {
    ...typography.body,
    color: colors.danger
  },
  notice: {
    ...typography.body,
    color: colors.success
  }
});
