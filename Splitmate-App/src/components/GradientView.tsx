import { ReactNode } from 'react';
import { Platform, StyleProp, View, ViewStyle } from 'react-native';

type Props = {
  colors: readonly string[];
  /** CSS angle, e.g. '135deg' for top-left to bottom-right. */
  angle?: string;
  style?: StyleProp<ViewStyle>;
  children?: ReactNode;
};

/**
 * A linear gradient without an extra package: the web build uses CSS, native uses React Native's
 * built-in background gradients. The first colour is the fallback where gradients aren't drawn.
 */
export function GradientView({ colors, angle = '135deg', style, children }: Props) {
  return <View style={[gradientFill(colors, angle), style]}>{children}</View>;
}

/** The style for a gradient background, for components that aren't a plain View (e.g. Pressable). */
export function gradientFill(colors: readonly string[], angle = '135deg'): ViewStyle {
  const gradient = `linear-gradient(${angle}, ${colors.join(', ')})`;
  return {
    backgroundColor: colors[0],
    ...(Platform.OS === 'web' ? { backgroundImage: gradient } : { experimental_backgroundImage: gradient })
  } as unknown as ViewStyle;
}
