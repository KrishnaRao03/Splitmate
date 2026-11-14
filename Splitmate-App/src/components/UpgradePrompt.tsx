import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { StyleSheet, View } from 'react-native';

import type { ApiError } from '@/api/client';
import { AppButton } from '@/components/AppButton';
import { AppText as Text } from '@/components/AppText';
import { colors, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import type { RootStackParamList } from '@/types';

/** True when the server refused because this month's free allowance is used up. */
export function isLimitReached(error: unknown) {
  return (error as ApiError | null)?.status === 402;
}

/** Shown when a free account runs out of receipt scans or grocery comparisons for the month. */
export function UpgradePrompt({ message }: { message: string }) {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  return (
    <View style={styles.box}>
      <Text style={styles.text}>{message}</Text>
      <AppButton icon="star-outline" onPress={() => navigation.navigate('Membership')}>See Splitmate Pro</AppButton>
    </View>
  );
}

const styles = StyleSheet.create({
  box: {
    gap: spacing.sm,
    padding: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.primarySoft
  },
  text: {
    color: colors.ink,
    ...typography.body
  }
});
