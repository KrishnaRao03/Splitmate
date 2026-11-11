import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useState } from 'react';
import { Alert } from 'react-native';

import { api } from '@/api/client';
import { AppButton } from '@/components/AppButton';
import { AppText as Text } from '@/components/AppText';
import { Card } from '@/components/Card';
import { Screen } from '@/components/Screen';
import { TextField } from '@/components/TextField';
import { colors, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import type { RootStackParamList } from '@/types';

type Props = NativeStackScreenProps<RootStackParamList, 'CreateGroup'>;

export function CreateGroupScreen({ navigation }: Props) {
  const [name, setName] = useState('');
  const [creating, setCreating] = useState(false);

  async function createGroup() {
    if (!name.trim()) {
      return;
    }
    setCreating(true);
    try {
      const created = await api.createGroup(name.trim());
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
        <AppButton icon="add-outline" loading={creating} onPress={createGroup}>Create Group</AppButton>
      </Card>
    </Screen>
  );
}
