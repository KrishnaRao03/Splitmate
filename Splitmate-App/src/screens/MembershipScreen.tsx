import { useFocusEffect } from '@react-navigation/native';
import { useCallback, useState } from 'react';
import { Alert, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { api } from '@/api/client';
import { AppButton } from '@/components/AppButton';
import { AppText as Text } from '@/components/AppText';
import { Card } from '@/components/Card';
import { Screen } from '@/components/Screen';
import { ErrorState, LoadingState } from '@/components/States';
import { colors, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import type { RewardsSummary } from '@/types';

export function MembershipScreen() {
  const [summary, setSummary] = useState<RewardsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setSummary(await api.rewards());
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not load membership plans.');
    }
  }, []);

  useFocusEffect(useCallback(() => {
    load();
  }, [load]));

  if (!summary) {
    return error ? <ErrorState message={error} onRetry={load} /> : <LoadingState label="Loading plans..." />;
  }

  const currentPlan = summary.membership_plan || 'free';
  const plans = summary.membership_plans || [];

  return (
    <Screen>
      <Text style={styles.intro}>Pick the plan that fits your household. You can keep using every core feature for free.</Text>
      {plans.map(plan => {
        const isCurrent = plan.id === currentPlan;
        return (
          <Card key={plan.id} style={[styles.plan, isCurrent && styles.current]}>
            <View style={styles.planHeader}>
              <Text style={styles.planName}>{plan.name}</Text>
              <View style={[styles.badge, isCurrent ? styles.badgeCurrent : null]}>
                <Text style={[styles.badgeText, isCurrent ? styles.badgeTextCurrent : null]}>{isCurrent ? 'Current plan' : plan.badge}</Text>
              </View>
            </View>
            <Text style={styles.price}>
              {plan.price}
              <Text style={styles.interval}> / {plan.interval}</Text>
            </Text>
            {plan.features.map(feature => (
              <View key={feature} style={styles.featureRow}>
                <Ionicons name="checkmark-circle" size={18} color={colors.success} />
                <Text style={styles.feature}>{feature}</Text>
              </View>
            ))}
            {!isCurrent ? (
              <AppButton
                icon="arrow-up-circle-outline"
                onPress={() => Alert.alert('Billing Setup Needed', 'Paid plans are not available yet. Splitmate Plus will be offered through the app store once billing is connected.')}
              >
                Upgrade
              </AppButton>
            ) : null}
          </Card>
        );
      })}
    </Screen>
  );
}

const styles = StyleSheet.create({
  intro: {
    color: colors.secondary,
    ...typography.body
  },
  plan: {
    gap: spacing.sm
  },
  current: {
    borderWidth: 2,
    borderColor: colors.primary
  },
  planHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm
  },
  planName: {
    color: colors.ink,
    ...typography.h2,
    flex: 1
  },
  badge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt
  },
  badgeCurrent: {
    backgroundColor: colors.primarySoft
  },
  badgeText: {
    color: colors.secondary,
    ...typography.caption
  },
  badgeTextCurrent: {
    color: colors.primary
  },
  price: {
    color: colors.ink,
    ...typography.display
  },
  interval: {
    color: colors.muted,
    ...typography.body
  },
  featureRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm
  },
  feature: {
    flex: 1,
    color: colors.text,
    ...typography.body
  }
});
