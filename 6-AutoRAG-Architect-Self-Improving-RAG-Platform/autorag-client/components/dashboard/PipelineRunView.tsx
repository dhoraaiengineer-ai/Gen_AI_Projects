"use client";

import { useState } from "react";

import { usePipelineRun } from "@/hooks/use-pipeline-run";
import { usePipelineVersions } from "@/hooks/use-pipeline-versions";
import { pipelineDisplayName } from "@/lib/format";
import type { Document, NodeTraceEntry } from "@/types";
import { IngestionEvidence } from "@/components/dashboard/IngestionEvidence";
import { BuilderEvidence } from "@/components/dashboard/BuilderEvidence";
import { RoutingDecision } from "@/components/dashboard/RoutingDecision";
import { RetryJourney } from "@/components/dashboard/RetryJourney";
import { RunIntegrity } from "@/components/dashboard/RunIntegrity";
import { OptimizationTimeline } from "@/components/optimizer/OptimizationTimeline";

/**
 * /dashboard/[id] — Pipeline Progress, the flagship screen (Part D, 12-Jul-2026).
 *
 * A vertical execution journey, not a node-link diagram (frontend_design.md §10.2).
 * Every value shown comes from real backend sources (node_trace, agent_metrics) —
 * no fabricated progress percentage mid-run, no Math.random(), no synthetic trends.
 * A node with no trace entry yet renders as "Pending", never a guessed duration/cost.
 */

const STAGE_ORDER = [
  "ingestion",
  "query_rewriter",
  "builder",
  "compressor",
  "evaluator",
  "observer",
  "diagnoser",
  "improver",
  "deployer",
] as const;

const STAGE_LABEL: Record<(typeof STAGE_ORDER)[number], string> = {
  ingestion: "Ingestion",
  query_rewriter: "Query Rewriter",
  builder: "Builder",
  compressor: "Compressor",
  evaluator: "Evaluator",
  observer: "Observer",
  diagnoser: "Diagnoser",
  improver: "Improver",
  deployer: "Deployer",
};

// Functional stage colors — frontend_design.md §2 / §11.
const STAGE_COLOR: Record<(typeof STAGE_ORDER)[number], string> = {
  ingestion: "#3B82F6",
  query_rewriter: "#3B82F6",
  builder: "#3B82F6",
  compressor: "#3B82F6",
  evaluator: "#5B5CE2",
  observer: "#06B6D4",
  diagnoser: "#F59E0B",
  improver: "#8B5CF6",
  deployer: "#10B981",
};

function formatMs(ms: number | undefined): string {
  if (ms === undefined) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

// A run is terminal once it can no longer produce new node_trace entries --
// mirrors hooks/use-pipeline-run.ts's TERMINAL_STATUSES.
const RUN_TERMINAL_STATUSES = new Set(["completed", "blocked", "failed"]);

/**
 * Execution-state semantics audit (13-Jul-2026, user-requested after Part H
 * flagship review): a node with no trace entry must NOT always read
 * "Pending" -- that implies "may still execute," which is false once the run
 * is terminal. Real persisted evidence, not inference, decides each label:
 *   - entry.status is real backend-set data (ingestion.py has a genuine
 *     "skipped" status; evaluator.py/deployer.py set real "blocked").
 *   - Absence of an entry + a terminal run.status = "Not Run" (never
 *     "Skipped" -- that requires real routing evidence, not just absence).
 *   - Absence of an entry + a non-terminal run.status = "Pending" (the run
 *     may still reach this node).
 */
function statusLabel(entry: NodeTraceEntry | undefined, runStatus: string): string {
  if (entry) {
    switch (entry.status) {
      case "success":
        return "Completed";
      case "blocked":
        return "Blocked";
      case "failed":
        return "Failed";
      case "skipped":
        return "Skipped";
      case "rolled_back":
        return "Rolled Back";
      case "retried":
        return "Retried";
      default:
        return entry.status;
    }
  }
  return RUN_TERMINAL_STATUSES.has(runStatus) ? "Not Run" : "Pending";
}

/** Header badge colors — frontend_design.md §2 functional palette + §18 status chips. */
function headerBadgeStyle(status: string): { background: string; color: string } {
  switch (status) {
    case "completed":
      return { background: "rgba(16,185,129,0.12)", color: "#34D399" }; // emerald
    case "pending_approval":
      return { background: "rgba(245,158,11,0.12)", color: "#FBBF24" }; // amber
    case "blocked":
    case "failed":
      return { background: "rgba(244,63,94,0.12)", color: "#FB7185" }; // coral
    default:
      return { background: "rgba(15,23,42,0.06)", color: "var(--text-3)" }; // neutral — running/pending
  }
}

function headerBadgeLabel(status: string): string {
  return status === "pending_approval" ? "AWAITING APPROVAL" : status.toUpperCase();
}

function statusDotColor(entry: NodeTraceEntry | undefined, stageColor: string, runStatus: string): string {
  if (!entry) {
    // Terminal run, node never reached: a slightly darker neutral than
    // "Pending" would use, so Not Run and Pending remain visually distinct.
    return RUN_TERMINAL_STATUSES.has(runStatus) ? "var(--text-3)" : "#D1D5DB";
  }
  if (entry.status === "blocked" || entry.status === "failed") return "#F43F5E"; // coral
  if (entry.status === "skipped") return "var(--text-3)"; // muted — intentionally bypassed, not an error
  return stageColor;
}

interface RunSummaryProps {
  runId: string;
  traceId: string | undefined;
  status: string;
  totalDurationMs: number | undefined;
  totalCostUsd: number | null | undefined;
  totalTokens: number | null | undefined;
  llmCalls: number | undefined;
  retries: number;
}

function RunSummary({
  runId,
  traceId,
  status,
  totalDurationMs,
  totalCostUsd,
  totalTokens,
  llmCalls,
  retries,
}: RunSummaryProps) {
  const rows: [string, string][] = [
    ["Run ID", runId],
    ["Trace ID", traceId ?? "Unavailable"],
    ["Status", status],
    ["Total Duration", totalDurationMs !== undefined ? formatMs(totalDurationMs) : "Not collected"],
    ["Total Cost", totalCostUsd != null ? `$${totalCostUsd.toFixed(4)}` : "Not collected"],
    ["Tokens", totalTokens != null ? totalTokens.toLocaleString() : "Not collected"],
    ["LLM Calls", llmCalls !== undefined ? String(llmCalls) : "Not collected"],
    ["Retries", String(retries)],
  ];

  return (
    <div className="sticky top-6 rounded-2xl border border-border bg-card p-5 shadow-sm">
      <h3 className="mb-4 text-[11px] font-semibold uppercase tracking-widest text-text-3">
        Run Summary
      </h3>
      <dl className="space-y-3">
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

function NodeRow({
  stage,
  entry,
  index,
  extra,
  runStatus,
}: {
  stage: (typeof STAGE_ORDER)[number];
  entry: NodeTraceEntry | undefined;
  index: number;
  /** Part H evidence surface (Ingestion/Builder Evidence) — always visible, not gated by expand. */
  extra?: React.ReactNode;
  /** The overall run's status — decides "Not Run" (terminal) vs "Pending" (still active). */
  runStatus: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const color = STAGE_COLOR[stage];
  const dotColor = statusDotColor(entry, color, runStatus);
  const hasExtras = entry
    ? Object.keys(entry).some(
        (k) =>
          ![
            "node",
            "status",
            "timestamp",
            "latency_ms",
            "x_trace_id",
            "retry_count",
            "cost_usd",
            "provider",
            "prompt_tokens",
            "completion_tokens",
            "graph_state_version",
          ].includes(k),
      )
    : false;

  return (
    <div className="relative pl-10">
      <span
        className="absolute left-0 top-1 flex h-6 w-6 items-center justify-center rounded-full border-2 bg-card text-[10px] font-bold"
        style={{ borderColor: dotColor, color: dotColor }}
      >
        {String(index + 1).padStart(2, "0")}
      </span>
      {index < STAGE_ORDER.length - 1 && (
        <span className="absolute left-[11px] top-7 h-[calc(100%-4px)] w-px bg-[rgba(15,23,42,0.1)]" />
      )}
      <button
        type="button"
        onClick={() => hasExtras && setExpanded((e) => !e)}
        className="flex w-full items-center justify-between gap-3 py-1 text-left"
        disabled={!hasExtras}
      >
        <span className="text-sm font-semibold text-foreground">{STAGE_LABEL[stage]}</span>
        <span className="flex items-center gap-2 text-xs">
          <span className="font-medium" style={{ color: dotColor }}>
            {statusLabel(entry, runStatus)}
          </span>
          <span className="font-mono text-text-3">{formatMs(entry?.latency_ms)}</span>
        </span>
      </button>

      {entry && (entry.provider || entry.cost_usd !== undefined || entry.prompt_tokens !== undefined) && (
        <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-[11px] text-text-3">
          {entry.provider && <span>Provider: {entry.provider}</span>}
          {entry.prompt_tokens !== undefined && (
            <span>
              Tokens: {entry.prompt_tokens}+{entry.completion_tokens ?? 0}
            </span>
          )}
          {entry.cost_usd !== undefined && <span>Cost: ${entry.cost_usd.toFixed(4)}</span>}
          {entry.retry_count > 0 && <span>Retries: {entry.retry_count}</span>}
        </div>
      )}

      {/* P0.7-5: safe per-run PII redaction evidence — counts only, never
          the original detected value. Sourced verbatim from the canonical
          detector's node_trace entry (app/services/pii_engine.py). */}
      {entry && typeof entry.pii_masked_count === "number" && entry.pii_masked_count > 0 && (
        <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-[11px] text-text-3">
          <span>PII Redactions: {entry.pii_masked_count}</span>
          {typeof entry.pii_detector_version === "string" && (
            <span>Detector: {entry.pii_detector_version}</span>
          )}
        </div>
      )}

      {expanded && hasExtras && entry && (
        <pre className="mt-2 overflow-x-auto rounded-lg bg-accent/5 p-3 text-[11px] text-text-3">
          {JSON.stringify(
            Object.fromEntries(
              Object.entries(entry).filter(
                ([k]) =>
                  ![
                    "node",
                    "status",
                    "timestamp",
                    "latency_ms",
                    "x_trace_id",
                    "retry_count",
                    "cost_usd",
                    "provider",
                    "prompt_tokens",
                    "completion_tokens",
                    "graph_state_version",
                  ].includes(k),
              ),
            ),
            null,
            2,
          )}
        </pre>
      )}

      {extra}
    </div>
  );
}

export function PipelineRunView({ pipelineId }: { pipelineId: string }) {
  const {
    pipeline,
    runId,
    score,
    metrics,
    isLoading,
    error,
    documents,
    documentsLoading,
    diagnosis,
    diagnosisLoading,
    improvement,
    improvementLoading,
    observerView,
  } = usePipelineRun(pipelineId);

  if (isLoading) {
    return <div className="p-8 text-sm text-text-3">Loading pipeline run…</div>;
  }
  if (error) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 p-6 text-sm text-rose-700" role="alert">
        Unable to load pipeline run: {error.message}
      </div>
    );
  }
  if (!pipeline) {
    return <div className="p-8 text-sm text-text-3">Pipeline not found.</div>;
  }
  if (!runId || !score) {
    return (
      <div className="rounded-xl border border-border bg-card p-8 text-sm text-text-3">
        No evaluation run yet for <strong>{pipelineDisplayName(pipeline)}</strong>. Run an
        evaluation to see the pipeline execution journey.
      </div>
    );
  }

  const traceByNode = new Map<string, NodeTraceEntry>();
  for (const entry of score.node_trace ?? []) {
    traceByNode.set(entry.node, entry);
  }

  const totalDurationMs = (score.node_trace ?? []).reduce((sum, e) => sum + (e.latency_ms ?? 0), 0);
  const totalRetries = (score.node_trace ?? []).reduce((sum, e) => sum + (e.retry_count ?? 0), 0);
  const lastEntry = (score.node_trace ?? []).at(-1);
  // Single-document-per-pipeline is the golden-path pattern this evidence
  // surface was built against; a pipeline with multiple documents shows the
  // first real match rather than guessing which one this run used.
  const matchedDocument: Document | null = documents[0] ?? null;

  return (
    <div className="space-y-6">
      <RoutingDecision score={score} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_280px]">
        <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
          <div className="mb-6 flex items-baseline justify-between">
            <div>
              <h2 className="text-xl font-semibold text-foreground">{pipelineDisplayName(pipeline)}</h2>
              <p className="mt-0.5 font-mono text-xs text-text-3">Run {runId}</p>
            </div>
            <span
              className="rounded-full px-3 py-1 text-xs font-semibold tracking-wide"
              style={headerBadgeStyle(score.status)}
            >
              {headerBadgeLabel(score.status)}
            </span>
          </div>

          <div className="space-y-5">
            {STAGE_ORDER.map((stage, i) => {
              let extra: React.ReactNode = undefined;
              if (stage === "ingestion") {
                extra = (
                  <IngestionEvidence
                    document={matchedDocument}
                    documentsLoading={documentsLoading}
                    entry={traceByNode.get("ingestion")}
                  />
                );
              } else if (stage === "builder" && traceByNode.get("builder")) {
                extra = <BuilderEvidence pipeline={pipeline} entry={traceByNode.get("builder")} />;
              }
              return (
                <NodeRow
                  key={stage}
                  stage={stage}
                  entry={traceByNode.get(stage)}
                  index={i}
                  extra={extra}
                  runStatus={score.status}
                />
              );
            })}
          </div>
        </div>

        <div className="space-y-6">
          <RunSummary
            runId={runId}
            traceId={lastEntry?.x_trace_id}
            status={score.status}
            totalDurationMs={score.node_trace ? totalDurationMs : undefined}
            totalCostUsd={metrics?.totals.cost_usd}
            totalTokens={metrics?.totals.total_tokens}
            llmCalls={metrics?.totals.llm_calls}
            retries={totalRetries}
          />
          <RunIntegrity runId={runId} score={score} lastEntry={lastEntry} totalRetries={totalRetries} />
        </div>
      </div>

      <RetryJourney
        score={score}
        diagnosis={diagnosis}
        diagnosisLoading={diagnosisLoading}
        improvement={improvement}
        improvementLoading={improvementLoading}
        observerView={observerView}
      />

      <OptimizationTimelineSection pipelineId={pipelineId} currentVersion={pipeline.current_version} />
    </div>
  );
}

/** Real version-history timeline (20-Jul-2026, Apply Improvement feature) --
 * complementary to the node_trace stage rail above: that shows *within-run*
 * agent progress, this shows *across-version* score progress as configs get
 * applied via ImproverWorkspace's Apply button. */
function OptimizationTimelineSection({
  pipelineId,
  currentVersion,
}: {
  pipelineId: string;
  currentVersion: number;
}) {
  const { versions, isLoading } = usePipelineVersions(pipelineId);

  if (isLoading || versions.length <= 1) return null; // nothing to show for a single-version pipeline

  return (
    <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
      <h2 className="mb-4 text-xs font-semibold uppercase tracking-wide text-text-3">
        Optimization Timeline
      </h2>
      <OptimizationTimeline versions={versions} currentVersion={currentVersion} />
    </div>
  );
}
