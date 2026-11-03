"use client";

import type { PipelineVersionSummary } from "@/types";
import { RollbackButton } from "@/components/optimizer/RollbackButton";
import { formatScorePercent } from "@/lib/score";

interface VersionHistoryTableProps {
  pipelineId: string;
  versions: PipelineVersionSummary[];
  currentVersion: number;
  onRolledBack?: () => void;
}

/**
 * Detail table behind the OptimizationTimeline strip -- every column is a
 * real column from GET /pipelines/{id}/versions (migration 0015 links each
 * applied version to the evaluation_run that scored it). A version with no
 * completed evaluation yet shows "—" for every metric, never a guess.
 */
export function VersionHistoryTable({
  pipelineId,
  versions,
  currentVersion,
  onRolledBack,
}: VersionHistoryTableProps) {
  if (versions.length === 0) {
    return <p className="text-xs text-text-3">No version history yet for this pipeline.</p>;
  }

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <table className="w-full text-left text-sm">
        <thead className="text-xs uppercase tracking-wide text-text-3">
          <tr className="border-b border-border">
            <th className="px-4 py-3 font-medium">Version</th>
            <th className="px-4 py-3 font-medium">Score</th>
            <th className="px-4 py-3 font-medium">Δ</th>
            <th className="px-4 py-3 font-medium">Recall</th>
            <th className="px-4 py-3 font-medium">Latency (p95)</th>
            <th className="px-4 py-3 font-medium">Cost</th>
            <th className="px-4 py-3 font-medium">Created</th>
            <th className="px-4 py-3 font-medium" />
          </tr>
        </thead>
        <tbody>
          {[...versions].reverse().map((v) => {
            const isCurrent = v.version_number === currentVersion;
            return (
              <tr key={v.version_number} className="border-b border-border last:border-0">
                <td className="px-4 py-3 font-mono text-foreground">
                  v{v.version_number}
                  {isCurrent && (
                    <span className="ml-2 rounded-full bg-accent/15 px-2 py-0.5 text-[10px] font-semibold uppercase text-accent">
                      Current
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 font-mono font-semibold text-foreground">
                  {formatScorePercent(v.unified_score)}
                </td>
                <td className="px-4 py-3 font-mono text-text-3">
                  {v.score_delta !== null
                    ? `${v.score_delta >= 0 ? "+" : ""}${v.score_delta.toFixed(3)}`
                    : "—"}
                </td>
                <td className="px-4 py-3 font-mono text-text-2">
                  {v.recall !== null ? v.recall.toFixed(3) : "—"}
                </td>
                <td className="px-4 py-3 font-mono text-text-2">
                  {v.latency_p95_ms !== null ? `${v.latency_p95_ms} ms` : "—"}
                </td>
                <td className="px-4 py-3 font-mono text-text-2">
                  {v.cost_usd !== null ? `$${v.cost_usd.toFixed(4)}` : "—"}
                </td>
                <td className="px-4 py-3 text-xs text-text-3">
                  {v.created_at ? new Date(v.created_at).toLocaleString() : "—"}
                </td>
                <td className="px-4 py-3">
                  {!isCurrent && (
                    <RollbackButton
                      pipelineId={pipelineId}
                      versionNumber={v.version_number}
                      onRolledBack={onRolledBack}
                    />
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
