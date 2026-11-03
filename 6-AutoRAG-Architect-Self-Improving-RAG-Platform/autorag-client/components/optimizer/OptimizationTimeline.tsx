"use client";

import { formatScorePercent } from "@/lib/score";
import type { PipelineVersionSummary } from "@/types";

interface OptimizationTimelineProps {
  versions: PipelineVersionSummary[];
  currentVersion: number;
}

/**
 * Real pipeline version history as a horizontal chain (20-Jul-2026, Apply
 * Improvement feature) -- each node's score is real (from GET
 * /pipelines/{id}/versions, sourced from evaluation_runs/experiment_runs),
 * never fabricated. A version with no completed evaluation yet shows "—",
 * not a guessed number. Score-band coloring mirrors the same 0.85/0.70
 * thresholds evaluator-standards.md Rule 2 documents platform-wide.
 */
export function OptimizationTimeline({ versions, currentVersion }: OptimizationTimelineProps) {
  if (versions.length === 0) {
    return (
      <p className="text-xs text-text-3">No version history yet for this pipeline.</p>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {versions.map((v, i) => (
        <div key={v.version_number} className="flex items-center gap-2">
          <div
            className={`flex flex-col items-center gap-1 rounded-xl border px-3 py-2.5 ${
              v.version_number === currentVersion
                ? "border-accent/50 bg-accent/10"
                : "border-border bg-accent/5"
            }`}
          >
            <span className="text-[10px] font-semibold uppercase tracking-wide text-text-3">
              v{v.version_number}
              {v.version_number === currentVersion && (
                <span className="ml-1 text-accent">· current</span>
              )}
            </span>
            <span className={`font-mono text-lg font-bold ${scoreColor(v.unified_score)}`}>
              {formatScorePercent(v.unified_score)}
            </span>
            <span className="text-[10px] capitalize text-text-3">{v.chunk_strategy}</span>
          </div>
          {i < versions.length - 1 && <span className="text-text-3">→</span>}
        </div>
      ))}
    </div>
  );
}

function scoreColor(score: number | null): string {
  if (score === null) return "text-text-3";
  if (score >= 0.85) return "text-emerald-400";
  if (score >= 0.7) return "text-amber-400";
  return "text-rose-400";
}
