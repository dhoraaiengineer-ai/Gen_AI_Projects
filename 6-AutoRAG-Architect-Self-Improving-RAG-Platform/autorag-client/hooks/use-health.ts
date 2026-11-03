/**
 * Hook — poll the backend /health endpoint for the Header connectivity dot.
 * Uses apiClient.getSystemHealth() (the enveloped GET /health -- same route
 * use-system-health.ts hits for the System Health Dashboard) so the header
 * also gets the real `environment`/`version` fields, not just an ok/fail
 * boolean. Polls every 30s; fails closed (healthy=false) on any network/parse
 * error. `lastCheckedAt` is set on every attempt (success or failure), real
 * client-clock time of the most recent probe -- not a fabricated value.
 */

"use client";

import { useEffect, useRef, useState } from "react";

import { apiClient } from "@/services/api-client";

const HEALTH_POLL_MS = 30_000;

interface UseHealthResult {
  healthy: boolean;
  service: string | null;
  environment: string | null;
  version: string | null;
  lastCheckedAt: number | null;
}

export function useHealth(): UseHealthResult {
  const [healthy, setHealthy] = useState(false);
  const [service, setService] = useState<string | null>(null);
  const [environment, setEnvironment] = useState<string | null>(null);
  const [version, setVersion] = useState<string | null>(null);
  const [lastCheckedAt, setLastCheckedAt] = useState<number | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;

    const check = async () => {
      try {
        const res = await apiClient.getSystemHealth();
        if (!mountedRef.current) return;
        setHealthy(res.status === "healthy");
        setService(res.service ?? null);
        setEnvironment(res.environment ?? null);
        setVersion(res.version ?? null);
        setLastCheckedAt(Date.now());
      } catch {
        if (!mountedRef.current) return;
        setHealthy(false);
        setLastCheckedAt(Date.now());
      }
    };

    void check();
    const id = setInterval(() => void check(), HEALTH_POLL_MS);
    return () => {
      mountedRef.current = false;
      clearInterval(id);
    };
  }, []);

  return { healthy, service, environment, version, lastCheckedAt };
}
