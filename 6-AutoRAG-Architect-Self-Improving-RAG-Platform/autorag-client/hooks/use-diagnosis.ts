/**
 * Hook — fetch ScoreResult (incl. failure_taxonomy) and the real Diagnoser
 * classification (confidence, remediation_hint, root_cause_analysis) for a
 * pipeline's latest run.
 *
 * Mirrors hooks/use-deployment.ts: native fetch via apiClient, no SWR/React Query
 * dependency (CLAUDE.md §6). No polling — a completed run's score is immutable.
 *
 * P0.5/Part E fix (12-Jul-2026): previously this hook only called getScore(),
 * with a comment noting it was "the only real, working endpoint" for Diagnoser
 * output — that was true only because GET /diagnose/{run_id} never had real
 * data to return (evaluate.py never persisted the Diagnoser node's
 * confidence/remediation_hint/root_cause_analysis, only the guardrail-block
 * shape). Both gaps are now fixed on the backend, so this hook calls the real
 * dedicated route for that data instead of leaving it unavailable.
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { apiClient } from "@/services/api-client";
import type { DiagnosisResponse, ScoreResult } from "@/types";

interface UseDiagnosisResult {
  score: ScoreResult | null;
  diagnosis: DiagnosisResponse | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
}

export function useDiagnosis(runId: string | null): UseDiagnosisResult {
  const [score, setScore] = useState<ScoreResult | null>(null);
  const [diagnosis, setDiagnosis] = useState<DiagnosisResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const mountedRef = useRef(true);

  const load = useCallback(async () => {
    if (!runId) {
      setScore(null);
      setDiagnosis(null);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    try {
      const [scoreResult, diagnosisResult] = await Promise.all([
        apiClient.getScore(runId),
        apiClient.getDiagnosis(runId),
      ]);
      if (!mountedRef.current) return;
      setScore(scoreResult);
      setDiagnosis(diagnosisResult);
      setError(null);
    } catch (err) {
      if (!mountedRef.current) return;
      setError(err instanceof Error ? err : new Error("Failed to analyze failure"));
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

  return { score, diagnosis, isLoading, error, refetch };
}
