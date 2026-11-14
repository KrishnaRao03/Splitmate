import { ReactNode } from 'react';
import {
  Image,
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

import { activeColorScheme, colors, spacing } from '@/theme/colors';

// Soft indigo and teal glow, matching the logo; a light overlay keeps text readable.
const BACKGROUND = activeColorScheme() === 'dark'
  ? require('../../assets/images/background-dark.jpg')
  : require('../../assets/images/background.jpg');
const OVERLAY = activeColorScheme() === 'dark' ? 'rgba(12, 14, 26, 0.35)' : 'rgba(246, 247, 251, 0.35)';

type ScreenProps = {
  children: ReactNode;
  scroll?: boolean;
  contentStyle?: StyleProp<ViewStyle>;
  /** Pass both to enable pull-to-refresh. */
  onRefresh?: () => void;
  refreshing?: boolean;
};

export function Screen({ children, scroll = true, contentStyle, onRefresh, refreshing = false }: ScreenProps) {
  const content = scroll ? (
    <ScrollView
      contentContainerStyle={styles.content}
      keyboardShouldPersistTaps="handled"
      refreshControl={onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} colors={[colors.primary]} /> : undefined}
    >
      <View style={[styles.inner, contentStyle]}>{children}</View>
    </ScrollView>
  ) : (
    <View style={[styles.content, styles.flex]}>
      <View style={[styles.inner, styles.flex, contentStyle]}>{children}</View>
    </View>
  );

  return (
    <View style={styles.background}>
      <Image source={BACKGROUND} resizeMode="cover" style={styles.backgroundImage} />
      <View style={styles.overlay}>
        <SafeAreaView style={styles.safeArea}>
          <KeyboardAvoidingView
            behavior={Platform.OS === 'ios' ? 'padding' : undefined}
            style={styles.flex}
          >
            {content}
          </KeyboardAvoidingView>
        </SafeAreaView>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  background: {
    flex: 1,
    backgroundColor: colors.bg
  },
  // Explicit size: on the web an Image keeps its own height unless told to fill.
  backgroundImage: {
    position: 'absolute',
    top: 0,
    left: 0,
    width: '100%',
    height: '100%'
  },
  overlay: {
    flex: 1,
    backgroundColor: OVERLAY
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
