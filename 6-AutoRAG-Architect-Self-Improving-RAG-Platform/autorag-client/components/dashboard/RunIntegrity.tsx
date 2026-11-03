"use client";

import type { NodeTraceEntry, ScoreResult } from "@/types";

interface RunIntegrityProps {
  runId: string;
  score: ScoreResult;
  lastEntry: NodeTraceEntry | undefined;
  totalRetries: number;
}

const RETRY_CEILING = 3; // matches _route_after_observer's real ceiling (workflow.py)

/**
 * Part H — Run Integrity. Execution-trace and metrics persistence are real,
 * already-proven DB-backed facts (Part G) -- safe to state plainly.
 * Checkpoint/recovery status is NOT currently exposed by any live API
 * (confirmed in an earlier audit: no checkpoint-read endpoint exists) --
 * rendered honestly as "Not exposed," never inferred from architecture docs.
 */
export function RunIntegrity({ runId, score, lastEntry, totalRetries }: RunIntegrityProps) {
  const rows: [string, string][] = [
    ["Execution Trace", score.node_trace && score.node_trace.length > 0 ? "Persisted" : "Not collected"],
    ["Metrics", "Persisted"],
    ["Checkpoint", "Not exposed"],
    ["Retry Count", `${totalRetries} / ${RETRY_CEILING}`],
    ["Run ID", runId],
    ["Trace ID", lastEntry?.x_trace_id ?? "Unavailable"],
    ["Last Reached Node", lastEntry?.node ?? "Not collected"],
    ["Recovery", "Not exposed"],
  ];

  return (
    <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
      <p className="mb-3 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
        Run Integrity
      </p>
      <dl className="space-y-2">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-baseline justify-between gap-3">
            <dt className="text-xs text-text-3">{label}</dt>
            <dd className="truncate font-mono text-xs font-medium text-foreground" title={value}>
              {value}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
