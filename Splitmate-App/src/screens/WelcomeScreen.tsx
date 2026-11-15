import AsyncStorage from '@react-native-async-storage/async-storage';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { AppButton } from '@/components/AppButton';
import { AppText as Text } from '@/components/AppText';
import { Icon, IconName } from '@/components/Icon';
import { Screen } from '@/components/Screen';
import { colors, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import type { RootStackParamList } from '@/types';
import { POINTS } from '@/utils/points';

type Props = NativeStackScreenProps<RootStackParamList, 'Welcome'>;

const STEPS: Array<{ icon: IconName; title: string; body: string }> = [
  {
    icon: 'people-outline',
    title: 'Make a group',
    body: 'Create a group for your home, trip or friends, then invite people by email or QR code.'
  },
  {
    icon: 'receipt-outline',
    title: 'Split a bill',
    body: 'Add what you paid and Splitmate works out who owes what. Scan a receipt to fill it in for you.'
  },
  {
    icon: 'swap-horizontal-outline',
    title: 'Settle up directly',
    body: 'Pay friends with Interac, PayPal or UPI. Splitmate never holds your money. They confirm it arrived, and the balance clears.'
  },
  {
    icon: 'gift-outline',
    title: 'Earn points',
    body: `Get ${POINTS.friendJoins} points when a friend you invite joins and ${POINTS.settleUp} when you settle up. Spend them on free Pro time and extra scans in Profile.`
  }
];

export function tourSeenKey(userId: number | undefined) {
  return `splitmate.tour.seen.${userId ?? 'guest'}`;
}

/** A short tour shown once to new accounts, and again from Settings. */
export function WelcomeScreen({ navigation, route }: Props) {
  const [step, setStep] = useState(0);
  const last = step === STEPS.length - 1;
  const current = STEPS[step];

  function finish() {
    AsyncStorage.setItem(tourSeenKey(route.params?.userId), '1').catch(() => undefined);
    navigation.goBack();
  }

  return (
    <Screen scroll={false} contentStyle={styles.content}>
      <View style={styles.top}>
        <Text style={styles.counter}>{step + 1} of {STEPS.length}</Text>
        {!last ? (
          <Pressable accessibilityRole="button" onPress={finish} hitSlop={12}>
            <Text style={styles.skip}>Skip</Text>
          </Pressable>
        ) : null}
      </View>

      <View style={styles.body}>
        <View style={styles.iconCircle}>
          <Icon name={current.icon} size={40} color={colors.onHighlight} />
        </View>
        <Text style={styles.title}>{current.title}</Text>
        <Text style={styles.text}>{current.body}</Text>
      </View>

      <View style={styles.dots}>
        {STEPS.map((item, index) => (
          <View key={item.title} style={[styles.dot, index === step && styles.dotActive]} />
        ))}
      </View>

      <View style={styles.actions}>
        {step > 0 ? (
          <AppButton variant="outline" onPress={() => setStep(step - 1)} style={styles.half}>Back</AppButton>
        ) : null}
        <AppButton onPress={last ? finish : () => setStep(step + 1)} style={styles.half}>
          {last ? 'Get started' : 'Next'}
        </AppButton>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: {
    flexGrow: 1,
    justifyContent: 'space-between',
    gap: spacing.xl,
    paddingVertical: spacing.xl
  },
  top: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center'
  },
  counter: {
    color: colors.muted,
    ...typography.caption
  },
  skip: {
    color: colors.primary,
    ...typography.bodyStrong
  },
  body: {
    alignItems: 'center',
    gap: spacing.md,
    paddingHorizontal: spacing.md
  },
  iconCircle: {
    width: 96,
    height: 96,
    borderRadius: radius.pill,
    backgroundColor: colors.highlight,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.md
  },
  title: {
    color: colors.ink,
    ...typography.h2,
    textAlign: 'center'
  },
  text: {
    color: colors.secondary,
    ...typography.body,
    textAlign: 'center',
    maxWidth: 360
  },
  dots: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: spacing.sm
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: radius.pill,
    backgroundColor: colors.borderStrong
  },
  dotActive: {
    width: 24,
    backgroundColor: colors.primary
  },
  actions: {
    flexDirection: 'row',
    gap: spacing.sm
  },
  half: {
    flex: 1
  }
});
