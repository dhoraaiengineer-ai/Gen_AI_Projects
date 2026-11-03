"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Copy, Check, ExternalLink } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { BatchEvaluation, GoldenQuestion, QuestionReviewStatus } from "@/types";

const REVIEW_BADGE: Record<QuestionReviewStatus, string> = {
  draft: "text-text-3 bg-white/5 border-border",
  under_review: "text-amber-600 bg-amber-50 border-amber-200",
  approved: "text-emerald-600 bg-emerald-50 border-emerald-200",
  rejected: "text-rose-600 bg-rose-50 border-rose-200",
  archived: "text-text-3 bg-white/5 border-border",
};

interface QuestionCardProps {
  question: GoldenQuestion;
  expanded: boolean;
  onToggle: () => void;
  /** Matched by golden_question_id from the dataset's most recent batch run, if any. */
  batchEvaluation: BatchEvaluation | undefined;
  documentName: string | null | undefined;
  onViewResult: (batchEvaluationId: string) => void;
}

/**
 * Expandable golden-question card (hand-rolled expand/collapse, matching
 * the existing precedent in components/audit/LogsTable.tsx -- no accordion
 * dependency added). Every expanded section renders only real, persisted
 * GoldenQuestion/BatchEvaluation fields -- no fabricated "Chunk Strategy",
 * "Generated Answer", or "Retrieved Chunks" text (see Version 5 backlog in
 * VERSION_5_ROADMAP.md for why those aren't here yet).
 */
export function QuestionCard({
  question: q,
  expanded,
  onToggle,
  batchEvaluation,
  documentName,
  onViewResult,
}: QuestionCardProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!q.reference_answer) return;
    await navigator.clipboard.writeText(q.reference_answer);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="rounded-lg border border-border bg-card">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="flex w-full items-start justify-between gap-3 px-3 py-3 text-left"
      >
        <div className="flex min-w-0 flex-1 items-start gap-2">
          {expanded ? (
            <ChevronDown className="mt-0.5 h-3.5 w-3.5 shrink-0 text-text-3" aria-hidden="true" />
          ) : (
            <ChevronRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-text-3" aria-hidden="true" />
          )}
          <div className="min-w-0 flex-1">
            <p className="text-sm text-foreground">{q.question}</p>
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
              {q.metric_focus && <Badge variant="outline">{q.metric_focus}</Badge>}
              {q.category && <Badge variant="outline">{q.category}</Badge>}
              {q.difficulty && <Badge variant="outline">{q.difficulty}</Badge>}
            </div>
          </div>
        </div>
        <span
          className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${REVIEW_BADGE[q.review_status]}`}
        >
          {q.review_status}
        </span>
      </button>

      {expanded && (
        <div className="space-y-4 border-t border-border px-3 py-4 text-xs">
          {/* Overview */}
          <section>
            <h4 className="eyebrow mb-1.5">Overview</h4>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-3">
              <div>
                <dt className="text-text-3">ID</dt>
                <dd className="font-mono text-foreground">{q.id.slice(0, 8)}</dd>
              </div>
              <div>
                <dt className="text-text-3">Category</dt>
                <dd className="text-foreground">{q.category ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-text-3">Difficulty</dt>
                <dd className="text-foreground">{q.difficulty ?? "—"}</dd>
              </div>
              {q.tags && q.tags.length > 0 && (
                <div className="col-span-2 sm:col-span-3">
                  <dt className="text-text-3">Tags</dt>
                  <dd className="mt-1 flex flex-wrap gap-1">
                    {q.tags.map((t) => (
                      <Badge key={t} variant="secondary">
                        {t}
                      </Badge>
                    ))}
                  </dd>
                </div>
              )}
            </dl>
          </section>

          {/* Purpose */}
          <section>
            <h4 className="eyebrow mb-1.5">Purpose</h4>
            {q.purpose ? (
              <p className="text-foreground">{q.purpose}</p>
            ) : (
              <p className="text-text-3">Not documented yet.</p>
            )}
          </section>

          {/* Expected Answer */}
          <section>
            <div className="mb-1.5 flex items-center justify-between">
              <h4 className="eyebrow">Expected Answer</h4>
              {q.reference_answer && (
                <button
                  type="button"
                  onClick={handleCopy}
                  className="flex items-center gap-1 text-[11px] font-semibold text-text-3 hover:text-foreground"
                >
                  {copied ? (
                    <Check className="h-3 w-3 text-emerald-500" aria-hidden="true" />
                  ) : (
                    <Copy className="h-3 w-3" aria-hidden="true" />
                  )}
                  {copied ? "Copied" : "Copy"}
                </button>
              )}
            </div>
            {q.reference_answer ? (
              <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-foreground">
                {q.reference_answer}
              </p>
            ) : (
              <p className="text-text-3">No reference answer recorded.</p>
            )}
          </section>

          {/* Expected Retrieval Context */}
          <section>
            <h4 className="eyebrow mb-1.5">Expected Retrieval Context</h4>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-3">
              <div>
                <dt className="text-text-3">Source Document</dt>
                <dd className="truncate text-foreground">
                  {q.reference_document_id ? (documentName ?? "—") : "—"}
                </dd>
              </div>
              <div>
                <dt className="text-text-3">Pages</dt>
                <dd className="text-foreground">{q.reference_pages ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-text-3">Chunks</dt>
                <dd className="text-foreground">
                  {q.relevant_chunk_ids && q.relevant_chunk_ids.length > 0
                    ? `${q.relevant_chunk_ids.length} chunk(s)`
                    : "—"}
                </dd>
              </div>
            </dl>
            {q.relevant_chunk_ids && q.relevant_chunk_ids.length > 0 && (
              <div className="mt-1.5 flex flex-wrap gap-1">
                {q.relevant_chunk_ids.map((id) => (
                  <span
                    key={id}
                    className="rounded border border-border bg-accent/5 px-1.5 py-0.5 font-mono text-[10px] text-text-3"
                  >
                    {id}
                  </span>
                ))}
              </div>
            )}
          </section>

          {/* Evaluation Metadata */}
          <section>
            <h4 className="eyebrow mb-1.5">Evaluation Metadata</h4>
            <p className="text-foreground">
              Primary Metric: <span className="font-semibold">{q.metric_focus ?? "Not set"}</span>
            </p>
          </section>

          {/* Evaluation Results */}
          <section>
            <h4 className="eyebrow mb-1.5">Evaluation Results</h4>
            {batchEvaluation ? (
              <div className="flex items-center justify-between rounded-lg border border-border bg-accent/5 px-3 py-2">
                <div className="flex items-center gap-3">
                  <span className="text-foreground">
                    {batchEvaluation.unified_score !== null
                      ? `Unified Score ${batchEvaluation.unified_score.toFixed(3)}`
                      : batchEvaluation.status}
                  </span>
                  {batchEvaluation.faithfulness !== null && (
                    <span className="text-text-3">
                      Faithfulness {batchEvaluation.faithfulness.toFixed(3)}
                    </span>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => onViewResult(batchEvaluation.id)}
                  className="flex items-center gap-1 text-[11px] font-semibold text-amber-700 hover:underline"
                >
                  View Full Result <ExternalLink className="h-3 w-3" aria-hidden="true" />
                </button>
              </div>
            ) : (
              <p className="text-text-3">
                No evaluation has been run yet — run this dataset from the Evaluation Center.
              </p>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
