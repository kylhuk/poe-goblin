import React, { createContext, useCallback, useContext, useEffect, useState, useRef } from 'react';
import { User } from '@supabase/supabase-js';
import { supabase } from '@/integrations/supabase/client';
import { logApiError } from './apiErrorLog';

const PROJECT_ID = import.meta.env.VITE_SUPABASE_PROJECT_ID;
const PROXY_URL = `https://${PROJECT_ID}.supabase.co/functions/v1/api-proxy`;

// Module-level POESESSID so proxyFetch can attach it on every request
let _poeSessionId: string | null = null;
export function setPoeSessionId(id: string | null) { _poeSessionId = id; }
export function getPoeSessionId() { return _poeSessionId; }

async function proxyFetch(path: string, init?: RequestInit): Promise<Response> {
  const { data: { session } } = await supabase.auth.getSession();
  const token = session?.access_token;
  const extraHeaders: Record<string, string> = {};
  if (_poeSessionId) {
    extraHeaders['x-poe-session'] = _poeSessionId;
  }
  return fetch(PROXY_URL, {
    ...init,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      'x-proxy-path': path,
      ...extraHeaders,
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

export type UserRole = 'public' | 'member' | 'admin';

interface AuthContextValue {
  /* Supabase / Lovable Cloud auth */
  supabaseUser: User | null;
  isAuthenticated: boolean;
  isApproved: boolean;
  userRole: UserRole;
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
  sessionPersisted: boolean;
}

const AuthContext = createContext<AuthContextValue>({
  supabaseUser: null,
  isAuthenticated: false,
  isApproved: false,
  userRole: 'public',
  signIn: async () => null,
  signUp: async () => null,
  signOut: async () => {},

  user: null,
  login: async () => false,
  logout: () => {},
  refreshSession: async () => {},
  sessionState: 'disconnected',
  isLoading: true,
  sessionPersisted: false,
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
  const [userRole, setUserRole] = useState<UserRole>('public');

  const checkApprovalAndRole = useCallback(async (userId: string) => {
    const { data: approval } = await supabase
      .from('approved_users')
      .select('id')
      .eq('user_id', userId)
      .maybeSingle();
    setIsApproved(!!approval);

    if (approval) {
      const { data: roleRow } = await supabase
        .from('user_roles')
        .select('role')
        .eq('user_id', userId)
        .maybeSingle();
      setUserRole((roleRow?.role as UserRole) ?? 'member');
    } else {
      setUserRole('public');
    }
  }, []);

  useEffect(() => {
    // Set up listener FIRST
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSupabaseUser(session?.user ?? null);
      if (session?.user) {
        checkApprovalAndRole(session.user.id);
      } else {
        setIsApproved(false);
        setUserRole('public');
      }
    });

    // Then check existing session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSupabaseUser(session?.user ?? null);
      if (session?.user) {
        checkApprovalAndRole(session.user.id).then(() => setSupabaseReady(true));
      } else {
        setSupabaseReady(true);
      }
    });

    return () => subscription.unsubscribe();
  }, [checkApprovalAndRole]);

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

  /* PoE session auth state */
  const [user, setUser] = useState<AuthUser | null>(null);
  const [sessionState, setSessionState] = useState<'connected' | 'disconnected' | 'session_expired'>('disconnected');
  const [isLoading, setIsLoading] = useState(true);
  const [sessionPersisted, setSessionPersisted] = useState(false);

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

  // Save POESESSID to database for persistence
  const saveSessionToDb = useCallback(async (poeSessionId: string, accountName: string) => {
    const userId = supabaseUser?.id;
    if (!userId) return;
    const { error } = await supabase
      .from('user_poe_sessions')
      .upsert({ user_id: userId, encrypted_session: poeSessionId, account_name: accountName }, { onConflict: 'user_id' });
    if (!error) setSessionPersisted(true);
  }, [supabaseUser]);

  const deleteSessionFromDb = useCallback(async () => {
    const userId = supabaseUser?.id;
    if (!userId) return;
    await supabase.from('user_poe_sessions').delete().eq('user_id', userId);
    setSessionPersisted(false);
  }, [supabaseUser]);

  // Restore saved session on init
  const restoreSession = useCallback(async () => {
    const userId = supabaseUser?.id;
    if (!userId) return;
    const { data } = await supabase
      .from('user_poe_sessions')
      .select('encrypted_session, account_name')
      .eq('user_id', userId)
      .maybeSingle();
    if (data?.encrypted_session) {
      setSessionPersisted(true);
      // Set in memory so all subsequent proxy requests include it
      setPoeSessionId(data.encrypted_session);
      // POST to establish backend session
      try {
        const response = await proxyFetch('/api/v1/auth/session', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ poeSessionId: data.encrypted_session }),
        });
        if (!response.ok) {
          logApiError({ path: '/api/v1/auth/session', statusCode: response.status, errorCode: 'auth_restore', message: `Session restore failed (${response.status})` });
        }
      } catch {
        // Silent fail on restore
      }
    }
  }, [supabaseUser]);

  useEffect(() => {
    if (!supabaseReady || !isApproved) {
      setIsLoading(false);
      return;
    }
    // Restore saved session then refresh
    restoreSession()
      .then(() => refreshSession())
      .finally(() => setIsLoading(false));
  }, [refreshSession, restoreSession, supabaseReady, isApproved]);

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      if (event.origin !== window.location.origin) {
        return;
      }
      const data = event.data;
      if (!data || typeof data !== 'object' || data.type !== 'poe_auth_callback_complete') {
        return;
      }
      void refreshSession();
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [refreshSession]);

  const login = useCallback(async (poeSessionId: string): Promise<boolean> => {
    // Store in memory so proxyFetch attaches it on every request
    setPoeSessionId(poeSessionId);
    try {
      // POST to establish backend session
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
      setPoeSessionId(null);
      return false;
    }
    // Verify session — the x-poe-session header will be sent automatically
    const result = await refreshSession();
    if (result.status === 'connected' && result.accountName) {
      await saveSessionToDb(poeSessionId, result.accountName);
      return true;
    }
    setPoeSessionId(null);
    return false;
  }, [refreshSession, saveSessionToDb]);

  const logout = useCallback(() => {
    proxyFetch('/api/v1/auth/logout', {
      method: 'POST',
    }).finally(() => {
      setUser(null);
      setSessionState('disconnected');
      deleteSessionFromDb();
    });
  }, [deleteSessionFromDb]);

  const isAuthenticated = !!supabaseUser;
  const combinedLoading = !supabaseReady || isLoading;

  return (
    <AuthContext.Provider value={{
      supabaseUser,
      isAuthenticated,
      isApproved,
      userRole,
      signIn,
      signUp,
      signOut: signOutFn,
      user,
      login,
      logout,
      refreshSession,
      sessionState,
      isLoading: combinedLoading,
      sessionPersisted,
    }}>
      {children}
    </AuthContext.Provider>
  );
};
