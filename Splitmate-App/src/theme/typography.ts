import { TextStyle } from 'react-native';

import { fonts } from '@/theme/colors';

export const typography: Record<
  'display' | 'h1' | 'h2' | 'h3' | 'body' | 'bodyStrong' | 'label' | 'caption',
  TextStyle
> = {
  display: {
    fontSize: 30,
    fontWeight: '700',
    fontFamily: fonts.bold
  },
  h1: {
    fontSize: 24,
    fontWeight: '700',
    fontFamily: fonts.bold
  },
  h2: {
    fontSize: 20,
    fontWeight: '700',
    fontFamily: fonts.bold
  },
  h3: {
    fontSize: 17,
    fontWeight: '600',
    fontFamily: fonts.semiBold
  },
  body: {
    fontSize: 15,
    fontWeight: '400',
    fontFamily: fonts.regular
  },
  bodyStrong: {
    fontSize: 15,
    fontWeight: '600',
    fontFamily: fonts.semiBold
  },
  label: {
    fontSize: 13,
    fontWeight: '600',
    fontFamily: fonts.semiBold
  },
  caption: {
    fontSize: 12,
    fontWeight: '500',
    fontFamily: fonts.medium
  }
};
