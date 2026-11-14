import { ReactNode } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  RefreshControl,
  ScrollView,
  StyleProp,
  StyleSheet,
  View,
  ViewStyle
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { colors, spacing } from '@/theme/colors';


type ScreenProps = {
  children: ReactNode;
  scroll?: boolean;
  contentStyle?: StyleProp<ViewStyle>;
  /** Pass both to enable pull-to-refresh. */
  onRefresh?: () => void;
  refreshing?: boolean;
  /** No side or top padding, so a screen can draw edge-to-edge sections. */
  flush?: boolean;
  /** Page colour behind the content (defaults to the theme background). */
  background?: string;
};

export function Screen({ children, scroll = true, contentStyle, onRefresh, refreshing = false, flush = false, background }: ScreenProps) {
  const content = scroll ? (
    <ScrollView
      contentContainerStyle={[styles.content, flush && styles.flush]}
      keyboardShouldPersistTaps="handled"
      refreshControl={onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} colors={[colors.primary]} /> : undefined}
    >
      <View style={[styles.inner, contentStyle]}>{children}</View>
    </ScrollView>
  ) : (
    <View style={[styles.content, flush && styles.flush, styles.flex]}>
      <View style={[styles.inner, styles.flex, contentStyle]}>{children}</View>
    </View>
  );

  return (
    <View style={[styles.background, background ? { backgroundColor: background } : null]}>
      <SafeAreaView style={styles.safeArea}>
          <KeyboardAvoidingView
            behavior={Platform.OS === 'ios' ? 'padding' : undefined}
            style={styles.flex}
          >
            {content}
          </KeyboardAvoidingView>
        </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  background: {
    flex: 1,
    backgroundColor: colors.bg
  },
  flush: {
    flexGrow: 1,
    paddingHorizontal: 0,
    paddingTop: 0,
    paddingBottom: 0
  },
  safeArea: {
    flex: 1
  },
  flex: {
    flex: 1
  },
  content: {
    paddingHorizontal: spacing.md,
    paddingTop: spacing.md,
    paddingBottom: spacing.xl
  },
  inner: {
    width: '100%',
    maxWidth: 880,
    alignSelf: 'center',
    gap: spacing.md
  }
});
