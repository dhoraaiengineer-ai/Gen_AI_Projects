/**
 * Experiments aggregation (F-16) -- pure, React-free, unit-testable.
 *
 * `GET /api/v1/experiments` is real (Part E, 12-Jul-2026 -- fixed two bugs
 * there too: it returned the internal `run.id` PK instead of the external
 * `run.run_id` correlation ID every other route expects, and read a
 * nonexistent `quality_score` column instead of the real `quality` one).
 * `toExperimentRecord` (score-fan-out based) is kept for callers that already
 * have a ScoreResult; `fromExperimentApiRecord` is the new primary path,
 * built directly from the real /experiments list.
 */

import { scoreBand, DEPLOY_GATE, HITL_LOWER } from "@/lib/score";
import type { ExperimentApiRecord, PipelineWithRun, ScoreResult, RunStatus } from "@/types";

// ---------------------------------------------------------------------------
// Derived domain types
// ---------------------------------------------------------------------------

export type ExperimentStatus = "completed" | "running" | "failed" | "promoted" | "archived";

export interface ExperimentRecord {
  id: string;            // pipeline run_id (or pipeline id if no run)
  pipelineId: string;
  pipelineName: string;
  version: string;
  status: ExperimentStatus;
  unifiedScore: number | null;
  latencyMs: number | null;
  costUsd: number | null;
  faithfulness: number | null;
  recall: number | null;
  createdBy: string;
  createdAt: string;
  /** Whether this experiment meets the >= 0.85 deploy gate. */
  deployEligible: boolean;
}

export interface ExperimentSummary {
  total: number;
  active: number;
  completed: number;
  bestUnifiedScore: number | null;
  avgLatencyMs: number | null;
}

export interface ComparisonRow {
  metric: string;
  a: string;
  b: string;
  winner: "a" | "b" | "tie";
}

export interface MetricsChartPoint {
  label: string;
  unified_score: number;
  latency_ms: number;
  cost_usd: number;
}

// ---------------------------------------------------------------------------
// Builders
// ---------------------------------------------------------------------------

function runStatusToExperiment(runStatus: RunStatus | undefined): ExperimentStatus {
  if (!runStatus) return "running";
  if (runStatus === "completed") return "completed";
  if (runStatus === "failed") return "failed";
  if (runStatus === "rolled_back") return "archived";
  return "running";
}

/** Convert a PipelineWithRun (+ optional scored result) into an ExperimentRecord. */
export function toExperimentRecord(
  pipeline: PipelineWithRun,
  score: ScoreResult | null,
): ExperimentRecord {
  const base = pipeline.name || `Pipeline ${pipeline.id.slice(0, 8)}`;
  const run = pipeline.latest_run;
  return {
    id: run?.id ?? pipeline.id,
    pipelineId: pipeline.id,
    pipelineName: base,
    version: String(pipeline.current_version),
    status: runStatusToExperiment(run?.status),
    unifiedScore: score?.unified_score ?? null,
    latencyMs: score?.latency_p95_ms ?? null,
    costUsd: score?.cost_per_query_usd ?? null,
    faithfulness: score?.faithfulness ?? null,
    recall: score?.recall ?? null,
    createdBy: pipeline.created_at ? "Team" : "Unknown",
    createdAt: pipeline.created_at,
    deployEligible: score !== null && score.unified_score !== null && score.unified_score >= DEPLOY_GATE,
  };
}

function apiStatusToExperiment(status: string): ExperimentStatus {
  if (status === "completed") return "completed";
  if (status === "failed") return "failed";
  if (status === "blocked") return "archived";
  // "pending" | "pending_approval" | anything else in-flight
  return "running";
}

/** Convert a real /experiments record + its owning pipeline into an ExperimentRecord. */
export function fromExperimentApiRecord(
  record: ExperimentApiRecord,
  pipeline: PipelineWithRun | undefined,
): ExperimentRecord {
  const base = pipeline?.name || `Pipeline ${record.pipeline_id.slice(0, 8)}`;
  return {
    id: record.run_id,
    pipelineId: record.pipeline_id,
    pipelineName: base,
    version: pipeline ? String(pipeline.current_version) : "—",
    status: apiStatusToExperiment(record.status),
    unifiedScore: record.unified_score,
    latencyMs: record.latency_p95_ms,
    costUsd: record.cost_usd,
    faithfulness: record.faithfulness,
    recall: record.recall,
    createdBy: pipeline?.created_at ? "Team" : "Unknown",
    createdAt: record.created_at ?? pipeline?.created_at ?? "",
    deployEligible: record.unified_score !== null && record.unified_score >= DEPLOY_GATE,
  };
}

/** Ch 30.7: aggregate summary cards across all experiment records. */
export function computeExperimentSummary(records: ExperimentRecord[]): ExperimentSummary {
  const completed = records.filter((r) => r.status === "completed" || r.status === "promoted");
  const active = records.filter((r) => r.status === "running");
  const scored = records.filter((r) => r.unifiedScore !== null);

  const bestUnifiedScore =
    scored.length > 0
      ? Math.max(...scored.map((r) => r.unifiedScore as number))
      : null;

  const latencies = scored
    .filter((r) => r.latencyMs !== null)
    .map((r) => r.latencyMs as number);
  const avgLatencyMs =
    latencies.length > 0
      ? latencies.reduce((a, b) => a + b, 0) / latencies.length
      : null;

  return {
    total: records.length,
    active: active.length,
    completed: completed.length,
    bestUnifiedScore,
    avgLatencyMs,
  };
}

// ---------------------------------------------------------------------------
// Comparison (Ch 30.9)
// ---------------------------------------------------------------------------

function fmtScore(v: number | null): string {
  return v === null ? "—" : v.toFixed(3);
}
function fmtMs(v: number | null): string {
  return v === null ? "—" : `${Math.round(v)} ms`;
}
function fmtUsd(v: number | null): string {
  return v === null ? "—" : `$${v.toFixed(4)}`;
}

/** Build side-by-side comparison rows for two experiment records (Ch 30.9). */
export function buildComparisonRows(a: ExperimentRecord, b: ExperimentRecord): ComparisonRow[] {
  function winner(
    aVal: number | null,
    bVal: number | null,
    higherIsBetter: boolean,
  ): "a" | "b" | "tie" {
    if (aVal === null || bVal === null) return "tie";
    if (aVal === bVal) return "tie";
    return (aVal > bVal) === higherIsBetter ? "a" : "b";
  }

  return [
    {
      metric: "Unified Score",
      a: fmtScore(a.unifiedScore),
      b: fmtScore(b.unifiedScore),
      winner: winner(a.unifiedScore, b.unifiedScore, true),
    },
    {
      metric: "Faithfulness",
      a: fmtScore(a.faithfulness),
      b: fmtScore(b.faithfulness),
      winner: winner(a.faithfulness, b.faithfulness, true),
    },
    {
      metric: "Recall",
      a: fmtScore(a.recall),
      b: fmtScore(b.recall),
      winner: winner(a.recall, b.recall, true),
    },
    {
      metric: "Latency (p95)",
      a: fmtMs(a.latencyMs),
      b: fmtMs(b.latencyMs),
      winner: winner(a.latencyMs, b.latencyMs, false),
    },
    {
      metric: "Cost / query",
      a: fmtUsd(a.costUsd),
      b: fmtUsd(b.costUsd),
      winner: winner(a.costUsd, b.costUsd, false),
    },
    {
      metric: "Deploy Eligible",
      a: a.deployEligible ? "Yes" : "No",
      b: b.deployEligible ? "Yes" : "No",
      winner:
        a.deployEligible === b.deployEligible
          ? "tie"
          : a.deployEligible
          ? "a"
          : "b",
    },
  ];
}

// ---------------------------------------------------------------------------
// Chart data (Ch 30.10)
// ---------------------------------------------------------------------------

/** Build Recharts-ready data points for the metrics dashboard (Ch 30.10). */
export function buildMetricsChartData(records: ExperimentRecord[]): MetricsChartPoint[] {
  return records
    .filter((r) => r.unifiedScore !== null)
    .map((r) => ({
      label: `v${r.version}`,
      unified_score: r.unifiedScore as number,
      latency_ms: r.latencyMs ?? 0,
      cost_usd: r.costUsd ?? 0,
    }));
}

// ---------------------------------------------------------------------------
// Score band helper (re-exported for component use)
// ---------------------------------------------------------------------------
export { scoreBand, DEPLOY_GATE, HITL_LOWER };

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------
export { fmtScore, fmtMs, fmtUsd };
