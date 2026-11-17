import { useEffect, useRef } from 'react';
import { AccessibilityInfo, Animated, Easing, StyleSheet, View } from 'react-native';

import { AppButton } from '@/components/AppButton';
import { AppText as Text } from '@/components/AppText';
import { Icon, IconName } from '@/components/Icon';
import { colors, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';

/** Grey blocks shaped like the cards that are loading, gently pulsing (still when reduced motion is on). */
export function LoadingState({ label = 'Loading Splitmate' }: { label?: string }) {
  const opacity = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    let loop: Animated.CompositeAnimation | null = null;
    AccessibilityInfo.isReduceMotionEnabled().then(reduce => {
      if (reduce) return;
      const easing = Easing.bezier(0.22, 1, 0.36, 1);
      loop = Animated.loop(Animated.sequence([
        Animated.timing(opacity, { toValue: 0.5, duration: 700, easing, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 1, duration: 700, easing, useNativeDriver: true })
      ]));
      loop.start();
    }).catch(() => undefined);
    return () => loop?.stop();
  }, [opacity]);

  return (
    <Animated.View accessibilityLabel={label} accessibilityRole="progressbar" style={[styles.skeleton, { opacity }]}>
      <View style={[styles.block, styles.hero]} />
      <View style={[styles.block, styles.card]} />
      <View style={[styles.line, { width: '40%' }]} />
      <View style={[styles.block, styles.row]} />
      <View style={[styles.block, styles.row]} />
    </Animated.View>
  );
}

export function EmptyState({ label, icon = 'document-text-outline' }: { label: string; icon?: IconName }) {
  return (
    <View style={styles.state}>
      <View style={styles.emptyIcon}><Icon name={icon} size={24} color={colors.primary} /></View>
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
  skeleton: {
    flex: 1,
    gap: spacing.md,
    padding: spacing.md,
    backgroundColor: colors.bg
  },
  block: {
    borderRadius: radius.lg,
    backgroundColor: colors.surfaceAlt
  },
  hero: {
    height: 128
  },
  card: {
    height: 176
  },
  row: {
    height: 64
  },
  line: {
    height: 16,
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceAlt
  },
  emptyIcon: {
    width: 48,
    height: 48,
    borderRadius: 9999,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primarySoft
  },
  text: {
    color: colors.muted,
    ...typography.bodyStrong,
    textAlign: 'center'
  }
});
