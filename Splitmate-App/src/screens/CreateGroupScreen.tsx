import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useState } from 'react';
import { Alert } from 'react-native';

import { api } from '@/api/client';
import { AppButton } from '@/components/AppButton';
import { AppText as Text } from '@/components/AppText';
import { Card } from '@/components/Card';
import { ChoiceChips } from '@/components/ChoiceChips';
import { Screen } from '@/components/Screen';
import { TextField } from '@/components/TextField';
import { useAuth } from '@/state/AuthContext';
import { colors, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import type { RootStackParamList } from '@/types';

type Props = NativeStackScreenProps<RootStackParamList, 'CreateGroup'>;

// Shown as quick picks after the user's own currency.
const COMMON_CURRENCIES = ['CAD', 'USD', 'EUR', 'GBP', 'INR', 'AUD'];

export function CreateGroupScreen({ navigation }: Props) {
  const { currencyCode } = useAuth();
  const [name, setName] = useState('');
  const [currency, setCurrency] = useState(currencyCode || 'CAD');
  const currencyOptions = Array.from(new Set([currencyCode || 'CAD', ...COMMON_CURRENCIES]))
    .map(code => ({ label: code, value: code }));
  const [creating, setCreating] = useState(false);

  async function createGroup() {
    if (!name.trim()) {
      return;
    }
    setCreating(true);
    try {
      const created = await api.createGroup(name.trim(), currency);
      navigation.replace('GroupDetail', { groupId: created.id, groupName: created.name });
    } catch (error) {
      Alert.alert('Could not create group', error instanceof Error ? error.message : 'Try again.');
    } finally {
      setCreating(false);
    }
  }

  return (
    <Screen>
      <Card>
        <Text style={{ ...typography.h3, color: colors.ink, marginBottom: spacing.sm }}>New Group</Text>
        <TextField label="Group name" value={name} onChangeText={setName} placeholder="Apartment, Trip, Project" autoFocus />
        <ChoiceChips<string> label="Currency" value={currency} onChange={setCurrency} options={currencyOptions} />
        <Text style={{ ...typography.caption, color: colors.muted, marginBottom: spacing.sm }}>
          Every expense and balance in this group uses this currency.
        </Text>
        <AppButton icon="add-outline" loading={creating} onPress={createGroup}>Create Group</AppButton>
      </Card>
    </Screen>
  );
}
