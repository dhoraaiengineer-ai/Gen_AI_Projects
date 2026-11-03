"use client";

import { isHardBlock, FAITHFULNESS_HARD_BLOCK } from "@/lib/score";

export interface RAGASMetricValues {
  faithfulness: number;
  answer_relevance: number;
  context_recall: number;
  context_precision: number;
}

interface RAGASMetricsProps {
  metrics: RAGASMetricValues;
}

interface MetricSpec {
  key: keyof RAGASMetricValues;
  label: string;
  target: number;
  hardBlockBelow?: number;
}

const METRIC_SPECS: MetricSpec[] = [
  { key: "faithfulness", label: "Faithfulness", target: 0.8, hardBlockBelow: FAITHFULNESS_HARD_BLOCK },
  { key: "answer_relevance", label: "Answer Relevance", target: 0.8 },
  { key: "context_recall", label: "Context Recall", target: 0.85 },
  { key: "context_precision", label: "Context Precision", target: 0.8 },
];

export function RAGASMetrics({ metrics }: RAGASMetricsProps) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {METRIC_SPECS.map((spec) => {
        const value = metrics[spec.key];
        const blocked = spec.hardBlockBelow !== undefined && value < spec.hardBlockBelow;
        const belowTarget = value < spec.target;

        const borderClass = blocked
          ? "border-red-700"
          : belowTarget
          ? "border-amber-700"
          : "border-border";

        const valueClass = blocked
          ? "text-red-500"
          : belowTarget
          ? "text-amber-400"
          : "text-emerald-400";

        const barColor = blocked
          ? "bg-red-500"
          : belowTarget
          ? "bg-amber-500"
          : "bg-emerald-500";

        return (
          <div
            key={spec.key}
            className={`rounded-lg border ${borderClass} bg-card p-4 animate-fade-in`}
          >
            <div className="flex items-start justify-between gap-2">
              <p className="text-xs font-medium uppercase tracking-wide text-text-3">
                {spec.label}
              </p>
              {blocked && (
                <span className="shrink-0 rounded-full bg-red-900/60 px-2 py-0.5 text-[10px] font-bold text-red-600">
                  HARD BLOCK
                </span>
              )}
            </div>

            <p className={`mt-2 text-2xl font-bold font-mono ${valueClass}`}>
              {value.toFixed(3)}
            </p>

            <p className="mt-0.5 text-[10px] text-text-3">
              Target: {"≥"} {spec.target}
              {spec.hardBlockBelow !== undefined && (
                <span className="ml-1 text-red-500">
                  (block &lt; {spec.hardBlockBelow})
                </span>
              )}
            </p>

            {/* Progress bar */}
            <div className="mt-2 h-1 w-full rounded-full bg-gray-200">
              <div
                className={`h-1 rounded-full ${barColor} motion-safe:transition-all motion-safe:duration-500`}
                style={{ width: `${Math.min(value * 100, 100)}%` }}
                role="progressbar"
                aria-valuenow={Math.round(value * 100)}
                aria-valuemin={0}
                aria-valuemax={100}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** Pull a numeric field out of the loose `ragas_metrics` record, or 0 if absent/non-numeric. */
function _numField(ragas: Record<string, unknown>, key: string): number {
  const value = ragas[key];
  return typeof value === "number" ? value : 0;
}

/**
 * Extract RAGAS metrics from the loose `ragas_metrics` record + known ScoreResult fields.
 * `ragas_metrics` also carries non-numeric provenance keys (evaluation_mode,
 * recall_at_5_measured, score_provenance — P0.6, 13-Jul-2026), hence the
 * `unknown` value type and the numeric guard above.
 */
export function extractRAGASMetrics(
  faithfulness: number,
  ragas: Record<string, unknown>,
): RAGASMetricValues {
  return {
    faithfulness,
    answer_relevance:
      _numField(ragas, "answer_relevance") || _numField(ragas, "answer_relevancy"),
    context_recall: _numField(ragas, "context_recall"),
    context_precision: _numField(ragas, "context_precision"),
  };
}

// Re-export for convenience
export { isHardBlock };
