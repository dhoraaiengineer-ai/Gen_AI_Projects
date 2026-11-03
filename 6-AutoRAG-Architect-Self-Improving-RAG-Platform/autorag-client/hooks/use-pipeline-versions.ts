/**
 * Hook — fetch real pipeline version history (GET /pipelines/{id}/versions,
 * 20-Jul-2026 Apply Improvement feature). Feeds the optimization timeline /
 * Pipeline Evolution view. Thin clone of hooks/use-improvement.ts: native
 * fetch via apiClient, no SWR/React Query (CLAUDE.md §6).
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { apiClient } from "@/services/api-client";
import type { PipelineVersionSummary } from "@/types";

interface UsePipelineVersionsResult {
  versions: PipelineVersionSummary[];
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
}

export function usePipelineVersions(pipelineId: string | null): UsePipelineVersionsResult {
  const [versions, setVersions] = useState<PipelineVersionSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const mountedRef = useRef(true);

  const load = useCallback(async () => {
    if (!pipelineId) {
      setVersions([]);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    try {
      const res = await apiClient.listPipelineVersions(pipelineId);
      if (!mountedRef.current) return;
      setVersions(res.versions);
      setError(null);
    } catch (err) {
      if (!mountedRef.current) return;
      setError(err instanceof Error ? err : new Error("Failed to load pipeline versions"));
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

  const refetch = useCallback(() => {
    void load();
  }, [load]);

  return { versions, isLoading, error, refetch };
}
