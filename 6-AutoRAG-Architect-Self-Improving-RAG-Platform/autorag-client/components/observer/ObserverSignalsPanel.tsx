"use client";

/**
 * Observer Signals Panel — real per-pipeline Observer output (GET /observe).
 * Added 13-Jul-2026: observer_signals/quality_drift/observation_flags were
 * already real and persisted (Part B.2, 12-Jul-2026) but never fetched or
 * rendered anywhere — ObserverDashboardClient.tsx's fleet view derives its
 * KPIs from a getScore fan-out instead (a different, also-real, but purely
 * quantitative signal set). This panel shows the qualitative signals the
 * fleet view can't: quality_trend, observation_flags, quality drift.
 */

import { AlertTriangle, CheckCircle2, TrendingDown, TrendingUp, Minus } from "lucide-react";

import { Card } from "@/components/ui/card";
import type { ObserverViewResponse } from "@/types";

interface ObserverSignalsPanelProps {
  data: ObserverViewResponse | undefined;
  isLoading: boolean;
  pipelineName: string;
}

const TREND_ICON = {
  improving: TrendingUp,
  stable: Minus,
  degrading: TrendingDown,
} as const;

const TREND_COLOR = {
  improving: "text-emerald-700 bg-emerald-50",
  stable: "text-text-2 bg-accent/5",
  degrading: "text-rose-700 bg-rose-50",
} as const;

const FLAG_LABELS: Record<string, string> = {
  latency_breach: "Latency Breach",
  score_drop: "Score Drop",
  error_spike: "Error Spike",
  quality_drift: "Quality Drift",
};

export function ObserverSignalsPanel({ data, isLoading, pipelineName }: ObserverSignalsPanelProps) {
  if (isLoading) {
    return (
      <Card className="p-5">
        <h3 className="mb-4 text-sm font-semibold text-foreground">Quality Signals</h3>
        <div className="h-24 animate-pulse rounded-lg bg-accent/5" />
      </Card>
    );
  }

  if (!data || data.signals === null) {
    return (
      <Card className="p-5">
        <h3 className="mb-4 text-sm font-semibold text-foreground">
          Quality Signals — {pipelineName}
        </h3>
        <div className="rounded-lg border border-border bg-accent/5 p-4 text-sm text-text-3">
          {data?.history_note ??
            "No Observer signals for this pipeline's latest run yet — it may not have reached Observer (e.g. blocked earlier in the graph)."}
        </div>
      </Card>
    );
  }

  const { signals, history, history_note } = data;
  const TrendIcon = signals.quality_trend ? TREND_ICON[signals.quality_trend] : Minus;
  const trendColor = signals.quality_trend ? TREND_COLOR[signals.quality_trend] : "text-text-3 bg-accent/5";
  const activeFlags = Object.entries(signals.observation_flags ?? {}).filter(([, v]) => v);
  const hasDrift = Boolean(signals.observation_flags?.quality_drift);

  return (
    <Card className="p-5">
      <h3 className="mb-4 text-sm font-semibold text-foreground">
        Quality Signals — {pipelineName}
      </h3>

      {/* Drift Detection badge (25-Jul-2026, capability-first polish pass) --
          real boolean flag only, no baseline/expected-value number (none
          exists in observer_signals). */}
      <div
        className={`mb-4 flex items-center gap-2 rounded-lg border px-3 py-2.5 text-sm font-medium ${
          hasDrift ? "border-amber-200 bg-amber-50 text-amber-800" : "border-emerald-200 bg-emerald-50 text-emerald-700"
        }`}
      >
        {hasDrift ? (
          <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
        ) : (
          <CheckCircle2 className="h-4 w-4 shrink-0" aria-hidden="true" />
        )}
        {hasDrift ? "Quality Drift Detected" : "No Drift Detected"}
      </div>

      <div className="mb-4 grid grid-cols-2 gap-3">
        <div className="rounded-lg border border-border bg-accent/5 p-3">
          <p className="mb-1 text-[11px] uppercase tracking-wide text-text-3">Quality Trend</p>
          <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${trendColor}`}>
            <TrendIcon className="h-3.5 w-3.5" aria-hidden="true" />
            {signals.quality_trend ?? "unknown"}
          </span>
        </div>
        <div className="rounded-lg border border-border bg-accent/5 p-3">
          <p className="mb-1 text-[11px] uppercase tracking-wide text-text-3">Error Rate</p>
          <span className="font-mono text-sm font-semibold text-foreground">
            {signals.error_rate !== null ? `${(signals.error_rate * 100).toFixed(1)}%` : "—"}
          </span>
        </div>
      </div>

      <div className="mb-4">
        <p className="mb-2 text-[11px] uppercase tracking-wide text-text-3">Observation Flags</p>
        {activeFlags.length === 0 ? (
          <div className="flex items-center gap-2 rounded-lg border border-border bg-accent/5 p-3 text-sm text-emerald-700">
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
            No flags raised on the latest run.
          </div>
        ) : (
          <ul className="space-y-1.5">
            {activeFlags.map(([key]) => (
              <li
                key={key}
                className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800"
              >
                <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                {FLAG_LABELS[key] ?? key}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <p className="mb-2 text-[11px] uppercase tracking-wide text-text-3">
          Score History ({history.length} run{history.length === 1 ? "" : "s"})
        </p>
        {history_note && (
          <p className="mb-2 text-xs italic text-text-3">{history_note}</p>
        )}
        {history.length === 0 ? (
          <p className="text-sm text-text-3">No completed runs yet.</p>
        ) : (
          <ul className="space-y-1">
            {history.map((run) => (
              <li key={run.run_id} className="flex items-center justify-between text-xs text-text-2">
                <span className="font-mono text-text-3">{run.run_id.slice(0, 8)}</span>
                <span className="font-mono">
                  {run.unified_score !== null ? run.unified_score.toFixed(3) : "—"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}
