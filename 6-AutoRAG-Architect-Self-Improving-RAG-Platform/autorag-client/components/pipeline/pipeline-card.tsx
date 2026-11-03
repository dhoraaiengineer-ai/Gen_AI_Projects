"use client";

import type { Pipeline, PipelineWithRun } from "@/types";

interface PipelineCardProps {
  pipeline: Pipeline;
  onEvaluate: (id: string) => void;
  onDeploy: (id: string) => void;
}

const STATUS_BADGE: Record<string, string> = {
  pending:        "bg-gray-700/60 text-gray-300",
  running:        "bg-blue-900/60 text-blue-300",
  ready:          "bg-emerald-900/60 text-emerald-300",
  failed:         "bg-red-900/60 text-red-300",
  decommissioned: "bg-amber-900/60 text-amber-300",
};

export function PipelineCard({ pipeline, onEvaluate, onDeploy }: PipelineCardProps): JSX.Element {
  const withRun = pipeline as PipelineWithRun;
  const score = withRun.latest_run?.unified_score ?? null;
  const scoreColor =
    score === null
      ? "text-text-3"
      : score >= 0.85
      ? "text-emerald-400"
      : score >= 0.70
      ? "text-amber-400"
      : "text-red-400";

  const badgeClass = STATUS_BADGE[pipeline.status] ?? "bg-gray-700/60 text-gray-300";
  const deployDisabled = score === null || score < 0.85;

  return (
    <div className="bg-card rounded-xl border border-border p-5 flex flex-col gap-3 hover:border-orange-500/30 transition-colors motion-safe:transition-all">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-semibold text-foreground truncate">
          {pipeline.name || `Pipeline ${pipeline.id.slice(0, 8)}`}
        </h3>
        <span className={`px-2 py-0.5 rounded text-xs font-medium shrink-0 ${badgeClass}`}>
          {pipeline.status}
        </span>
      </div>

      {/* Meta row */}
      <div className="flex items-center gap-3 text-xs text-text-3">
        <span>v{pipeline.current_version}</span>
        <span className="text-foreground">&bull;</span>
        <span>{pipeline.chunk_strategy ?? "—"}</span>
      </div>

      {/* Score */}
      <div className="flex items-center justify-between border-t border-border pt-3">
        <div>
          <p className={`text-xl font-bold tabular-nums ${scoreColor}`}>
            {score !== null ? score.toFixed(3) : "—"}
          </p>
          <p className="text-[10px] text-text-2 uppercase tracking-wide mt-0.5">
            Unified Score
          </p>
        </div>
        {withRun.latest_run && (
          <div className="text-right">
            <p className="text-xs text-text-3">{withRun.latest_run.status}</p>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex gap-2 mt-1">
        <button
          onClick={() => onEvaluate(pipeline.id)}
          className="flex-1 px-3 py-1.5 text-xs font-medium rounded-lg bg-white/5 hover:bg-white/10 text-gray-300 transition-colors"
        >
          Evaluate
        </button>
        <button
          onClick={() => onDeploy(pipeline.id)}
          disabled={deployDisabled}
          title={deployDisabled ? "Unified Score must be >= 0.85 to deploy" : "Deploy pipeline"}
          className="flex-1 px-3 py-1.5 text-xs font-medium rounded-lg bg-orange-500/80 hover:bg-orange-500 disabled:opacity-30 disabled:cursor-not-allowed text-foreground transition-colors"
        >
          Deploy
        </button>
      </div>
    </div>
  );
}
