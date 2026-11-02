import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { api, setToken } from "../api/client";
import { TokenSchema, type Me } from "../api/schemas";

type AuthState = {
  me: Me | null;
  login: (email: string, password: string) => Promise<Me>;
  logout: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children, initialUser = null }: { children: ReactNode; initialUser?: Me | null }) {
  const [me, setMe] = useState<Me | null>(initialUser);

  const login = useCallback(async (email: string, password: string) => {
    const out = await api("/api/v1/auth/login", TokenSchema, { body: { email, password } });
    setToken(out.access_token);
    setMe(out.user);
    return out.user;
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setMe(null);
  }, []);

  const value = useMemo(() => ({ me, login, logout }), [me, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

/** Client-side guard for navigation only — the backend enforces every role check (rules/20). */
export function RequireRole({ roles, children }: { roles: Me["role"][]; children: ReactNode }) {
  const { me } = useAuth();
  const location = useLocation();
  if (!me) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (!roles.includes(me.role)) {
    return (
      <p role="alert" className="mx-auto max-w-4xl p-6">
        Your role ({me.role}) cannot open this page.
      </p>
    );
  }
  return <>{children}</>;
}
