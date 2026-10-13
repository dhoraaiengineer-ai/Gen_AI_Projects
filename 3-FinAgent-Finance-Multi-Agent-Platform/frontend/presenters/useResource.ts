"use client";
// Presenter helper: load one resource for the signed-in user, with loading/error state and reload.
// ``key`` identifies the request (null = don't load); the loader always receives the token.
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/lib/api";
import { useSession } from "@/presenters/session";

interface Loaded<T> {
  key: string;
  data: T | null;
  error: string | null;
}

export function describe(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 403) return "Your role does not have access to this.";
    if (e.status === 429) return `Too many requests — try again in ${e.retryAfter ?? 60} s.`;
    return `${e.message}${e.requestId ? ` (request ${e.requestId})` : ""}`;
  }
  return e instanceof Error ? e.message : String(e);
}

export function useResource<T>(key: string | null, load: (token: string) => Promise<T>) {
  const { token } = useSession();
  const [state, setState] = useState<Loaded<T> | null>(null);
  const [nonce, setNonce] = useState(0);
  const loader = useRef(load);
  useEffect(() => {
    loader.current = load;
  });

  const id = token && key !== null ? `${key}#${nonce}` : null;

  useEffect(() => {
    if (!id || !token) return;
    let cancelled = false;
    loader.current(token).then(
      (data) => {
        if (!cancelled) setState({ key: id, data, error: null });
      },
      (e: unknown) => {
        if (!cancelled) setState({ key: id, data: null, error: describe(e) });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [id, token]);

  const current = state && state.key === id ? state : null;
  // Keep showing the previous data for the same resource while it reloads.
  const previous = state && key !== null && state.key.startsWith(`${key}#`) ? state : null;
  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return {
    data: (current ?? previous)?.data ?? null,
    error: current?.error ?? null,
    loading: id !== null && !current,
    reload,
  };
}
