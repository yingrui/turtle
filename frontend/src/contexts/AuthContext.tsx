import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiFetch, clearToken, getToken, setToken } from '../utils/api';

type User = { id: string; login: string; is_admin: boolean };

type AuthContextValue = {
  isAuthenticated: boolean;
  isLoading: boolean;
  authMode: string;
  allowSignup: boolean;
  user: User | null;
  login: (login: string, password: string) => Promise<void>;
  register: (login: string, password: string) => Promise<void>;
  logout: () => void;
  completeLocalSession: (token: string) => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [authMode, setAuthMode] = useState('local');
  const [allowSignup, setAllowSignup] = useState(true);
  const navigate = useNavigate();

  const loadUser = useCallback(async () => {
    const token = getToken();
    if (!token) {
      setUser(null);
      setIsLoading(false);
      return;
    }
    try {
      const me = await apiFetch<User>('/api/auth/me');
      setUser(me);
    } catch {
      clearToken();
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    apiFetch<{ mode: string; allow_signup: boolean }>('/api/auth/mode')
      .then((m) => {
        setAuthMode(m.mode);
        setAllowSignup(m.allow_signup);
      })
      .catch(() => {});
    loadUser();
  }, [loadUser]);

  const completeLocalSession = useCallback(async (token: string) => {
    setToken(token);
    await loadUser();
  }, [loadUser]);

  const login = useCallback(async (loginName: string, password: string) => {
    const res = await apiFetch<{ access_token: string }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ login: loginName, password }),
    });
    await completeLocalSession(res.access_token);
  }, [completeLocalSession]);

  const register = useCallback(async (loginName: string, password: string) => {
    const res = await apiFetch<{ access_token: string }>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ login: loginName, password }),
    });
    await completeLocalSession(res.access_token);
  }, [completeLocalSession]);

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
    navigate('/login');
  }, [navigate]);

  const value = useMemo(
    () => ({
      isAuthenticated: !!user,
      isLoading,
      authMode,
      allowSignup,
      user,
      login,
      register,
      logout,
      completeLocalSession,
    }),
    [user, isLoading, authMode, allowSignup, login, register, logout, completeLocalSession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
