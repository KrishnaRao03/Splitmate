import { ActivityIndicator, StyleSheet, View } from 'react-native';

import { AppButton } from '@/components/AppButton';
import { AppText as Text } from '@/components/AppText';
import { colors, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';

export function LoadingState({ label = 'Loading Splitmate...' }: { label?: string }) {
  return (
    <View style={styles.state}>
      <ActivityIndicator color={colors.primary} />
      <Text style={styles.text}>{label}</Text>
    </View>
  );
}

export function EmptyState({ label }: { label: string }) {
  return (
    <View style={styles.state}>
      <Text style={styles.text}>{label}</Text>
    </View>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <View style={styles.state}>
      <Text style={styles.text}>{message}</Text>
      {onRetry ? <AppButton variant="outline" icon="refresh-outline" onPress={onRetry}>Try again</AppButton> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  state: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    padding: spacing.lg
  },
  text: {
    color: colors.muted,
    ...typography.bodyStrong,
    textAlign: 'center'
  }
});
