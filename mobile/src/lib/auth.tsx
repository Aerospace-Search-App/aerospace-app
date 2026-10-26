import { useQueryClient } from '@tanstack/react-query';
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import { api, ApiError, endpoints } from './api';
import { storage } from './storage';
import type { User } from './types';

const TOKEN_KEY = 'aerostd.token';
const USER_KEY = 'aerostd.user';

interface AuthState {
  ready: boolean;
  user: User | null;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (username: string, email: string, password: string, acceptTerms: boolean) => Promise<void>;
  signOut: () => Promise<void>;
  updateUser: (u: User) => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState<User | null>(null);

  const clear = useCallback(async () => {
    api.setToken(null);
    setUser(null);
    qc.clear();
    await Promise.all([storage.remove(TOKEN_KEY), storage.remove(USER_KEY)]);
  }, [qc]);

  useEffect(() => {
    api.setUnauthorizedHandler(() => void clear());
    (async () => {
      await api.loadServer();
      const [t, u] = await Promise.all([storage.get(TOKEN_KEY), storage.get(USER_KEY)]);
      if (t && u) {
        api.setToken(t);
        try {
          setUser(JSON.parse(u));
        } catch {
          await clear();
        }
        // Arka planda doğrula; sunucuya ulaşılamazsa çevrimdışı oturum korunur
        endpoints
          .me()
          .then((fresh) => {
            setUser(fresh);
            void storage.set(USER_KEY, JSON.stringify(fresh));
          })
          .catch((e) => {
            if (e instanceof ApiError && e.status === 401) void clear();
          });
      }
      setReady(true);
    })();
    return () => api.setUnauthorizedHandler(null);
  }, [clear]);

  const persist = useCallback(async (token: string, u: User) => {
    api.setToken(token);
    await Promise.all([storage.set(TOKEN_KEY, token), storage.set(USER_KEY, JSON.stringify(u))]);
    setUser(u);
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      ready,
      user,
      signIn: async (email, password) => {
        const r = await endpoints.login(email.trim(), password);
        await persist(r.access_token, r.user);
      },
      signUp: async (username, email, password, acceptTerms) => {
        const r = await endpoints.register(username.trim(), email.trim(), password, acceptTerms);
        await persist(r.access_token, r.user);
      },
      signOut: clear,
      updateUser: (u) => {
        setUser(u);
        void storage.set(USER_KEY, JSON.stringify(u));
      },
    }),
    [ready, user, persist, clear],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth, AuthProvider içinde kullanılmalı');
  return ctx;
}
