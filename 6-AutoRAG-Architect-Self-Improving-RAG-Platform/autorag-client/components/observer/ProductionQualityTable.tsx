import { Check, X } from "lucide-react";

import { DEPLOY_GATE, formatScore } from "@/lib/score";
import { LATENCY_SLA_MS } from "@/lib/observer";
import type { ScoreResult } from "@/types";

interface ProductionQualityTableProps {
  score: ScoreResult | null;
}

interface Row {
  metric: string;
  current: string;
  target: string;
  pass: boolean | null;
}

/**
 * Real Metric/Current/Target/Status table for the selected pipeline
 * (25-Jul-2026, capability-first polish pass). Current values come from the
 * already-fetched ScoreResult; targets are this app's existing real
 * governance constants (lib/score.ts, lib/observer.ts) -- no invented
 * thresholds (Recall/Cost have no real target defined anywhere in the
 * codebase, so they're intentionally left out rather than guessed).
 */
export function ProductionQualityTable({ score }: ProductionQualityTableProps) {
  if (!score) {
    return (
      <div className="rounded-xl border border-border bg-card p-6 text-center text-sm text-text-3">
        No completed evaluation run for this pipeline yet.
      </div>
    );
  }

  const rows: Row[] = [
    {
      metric: "Unified Score",
      current: formatScore(score.unified_score),
      target: `≥ ${DEPLOY_GATE}`,
      pass: score.unified_score !== null ? score.unified_score >= DEPLOY_GATE : null,
    },
    {
      metric: "Latency (p95)",
      current: score.latency_p95_ms !== null ? `${(score.latency_p95_ms / 1000).toFixed(1)}s` : "—",
      target: `< ${(LATENCY_SLA_MS / 1000).toFixed(0)}s`,
      pass: score.latency_p95_ms !== null ? score.latency_p95_ms < LATENCY_SLA_MS : null,
    },
  ];

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <table className="w-full text-left text-sm">
        <thead className="text-[10px] uppercase tracking-wide text-text-3">
          <tr className="border-b border-border">
            <th className="px-4 py-2.5 font-medium">Metric</th>
            <th className="px-4 py-2.5 font-medium">Current</th>
            <th className="px-4 py-2.5 font-medium">Target</th>
            <th className="px-4 py-2.5 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.metric} className="border-b border-border/60 last:border-0">
              <td className="px-4 py-2.5 text-text-2">{row.metric}</td>
              <td className="px-4 py-2.5 font-mono font-semibold text-foreground">{row.current}</td>
              <td className="px-4 py-2.5 font-mono text-text-3">{row.target}</td>
              <td className="px-4 py-2.5">
                {row.pass === null ? (
                  <span className="text-text-3">—</span>
                ) : row.pass ? (
                  <Check className="h-4 w-4 text-emerald-500" aria-hidden="true" />
                ) : (
                  <X className="h-4 w-4 text-rose-500" aria-hidden="true" />
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
