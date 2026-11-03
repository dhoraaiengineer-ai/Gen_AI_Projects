/**
 * Hook — real Pipeline Progress data for /dashboard/[id] (Part D, 12-Jul-2026).
 *
 * Resolves pipelineId -> latest real run_id (GET /pipelines/{id}), then polls
 * GET /score/{run_id} (which now carries `node_trace`, Part A/B.1) while the
 * run is pending/running, and GET /runs/{run_id}/metrics (Part B.0) once a
 * run_id is known, for the real per-agent cost/token/provider breakdown.
 *
 * No fabricated progress: this only reports what the backend has actually
 * persisted. There is no live per-node streaming yet (confirmed in Part 0's
 * audit — LangGraph only exposes a coarse pending/running/terminal status
 * mid-run) — node_trace only reflects nodes that have actually completed.
 *
 * Mirrors hooks/use-deployment.ts: native fetch via apiClient + setInterval,
 * no SWR/React Query dependency (CLAUDE.md §6).
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { apiClient } from "@/services/api-client";
import type {
  Document,
  DiagnosisResponse,
  ImprovementResponse,
  ObserverViewResponse,
  Pipeline,
  RunMetricsResponse,
  ScoreResult,
} from "@/types";

const POLL_MS = 5_000;
const TERMINAL_STATUSES = new Set(["completed", "blocked", "failed"]);

interface UsePipelineRunResult {
  pipeline: Pipeline | null;
  runId: string | null;
  score: ScoreResult | null;
  metrics: RunMetricsResponse | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
  // Part H Mission Control evidence surfaces — each independently loaded/
  // errored so a failure in one never blanks the core execution journey.
  documents: Document[];
  documentsLoading: boolean;
  diagnosis: DiagnosisResponse | null;
  diagnosisLoading: boolean;
  improvement: ImprovementResponse | null;
  improvementLoading: boolean;
  observerView: ObserverViewResponse | null;
  observerLoading: boolean;
}

export function usePipelineRun(pipelineId: string | null): UsePipelineRunResult {
  const [pipeline, setPipeline] = useState<Pipeline | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [score, setScore] = useState<ScoreResult | null>(null);
  const [metrics, setMetrics] = useState<RunMetricsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const [documents, setDocuments] = useState<Document[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [diagnosis, setDiagnosis] = useState<DiagnosisResponse | null>(null);
  const [diagnosisLoading, setDiagnosisLoading] = useState(false);
  const [improvement, setImprovement] = useState<ImprovementResponse | null>(null);
  const [improvementLoading, setImprovementLoading] = useState(false);
  const [observerView, setObserverView] = useState<ObserverViewResponse | null>(null);
  const [observerLoading, setObserverLoading] = useState(false);

  const mountedRef = useRef(true);

  const loadPipeline = useCallback(async () => {
    if (!pipelineId) {
      setPipeline(null);
      setRunId(null);
      setIsLoading(false);
      return;
    }
    try {
      const detail = await apiClient.getPipeline(pipelineId);
      if (!mountedRef.current) return;
      setPipeline(detail.pipeline);
      setRunId(detail.latest_run?.id ?? null);
      setError(null);
    } catch (err) {
      if (!mountedRef.current) return;
      setError(err instanceof Error ? err : new Error("Failed to load pipeline"));
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, [pipelineId]);

  const loadRunData = useCallback(async (id: string) => {
    try {
      const [scoreRes, metricsRes] = await Promise.all([
        apiClient.getScore(id),
        apiClient.getRunMetrics(id),
      ]);
      if (!mountedRef.current) return;
      setScore(scoreRes);
      setMetrics(metricsRes);
      setError(null);
    } catch (err) {
      if (!mountedRef.current) return;
      setError(err instanceof Error ? err : new Error("Failed to load run data"));
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void loadPipeline();
    return () => {
      mountedRef.current = false;
    };
  }, [loadPipeline]);

  useEffect(() => {
    if (!runId) return;
    void loadRunData(runId);
  }, [runId, loadRunData]);

  useEffect(() => {
    if (!runId) return;
    if (score && TERMINAL_STATUSES.has(score.status)) return;
    const id = setInterval(() => void loadRunData(runId), POLL_MS);
    return () => clearInterval(id);
  }, [runId, score, loadRunData]);

  // Document evidence: no server-side pipeline filter exists (confirmed
  // Part G), so fetch the org's documents and filter client-side by
  // `project_id` (the real field name -- `Document` has no `pipeline_id`).
  useEffect(() => {
    if (!pipeline) {
      setDocuments([]);
      return;
    }
    let cancelled = false;
    setDocumentsLoading(true);
    apiClient
      .listDocuments({ page_size: 200 })
      .then((res) => {
        if (cancelled || !mountedRef.current) return;
        setDocuments(res.documents.filter((d) => d.project_id === pipeline.id));
      })
      .catch(() => {
        if (!cancelled && mountedRef.current) setDocuments([]);
      })
      .finally(() => {
        if (!cancelled && mountedRef.current) setDocumentsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [pipeline]);

  // Observer signals: real per-pipeline data, independent of this run's outcome.
  useEffect(() => {
    if (!pipeline) {
      setObserverView(null);
      return;
    }
    let cancelled = false;
    setObserverLoading(true);
    apiClient
      .getObserverView(pipeline.id)
      .then((res) => {
        if (!cancelled && mountedRef.current) setObserverView(res);
      })
      .catch(() => {
        if (!cancelled && mountedRef.current) setObserverView(null);
      })
      .finally(() => {
        if (!cancelled && mountedRef.current) setObserverLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [pipeline]);

  // Diagnosis only exists once Diagnoser has actually run for this run --
  // score.failure_taxonomy is non-empty exactly when that's true.
  const hasFailureTaxonomy = (score?.failure_taxonomy.length ?? 0) > 0;
  useEffect(() => {
    if (!runId || !hasFailureTaxonomy) {
      setDiagnosis(null);
      return;
    }
    let cancelled = false;
    setDiagnosisLoading(true);
    apiClient
      .getDiagnosis(runId)
      .then((res) => {
        if (!cancelled && mountedRef.current) setDiagnosis(res);
      })
      .catch(() => {
        if (!cancelled && mountedRef.current) setDiagnosis(null);
      })
      .finally(() => {
        if (!cancelled && mountedRef.current) setDiagnosisLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [runId, hasFailureTaxonomy]);

  // Improvement only exists once Improver has run, which only happens after
  // a real diagnosis (workflow.py: observer -> diagnoser -> improver).
  useEffect(() => {
    if (!runId || !diagnosis) {
      setImprovement(null);
      return;
    }
    let cancelled = false;
    setImprovementLoading(true);
    apiClient
      .getImprovement(runId)
      .then((res) => {
        if (!cancelled && mountedRef.current) setImprovement(res);
      })
      .catch(() => {
        if (!cancelled && mountedRef.current) setImprovement(null);
      })
      .finally(() => {
        if (!cancelled && mountedRef.current) setImprovementLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [runId, diagnosis]);

  const refetch = useCallback(() => {
    void loadPipeline();
    if (runId) void loadRunData(runId);
  }, [loadPipeline, runId, loadRunData]);

  return {
    pipeline,
    runId,
    score,
    metrics,
    isLoading,
    error,
    refetch,
    documents,
    documentsLoading,
    diagnosis,
    diagnosisLoading,
    improvement,
    improvementLoading,
    observerView,
    observerLoading,
  };
}
