/**
 * Hook — poll GET /health for the System Health Dashboard (F-19).
 *
 * Richer than use-health.ts (which only drives the header dot): this measures
 * client-side round-trip latency, accumulates a session uptime ratio + failure
 * streak, and keeps a rolling sample history for the status strip. Native
 * fetch/setInterval (no TanStack) because the latency measurement + rolling
 * history don't map cleanly onto a query cache. Fails closed on any error.
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { apiClient } from "@/services/api-client";
import type { HealthSample } from "@/lib/health";
import type { SystemHealth } from "@/types";

const POLL_MS = 15_000;
const HISTORY_LIMIT = 40;

export interface SystemHealthState {
  health: SystemHealth | null;
  isOnline: boolean;
  latencyMs: number | null;
  lastCheckedAt: number | null;
  failStreak: number;
  totalChecks: number;
  successfulChecks: number;
  history: HealthSample[];
  /** True only until the very first probe resolves. */
  isInitialLoading: boolean;
  refresh: () => void;
}

export function useSystemHealth(): SystemHealthState {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [isOnline, setIsOnline] = useState(false);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [lastCheckedAt, setLastCheckedAt] = useState<number | null>(null);
  const [failStreak, setFailStreak] = useState(0);
  const [totalChecks, setTotalChecks] = useState(0);
  const [successfulChecks, setSuccessfulChecks] = useState(0);
  const [history, setHistory] = useState<HealthSample[]>([]);
  const [isInitialLoading, setIsInitialLoading] = useState(true);

  const mountedRef = useRef(true);

  const probe = useCallback(async () => {
    const start = performance.now();
    let ok = false;
    let elapsed: number | null = null;
    try {
      const result = await apiClient.getSystemHealth();
      elapsed = performance.now() - start;
      if (!mountedRef.current) return;
      ok = result.status === "healthy";
      setHealth(result);
    } catch {
      if (!mountedRef.current) return;
      ok = false;
      elapsed = null;
    }

    const at = Date.now();
    setIsOnline(ok);
    setLatencyMs(elapsed === null ? null : Math.round(elapsed));
    setLastCheckedAt(at);
    setFailStreak((prev) => (ok ? 0 : prev + 1));
    setTotalChecks((prev) => prev + 1);
    setSuccessfulChecks((prev) => (ok ? prev + 1 : prev));
    setHistory((prev) => {
      const next = [...prev, { ok, latencyMs: elapsed === null ? null : Math.round(elapsed), at }];
      return next.slice(-HISTORY_LIMIT);
    });
    setIsInitialLoading(false);
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void probe();
    const id = setInterval(() => void probe(), POLL_MS);
    return () => {
      mountedRef.current = false;
      clearInterval(id);
    };
  }, [probe]);

  const refresh = useCallback(() => {
    void probe();
  }, [probe]);

  return {
    health,
    isOnline,
    latencyMs,
    lastCheckedAt,
    failStreak,
    totalChecks,
    successfulChecks,
    history,
    isInitialLoading,
    refresh,
  };
}
