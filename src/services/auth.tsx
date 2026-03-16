import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { User } from '@supabase/supabase-js';
import { supabase } from '@/integrations/supabase/client';
import { logApiError } from './apiErrorLog';

const PROJECT_ID = import.meta.env.VITE_SUPABASE_PROJECT_ID;
const PROXY_URL = `https://${PROJECT_ID}.supabase.co/functions/v1/api-proxy`;

async function proxyFetch(path: string, init?: RequestInit): Promise<Response> {
  const { data: { session } } = await supabase.auth.getSession();
  const token = session?.access_token;
  return fetch(PROXY_URL, {
    ...init,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      'x-proxy-path': path,
      ...(init?.headers || {}),
    },
  });
}

export interface AuthUser {
  accountName: string;
}

interface SessionPayload {
  status: 'connected' | 'disconnected' | 'session_expired';
  accountName?: string | null;
  expiresAt?: string | null;
}

interface AuthContextValue {
  /* Supabase / Lovable Cloud auth */
  supabaseUser: User | null;
  isAuthenticated: boolean;
  isApproved: boolean;
  signIn: (email: string, password: string) => Promise<string | null>;
  signUp: (email: string, password: string) => Promise<string | null>;
  signOut: () => Promise<void>;

  /* PoE session auth (unchanged) */
  user: AuthUser | null;
  login: (poeSessionId: string) => Promise<boolean>;
  logout: () => void;
  refreshSession: () => Promise<void | SessionPayload>;
  sessionState: 'connected' | 'disconnected' | 'session_expired';
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextValue>({
  supabaseUser: null,
  isAuthenticated: false,
  isApproved: false,
  signIn: async () => null,
  signUp: async () => null,
  signOut: async () => {},

  user: null,
  login: async () => false,
  logout: () => {},
  refreshSession: async () => {},
  sessionState: 'disconnected',
  isLoading: true,
});

export const useAuth = () => useContext(AuthContext);

/* ---------- PoE session helpers (unchanged) ---------- */

async function fetchSession(): Promise<SessionPayload> {
  try {
    const response = await proxyFetch('/api/v1/auth/session');
    if (!response.ok) {
      logApiError({ path: '/api/v1/auth/session', statusCode: response.status, errorCode: 'auth_session', message: `Session check failed (${response.status})` });
      return { status: 'disconnected' };
    }
    return (await response.json()) as SessionPayload;
  } catch (err) {
    logApiError({ path: '/api/v1/auth/session', errorCode: 'network_error', message: err instanceof Error ? err.message : 'Network error' });
    return { status: 'disconnected' };
  }
}

/* ---------- Provider ---------- */

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  /* Supabase auth state */
  const [supabaseUser, setSupabaseUser] = useState<User | null>(null);
  const [supabaseReady, setSupabaseReady] = useState(false);
  const [isApproved, setIsApproved] = useState(false);

  const checkApproval = useCallback(async (userId: string) => {
    const { data } = await supabase
      .from('approved_users')
      .select('id')
      .eq('user_id', userId)
      .maybeSingle();
    setIsApproved(!!data);
  }, []);

  useEffect(() => {
    // Set up listener FIRST
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSupabaseUser(session?.user ?? null);
      if (session?.user) {
        checkApproval(session.user.id);
      } else {
        setIsApproved(false);
      }
    });

    // Then check existing session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSupabaseUser(session?.user ?? null);
      if (session?.user) {
        checkApproval(session.user.id).then(() => setSupabaseReady(true));
      } else {
        setSupabaseReady(true);
      }
    });

    return () => subscription.unsubscribe();
  }, [checkApproval]);

  const signIn = useCallback(async (email: string, password: string): Promise<string | null> => {
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    return error ? error.message : null;
  }, []);

  const signUp = useCallback(async (email: string, password: string): Promise<string | null> => {
    const { error } = await supabase.auth.signUp({ email, password });
    return error ? error.message : null;
  }, []);

  const signOutFn = useCallback(async () => {
    await supabase.auth.signOut();
  }, []);

  /* PoE session auth state (unchanged) */
  const [user, setUser] = useState<AuthUser | null>(null);
  const [sessionState, setSessionState] = useState<'connected' | 'disconnected' | 'session_expired'>('disconnected');
  const [isLoading, setIsLoading] = useState(true);

  const refreshSession = useCallback(async (): Promise<SessionPayload> => {
    const payload = await fetchSession();
    if (payload.status === 'connected' && payload.accountName) {
      setUser({ accountName: payload.accountName });
      setSessionState('connected');
      return payload;
    }
    setUser(null);
    setSessionState(payload.status);
    return payload;
  }, []);

  useEffect(() => {
    refreshSession().finally(() => setIsLoading(false));
  }, [refreshSession]);

  const login = useCallback(async (poeSessionId: string): Promise<boolean> => {
    try {
      const response = await proxyFetch('/api/v1/auth/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ poeSessionId }),
      });
      if (!response.ok) {
        logApiError({ path: '/api/v1/auth/session', statusCode: response.status, errorCode: 'auth_login', message: `Login failed (${response.status})` });
      }
    } catch (err) {
      logApiError({ path: '/api/v1/auth/session', errorCode: 'network_error', message: err instanceof Error ? err.message : 'Network error' });
      return false;
    }
    const result = await refreshSession();
    return result.status === 'connected' && !!result.accountName;
  }, [refreshSession]);

  const logout = useCallback(() => {
    proxyFetch('/api/v1/auth/logout', {
      method: 'POST',
    }).finally(() => {
      setUser(null);
      setSessionState('disconnected');
    });
  }, []);

  const isAuthenticated = !!supabaseUser;
  const combinedLoading = !supabaseReady || isLoading;

  return (
    <AuthContext.Provider value={{
      supabaseUser,
      isAuthenticated,
      isApproved,
      signIn,
      signUp,
      signOut: signOutFn,
      user,
      login,
      logout,
      refreshSession,
      sessionState,
      isLoading: combinedLoading,
    }}>
      {children}
    </AuthContext.Provider>
  );
};
