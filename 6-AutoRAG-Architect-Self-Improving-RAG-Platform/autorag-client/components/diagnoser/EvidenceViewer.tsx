"use client";

import { CostLatencyPanel } from "@/components/evaluation/CostLatencyPanel";
import { FAITHFULNESS_HARD_BLOCK } from "@/lib/score";
import type { ScoreResult } from "@/types";

interface EvidenceViewerProps {
  score: ScoreResult;
}

/** Matches autorag-server/app/graph/nodes/diagnoser.py `_LATENCY_THRESHOLD_MS`. */
const LATENCY_GATE_MS = 3000;

interface MetricRow {
  label: string;
  display: string;
  breach: boolean;
  /** Only set for metrics with a verified runtime gate in diagnoser.py — Recall/Quality
   *  have no fixed numeric threshold enforced anywhere in the real classification code. */
  gate: string | null;
}

/** The real numbers backing RootCausePanel's classification — reuses CostLatencyPanel as-is. */
export function EvidenceViewer({ score }: EvidenceViewerProps) {
  const rows: MetricRow[] = [
    {
      label: "Recall",
      display: score.recall !== null ? score.recall.toFixed(2) : "Unavailable",
      breach: false,
      gate: null,
    },
    {
      label: "Quality",
      display: score.quality !== null ? score.quality.toFixed(2) : "Unavailable",
      breach: false,
      gate: null,
    },
    {
      label: "Faithfulness",
      display: score.faithfulness !== null ? score.faithfulness.toFixed(2) : "Unavailable",
      breach: score.faithfulness !== null && score.faithfulness < FAITHFULNESS_HARD_BLOCK,
      gate: `>= ${FAITHFULNESS_HARD_BLOCK}`,
    },
    {
      label: "Latency p95",
      display: score.latency_p95_ms !== null ? `${score.latency_p95_ms}ms` : "Unavailable",
      breach: score.latency_p95_ms !== null && score.latency_p95_ms > LATENCY_GATE_MS,
      gate: `< ${LATENCY_GATE_MS}ms`,
    },
  ];

  return (
    <div className="space-y-4">
      <div className="overflow-hidden rounded-xl border border-border bg-card">
        <table className="w-full text-left text-sm">
          <thead className="text-xs uppercase tracking-wide text-text-3">
            <tr className="border-b border-border">
              <th className="px-4 py-3 font-medium">Metric</th>
              <th className="px-4 py-3 font-medium">Value</th>
              <th className="px-4 py-3 font-medium">Gate</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.label} className="border-b border-border/60">
                <td className="px-4 py-3 text-text-2">{row.label}</td>
                <td
                  className={`px-4 py-3 font-mono ${
                    row.display === "Unavailable"
                      ? "italic text-text-3"
                      : row.breach
                        ? "text-red-500"
                        : "text-foreground"
                  }`}
                >
                  {row.display}
                </td>
                <td className="px-4 py-3 text-xs text-text-3">{row.gate ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <CostLatencyPanel score={score} />
    </div>
  );
}
