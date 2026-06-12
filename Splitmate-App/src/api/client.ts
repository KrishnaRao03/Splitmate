import Constants from 'expo-constants';

import type { AuthResponse, Group, GroupDetail, Note, Task } from '@/types';

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

export type ApiError = Error & { status?: number };

export class SplitmateApi {
  private token: string | null = null;

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

  async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers = new Headers(options.headers);
    headers.set('Accept', 'application/json');

    if (options.body && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }
    if (this.token) {
      headers.set('Authorization', `Bearer ${this.token}`);
    }

    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers
    });

    const text = await response.text();
    const payload = text ? JSON.parse(text) : null;

    if (!response.ok) {
      const error = new Error(payload?.error || 'Request failed') as ApiError;
      error.status = response.status;
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

  register(name: string, email: string, password: string) {
    return this.request<{ verification_required: boolean; otp_sent: boolean; user: { email: string } }>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ name, email, password, confirm_password: password })
    });
  }

  verifyEmail(email: string, otp: string) {
    return this.request<AuthResponse>('/auth/verify-email', {
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

  me() {
    return this.request<{ user: AuthResponse['user']; currency_code: string }>('/me');
  }

  groups() {
    return this.request<Group[]>('/groups');
  }

  createGroup(name: string) {
    return this.request<Group>('/groups', {
      method: 'POST',
      body: JSON.stringify({ name })
    });
  }

  groupDetail(groupId: number) {
    return this.request<GroupDetail>(`/groups/${groupId}`);
  }

  addMember(groupId: number, email: string) {
    return this.request(`/groups/${groupId}/members`, {
      method: 'POST',
      body: JSON.stringify({ email })
    });
  }

  addExpense(groupId: number, body: unknown) {
    return this.request(`/groups/${groupId}/expenses`, {
      method: 'POST',
      body: JSON.stringify(body)
    });
  }

  recordPayment(groupId: number, receiverId: number, amount: string) {
    return this.request(`/groups/${groupId}/payments`, {
      method: 'POST',
      body: JSON.stringify({ receiver_id: receiverId, amount })
    });
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

  upcomingReminders() {
    return this.request<Task[]>('/reminders/upcoming');
  }

  registerDevice(expoPushToken: string, platform: string) {
    return this.request<{ registered: boolean }>('/devices', {
      method: 'POST',
      body: JSON.stringify({ expo_push_token: expoPushToken, platform })
    });
  }
}

export const api = new SplitmateApi();
export { TOKEN_KEY };
