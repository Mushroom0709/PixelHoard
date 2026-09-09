/**
 * 认证状态 hook — 全局 access_token + user,持久化到 localStorage。
 */
import { createContext, useCallback, useContext, useEffect, useState } from "react";

export interface AuthUser {
  id: number;
  email: string;
  display_name: string | null;
  is_admin: boolean;
  is_verified: boolean;
  created_at: string;
}

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: AuthUser | null;
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => void;
  isAdmin: boolean;
  loading: boolean;
}

const STORAGE_KEY = "ph.auth.v1";

const AuthCtx = createContext<AuthContextValue | null>(null);

interface StoredAuth {
  accessToken: string;
  refreshToken: string;
  user: AuthUser;
}

function loadStored(): StoredAuth | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as StoredAuth;
  } catch {
    return null;
  }
}

function saveStored(s: StoredAuth | null) {
  if (s === null) {
    localStorage.removeItem(STORAGE_KEY);
  } else {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>(() => {
    const stored = loadStored();
    if (stored) {
      return {
        accessToken: stored.accessToken,
        refreshToken: stored.refreshToken,
        user: stored.user,
      };
    }
    return { accessToken: null, refreshToken: null, user: null };
  });
  const [loading, setLoading] = useState(false);

  const doAuth = useCallback(
    async (path: string, body: Record<string, unknown>) => {
      setLoading(true);
      try {
        const r = await fetch(path, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!r.ok) {
          let msg = `${r.status}`;
          try {
            const j = await r.json();
            if (typeof j.detail === "string") msg = j.detail;
            else if (Array.isArray(j.detail) && j.detail[0]?.msg) msg = j.detail[0].msg;
          } catch {}
          throw new Error(msg);
        }
        const data = await r.json();
        const stored: StoredAuth = {
          accessToken: data.access_token,
          refreshToken: data.refresh_token,
          user: data.user,
        };
        saveStored(stored);
        setState(stored);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const login = useCallback(
    (email: string, password: string) => doAuth("/api/auth/login", { email, password }),
    [doAuth]
  );

  const register = useCallback(
    (email: string, password: string, displayName?: string) =>
      doAuth("/api/auth/register", { email, password, display_name: displayName }),
    [doAuth]
  );

  const logout = useCallback(() => {
    saveStored(null);
    setState({ accessToken: null, refreshToken: null, user: null });
  }, []);

  // 跨 tab 同步
  useEffect(() => {
    function onStorage(e: StorageEvent) {
      if (e.key === STORAGE_KEY) {
        const stored = loadStored();
        if (stored) setState(stored);
        else setState({ accessToken: null, refreshToken: null, user: null });
      }
    }
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const value: AuthContextValue = {
    ...state,
    login,
    register,
    logout,
    isAdmin: state.user?.is_admin ?? false,
    loading,
  };

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

/**
 * 兼容老调用 — 直接读 localStorage 的 access token。
 */
export function getAccessToken(): string | null {
  return loadStored()?.accessToken ?? null;
}