/**
 * Links that open the web build with something to do: ?invite=<token> from a group invite email,
 * ?membership=success|cancelled from Stripe. Read once when the app loads and the address bar is
 * cleaned straight away; screens take each one when they are ready (after sign-in).
 */
type Location = { search: string; pathname: string };
type History = { replaceState: (data: null, title: string, url: string) => void };

const location = (globalThis as unknown as { location?: Location }).location;
const params = location?.search ? new URLSearchParams(location.search) : null;
const pending: { invite: string | null; membership: string | null } = {
  invite: params?.get('invite') || null,
  membership: params?.get('membership') || null
};

if (pending.invite || pending.membership) {
  (globalThis as unknown as { history?: History }).history?.replaceState(null, '', location?.pathname || '/');
}

export function hasPendingInvite() {
  return Boolean(pending.invite);
}

/** Returns the value once, then forgets it. */
export function takeLaunchLink(key: keyof typeof pending) {
  const value = pending[key];
  pending[key] = null;
  return value;
}
