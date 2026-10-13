"use client";
// Presenter: Supabase session (or a mock role in mock mode) and the signed-in user's profile,
// shared by every page through context.
import type { Session } from "@supabase/supabase-js";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

import { api } from "@/lib/api";
import { API_MODE } from "@/lib/config";
import { setMockRole } from "@/lib/mock";
import { supabase } from "@/lib/supabase";
import type { Me } from "@/types";

export interface SessionState {
  token: string | null;
  me: Me | null;
  loading: boolean;
  error: string | null;
  signIn: (email: string, password: string) => Promise<void>;
  signInMock: (role: string) => void;
  signOut: () => Promise<void>;
  can: (permission: string) => boolean;
}

const SessionContext = createContext<SessionState | null>(null);

export function useSession(): SessionState {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside <SessionProvider>");
  return value;
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [mockToken, setMockToken] = useState<string | null>(null);
  const [profile, setProfile] = useState<{ token: string; me: Me } | null>(null);
  const [loading, setLoading] = useState(API_MODE !== "mock");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (API_MODE === "mock") return;
    const client = supabase();
    client.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });
    const { data } = client.auth.onAuthStateChange((_event, next) => setSession(next));
    return () => data.subscription.unsubscribe();
  }, []);

  const token = API_MODE === "mock" ? mockToken : (session?.access_token ?? null);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    api
      .me(token)
      .then((me) => {
        if (!cancelled) setProfile({ token, me });
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const signIn = useCallback(async (email: string, password: string) => {
    setError(null);
    const { error: authError } = await supabase().auth.signInWithPassword({ email, password });
    if (authError) setError(authError.message);
  }, []);

  const signInMock = useCallback((role: string) => {
    setMockRole(role);
    setMockToken(`mock-${role}`);
  }, []);

  const signOut = useCallback(async () => {
    setProfile(null);
    if (API_MODE === "mock") setMockToken(null);
    else await supabase().auth.signOut();
  }, []);

  // Derived, not stored: the profile only counts while it belongs to the current token.
  const me = profile && profile.token === token ? profile.me : null;
  const can = useCallback((permission: string) => Boolean(me?.permissions.includes(permission)), [me]);

  return (
    <SessionContext.Provider value={{ token, me, loading, error, signIn, signInMock, signOut, can }}>
      {children}
    </SessionContext.Provider>
  );
}
