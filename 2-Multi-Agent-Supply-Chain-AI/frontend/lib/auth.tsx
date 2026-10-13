"use client";

/**
 * Authentication (API mode). Supabase Auth issues the session in the browser; the FastAPI backend verifies the
 * access token against the project's JWKS. The browser-safe config (URL + publishable key) is loaded at runtime
 * from the backend, so one frontend image works in every environment. Demo mode needs no sign-in.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { createClient, type Session, type SupabaseClient } from "@supabase/supabase-js";
import { useQueryClient } from "@tanstack/react-query";
import { setTokenProvider } from "./api";
import { DATA_SOURCE } from "./constants";

type AuthState =
  | { status: "loading" }
  | { status: "demo" }
  | { status: "signed_out"; error?: string }
  | { status: "signed_in"; session: Session }
  | { status: "unavailable"; error: string };

interface AuthContextValue {
  state: AuthState;
  signIn: (email: string, password: string) => Promise<string | null>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

async function loadClient(): Promise<SupabaseClient> {
  const res = await fetch("/api/config/public", { cache: "no-store" });
  if (!res.ok) throw new Error("The sign-in service is unavailable.");
  const cfg = (await res.json()) as { supabaseUrl: string; supabasePublishableKey: string };
  if (!cfg.supabaseUrl || !cfg.supabasePublishableKey) throw new Error("Sign-in is not configured on the server.");
  return createClient(cfg.supabaseUrl, cfg.supabasePublishableKey, { auth: { persistSession: true, autoRefreshToken: true } });
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [client, setClient] = useState<SupabaseClient | null>(null);
  const [state, setState] = useState<AuthState>(DATA_SOURCE === "mock" ? { status: "demo" } : { status: "loading" });
  const queryClient = useQueryClient();

  useEffect(() => {
    if (DATA_SOURCE === "mock") return;
    let unsubscribe: (() => void) | undefined;
    loadClient()
      .then(async (c) => {
        setClient(c);
        setTokenProvider(async () => (await c.auth.getSession()).data.session?.access_token ?? null);
        const { data } = await c.auth.getSession();
        setState(data.session ? { status: "signed_in", session: data.session } : { status: "signed_out" });
        const { data: sub } = c.auth.onAuthStateChange((_event, session) => {
          setState(session ? { status: "signed_in", session } : { status: "signed_out" });
        });
        unsubscribe = () => sub.subscription.unsubscribe();
      })
      .catch((err: unknown) => setState({ status: "unavailable", error: err instanceof Error ? err.message : "Sign-in is unavailable." }));
    return () => unsubscribe?.();
  }, []);

  const signIn = useCallback(
    async (email: string, password: string) => {
      if (!client) return "Sign-in is still starting. Try again in a moment.";
      const { error } = await client.auth.signInWithPassword({ email, password });
      if (error) return error.message === "Invalid login credentials" ? "Incorrect email or password." : error.message;
      queryClient.clear();
      return null;
    },
    [client, queryClient],
  );

  const signOut = useCallback(async () => {
    await client?.auth.signOut();
    queryClient.clear();
  }, [client, queryClient]);

  const value = useMemo(() => ({ state, signIn, signOut }), [state, signIn, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
