import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { User } from '@supabase/supabase-js';
import { supabase } from '@/integrations/supabase/client';
import { toast } from 'sonner';
import {
  authProxyFetch,
  consumeOAuthRelayResult,
  getOAuthPopupFeatures,
  POE_OAUTH_MESSAGE,
  type OAuthRelayResult,
} from './authProxy';
import { logApiError } from './apiErrorLog';

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
  supabaseUser: User | null;
  isAuthenticated: boolean;
  isApproved: boolean;
  userRole: UserRole;
  signIn: (email: string, password: string) => Promise<string | null>;
  signUp: (email: string, password: string) => Promise<string | null>;
  signOut: () => Promise<void>;
  user: AuthUser | null;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<void | SessionPayload>;
  sessionState: 'connected' | 'disconnected' | 'session_expired';
  isLoading: boolean;
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
  login: async () => {},
  logout: async () => {},
  refreshSession: async () => {},
  sessionState: 'disconnected',
  isLoading: true,
});

export const useAuth = () => useContext(AuthContext);

async function fetchSession(): Promise<SessionPayload> {
  try {
    const response = await authProxyFetch('/session');
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

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [supabaseUser, setSupabaseUser] = useState<User | null>(null);
  const [supabaseReady, setSupabaseReady] = useState(false);
  const [isApproved, setIsApproved] = useState(false);
  const [userRole, setUserRole] = useState<UserRole>('public');
  const popupRef = useRef<Window | null>(null);
  const popupPollRef = useRef<number | null>(null);
  const pendingOAuthStateRef = useRef<string | null>(null);
  const oauthResultPollRef = useRef<number | null>(null);

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
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSupabaseUser(session?.user ?? null);
      if (session?.user) {
        checkApprovalAndRole(session.user.id);
      } else {
        setIsApproved(false);
        setUserRole('public');
      }
    });

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

  const clearOAuthPollers = useCallback(() => {
    if (popupPollRef.current !== null) {
      window.clearInterval(popupPollRef.current);
      popupPollRef.current = null;
    }
    if (oauthResultPollRef.current !== null) {
      window.clearInterval(oauthResultPollRef.current);
      oauthResultPollRef.current = null;
    }
  }, []);

  const handleOAuthRelayResult = useCallback(
    async (result: OAuthRelayResult | null) => {
      if (!result || result.type !== POE_OAUTH_MESSAGE) {
        return;
      }
      if (pendingOAuthStateRef.current && result.state && result.state !== pendingOAuthStateRef.current) {
        return;
      }

      clearOAuthPollers();
      popupRef.current = null;
      pendingOAuthStateRef.current = null;

      if (result.status !== 'success') {
        toast.dismiss('poe-oauth');
        toast.error(result.message || 'Path of Exile login failed');
        return;
      }

      if (result.accountName) {
        setUser({ accountName: result.accountName });
        setSessionState('connected');
      } else {
        const session = await refreshSession();
        if (session.status !== 'connected' || !session.accountName) {
          toast.dismiss('poe-oauth');
          toast.error('Path of Exile session was not confirmed');
          return;
        }
      }

      toast.dismiss('poe-oauth');
      toast.success('Path of Exile connected');
    },
    [clearOAuthPollers, refreshSession],
  );

  useEffect(() => {
    if (!supabaseReady || !isApproved) {
      setIsLoading(false);
      return;
    }
    void refreshSession().finally(() => setIsLoading(false));
  }, [refreshSession, supabaseReady, isApproved]);

  useEffect(() => {
    const handleMessage = async (event: MessageEvent) => {
      if (event.origin !== window.location.origin || event.data?.type !== POE_OAUTH_MESSAGE) {
        return;
      }
      await handleOAuthRelayResult(event.data as OAuthRelayResult);
    };

    const handleStorage = (event: StorageEvent) => {
      if (event.key !== 'poe-oauth-result' || !event.newValue) {
        return;
      }
      try {
        const parsed = JSON.parse(event.newValue) as OAuthRelayResult;
        void handleOAuthRelayResult(parsed);
      } catch {
        // ignore
      }
    };

    window.addEventListener('message', handleMessage);
    window.addEventListener('storage', handleStorage);
    return () => {
      clearOAuthPollers();
      window.removeEventListener('message', handleMessage);
      window.removeEventListener('storage', handleStorage);
    };
  }, [clearOAuthPollers, handleOAuthRelayResult]);

  const login = useCallback(async () => {
    if (popupRef.current && !popupRef.current.closed) {
      popupRef.current.focus();
      return;
    }

    // Open blank popup SYNCHRONOUSLY to preserve user-gesture context
    const popup = window.open('about:blank', 'poe-oauth', getOAuthPopupFeatures());
    if (!popup) {
      toast.error('Popup blocked. Please allow popups and try again.');
      return;
    }

    popupRef.current = popup;
    toast.loading('Waiting for Path of Exile login…', { id: 'poe-oauth' });

    try {
      const res = await authProxyFetch('/login');
      if (!res.ok) throw new Error(`Login request failed (${res.status})`);
      const data = await res.json();
      const authorizeUrl = data.authorizeUrl || data.authorize_url || data.url;
      if (!authorizeUrl) throw new Error('No authorize URL returned from backend');

      try {
        const parsed = new URL(authorizeUrl, window.location.origin);
        pendingOAuthStateRef.current = parsed.searchParams.get('state');
      } catch {
        pendingOAuthStateRef.current = null;
      }

      popup.location.href = authorizeUrl;
      popup.focus();

      if (popupPollRef.current !== null) window.clearInterval(popupPollRef.current);
      if (oauthResultPollRef.current !== null) window.clearInterval(oauthResultPollRef.current);

      popupPollRef.current = window.setInterval(() => {
        if (popupRef.current && popupRef.current.closed) {
          clearOAuthPollers();
          popupRef.current = null;
          pendingOAuthStateRef.current = null;
          toast.dismiss('poe-oauth');
        }
      }, 500);

      oauthResultPollRef.current = window.setInterval(() => {
        const result = consumeOAuthRelayResult();
        if (result) {
          void handleOAuthRelayResult(result);
        }
      }, 250);
    } catch (err) {
      popup.close();
      popupRef.current = null;
      pendingOAuthStateRef.current = null;
      clearOAuthPollers();
      toast.dismiss('poe-oauth');
      logApiError({ path: '/api/v1/auth/login', errorCode: 'login_error', message: err instanceof Error ? err.message : 'Login failed' });
      toast.error(err instanceof Error ? err.message : 'Login failed');
    }
  }, [clearOAuthPollers, handleOAuthRelayResult]);

  const logout = useCallback(async () => {
    try {
      await authProxyFetch('/logout', { method: 'POST' });
    } catch (err) {
      logApiError({ path: '/api/v1/auth/logout', errorCode: 'network_error', message: err instanceof Error ? err.message : 'Network error' });
    } finally {
      setUser(null);
      setSessionState('disconnected');
      toast.success('Disconnected from Path of Exile');
    }
  }, []);

  const isAuthenticated = !!supabaseUser;
  const combinedLoading = !supabaseReady || isLoading;

  return (
    <AuthContext.Provider
      value={{
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
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};
