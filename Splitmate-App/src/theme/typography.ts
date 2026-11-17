import { TextStyle } from 'react-native';

import { fonts } from '@/theme/colors';

/**
 * Every text style sits on the Tailwind type scale (12/16, 14/20, 16/24, 18/28, 20/28, 24/32, 30/36)
 * and maps to one named style from the design guide, shown beside each key.
 */
export const typography: Record<
  'display' | 'h1' | 'h2' | 'h3' | 'body' | 'bodyStrong' | 'label' | 'caption' | 'button',
  TextStyle
> = {
  // Heading 4
  display: { fontSize: 30, lineHeight: 36, fontWeight: '600', fontFamily: fonts.semiBold },
  // Heading 5
  h1: { fontSize: 24, lineHeight: 32, fontWeight: '600', fontFamily: fonts.semiBold },
  // Heading 6
  h2: { fontSize: 20, lineHeight: 28, fontWeight: '600', fontFamily: fonts.semiBold },
  // Title 3
  h3: { fontSize: 16, lineHeight: 24, fontWeight: '500', fontFamily: fonts.medium },
  // Body 6
  body: { fontSize: 14, lineHeight: 20, fontWeight: '400', fontFamily: fonts.regular },
  // Body 4
  bodyStrong: { fontSize: 14, lineHeight: 20, fontWeight: '600', fontFamily: fonts.semiBold },
  // Title 4
  label: { fontSize: 14, lineHeight: 20, fontWeight: '500', fontFamily: fonts.medium },
  // Caption 4
  caption: { fontSize: 12, lineHeight: 16, fontWeight: '500', fontFamily: fonts.medium },
  // Button-md
  button: { fontSize: 16, lineHeight: 24, fontWeight: '600', fontFamily: fonts.semiBold }
};
