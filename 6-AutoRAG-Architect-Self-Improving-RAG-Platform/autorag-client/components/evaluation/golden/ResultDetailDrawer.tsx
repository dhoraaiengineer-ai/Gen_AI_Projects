"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";

import { apiClient } from "@/services/api-client";
import { extractRAGASMetrics, RAGASMetrics } from "@/components/evaluation/RAGASMetrics";
import type { ResultDetail, RetrievedContextPreviewChunk } from "@/types";

interface ResultDetailDrawerProps {
  batchEvaluationId: string | null;
  onClose: () => void;
}

const ERROR_TYPE_LABEL: Record<string, string> = {
  RATE_LIMIT: "Rate limit exceeded",
  TIMEOUT: "Request timed out",
  CONNECTION_ERROR: "Network connection lost",
  AUTHENTICATION_ERROR: "Invalid API credentials",
  EVALUATION_FAILED: "Evaluation failed",
  EVALUATION_INCOMPLETE: "Evaluation did not complete",
  QUESTION_NOT_FOUND: "Question no longer available",
  UNKNOWN: "Unexpected error",
};

/**
 * Drill-in view for a single batch_evaluations row (Evaluation Center Phase
 * 2d). Only renders sections backed by data GET /batch-evaluations/results/
 * {id}/detail genuinely returns (ragas_metrics, agent_execution_metadata,
 * failure_taxonomy, from evaluation_runs) -- no fabricated "Prompt" section.
 * V4 (26-Jul-2026): Generated Answer / Retrieved Context / Judge Reason are
 * now real, captured fields (previously discarded before persistence -- see
 * evaluation_dispatch.py); failure reason (error_message/error_type) is also
 * real, persisted since migration 0019.
 */
export function ResultDetailDrawer({ batchEvaluationId, onClose }: ResultDetailDrawerProps) {
  const [detail, setDetail] = useState<ResultDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!batchEvaluationId) {
      setDetail(null);
      return;
    }
    setLoading(true);
    setError(null);
    apiClient
      .getResultDetail(batchEvaluationId)
      .then(setDetail)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load result"))
      .finally(() => setLoading(false));
  }, [batchEvaluationId]);

  if (!batchEvaluationId) return null;

  const ragas =
    detail?.ragas_metrics && typeof detail.ragas_metrics.faithfulness === "number"
      ? extractRAGASMetrics(detail.ragas_metrics.faithfulness, detail.ragas_metrics)
      : null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/50" role="dialog" aria-modal="true">
      <div className="h-full w-full max-w-lg overflow-y-auto border-l border-border bg-background p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-bold text-foreground">Result Detail</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-lg p-1 text-text-3 hover:bg-accent/5 hover:text-foreground"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        {loading && (
          <div className="space-y-3" aria-hidden="true">
            <div className="h-24 motion-safe:animate-pulse rounded-lg bg-accent/5" />
            <div className="h-24 motion-safe:animate-pulse rounded-lg bg-accent/5" />
          </div>
        )}

        {error && (
          <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </div>
        )}

        {detail && !loading && (
          <div className="space-y-5">
            <div className="flex items-center gap-3 text-xs">
              <span className="rounded-full border border-border bg-white/5 px-2.5 py-0.5 font-semibold text-text-2">
                {detail.status}
              </span>
              <span className="rounded-full border border-border bg-white/5 px-2.5 py-0.5 font-semibold text-text-2">
                review: {detail.review_status}
              </span>
              {detail.unified_score !== null && (
                <span className="font-mono font-bold text-foreground">
                  Score {detail.unified_score.toFixed(3)}
                </span>
              )}
            </div>

            {detail.status === "failed" && detail.error_message && (
              <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3">
                <p className="text-sm font-semibold text-rose-700">
                  {(detail.error_type && ERROR_TYPE_LABEL[detail.error_type]) ?? "Failed"}
                </p>
                <p className="mt-1 text-xs text-rose-700">{detail.error_message}</p>
                {detail.failed_at && (
                  <p className="mt-1 text-[11px] text-rose-500">
                    Occurred at {new Date(detail.failed_at).toLocaleString()}
                  </p>
                )}
              </div>
            )}

            {ragas && (
              <section>
                <h3 className="eyebrow mb-2">RAGAS Metrics</h3>
                <RAGASMetrics metrics={ragas} />
              </section>
            )}

            {typeof detail.agent_execution_metadata?.generated_answer === "string" && (
              <section>
                <h3 className="eyebrow mb-2">Generated Answer</h3>
                <p className="rounded-lg border border-border bg-card px-3 py-2 text-xs text-foreground">
                  {detail.agent_execution_metadata.generated_answer}
                </p>
              </section>
            )}

            {Array.isArray(detail.agent_execution_metadata?.retrieved_context_preview) && (
              <section>
                <h3 className="eyebrow mb-2">Retrieved Context</h3>
                <div className="space-y-2">
                  {(
                    detail.agent_execution_metadata
                      .retrieved_context_preview as RetrievedContextPreviewChunk[]
                  ).map((chunk) => (
                    <div
                      key={`${chunk.chunk_id}-${chunk.rank}`}
                      className="rounded-lg border border-border bg-card px-3 py-2 text-xs"
                    >
                      <div className="mb-1 flex flex-wrap items-center gap-2 text-[11px] text-text-3">
                        <span className="font-semibold text-foreground">#{chunk.rank}</span>
                        {chunk.retrieval_score !== null && (
                          <span>Score {chunk.retrieval_score.toFixed(3)}</span>
                        )}
                        {chunk.page_number !== null && <span>Page {chunk.page_number}</span>}
                        {chunk.chunk_strategy && <span>{chunk.chunk_strategy}</span>}
                      </div>
                      <p className="text-text-2">{chunk.preview}</p>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {typeof detail.ragas_metrics?.reasoning === "object" &&
              detail.ragas_metrics.reasoning !== null && (
                <section>
                  <h3 className="eyebrow mb-2">Judge Reason</h3>
                  <dl className="space-y-1.5 text-xs">
                    {Object.entries(detail.ragas_metrics.reasoning as Record<string, string>).map(
                      ([metric, reason]) => (
                        <div key={metric}>
                          <dt className="font-semibold capitalize text-foreground">
                            {metric.replace(/_/g, " ")}
                          </dt>
                          <dd className="text-text-3">{reason}</dd>
                        </div>
                      ),
                    )}
                  </dl>
                </section>
              )}

            {detail.ragas_metrics?.answer_correctness !== undefined && (
              <section className="text-xs text-text-3">
                Answer Correctness:{" "}
                <span className="font-mono text-foreground">
                  {detail.ragas_metrics.answer_correctness !== null
                    ? detail.ragas_metrics.answer_correctness.toFixed(3)
                    : "NOT_COLLECTED (no ground truth)"}
                </span>
              </section>
            )}

            {detail.failure_taxonomy && (
              <section>
                <h3 className="eyebrow mb-2">Failure Taxonomy</h3>
                <pre className="overflow-x-auto rounded-lg border border-border bg-card p-3 text-[11px] text-text-2">
                  {JSON.stringify(detail.failure_taxonomy, null, 2)}
                </pre>
              </section>
            )}

            {detail.agent_execution_metadata && (
              <section>
                <h3 className="eyebrow mb-2">Agent Execution Metadata</h3>
                <pre className="overflow-x-auto rounded-lg border border-border bg-card p-3 text-[11px] text-text-2">
                  {JSON.stringify(detail.agent_execution_metadata, null, 2)}
                </pre>
              </section>
            )}

            {!ragas && !detail.evaluation_run_id && (
              <p className="text-xs text-text-3">
                This question hasn&apos;t completed a graph run yet — no metrics available.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
