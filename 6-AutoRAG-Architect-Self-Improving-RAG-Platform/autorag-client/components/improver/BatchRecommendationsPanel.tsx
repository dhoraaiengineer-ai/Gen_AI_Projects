"use client";

/**
 * Batch Recommendations (Evaluation Center Phase 4, 24-Jul-2026) -- additive
 * panel: surfaces the pipeline's most recent batch run's low-scoring
 * questions in Improver context. improver_candidates (when present) already
 * live in evaluation_runs.agent_execution_metadata and are shown via the
 * same ResultDetailDrawer the Evaluation Center and Diagnoser use -- no new
 * recommendation engine, no duplicated logic.
 */

import { useEffect, useState } from "react";

import { apiClient } from "@/services/api-client";
import { ResultDetailDrawer } from "@/components/evaluation/golden/ResultDetailDrawer";
import type { BatchRun, BatchRunSummary } from "@/types";

interface BatchRecommendationsPanelProps {
  pipelineId: string | null;
}

export function BatchRecommendationsPanel({ pipelineId }: BatchRecommendationsPanelProps) {
  const [latestRun, setLatestRun] = useState<BatchRun | null>(null);
  const [summary, setSummary] = useState<BatchRunSummary | null>(null);
  const [drawerId, setDrawerId] = useState<string | null>(null);

  useEffect(() => {
    if (!pipelineId) return;
    setLatestRun(null);
    setSummary(null);
    apiClient
      .listBatchRuns({ pipelineId, status: "completed" })
      .then((items) => setLatestRun(items[0] ?? null))
      .catch(() => setLatestRun(null));
  }, [pipelineId]);

  useEffect(() => {
    if (!latestRun) return;
    apiClient.getBatchRun(latestRun.id).then(setSummary).catch(() => setSummary(null));
  }, [latestRun]);

  if (!pipelineId || !latestRun) return null;

  return (
    <section aria-labelledby="improve-batch-recs">
      <h2 id="improve-batch-recs" className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-3">
        Batch Recommendations
      </h2>
      <p className="mb-3 text-xs text-text-3">
        Low-scoring questions from the most recent batch run ({latestRun.id.slice(0, 8)}) — open a
        question to see any Improver candidates captured for that run.
      </p>

      {summary && summary.worst_scoring.length === 0 && (
        <p className="rounded-xl border border-border bg-card p-6 text-center text-sm text-text-3">
          No low-scoring questions in the latest batch run.
        </p>
      )}

      <div className="space-y-2">
        {summary?.worst_scoring.map((r) => (
          <button
            key={r.id}
            onClick={() => setDrawerId(r.id)}
            className="flex w-full items-center justify-between rounded-lg border border-border bg-card px-4 py-2.5 text-left text-xs hover:bg-accent/5"
          >
            <span className="font-mono text-text-3">{r.golden_question_id.slice(0, 8)}</span>
            <span className="font-mono font-bold text-rose-400">
              {r.unified_score !== null ? r.unified_score.toFixed(3) : "—"}
            </span>
          </button>
        ))}
      </div>

      <ResultDetailDrawer batchEvaluationId={drawerId} onClose={() => setDrawerId(null)} />
    </section>
  );
}
