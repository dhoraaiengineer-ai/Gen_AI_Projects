"use client";

import { useCallback, useSyncExternalStore } from "react";

const noopSubscribe = () => () => {};

/** True only in the browser after hydration — for values that must not render on the server. */
export function useIsClient(): boolean {
  return useSyncExternalStore(
    noopSubscribe,
    () => true,
    () => false,
  );
}

/** A value computed from the browser environment (e.g. local time); `serverValue` is used during SSR. */
export function useClientValue<T>(compute: () => T, serverValue: T): T {
  return useSyncExternalStore(noopSubscribe, compute, () => serverValue);
}

const listeners = new Map<string, Set<() => void>>();

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null; // storage unavailable (private mode, blocked site data)
  }
}

/**
 * localStorage-backed state for per-viewer preferences. Falls back to the default when storage is
 * unavailable, and stays consistent across components using the same key.
 */
export function useStoredState<T>(key: string, defaultValue: T): [T, (value: T) => void] {
  const subscribe = useCallback(
    (cb: () => void) => {
      const set = listeners.get(key) ?? new Set();
      set.add(cb);
      listeners.set(key, set);
      return () => set.delete(cb);
    },
    [key],
  );
  const raw = useSyncExternalStore(subscribe, () => read(key), () => null);
  let value = defaultValue;
  if (raw !== null) {
    try {
      value = JSON.parse(raw) as T;
    } catch {
      value = defaultValue;
    }
  }
  const setValue = useCallback(
    (next: T) => {
      try {
        localStorage.setItem(key, JSON.stringify(next));
      } catch {
        /* ignore — preference just won't persist */
      }
      listeners.get(key)?.forEach((cb) => cb());
    },
    [key],
  );
  return [value, setValue];
}
