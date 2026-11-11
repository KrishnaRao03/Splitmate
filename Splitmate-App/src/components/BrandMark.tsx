import { StyleSheet, View, ViewStyle } from 'react-native';

import { AppText as Text } from '@/components/AppText';
import { colors, radius } from '@/theme/colors';

type Props = {
  size?: number;
  style?: ViewStyle;
};

export function BrandMark({ size = 40, style }: Props) {
  return (
    <View style={[styles.mark, { width: size, height: size, borderRadius: radius.md }, style]}>
      <View style={styles.accentLine} />
      <Text style={[styles.letter, { fontSize: Math.round(size * 0.43) }]}>S</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  mark: {
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
    backgroundColor: colors.primary
  },
  accentLine: {
    position: 'absolute',
    right: -6,
    bottom: -10,
    width: 26,
    height: 42,
    borderRadius: 13,
    backgroundColor: colors.accent,
    opacity: 0.95,
    transform: [{ rotate: '35deg' }]
  },
  letter: {
    color: colors.white,
    fontWeight: '900'
  }
});
