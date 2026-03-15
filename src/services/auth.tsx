import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';

import { API_BASE } from './config';
import { logApiError } from './apiErrorLog';

export interface AuthUser {
  accountName: string;
}

interface SessionPayload {
  status: 'connected' | 'disconnected' | 'session_expired';
  accountName?: string | null;
  expiresAt?: string | null;
}

interface AuthContextValue {
  user: AuthUser | null;
  login: (poeSessionId: string) => Promise<boolean>;
  logout: () => void;
  refreshSession: () => Promise<void>;
  sessionState: 'connected' | 'disconnected' | 'session_expired';
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  login: async () => false,
  logout: () => {},
  refreshSession: async () => {},
  sessionState: 'disconnected',
  isLoading: true,
});

export const useAuth = () => useContext(AuthContext);

async function fetchSession(): Promise<SessionPayload> {
  try {
    const response = await fetch(`${API_BASE}/api/v1/auth/session`, {
      credentials: 'include',
    });
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
  const [user, setUser] = useState<AuthUser | null>(null);
  const [sessionState, setSessionState] = useState<'connected' | 'disconnected' | 'session_expired'>('disconnected');
  const [isLoading, setIsLoading] = useState(true);

  const refreshSession = useCallback(async () => {
    const payload = await fetchSession();
    if (payload.status === 'connected' && payload.accountName) {
      setUser({ accountName: payload.accountName });
      setSessionState('connected');
      return;
    }
    setUser(null);
    setSessionState(payload.status);
  }, []);

  useEffect(() => {
    refreshSession().finally(() => setIsLoading(false));
  }, [refreshSession]);

  const login = useCallback(async (poeSessionId: string): Promise<boolean> => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/auth/session`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ poeSessionId }),
        credentials: 'include',
      });
      if (!response.ok) {
        logApiError({ path: '/api/v1/auth/session', statusCode: response.status, errorCode: 'auth_login', message: `Login failed (${response.status})` });
      }
    } catch (err) {
      logApiError({ path: '/api/v1/auth/session', errorCode: 'network_error', message: err instanceof Error ? err.message : 'Network error' });
      return false;
    }
    await refreshSession();
    return sessionState === 'connected' && !!user;
  }, [refreshSession, sessionState, user]);

  const logout = useCallback(() => {
    fetch(`${API_BASE}/api/v1/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    }).finally(() => {
      setUser(null);
      setSessionState('disconnected');
    });
  }, []);

  return (
    <AuthContext.Provider value={{ user, login, logout, refreshSession, sessionState, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
};
