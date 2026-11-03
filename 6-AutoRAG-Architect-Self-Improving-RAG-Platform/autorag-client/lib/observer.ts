/**
 * Observer Dashboard aggregation (F-21) — pure, React-free, unit-testable.
 *
 * No /api/v1/observer/* backend exists (Ch 27.17 lists 7 endpoints; none are
 * implemented). The Observer's remit — watch production latency/cost/quality —
 * is served from real telemetry already present in each pipeline's latest
 * evaluation run (ScoreResult via getScore). This module aggregates that across
 * pipelines into KPIs, and DERIVES alerts + recommendations from real threshold
 * breaches and the persisted failure_taxonomy. Nothing here fabricates a metric:
 * a pipeline with no completed run contributes no score.
 */

import { DEPLOY_GATE, FAITHFULNESS_HARD_BLOCK, HITL_LOWER } from "@/lib/score";
import { FAILURE_CODE_INFO, isFailureCode } from "@/types";
import type { FailureCode, PipelineWithRun, ScoreResult } from "@/types";

/** p95 latency SLA — mirrors CLAUDE.md §9 (p95 query response < 3s). */
export const LATENCY_SLA_MS = 3000;

/** One monitored pipeline paired with its latest-run telemetry (null if none). */
export interface PipelineTelemetry {
  pipeline: PipelineWithRun;
  score: ScoreResult | null;
}

export interface ObserverKPIs {
  activePipelines: number;
  monitoredCount: number;
  avgUnifiedScore: number | null;
  avgLatencyMs: number | null;
  avgCostPerQuery: number | null;
  totalTokens: number;
  alertCount: number;
}

function mean(values: Array<number | null>): number | null {
  const present = values.filter((v): v is number => v !== null);
  if (present.length === 0) return null;
  return present.reduce((a, b) => a + b, 0) / present.length;
}

/** Aggregate KPIs across the telemetry rows that actually carry a score. */
export function computeObserverKPIs(telemetry: PipelineTelemetry[]): ObserverKPIs {
  const scored = telemetry.filter((t): t is PipelineTelemetry & { score: ScoreResult } => t.score !== null);
  return {
    activePipelines: telemetry.filter((t) => t.pipeline.status === "ready").length,
    monitoredCount: scored.length,
    avgUnifiedScore: mean(scored.map((t) => t.score.unified_score)),
    avgLatencyMs: mean(scored.map((t) => t.score.latency_p95_ms)),
    avgCostPerQuery: mean(scored.map((t) => t.score.cost_per_query_usd)),
    totalTokens: scored.reduce((sum, t) => sum + (t.score.total_tokens ?? 0), 0),
    alertCount: deriveAlerts(telemetry).length,
  };
}

// ── Alerts (§27.14) ───────────────────────────────────────────────────────────
export type AlertSeverity = "critical" | "warning" | "info";

export interface ObserverAlert {
  id: string;
  pipelineLabel: string;
  severity: AlertSeverity;
  category: string;
  message: string;
}

/** Human label for a pipeline (name falls back to short id), suffixed with version. */
export function pipelineLabel(pipeline: PipelineWithRun): string {
  const base = pipeline.name || `Pipeline ${pipeline.id.slice(0, 8)}`;
  return `${base} · v${pipeline.current_version}`;
}

/**
 * Derive alerts from real threshold breaches, most-severe first. Each rule maps a
 * measured value to a governance threshold (lib/score + LATENCY_SLA_MS).
 */
export function deriveAlerts(telemetry: PipelineTelemetry[]): ObserverAlert[] {
  const alerts: ObserverAlert[] = [];

  for (const { pipeline, score } of telemetry) {
    // unified_score is null when a run failed before Evaluator ever ran --
    // no score-based alert is meaningful for a run that was never scored.
    if (!score || score.unified_score === null) continue;
    const label = pipelineLabel(pipeline);

    if (score.faithfulness !== null && score.faithfulness < FAITHFULNESS_HARD_BLOCK) {
      alerts.push({
        id: `${pipeline.id}-faith`,
        pipelineLabel: label,
        severity: "critical",
        category: "Hallucination",
        message: `Faithfulness ${score.faithfulness!.toFixed(2)} below ${FAITHFULNESS_HARD_BLOCK} hard-block gate.`,
      });
    }
    if (!score.adversarial_passed) {
      alerts.push({
        id: `${pipeline.id}-adv`,
        pipelineLabel: label,
        severity: "critical",
        category: "Adversarial",
        message: "Failed the adversarial benchmark — fabricated answer detected.",
      });
    }
    if (score.unified_score < HITL_LOWER) {
      alerts.push({
        id: `${pipeline.id}-score`,
        pipelineLabel: label,
        severity: "critical",
        category: "Unified Score Drop",
        message: `Unified Score ${score.unified_score.toFixed(2)} below ${HITL_LOWER} — retry/improve required.`,
      });
    } else if (score.unified_score < DEPLOY_GATE) {
      alerts.push({
        id: `${pipeline.id}-hitl`,
        pipelineLabel: label,
        severity: "warning",
        category: "Below Deploy Gate",
        message: `Unified Score ${score.unified_score.toFixed(2)} in the HITL band (< ${DEPLOY_GATE}).`,
      });
    }
    if (score.latency_p95_ms !== null && score.latency_p95_ms > LATENCY_SLA_MS) {
      alerts.push({
        id: `${pipeline.id}-lat`,
        pipelineLabel: label,
        severity: "warning",
        category: "High Latency",
        message: `p95 latency ${score.latency_p95_ms}ms exceeds the ${LATENCY_SLA_MS}ms SLA.`,
      });
    }
  }

  const rank: Record<AlertSeverity, number> = { critical: 0, warning: 1, info: 2 };
  return alerts.sort((a, b) => rank[a.severity] - rank[b.severity]);
}

// ── Recommendations ────────────────────────────────────────────────────────────
/** Failure-code → informational recommendation (mirrors the Diagnoser hints). */
const RECOMMENDATION_TEXT: Record<FailureCode, string> = {
  "F-01": "Enable hybrid retrieval (BM25 + dense) and lower the similarity threshold to recover recall.",
  "F-02": "Reduce chunk size or top-k so compressed context fits the token budget.",
  "F-03": "Increase retrieval k and enable reranking to raise faithfulness.",
  "F-04": "Review the prompt template and retrieved context for completeness gaps.",
  "F-05": "Reduce top-k and enable context compression to cut latency.",
  "F-06": "Trigger the Improver agent to generate hyperparameter variants; review chunking strategy and embedding model version for data drift.",
};

export interface ObserverRecommendation {
  id: string;
  pipelineLabel: string;
  code: FailureCode;
  codeLabel: string;
  text: string;
}

/** Derive informational recommendations from each run's failure_taxonomy. */
export function deriveRecommendations(telemetry: PipelineTelemetry[]): ObserverRecommendation[] {
  const recs: ObserverRecommendation[] = [];
  for (const { pipeline, score } of telemetry) {
    if (!score) continue;
    const label = pipelineLabel(pipeline);
    for (const raw of score.failure_taxonomy) {
      if (!isFailureCode(raw)) continue;
      recs.push({
        id: `${pipeline.id}-${raw}`,
        pipelineLabel: label,
        code: raw,
        codeLabel: FAILURE_CODE_INFO[raw].label,
        text: RECOMMENDATION_TEXT[raw],
      });
    }
  }
  return recs;
}

// ── Chart builders (§27.9/11/12) ──────────────────────────────────────────────
export interface ChartPoint {
  label: string;
  unified_score: number;
  latency_ms: number;
  total_tokens: number;
}

/** One point per monitored pipeline, ordered as given (skips unscored rows). */
export function buildChartData(telemetry: PipelineTelemetry[]): ChartPoint[] {
  return telemetry
    .filter(
      (
        t,
      ): t is PipelineTelemetry & {
        score: ScoreResult & { unified_score: number; latency_p95_ms: number };
      } =>
        t.score !== null && t.score.unified_score !== null && t.score.latency_p95_ms !== null,
    )
    .map((t) => ({
      label: `v${t.pipeline.current_version}`,
      unified_score: t.score.unified_score,
      latency_ms: t.score.latency_p95_ms,
      total_tokens: t.score.total_tokens ?? 0,
    }));
}

// ── Formatting ────────────────────────────────────────────────────────────────
export function formatCost(usd: number | null): string {
  return usd === null ? "—" : `$${usd.toFixed(4)}`;
}
export function formatLatencyMs(ms: number | null): string {
  return ms === null ? "—" : `${Math.round(ms)} ms`;
}
