import * as SecureStore from 'expo-secure-store';
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { Platform } from 'react-native';

import { api, TOKEN_KEY } from '@/api/client';
import type { ApiError } from '@/api/client';
import type { PaymentHandles, User } from '@/types';

type AuthState = {
  apiBaseUrl: string;
  currencyCode: string;
  isLoading: boolean;
  token: string | null;
  user: User | null;
  setApiBaseUrl: (url: string) => void;
  signIn: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string, confirmPassword: string, country: string) => Promise<{ email: string; otpSent: boolean }>;
  verifyEmail: (email: string, otp: string) => Promise<void>;
  resendOtp: (email: string) => Promise<boolean>;
  requestPasswordReset: (email: string) => Promise<void>;
  updateProfile: (details: { name: string; email: string; currentPassword?: string; phone?: string; country?: string } & PaymentHandles) => Promise<{ verificationRequired: boolean; otpSent: boolean; interacCodeSent: boolean }>;
  updatePassword: (currentPassword: string, newPassword: string, confirmPassword: string) => Promise<void>;
  /** Re-reads the signed-in user, e.g. after the Interac email is confirmed. */
  reloadUser: () => Promise<void>;
  signOut: () => Promise<void>;
  signOutEverywhere: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);
const API_URL_KEY = 'splitmate.mobile.api-url';

type WebStorage = {
  getItem: (key: string) => string | null;
  setItem: (key: string, value: string) => void;
  removeItem: (key: string) => void;
};

function webStorage() {
  if (Platform.OS !== 'web') {
    return null;
  }
  return (globalThis as unknown as { localStorage?: WebStorage }).localStorage || null;
}

async function getStoredValue(key: string) {
  const storage = webStorage();
  if (storage) {
    return storage.getItem(key);
  }
  return SecureStore.getItemAsync(key);
}

async function setStoredValue(key: string, value: string) {
  const storage = webStorage();
  if (storage) {
    storage.setItem(key, value);
    return;
  }
  await SecureStore.setItemAsync(key, value);
}

async function deleteStoredValue(key: string) {
  const storage = webStorage();
  if (storage) {
    storage.removeItem(key);
    return;
  }
  await SecureStore.deleteItemAsync(key);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isLoading, setIsLoading] = useState(true);
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [currencyCode, setCurrencyCode] = useState('CAD');
  const [apiBaseUrl, setApiBaseUrlState] = useState(api.getBaseUrl());

  const applySession = useCallback(async (nextToken: string, nextUser: User, nextCurrency: string) => {
    api.setToken(nextToken);
    setToken(nextToken);
    setUser(nextUser);
    setCurrencyCode(nextCurrency || 'CAD');
    await setStoredValue(TOKEN_KEY, nextToken);
  }, []);

  useEffect(() => {
    async function bootstrap() {
      try {
        const savedApiUrl = await getStoredValue(API_URL_KEY);
        if (savedApiUrl) {
          api.setBaseUrl(savedApiUrl);
          setApiBaseUrlState(savedApiUrl);
        }

        const savedToken = await getStoredValue(TOKEN_KEY);
        if (!savedToken) {
          return;
        }

        api.setToken(savedToken);
        const profile = await api.me();
        setToken(savedToken);
        setUser(profile.user);
        setCurrencyCode(profile.currency_code || 'CAD');
      } catch (error) {
        // Only discard the saved login when the server says it is invalid.
        // A network failure must not sign the user out.
        if ((error as ApiError).status === 401) {
          await deleteStoredValue(TOKEN_KEY).catch(() => undefined);
          api.setToken(null);
        } else {
          const savedToken = await getStoredValue(TOKEN_KEY).catch(() => null);
          if (savedToken) {
            setToken(savedToken);
          }
        }
      } finally {
        setIsLoading(false);
      }
    }

    bootstrap();
  }, []);

  const clearSession = useCallback(async () => {
    await deleteStoredValue(TOKEN_KEY).catch(() => undefined);
    api.setToken(null);
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    api.setUnauthorizedHandler(() => {
      clearSession();
    });
    return () => api.setUnauthorizedHandler(null);
  }, [clearSession]);

  const value = useMemo<AuthState>(() => ({
    apiBaseUrl,
    currencyCode,
    isLoading,
    token,
    user,
    setApiBaseUrl: (url: string) => {
      const nextUrl = url.trim();
      api.setBaseUrl(nextUrl);
      setApiBaseUrlState(api.getBaseUrl());
      setStoredValue(API_URL_KEY, api.getBaseUrl()).catch(() => undefined);
    },
    signIn: async (email: string, password: string) => {
      const response = await api.login(email.trim(), password);
      await applySession(response.token, response.user, response.currency_code);
    },
    register: async (name: string, email: string, password: string, confirmPassword: string, country: string) => {
      const response = await api.register(name.trim(), email.trim(), password, confirmPassword, country);
      return { email: response.user.email, otpSent: response.otp_sent };
    },
    verifyEmail: async (email: string, otp: string) => {
      const response = await api.verifyEmail(email.trim(), otp.trim());
      if (!response.token || !response.user) {
        throw new Error(response.message || 'This email is already verified. Sign in with your password.');
      }
      await applySession(response.token, response.user, response.currency_code || 'CAD');
    },
    resendOtp: async (email: string) => {
      const response = await api.resendOtp(email.trim());
      return response.sent;
    },
    requestPasswordReset: async (email: string) => {
      await api.requestPasswordReset(email.trim());
    },
    updateProfile: async details => {
      const response = await api.updateProfile({ ...details, name: details.name.trim(), email: details.email.trim() });
      await applySession(response.token, response.user, response.currency_code);
      return {
        verificationRequired: response.verification_required,
        otpSent: response.otp_sent,
        interacCodeSent: Boolean(response.interac_code_sent)
      };
    },
    updatePassword: async (currentPassword: string, newPassword: string, confirmPassword: string) => {
      // The server revokes every old token on a password change and returns a new one for this device.
      const response = await api.updatePassword(currentPassword, newPassword, confirmPassword);
      await applySession(response.token, response.user, response.currency_code);
    },
    reloadUser: async () => {
      const profile = await api.me();
      setUser(profile.user);
    },
    signOut: clearSession,
    signOutEverywhere: async () => {
      await api.logoutAllDevices();
      await clearSession();
    }
  }), [apiBaseUrl, applySession, clearSession, currencyCode, isLoading, token, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider');
  }
  return context;
}
