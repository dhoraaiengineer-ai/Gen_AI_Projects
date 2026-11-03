/**
 * Hook — fetch the ScoreResult (baseline metrics + failure_taxonomy) the client-derived
 * proposed variant is built from, plus the real Improver Agent output (3 backend-scored
 * candidates — GET /improve/{run_id}, Part E, 12-Jul-2026). See lib/variant.ts's header
 * comment for why the two aren't merged into one config schema.
 *
 * Thin clone of hooks/use-diagnosis.ts: native fetch via apiClient, no SWR/React
 * Query (CLAUDE.md §6).
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { apiClient } from "@/services/api-client";
import type { ImprovementResponse, ScoreResult } from "@/types";

interface UseImprovementResult {
  score: ScoreResult | null;
  improvement: ImprovementResponse | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
}

export function useImprovement(runId: string | null): UseImprovementResult {
  const [score, setScore] = useState<ScoreResult | null>(null);
  const [improvement, setImprovement] = useState<ImprovementResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const mountedRef = useRef(true);

  const load = useCallback(async () => {
    if (!runId) {
      setScore(null);
      setImprovement(null);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    try {
      const [scoreResult, improvementResult] = await Promise.all([
        apiClient.getScore(runId),
        apiClient.getImprovement(runId),
      ]);
      if (!mountedRef.current) return;
      setScore(scoreResult);
      setImprovement(improvementResult);
      setError(null);
    } catch (err) {
      if (!mountedRef.current) return;
      setError(err instanceof Error ? err : new Error("Failed to load pipeline metrics"));
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, [runId]);

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

  return { score, improvement, isLoading, error, refetch };
}
