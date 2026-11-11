import { StyleSheet, Text as NativeText, TextProps, TextStyle } from 'react-native';

import { fonts } from '@/theme/colors';

function fontFamilyFor(style: TextProps['style']) {
  const flattened = StyleSheet.flatten(style) as TextStyle | undefined;
  const rawWeight = flattened?.fontWeight;
  const weight = typeof rawWeight === 'number' ? rawWeight : Number.parseInt(String(rawWeight || 400), 10);

  if (weight >= 800) {
    return fonts.extraBold;
  }
  if (weight >= 700) {
    return fonts.bold;
  }
  if (weight >= 600) {
    return fonts.semiBold;
  }
  if (weight >= 500) {
    return fonts.medium;
  }
  return fonts.regular;
}

export function AppText({ style, ...props }: TextProps) {
  return (
    <NativeText
      {...props}
      style={[style, { fontFamily: fontFamilyFor(style), fontWeight: 'normal' }]}
    />
  );
}
