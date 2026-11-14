import { useFocusEffect } from '@react-navigation/native';
import { useCallback, useState } from 'react';
import { Linking, Platform, StyleSheet, View } from 'react-native';
import { Icon } from '@/components/Icon';

import { api } from '@/api/client';
import { AppButton } from '@/components/AppButton';
import { AppText as Text } from '@/components/AppText';
import { Card } from '@/components/Card';
import { Screen } from '@/components/Screen';
import { ErrorState, LoadingState } from '@/components/States';
import { colors, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import type { RewardsSummary } from '@/types';
import { formatDate } from '@/utils/dates';

/** On the web build, Stripe returns to this same app; the native app falls back to the website. */
function appOrigin() {
  return Platform.OS === 'web' ? (globalThis as unknown as { location?: { origin: string } }).location?.origin : undefined;
}

async function openStripe(url: string) {
  if (Platform.OS === 'web') {
    // Same tab, so the iPhone home-screen app stays in the app instead of jumping to Safari.
    (globalThis as unknown as { location: { assign: (to: string) => void } }).location.assign(url);
  } else {
    await Linking.openURL(url);
  }
}

export function MembershipScreen() {
  const [summary, setSummary] = useState<RewardsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState<string | null>(null);

  async function go(key: string, action: () => Promise<{ url: string }>) {
    setBusy(key);
    setMessage('');
    try {
      await openStripe((await action()).url);
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : 'Could not open the payment page.');
    } finally {
      setBusy(null);
    }
  }

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

  const isPro = summary.membership_plan === 'pro';
  const plans = summary.membership_plans || [];
  const billing = Boolean(summary.billing_enabled);

  return (
    <Screen>
      <Text style={styles.intro}>Splitting, groups and settling up stay free for everyone. Pro adds the extras and keeps Splitmate running.</Text>
      {isPro ? (
        <Card style={styles.plan}>
          <Text style={styles.planName}>You have Splitmate Pro</Text>
          <Text style={styles.feature}>
            Billed {summary.membership_interval === 'year' ? 'yearly' : 'monthly'}.
            {summary.membership_renews_at ? ` ${summary.membership_cancel_at_period_end ? 'Ends' : 'Renews'} on ${formatDate(summary.membership_renews_at)}.` : ''}
          </Text>
          {summary.membership_status === 'past_due' ? <Text style={styles.warning}>Your last payment failed. Update your card to keep Pro.</Text> : null}
          <AppButton icon="settings-outline" variant="outline" loading={busy === 'portal'} onPress={() => go('portal', () => api.membershipPortal(appOrigin()))}>
            Manage subscription
          </AppButton>
        </Card>
      ) : null}
      {!isPro && summary.usage ? (
        <Card style={styles.plan}>
          <Text style={styles.feature}>Left this month on Free</Text>
          <Text style={styles.footnote}>
            {summary.usage.receipt_scan.remaining} of {summary.usage.receipt_scan.limit} receipt scans · {summary.usage.grocery_compare.remaining} of {summary.usage.grocery_compare.limit} grocery comparisons
          </Text>
        </Card>
      ) : null}
      {message ? <Text style={styles.warning}>{message}</Text> : null}
      {plans.map(plan => (
        <Card key={plan.id} style={[styles.plan, plan.is_current && styles.current]}>
          <View style={styles.planHeader}>
            <Text style={styles.planName}>{plan.name}</Text>
            <View style={[styles.badge, plan.is_current ? styles.badgeCurrent : null]}>
              <Text style={[styles.badgeText, plan.is_current ? styles.badgeTextCurrent : null]}>{plan.is_current ? 'Current plan' : plan.badge}</Text>
            </View>
          </View>
          <Text style={styles.price}>
            {plan.price}
            <Text style={styles.interval}> / {plan.interval}</Text>
          </Text>
          {plan.features.map(feature => (
            <View key={feature} style={styles.featureRow}>
              <Icon name="checkmark-circle" size={18} color={colors.success} />
              <Text style={styles.feature}>{feature}</Text>
            </View>
          ))}
          {plan.checkout_interval && !isPro ? (
            <AppButton
              icon="card-outline"
              disabled={!billing}
              loading={busy === plan.id}
              onPress={() => go(plan.id, () => api.membershipCheckout(plan.checkout_interval as 'month' | 'year', appOrigin()))}
            >
              {billing ? `Upgrade for ${plan.price}/${plan.interval}` : 'Coming soon'}
            </AppButton>
          ) : null}
        </Card>
      ))}
      <Text style={styles.footnote}>Payments are handled by Stripe. Splitmate never sees your card number. Cancel any time from Manage subscription.</Text>
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
  warning: {
    color: colors.danger,
    ...typography.body
  },
  footnote: {
    color: colors.muted,
    ...typography.caption
  },
  feature: {
    flex: 1,
    color: colors.text,
    ...typography.body
  }
});
