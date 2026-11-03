import { Info } from "lucide-react";

import type { ScoreResult } from "@/types";

interface PredictedImprovementsProps {
  score: ScoreResult;
}

/**
 * §29.11 Predicted Improvements — HONEST boundary.
 *
 * The spec asks for predicted Unified Score / latency / faithfulness etc. Nothing
 * in the platform computes a prediction for an unbuilt variant, and fabricating
 * one violates CLAUDE.md Forbidden Pattern #2 + Rule 50. So this panel shows the
 * real current baseline and states plainly that predicted values require an
 * actual evaluation run (the "Queue for Evaluation" action below).
 */
export function PredictedImprovements({ score }: PredictedImprovementsProps) {
  const rows: { label: string; value: string }[] = [
    { label: "Unified Score", value: score.unified_score !== null ? score.unified_score.toFixed(2) : "Not collected" },
    { label: "Faithfulness", value: score.faithfulness !== null ? score.faithfulness.toFixed(2) : "Not collected" },
    { label: "Recall", value: score.recall !== null ? score.recall.toFixed(2) : "Unavailable" },
    { label: "Quality", value: score.quality !== null ? score.quality.toFixed(2) : "Unavailable" },
    { label: "Latency p95", value: `${score.latency_p95_ms} ms` },
    { label: "Cost / query", value: score.cost_per_query_usd === null ? "—" : `$${score.cost_per_query_usd.toFixed(4)}` },
    { label: "Total tokens", value: score.total_tokens === null ? "—" : score.total_tokens.toLocaleString() },
  ];

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
        {rows.map((row) => (
          <div key={row.label}>
            <dt className="text-xs font-medium uppercase tracking-wide text-text-3">{row.label}</dt>
            <dd className="mt-1 font-mono text-sm text-foreground">{row.value}</dd>
          </div>
        ))}
      </dl>

      <p className="mt-5 flex items-start gap-2 rounded-lg border border-border bg-accent/5 p-3 text-xs text-text-3">
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-text-3" aria-hidden="true" />
        <span>
          Values above are the <span className="font-medium text-text-2">current baseline</span>.
          Predicted scores for the proposed variant require a real evaluation run — queue it below to
          measure the actual impact.
        </span>
      </p>
    </div>
  );
}
