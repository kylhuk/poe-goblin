import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const API_BASE = 'https://api.poe.lama-lan.ch';
const STORAGE_KEY = 'poe_auth_user';

export interface AuthUser {
  accountName: string;
  token: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  login: () => void;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  login: () => {},
  logout: () => {},
  isLoading: true,
});

export const useAuth = () => useContext(AuthContext);

export function getStoredToken(): string | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as AuthUser;
    return parsed.token || null;
  } catch {
    return null;
  }
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Hydrate from localStorage on mount
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as AuthUser;
        if (parsed.token && parsed.accountName) {
          setUser(parsed);
        }
      }
    } catch {
      localStorage.removeItem(STORAGE_KEY);
    }
    setIsLoading(false);
  }, []);

  // Listen for postMessage from popup callback
  useEffect(() => {
    const handler = (event: MessageEvent) => {
      if (event.data?.type === 'poe_auth_callback') {
        const { accountName, token } = event.data as { type: string; accountName: string; token: string };
        if (token && accountName) {
          const authUser: AuthUser = { accountName, token };
          localStorage.setItem(STORAGE_KEY, JSON.stringify(authUser));
          setUser(authUser);
        }
      }
    };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, []);

  const login = useCallback(() => {
    const callbackUrl = `${window.location.origin}/auth/callback`;
    const authUrl = `${API_BASE}/api/v1/auth/login?redirect_uri=${encodeURIComponent(callbackUrl)}`;
    const width = 500;
    const height = 700;
    const left = window.screenX + (window.innerWidth - width) / 2;
    const top = window.screenY + (window.innerHeight - height) / 2;
    window.open(
      authUrl,
      'poe_auth_popup',
      `width=${width},height=${height},left=${left},top=${top},popup=yes`
    );
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, login, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
};
