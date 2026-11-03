"use client";

import type { ScoreResult, ValueType } from "@/types";

interface ScoreProvenanceProps {
  score: ScoreResult;
}

const BADGE_STYLE: Record<ValueType, { bg: string; color: string }> = {
  MEASURED: { bg: "rgba(16,185,129,0.12)", color: "#34D399" },
  DERIVED: { bg: "rgba(91,92,226,0.12)", color: "#818CF8" },
  ESTIMATED: { bg: "rgba(139,92,246,0.12)", color: "#A78BFA" },
  NOT_COLLECTED: { bg: "rgba(15,23,42,0.06)", color: "var(--text-3)" },
};

function Badge({ type }: { type: ValueType }) {
  const s = BADGE_STYLE[type];
  return (
    <span
      className="rounded-full px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide"
      style={{ backgroundColor: s.bg, color: s.color }}
    >
      {type.replace("_", " ")}
    </span>
  );
}

/**
 * Part H — Score Provenance. Shows the 5 real inputs behind the Unified
 * Score formula, each with an explicit MEASURED/DERIVED/ESTIMATED/
 * NOT_COLLECTED badge (P0.6-3's value_types, never inferred client-side).
 * A field with no value_types entry and a null value renders NOT_COLLECTED
 * defensively -- never silently converted to 0.
 */
export function ScoreProvenance({ score }: ScoreProvenanceProps) {
  const vt = score.value_types ?? {};

  const rows: { label: string; value: string; type: ValueType }[] = [
    {
      label: "Retrieval / Recall",
      value: score.recall !== null ? score.recall.toFixed(3) : "Not collected",
      type: vt.recall ?? (score.recall !== null ? "MEASURED" : "NOT_COLLECTED"),
    },
    {
      label: "Quality",
      value: score.quality !== null ? score.quality.toFixed(3) : "Not collected",
      type: vt.quality ?? (score.quality !== null ? "MEASURED" : "NOT_COLLECTED"),
    },
    {
      label: "Faithfulness",
      value: score.faithfulness !== null ? score.faithfulness.toFixed(3) : "Not collected",
      type: vt.faithfulness ?? (score.faithfulness !== null ? "MEASURED" : "NOT_COLLECTED"),
    },
    {
      label: "Latency (p95)",
      value: score.latency_p95_ms !== null ? `${score.latency_p95_ms}ms` : "Not collected",
      type: vt.latency_p95_ms ?? (score.latency_p95_ms !== null ? "MEASURED" : "NOT_COLLECTED"),
    },
    {
      label: "Cost / Query",
      value: score.cost_per_query_usd !== null ? `$${score.cost_per_query_usd.toFixed(5)}` : "Not collected",
      type: vt.cost_per_query_usd ?? (score.cost_per_query_usd !== null ? "MEASURED" : "NOT_COLLECTED"),
    },
  ];

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="mb-3 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
        Score Provenance
      </p>
      <dl className="grid grid-cols-1 gap-3 sm:grid-cols-5">
        {rows.map((row) => (
          <div key={row.label} className="min-w-0">
            <dt className="text-[10px] text-muted-foreground">{row.label}</dt>
            <dd className="mt-0.5 font-mono text-sm font-semibold text-foreground">{row.value}</dd>
            <div className="mt-1">
              <Badge type={row.type} />
            </div>
          </div>
        ))}
      </dl>
      {score.score_provenance && (
        <p className="mt-3 border-t border-border pt-2 text-[10px] text-muted-foreground">
          Formula {score.score_provenance.formula_version} · {score.score_provenance.evaluation_mode} mode
        </p>
      )}
    </div>
  );
}
