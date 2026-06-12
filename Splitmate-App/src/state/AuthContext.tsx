import * as SecureStore from 'expo-secure-store';
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { api, TOKEN_KEY } from '@/api/client';
import type { User } from '@/types';

type AuthState = {
  apiBaseUrl: string;
  currencyCode: string;
  isLoading: boolean;
  token: string | null;
  user: User | null;
  setApiBaseUrl: (url: string) => void;
  signIn: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<string>;
  verifyEmail: (email: string, otp: string) => Promise<void>;
  resendOtp: (email: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);
const API_URL_KEY = 'splitmate.mobile.api-url';

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
    await SecureStore.setItemAsync(TOKEN_KEY, nextToken);
  }, []);

  useEffect(() => {
    async function bootstrap() {
      try {
        const savedApiUrl = await SecureStore.getItemAsync(API_URL_KEY);
        if (savedApiUrl) {
          api.setBaseUrl(savedApiUrl);
          setApiBaseUrlState(savedApiUrl);
        }

        const savedToken = await SecureStore.getItemAsync(TOKEN_KEY);
        if (!savedToken) {
          return;
        }

        api.setToken(savedToken);
        const profile = await api.me();
        setToken(savedToken);
        setUser(profile.user);
        setCurrencyCode(profile.currency_code || 'CAD');
      } catch (error) {
        await SecureStore.deleteItemAsync(TOKEN_KEY);
        api.setToken(null);
      } finally {
        setIsLoading(false);
      }
    }

    bootstrap();
  }, []);

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
      SecureStore.setItemAsync(API_URL_KEY, api.getBaseUrl()).catch(() => undefined);
    },
    signIn: async (email: string, password: string) => {
      const response = await api.login(email.trim(), password);
      await applySession(response.token, response.user, response.currency_code);
    },
    register: async (name: string, email: string, password: string) => {
      const response = await api.register(name.trim(), email.trim(), password);
      return response.user.email;
    },
    verifyEmail: async (email: string, otp: string) => {
      const response = await api.verifyEmail(email.trim(), otp.trim());
      await applySession(response.token, response.user, response.currency_code);
    },
    resendOtp: async (email: string) => {
      await api.resendOtp(email.trim());
    },
    signOut: async () => {
      await SecureStore.deleteItemAsync(TOKEN_KEY);
      api.setToken(null);
      setToken(null);
      setUser(null);
    }
  }), [apiBaseUrl, applySession, currencyCode, isLoading, token, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider');
  }
  return context;
}
