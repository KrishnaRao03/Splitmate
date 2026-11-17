import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useEffect, useState } from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';

import { api } from '@/api/client';
import { AppButton } from '@/components/AppButton';
import { AppText as Text } from '@/components/AppText';
import { Card } from '@/components/Card';
import { Icon } from '@/components/Icon';
import { Screen } from '@/components/Screen';
import { useAuth } from '@/state/AuthContext';
import { colors, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import type { RewardsSummary, RootStackParamList } from '@/types';
import { formatDate } from '@/utils/dates';

type Props = NativeStackScreenProps<RootStackParamList, 'MembershipWelcome'>;

const CHECK_EVERY_MS = 3000;
const GIVE_UP_AFTER = 20;

/** Shown after Stripe checkout. Stripe tells the server a moment later, so it checks until Pro is on. */
export function MembershipWelcomeScreen({ navigation }: Props) {
  const { user } = useAuth();
  const [summary, setSummary] = useState<RewardsSummary | null>(null);
  const [tries, setTries] = useState(0);
  const isPro = summary?.membership_plan === 'pro';

  useEffect(() => {
    if (isPro || tries >= GIVE_UP_AFTER) {
      return;
    }
    const timer = setTimeout(() => {
      api.rewards().then(setSummary).catch(() => undefined).finally(() => setTries(count => count + 1));
    }, tries === 0 ? 0 : CHECK_EVERY_MS);
    return () => clearTimeout(timer);
  }, [isPro, tries]);

  const goHome = () => navigation.reset({ index: 0, routes: [{ name: 'Main' }] });

  return (
    <Screen contentStyle={styles.content}>
      <Card style={styles.card}>
        <View style={[styles.icon, isPro ? styles.iconDone : styles.iconWaiting]}>
          {isPro ? <Icon name="checkmark" size={32} color={colors.onHighlight} /> : <ActivityIndicator color={colors.primary} />}
        </View>
        {isPro ? (
          <>
            <Text style={styles.title}>Welcome to Splitmate Pro</Text>
            <Text style={styles.body}>
              Your payment went through and Pro is on. You're billed {summary?.membership_interval === 'year' ? 'yearly' : 'monthly'}
              {summary?.membership_renews_at ? `, next on ${formatDate(summary.membership_renews_at)}` : ''}.
              {user?.email ? ` A confirmation email is on its way to ${user.email}.` : ''}
            </Text>
            <View style={styles.list}>
              {['Unlimited receipt scans', 'Unlimited grocery price comparisons', 'Cancel any time from Membership'].map(item => (
                <View key={item} style={styles.row}>
                  <Icon name="checkmark-circle" size={18} color={colors.success} />
                  <Text style={styles.item}>{item}</Text>
                </View>
              ))}
            </View>
          </>
        ) : tries >= GIVE_UP_AFTER ? (
          <>
            <Text style={styles.title}>Payment received</Text>
            <Text style={styles.body}>Pro is taking longer than usual to switch on. It will appear on Membership shortly; you won't be charged twice.</Text>
          </>
        ) : (
          <>
            <Text style={styles.title}>Payment received</Text>
            <Text style={styles.body}>We're switching on Pro for you. This takes a few seconds.</Text>
          </>
        )}
        <AppButton icon="home-outline" onPress={goHome}>Go home</AppButton>
        {isPro || tries >= GIVE_UP_AFTER ? (
          <AppButton variant="ghost" onPress={() => navigation.replace('Membership')}>View membership</AppButton>
        ) : null}
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: {
    maxWidth: 520,
    justifyContent: 'center',
    flexGrow: 1
  },
  card: {
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.xl
  },
  icon: {
    width: 64,
    height: 64,
    borderRadius: 9999,
    alignItems: 'center',
    justifyContent: 'center'
  },
  iconDone: {
    backgroundColor: colors.highlight
  },
  iconWaiting: {
    backgroundColor: colors.surfaceAlt
  },
  title: {
    ...typography.h2,
    color: colors.ink,
    textAlign: 'center'
  },
  body: {
    ...typography.body,
    color: colors.secondary,
    textAlign: 'center'
  },
  list: {
    alignSelf: 'stretch',
    gap: spacing.sm
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm
  },
  item: {
    ...typography.body,
    color: colors.text,
    flex: 1
  }
});
