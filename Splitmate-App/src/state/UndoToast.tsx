import { createContext, ReactNode, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { Animated, Easing, Modal, Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { AppText as Text } from '@/components/AppText';
import { colors, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';

type Pending = { id: number; message: string; detail?: string; commit: () => void; undo?: () => void };
type ShowUndo = (message: string, actions: { commit: () => void; undo: () => void }) => void;

const UndoContext = createContext<ShowUndo>((_message, { commit }) => commit());

// Lets code outside React components (and screens without the hook) show a calm message.
let notifyHandler: ((title: string, detail?: string) => void) | null = null;

/**
 * A short message at the bottom of the screen that fades after a few seconds, used instead of
 * blocking pop-ups for errors and confirmations ("Could not save note. Check your connection.").
 */
export function notify(title: string, detail?: string) {
  notifyHandler?.(title, detail);
}

type ConfirmAction = { text: string; style?: 'cancel' | 'destructive' | 'default'; onPress?: () => void };
type ConfirmRequest = { title: string; message?: string; actions: ConfirmAction[] };
let confirmHandler: ((request: ConfirmRequest) => void) | null = null;

/**
 * Same arguments as Alert.alert, but drawn inside the app, so it also works in the web build
 * (where Alert.alert buttons never appear) and matches the app's look.
 */
export function confirm(title: string, message: string | undefined, actions: ConfirmAction[]) {
  confirmHandler?.({ title, message, actions });
}
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
    if (run === 'undo') current?.undo?.();
    else current?.commit();
  }, []);

  const showMessage = useCallback((message: string, detail?: string) => {
    if (pendingRef.current) finish('commit');
    const next = { id: Date.now(), message, detail, commit: () => undefined };
    pendingRef.current = next;
    setPending(next);
    timer.current = setTimeout(() => finish('commit'), 4000);
  }, [finish]);

  useEffect(() => {
    notifyHandler = showMessage;
    return () => { notifyHandler = null; };
  }, [showMessage]);

  const [asking, setAsking] = useState<ConfirmRequest | null>(null);
  useEffect(() => {
    confirmHandler = setAsking;
    return () => { confirmHandler = null; };
  }, []);

  function answer(action?: ConfirmAction) {
    setAsking(null);
    action?.onPress?.();
  }
  const cancelAction = asking?.actions.find(action => action.style === 'cancel');

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
          <View style={styles.texts}>
            <Text style={styles.message} numberOfLines={2}>{pending?.message}</Text>
            {pending?.detail ? <Text style={styles.detail} numberOfLines={3}>{pending.detail}</Text> : null}
          </View>
          {pending?.undo ? (
            <Pressable accessibilityRole="button" hitSlop={12} onPress={() => finish('undo')}>
              <Text style={styles.undo}>Undo</Text>
            </Pressable>
          ) : (
            <Pressable accessibilityRole="button" accessibilityLabel="Dismiss" hitSlop={12} onPress={() => finish('commit')}>
              <Text style={styles.undo}>OK</Text>
            </Pressable>
          )}
        </View>
      </Animated.View>
      <Modal transparent visible={!!asking} animationType="fade" onRequestClose={() => answer(cancelAction)}>
        <Pressable style={styles.backdrop} onPress={() => answer(cancelAction)} accessibilityLabel="Close">
          <Pressable style={styles.sheet} onPress={() => undefined} accessibilityRole="alert">
            <Text style={styles.sheetTitle}>{asking?.title}</Text>
            {asking?.message ? <Text style={styles.sheetMessage}>{asking.message}</Text> : null}
            <View style={styles.sheetActions}>
              {asking?.actions.map(action => (
                <Pressable
                  key={action.text}
                  accessibilityRole="button"
                  onPress={() => answer(action)}
                  style={({ pressed }) => [
                    styles.sheetButton,
                    action.style === 'cancel' ? styles.sheetCancel : action.style === 'destructive' ? styles.sheetDanger : styles.sheetPrimary,
                    pressed && styles.sheetPressed
                  ]}
                >
                  <Text style={[styles.sheetButtonText, action.style === 'cancel' ? styles.sheetCancelText : action.style === 'destructive' ? styles.sheetDangerText : styles.sheetPrimaryText]}>
                    {action.text}
                  </Text>
                </Pressable>
              ))}
            </View>
          </Pressable>
        </Pressable>
      </Modal>
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
  texts: {
    flex: 1,
    gap: 2
  },
  message: {
    ...typography.bodyStrong,
    color: '#ffffff'
  },
  detail: {
    ...typography.caption,
    color: '#c4c6cb'
  },
  undo: {
    ...typography.bodyStrong,
    color: '#ffc83d'
  },
  backdrop: {
    flex: 1,
    justifyContent: 'center',
    padding: spacing.lg,
    backgroundColor: 'rgba(0,0,0,0.45)'
  },
  sheet: {
    alignSelf: 'center',
    width: '100%',
    maxWidth: 420,
    gap: spacing.sm,
    padding: spacing.lg,
    borderRadius: radius.lg,
    borderCurve: 'continuous',
    backgroundColor: colors.surface
  },
  sheetTitle: {
    ...typography.h3,
    color: colors.ink
  },
  sheetMessage: {
    ...typography.body,
    color: colors.muted
  },
  sheetActions: {
    gap: spacing.sm,
    marginTop: spacing.sm
  },
  sheetButton: {
    alignItems: 'center',
    paddingVertical: spacing.md,
    borderRadius: radius.md,
    borderCurve: 'continuous'
  },
  sheetPressed: {
    opacity: 0.85,
    transform: [{ scale: 0.98 }]
  },
  sheetPrimary: {
    backgroundColor: colors.primary
  },
  sheetDanger: {
    backgroundColor: colors.danger
  },
  sheetCancel: {
    backgroundColor: colors.surfaceAlt
  },
  sheetButtonText: {
    ...typography.button
  },
  sheetPrimaryText: {
    color: colors.onPrimary
  },
  sheetDangerText: {
    color: '#ffffff'
  },
  sheetCancelText: {
    color: colors.ink
  }
});
