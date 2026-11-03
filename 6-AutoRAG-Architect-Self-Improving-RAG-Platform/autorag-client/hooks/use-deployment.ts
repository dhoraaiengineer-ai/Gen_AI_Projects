/**
 * Hook — fetch + poll the current deployment status and history for a pipeline.
 *
 * Mirrors hooks/use-pipelines.ts: native fetch via apiClient + setInterval,
 * no SWR/React Query dependency (CLAUDE.md §6 "avoid unnecessary dependencies").
 * Polling: 5s while a canary is in flight (status === "blue_green"), otherwise 30s.
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { apiClient } from "@/services/api-client";
import type { Deployment } from "@/types";

const FAST_POLL_MS = 5_000;
const SLOW_POLL_MS = 30_000;

interface UseDeploymentResult {
  current: Deployment | null;
  history: Deployment[];
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
}

export function useDeployment(pipelineId: string | null): UseDeploymentResult {
  const [current, setCurrent] = useState<Deployment | null>(null);
  const [history, setHistory] = useState<Deployment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const mountedRef = useRef(true);

  const load = useCallback(async () => {
    if (!pipelineId) {
      setCurrent(null);
      setHistory([]);
      setIsLoading(false);
      return;
    }
    try {
      const [statusRes, historyRes] = await Promise.all([
        apiClient.getDeploymentStatus(pipelineId),
        apiClient.getDeploymentHistory(pipelineId),
      ]);
      if (!mountedRef.current) return;
      setCurrent(statusRes.deployment);
      setHistory(historyRes.deployments);
      setError(null);
    } catch (err) {
      if (!mountedRef.current) return;
      setError(err instanceof Error ? err : new Error("Failed to load deployment status"));
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, [pipelineId]);

  useEffect(() => {
    mountedRef.current = true;
    void load();
    return () => {
      mountedRef.current = false;
    };
  }, [load]);

  useEffect(() => {
    const intervalMs = current?.status === "blue_green" ? FAST_POLL_MS : SLOW_POLL_MS;
    const id = setInterval(() => void load(), intervalMs);
    return () => clearInterval(id);
  }, [load, current?.status]);

  const refetch = useCallback(() => {
    void load();
  }, [load]);

  return { current, history, isLoading, error, refetch };
}
