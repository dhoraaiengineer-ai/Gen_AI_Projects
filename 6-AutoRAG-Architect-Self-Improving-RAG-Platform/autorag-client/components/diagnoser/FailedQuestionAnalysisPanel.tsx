"use client";

/**
 * Failed Question Analysis (Evaluation Center Phase 4, 24-Jul-2026) --
 * additive panel, not a rebuild: drills into a batch run's low-scoring
 * questions using the failure taxonomy already persisted per evaluation_run
 * (build_failure_taxonomy() in evaluation_dispatch.py) via the existing
 * Result Detail endpoint -- no new diagnosis logic, reuses ResultDetailDrawer
 * verbatim rather than duplicating it.
 */

import { useEffect, useState } from "react";

import { apiClient } from "@/services/api-client";
import { ResultDetailDrawer } from "@/components/evaluation/golden/ResultDetailDrawer";
import type { BatchRun, BatchRunSummary } from "@/types";

interface FailedQuestionAnalysisPanelProps {
  pipelineId: string | null;
}

export function FailedQuestionAnalysisPanel({ pipelineId }: FailedQuestionAnalysisPanelProps) {
  const [runs, setRuns] = useState<BatchRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [summary, setSummary] = useState<BatchRunSummary | null>(null);
  const [drawerId, setDrawerId] = useState<string | null>(null);

  useEffect(() => {
    if (!pipelineId) return;
    setSelectedRunId("");
    setSummary(null);
    apiClient
      .listBatchRuns({ pipelineId, status: "completed" })
      .then((items) => {
        setRuns(items);
        setSelectedRunId(items[0]?.id ?? "");
      })
      .catch(() => setRuns([]));
  }, [pipelineId]);

  useEffect(() => {
    if (!selectedRunId) return;
    apiClient.getBatchRun(selectedRunId).then(setSummary).catch(() => setSummary(null));
  }, [selectedRunId]);

  if (!pipelineId || runs.length === 0) {
    return (
      <section aria-labelledby="diagnose-failed-questions-heading">
        <h2
          id="diagnose-failed-questions-heading"
          className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-3"
        >
          Failed Question Analysis
        </h2>
        <p className="rounded-xl border border-border bg-card p-6 text-center text-sm text-text-3">
          No completed batch evaluation runs for this pipeline yet — start one from the Evaluation
          Center&apos;s Batch Runs tab.
        </p>
      </section>
    );
  }

  return (
    <section aria-labelledby="diagnose-failed-questions-heading">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2
          id="diagnose-failed-questions-heading"
          className="text-xs font-semibold uppercase tracking-wide text-text-3"
        >
          Failed Question Analysis
        </h2>
        <select
          value={selectedRunId}
          onChange={(e) => setSelectedRunId(e.target.value)}
          aria-label="Batch run"
          className="rounded-md border border-border bg-accent/5 px-2 py-1 text-xs text-foreground"
        >
          {runs.map((r) => (
            <option key={r.id} value={r.id}>
              {r.id.slice(0, 8)} — {r.created_at ? new Date(r.created_at).toLocaleDateString() : ""}
            </option>
          ))}
        </select>
      </div>

      {summary && summary.worst_scoring.length === 0 && (
        <p className="rounded-xl border border-border bg-card p-6 text-center text-sm text-text-3">
          No low-scoring questions in this batch run.
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
