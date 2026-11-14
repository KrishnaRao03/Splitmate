import { createContext, ReactNode, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { Animated, Easing, Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { AppText as Text } from '@/components/AppText';
import { radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';

type Pending = { id: number; message: string; commit: () => void; undo: () => void };
type ShowUndo = (message: string, actions: { commit: () => void; undo: () => void }) => void;

const UndoContext = createContext<ShowUndo>((_message, { commit }) => commit());
const DELAY_MS = 5000;
const EASE = Easing.bezier(0.22, 1, 0.36, 1);

/**
 * Deleting shows "Note deleted · Undo" for five seconds instead of an "Are you sure?" pop-up.
 * The screen hides the item at once; the server delete runs only when the toast times out
 * (or another delete replaces it), and Undo brings the item back without touching the server.
 */
export function UndoToastProvider({ children }: { children: ReactNode }) {
  const insets = useSafeAreaInsets();
  const [pending, setPending] = useState<Pending | null>(null);
  const pendingRef = useRef<Pending | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const shown = useRef(new Animated.Value(0)).current;

  const finish = useCallback((run: 'commit' | 'undo') => {
    const current = pendingRef.current;
    if (timer.current) clearTimeout(timer.current);
    pendingRef.current = null;
    setPending(null);
    current?.[run]();
  }, []);

  const show = useCallback<ShowUndo>((message, actions) => {
    if (pendingRef.current) finish('commit');
    const next = { id: Date.now(), message, ...actions };
    pendingRef.current = next;
    setPending(next);
    timer.current = setTimeout(() => finish('commit'), DELAY_MS);
  }, [finish]);

  useEffect(() => {
    // Animated values can be retargeted mid-way, so a quick undo reverses smoothly.
    Animated.timing(shown, { toValue: pending ? 1 : 0, duration: 300, easing: EASE, useNativeDriver: true }).start();
  }, [pending, shown]);

  useEffect(() => () => {
    if (pendingRef.current) pendingRef.current.commit();
    if (timer.current) clearTimeout(timer.current);
  }, []);

  return (
    <UndoContext.Provider value={show}>
      {children}
      <Animated.View
        pointerEvents={pending ? 'box-none' : 'none'}
        style={[styles.wrap, { bottom: insets.bottom + 88, opacity: shown, transform: [{ translateY: shown.interpolate({ inputRange: [0, 1], outputRange: [24, 0] }) }] }]}
      >
        <View style={styles.toast} accessibilityLiveRegion="polite">
          <Text style={styles.message} numberOfLines={1}>{pending?.message}</Text>
          <Pressable accessibilityRole="button" hitSlop={12} onPress={() => finish('undo')}>
            <Text style={styles.undo}>Undo</Text>
          </Pressable>
        </View>
      </Animated.View>
    </UndoContext.Provider>
  );
}

export function useUndo() {
  return useContext(UndoContext);
}

const styles = StyleSheet.create({
  wrap: {
    position: 'absolute',
    left: spacing.lg,
    right: spacing.lg
  },
  toast: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.md,
    borderCurve: 'continuous',
    backgroundColor: '#1f2023'
  },
  message: {
    ...typography.body,
    flex: 1,
    color: '#ffffff'
  },
  undo: {
    ...typography.bodyStrong,
    color: '#ffc83d'
  }
});
