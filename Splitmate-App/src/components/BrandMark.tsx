import { Image, ImageStyle, StyleProp } from 'react-native';

import { activeColorScheme } from '@/theme/colors';

// The same artwork as the website (Splitmate-Web/app/static/images), with dark-mode versions.
const MARK = { light: require('../../assets/images/logo-mark.png'), dark: require('../../assets/images/logo-mark-dark.png') };
const WORDMARK = { light: require('../../assets/images/logo.png'), dark: require('../../assets/images/logo-dark.png') };

type Props = {
  size?: number;
  style?: StyleProp<ImageStyle>;
};

/** The split-coin logo mark. */
export function BrandMark({ size = 40, style }: Props) {
  return (
    <Image
      source={MARK[activeColorScheme()]}
      style={[{ width: size, height: size }, style]}
      resizeMode="contain"
      accessibilityLabel="Splitmate"
    />
  );
}

/** The logo mark with the "splitmate" wordmark, used at the top of the app and the website. */
export function BrandLogo({ size = 180, style }: Props) {
  return (
    <Image
      source={WORDMARK[activeColorScheme()]}
      style={[{ width: size, height: size * 0.218 }, style]}
      resizeMode="contain"
      accessibilityLabel="Splitmate"
    />
  );
}
