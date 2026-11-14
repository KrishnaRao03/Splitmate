import Constants from 'expo-constants';

import type {
  AuthResponse,
  Dashboard,
  DefaultSplit,
  Expense,
  ExpenseSearchResult,
  GroceryComparison,
  Group,
  GroupActivity,
  GroupDetail,
  MyInvite,
  Note,
  PaymentHandles,
  PersonBalance,
  ProfileQr,
  ReceiptScan,
  RewardsSummary,
  Task
} from '@/types';

const TOKEN_KEY = 'splitmate.mobile.token';

function trimSlash(value: string) {
  return value.replace(/\/+$/, '');
}

export function defaultApiBaseUrl() {
  const envUrl = process.env.EXPO_PUBLIC_SPLITMATE_API_URL;
  const configured = Constants.expoConfig?.extra?.apiBaseUrl as string | undefined;
  if (envUrl) {
    return trimSlash(envUrl);
  }
  if (configured) {
    return trimSlash(configured);
  }

  const hostUri = Constants.expoConfig?.hostUri || Constants.manifest2?.extra?.expoGo?.debuggerHost;
  const host = hostUri ? String(hostUri).split(':')[0] : '127.0.0.1';
  return `http://${host}:5000/api/mobile`;
}

export type ApiError = Error & { status?: number; isNetworkError?: boolean; data?: Record<string, unknown> };

const REQUEST_TIMEOUT_MS = 20000;

type UnauthorizedHandler = () => void;

export class SplitmateApi {
  private token: string | null = null;
  private onUnauthorized: UnauthorizedHandler | null = null;

  constructor(private baseUrl = defaultApiBaseUrl()) {}

  setBaseUrl(baseUrl: string) {
    this.baseUrl = trimSlash(baseUrl || defaultApiBaseUrl());
  }

  getBaseUrl() {
    return this.baseUrl;
  }

  setToken(token: string | null) {
    this.token = token;
  }

  /** Called when an authenticated request comes back 401 (expired/revoked token). */
  setUnauthorizedHandler(handler: UnauthorizedHandler | null) {
    this.onUnauthorized = handler;
  }

  async request<T>(path: string, options: RequestInit = {}, timeoutMs = REQUEST_TIMEOUT_MS): Promise<T> {
    const headers = new Headers(options.headers);
    headers.set('Accept', 'application/json');

    const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;
    if (options.body && !isFormData && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }
    if (this.token) {
      headers.set('Authorization', `Bearer ${this.token}`);
    }

    const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
    const timer = controller ? setTimeout(() => controller.abort(), timeoutMs) : null;

    let response: Response;
    try {
      response = await fetch(`${this.baseUrl}${path}`, {
        ...options,
        headers,
        signal: controller?.signal
      });
    } catch (cause) {
      const timedOut = cause instanceof Error && cause.name === 'AbortError';
      const error = new Error(
        timedOut
          ? 'The Splitmate server took too long to respond. Check your connection and try again.'
          : `Can't reach the Splitmate server at ${this.baseUrl}. Check your connection or the server address in Settings.`
      ) as ApiError;
      error.isNetworkError = true;
      throw error;
    } finally {
      if (timer) {
        clearTimeout(timer);
      }
    }

    const text = await response.text();
    let payload: any = null;
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        payload = { error: text };
      }
    }

    if (!response.ok) {
      const error = new Error(payload?.error || `Request failed (${response.status})`) as ApiError;
      error.status = response.status;
      error.data = payload ?? undefined;
      // A 401 on an authenticated request means the saved login is no longer valid.
      if (response.status === 401 && this.token && !path.startsWith('/auth/')) {
        this.onUnauthorized?.();
      }
      throw error;
    }

    return payload as T;
  }

  login(email: string, password: string) {
    return this.request<AuthResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password })
    });
  }

  register(name: string, email: string, password: string, confirmPassword: string, country: string) {
    return this.request<{ verification_required: boolean; otp_sent: boolean; user: { email: string } }>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ name, email, password, confirm_password: confirmPassword, country })
    });
  }

  /** An already-verified email gets `already_verified` and no token: the user signs in with their password. */
  verifyEmail(email: string, otp: string) {
    return this.request<Partial<AuthResponse> & { already_verified?: boolean; message?: string }>('/auth/verify-email', {
      method: 'POST',
      body: JSON.stringify({ email, otp })
    });
  }

  resendOtp(email: string) {
    return this.request<{ sent: boolean }>('/auth/resend-otp', {
      method: 'POST',
      body: JSON.stringify({ email })
    });
  }

  requestPasswordReset(email: string) {
    return this.request<{ sent: boolean; message: string }>('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email })
    });
  }

  me() {
    return this.request<{ user: AuthResponse['user']; currency_code: string }>('/me');
  }

  /** `currentPassword` is required by the server only when the email changes. */
  updateProfile(details: { name: string; email: string; currentPassword?: string; phone?: string; country?: string } & PaymentHandles) {
    const { currentPassword, ...rest } = details;
    return this.request<AuthResponse & { verification_required: boolean; otp_sent: boolean; interac_code_sent?: boolean }>('/me', {
      method: 'PATCH',
      body: JSON.stringify({ ...rest, current_password: currentPassword })
    });
  }

  verifyInterac(otp: string) {
    return this.request<{ user: AuthResponse['user'] }>('/me/interac/verify', {
      method: 'POST',
      body: JSON.stringify({ otp })
    });
  }

  resendInteracCode() {
    return this.request<{ sent: boolean }>('/me/interac/resend', { method: 'POST' });
  }

  /** Asks someone who owes you to approve sharing their Interac email; they get an email about it. */
  requestMoney(groupId: number, payerId: number) {
    return this.request<{ id: number; status: string }>(`/groups/${groupId}/money-requests`, {
      method: 'POST',
      body: JSON.stringify({ payer_id: payerId })
    });
  }

  answerMoneyRequest(requestId: number, answer: 'approve' | 'decline') {
    return this.request<{ status: string }>(`/money-requests/${requestId}/${answer}`, { method: 'POST' });
  }

  /** Changing the password revokes every token, so the reply carries a fresh one for this device. */
  updatePassword(currentPassword: string, newPassword: string, confirmPassword: string) {
    return this.request<AuthResponse & { updated: boolean }>('/me/password', {
      method: 'POST',
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword
      })
    });
  }

  /** Split one expense equally with friends found by email or phone; reuses their earlier Quick split group. */
  quickSplit(contacts: string[], description: string, amount: number) {
    return this.request<{ group: Group; expense: Expense }>('/quick-split', {
      method: 'POST',
      body: JSON.stringify({ contacts, description, amount })
    });
  }

  inviteSplitmate(email: string) {
    return this.request<{ message: string; invite_url?: string }>('/invite-splitmate', {
      method: 'POST',
      body: JSON.stringify({ email })
    });
  }

  dashboard() {
    return this.request<Dashboard>('/dashboard');
  }

  groups() {
    return this.request<Group[]>('/groups');
  }

  /** `currency` defaults to the creator's country currency on the server. */
  createGroup(name: string, currency?: string) {
    return this.request<Group>('/groups', {
      method: 'POST',
      body: JSON.stringify({ name, currency })
    });
  }

  groupDetail(groupId: number) {
    return this.request<GroupDetail>(`/groups/${groupId}`);
  }

  /** Sends an invite; the person joins once they accept it. */
  addMember(groupId: number, email: string) {
    return this.request<{ invited: boolean; already_member: boolean; message: string }>(`/groups/${groupId}/members`, {
      method: 'POST',
      body: JSON.stringify({ email })
    });
  }

  private expenseRequest(path: string, method: 'POST' | 'PUT', body: Record<string, unknown>, receipt?: { uri: string; name: string; mimeType?: string; file?: File }) {
    if (receipt) {
      const form = new FormData();
      form.append('payload', JSON.stringify(body));
      if (receipt.file) {
        form.append('receipt', receipt.file, receipt.name);
      } else {
        form.append('receipt', {
          uri: receipt.uri,
          name: receipt.name,
          type: receipt.mimeType || 'application/octet-stream'
        } as unknown as Blob);
      }
      return this.request(path, { method, body: form });
    }
    return this.request(path, {
      method,
      body: JSON.stringify(body)
    });
  }

  addExpense(groupId: number, body: Record<string, unknown>, receipt?: { uri: string; name: string; mimeType?: string; file?: File }) {
    return this.expenseRequest(`/groups/${groupId}/expenses`, 'POST', body, receipt);
  }

  updateExpense(expenseId: number, body: Record<string, unknown>, receipt?: { uri: string; name: string; mimeType?: string; file?: File }) {
    return this.expenseRequest(`/expenses/${expenseId}`, 'PUT', body, receipt);
  }

  /** Reads a receipt image on the server and returns its line items. */
  scanReceipt(receipt: { uri: string; name: string; mimeType?: string; file?: File }) {
    const form = new FormData();
    if (receipt.file) {
      form.append('receipt', receipt.file, receipt.name);
    } else {
      form.append('receipt', {
        uri: receipt.uri,
        name: receipt.name,
        type: receipt.mimeType || 'image/jpeg'
      } as unknown as Blob);
    }
    // Reading a receipt with the vision model can take well over the default timeout.
    return this.request<ReceiptScan>('/receipts/scan', { method: 'POST', body: form }, 90000);
  }

  deleteExpense(expenseId: number) {
    return this.request<{ deleted: boolean }>(`/expenses/${expenseId}`, { method: 'DELETE' });
  }

  clearExpenses(groupId: number) {
    return this.request<{ cleared: boolean }>(`/groups/${groupId}/expenses`, { method: 'DELETE' });
  }

  /** Records a payment made outside the app; it stays pending until the receiver confirms it. */
  recordPayment(groupId: number, receiverId: number, amount: string) {
    return this.request<{ id: number; status: string }>(`/groups/${groupId}/payments`, {
      method: 'POST',
      body: JSON.stringify({ receiver_id: receiverId, amount })
    });
  }

  confirmPayment(paymentId: number) {
    return this.request<{ confirmed: boolean }>(`/payments/${paymentId}/confirm`, { method: 'POST' });
  }

  declinePayment(paymentId: number) {
    return this.request<{ declined: boolean }>(`/payments/${paymentId}/decline`, { method: 'POST' });
  }

  logoutAllDevices() {
    return this.request<{ logged_out: boolean }>('/me/logout-all', { method: 'POST' });
  }

  settleSplit(splitId: number) {
    return this.request(`/splits/${splitId}/settle`, { method: 'POST' });
  }

  addTask(groupId: number, body: unknown) {
    return this.request<Task>(`/groups/${groupId}/tasks`, {
      method: 'POST',
      body: JSON.stringify(body)
    });
  }

  toggleTask(taskId: number) {
    return this.request<{ is_completed: boolean }>(`/tasks/${taskId}/toggle`, { method: 'POST' });
  }

  deleteTask(taskId: number) {
    return this.request<{ deleted: boolean }>(`/tasks/${taskId}`, { method: 'DELETE' });
  }

  addNote(groupId: number, body: unknown) {
    return this.request<Note>(`/groups/${groupId}/notes`, {
      method: 'POST',
      body: JSON.stringify(body)
    });
  }

  toggleNote(noteId: number) {
    return this.request<{ is_completed: boolean }>(`/notes/${noteId}/toggle`, { method: 'POST' });
  }

  deleteNote(noteId: number) {
    return this.request<{ deleted: boolean }>(`/notes/${noteId}`, { method: 'DELETE' });
  }

  updateNote(noteId: number, title: string, description: string) {
    return this.request<Note>(`/notes/${noteId}`, {
      method: 'PATCH',
      body: JSON.stringify({ title, description })
    });
  }

  // Price lookups can search store websites, so they get more time than other requests.
  compareGroceries(noteId: number, location = '') {
    const query = location ? `?location=${encodeURIComponent(location)}` : '';
    return this.request<GroceryComparison>(`/notes/${noteId}/grocery-comparison${query}`, {}, 60000);
  }

  /** Real store prices for a typed list like "apple, banana, 2 milk", cheapest store first. */
  compareGroceryList(items: string, location = '') {
    return this.request<GroceryComparison>('/grocery/compare', {
      method: 'POST',
      body: JSON.stringify({ items, location })
    }, 60000);
  }

  /** Creates (or reuses) an email invite; the reply carries the link and a QR code of it. */
  inviteToGroup(groupId: number, email: string) {
    return this.request<{ message: string; email: string; email_sent: boolean; invite_url: string; qr_rows: string[] }>(`/groups/${groupId}/invites`, {
      method: 'POST',
      body: JSON.stringify({ email })
    });
  }

  renameGroup(groupId: number, name: string) {
    return this.request<Group>(`/groups/${groupId}`, {
      method: 'PATCH',
      body: JSON.stringify({ name })
    });
  }

  /** The current admin hands the admin role to another member. */
  transferAdmin(groupId: number, userId: number) {
    return this.request<Group>(`/groups/${groupId}/admin`, {
      method: 'POST',
      body: JSON.stringify({ user_id: userId })
    });
  }

  /** Members (not the admin) can leave once they have no open balances in the group. */
  leaveGroup(groupId: number) {
    return this.request<{ left: boolean }>(`/groups/${groupId}/leave`, { method: 'POST' });
  }

  /** Admin only, and only for groups with no expense or payment history (history is never deleted). */
  deleteGroup(groupId: number) {
    return this.request<{ deleted: boolean }>(`/groups/${groupId}`, { method: 'DELETE' });
  }

  revokeGroupInvite(groupId: number, inviteId: number) {
    return this.request<{ revoked: boolean }>(`/groups/${groupId}/invites/${inviteId}`, { method: 'DELETE' });
  }

  updateMemberNickname(groupId: number, userId: number, nickname: string) {
    return this.request<{ nickname: string }>(`/groups/${groupId}/members/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify({ nickname })
    });
  }

  removeMember(groupId: number, userId: number) {
    return this.request<{ removed: boolean }>(`/groups/${groupId}/members/${userId}`, { method: 'DELETE' });
  }

  saveDefaultSplit(groupId: number, split: DefaultSplit) {
    return this.request<DefaultSplit>(`/groups/${groupId}/default-split`, {
      method: 'PUT',
      body: JSON.stringify(split)
    });
  }

  clearDefaultSplit(groupId: number) {
    return this.request<DefaultSplit>(`/groups/${groupId}/default-split`, { method: 'DELETE' });
  }

  groupActivity(groupId: number, filters: Record<string, string> = {}) {
    const query = Object.entries(filters)
      .filter(([, value]) => value.trim())
      .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value.trim())}`)
      .join('&');
    return this.request<GroupActivity>(`/groups/${groupId}/activity${query ? `?${query}` : ''}`);
  }

  searchExpenses(groupId: number, params: Record<string, string> = {}) {
    const query = Object.entries(params)
      .filter(([, value]) => value.trim())
      .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value.trim())}`)
      .join('&');
    return this.request<ExpenseSearchResult[]>(`/groups/${groupId}/expenses/search${query ? `?${query}` : ''}`);
  }

  exportData() {
    return this.request<Record<string, unknown>>('/export');
  }

  /**
   * Fetches a group's activity log as raw CSV text. Bypasses `request()`
   * because that method always attempts `JSON.parse` on the response body,
   * which would mangle a CSV payload.
   */
  async exportActivityCsv(groupId: number): Promise<string> {
    const headers = new Headers();
    if (this.token) {
      headers.set('Authorization', `Bearer ${this.token}`);
    }

    let response: Response;
    try {
      response = await fetch(`${this.baseUrl}/groups/${groupId}/activity.csv`, { headers });
    } catch {
      const error = new Error(
        `Can't reach the Splitmate server at ${this.baseUrl}. Check your connection or the server address in Settings.`
      ) as ApiError;
      error.isNetworkError = true;
      throw error;
    }

    const text = await response.text();
    if (!response.ok) {
      const error = new Error(text || `Request failed (${response.status})`) as ApiError;
      error.status = response.status;
      if (response.status === 401 && this.token) {
        this.onUnauthorized?.();
      }
      throw error;
    }

    return text;
  }

  resolveUrl(path: string) {
    if (/^https?:\/\//i.test(path)) {
      return path;
    }
    const origin = this.baseUrl.replace(/\/api\/mobile$/, '');
    return `${origin}${path.startsWith('/') ? '' : '/'}${path}`;
  }

  upcomingReminders() {
    return this.request<Task[]>('/reminders/upcoming');
  }

  allNotes() {
    return this.request<Note[]>('/notes');
  }

  allTasks() {
    return this.request<Task[]>('/tasks');
  }

  peopleBalances() {
    return this.request<PersonBalance[]>('/balances/people');
  }

  registerDevice(expoPushToken: string, platform: string) {
    return this.request<{ registered: boolean }>('/devices', {
      method: 'POST',
      body: JSON.stringify({ expo_push_token: expoPushToken, platform })
    });
  }

  rewards() {
    return this.request<RewardsSummary>('/rewards');
  }

  /** Stripe's hosted payment page for Splitmate Pro. `returnUrl` is where Stripe sends the person back. */
  membershipCheckout(interval: 'month' | 'year', returnUrl?: string) {
    return this.request<{ url: string }>('/membership/checkout', {
      method: 'POST',
      body: JSON.stringify({ interval, return_url: returnUrl })
    });
  }

  /** Stripe's page for changing the card, switching plan or cancelling. */
  membershipPortal(returnUrl?: string) {
    return this.request<{ url: string }>('/membership/portal', {
      method: 'POST',
      body: JSON.stringify({ return_url: returnUrl })
    });
  }

  profileQr() {
    return this.request<ProfileQr>('/me/qr');
  }

  myInvites() {
    return this.request<MyInvite[]>('/invites');
  }

  acceptInvite(inviteId: number) {
    return this.request<{ joined: boolean; message: string; group: Group }>(`/invites/${inviteId}/accept`, { method: 'POST' });
  }

  acceptInviteLink(link: string) {
    return this.request<{ joined: boolean; message: string; group: Group }>('/invites/accept-link', {
      method: 'POST',
      body: JSON.stringify({ link })
    });
  }
}

export const api = new SplitmateApi();
export { TOKEN_KEY };
