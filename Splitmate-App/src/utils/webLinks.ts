import { Linking } from 'react-native';

import { api } from '@/api/client';

/** Pages on the Splitmate website, which lives at the API's host. */
export function websiteUrl(path: string) {
  return api.getBaseUrl().replace(/\/api\/mobile\/?$/, '') + path;
}

export function openWebsitePage(path: '/privacy' | '/terms' | '/delete-account') {
  return Linking.openURL(websiteUrl(path));
}
