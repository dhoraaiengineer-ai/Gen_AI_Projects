"use client";

/**
 * API Health — Chapter 33.12. Live monitor for the one genuinely instrumented
 * endpoint (GET /health): status, client-measured latency, last failure, and a
 * rolling status strip built from the probe history (lib/health HealthSample).
 */

import { RefreshCw } from "lucide-react";

import { Card } from "@/components/ui/card";
import { relativeTime } from "@/lib/format";
import { formatLatency, type HealthSample } from "@/lib/health";

interface ApiHealthPanelProps {
  isOnline: boolean;
  latencyMs: number | null;
  lastCheckedAt: number | null;
  failStreak: number;
  totalChecks: number;
  history: HealthSample[];
  onRefresh: () => void;
}

export function ApiHealthPanel({
  isOnline,
  latencyMs,
  lastCheckedAt,
  failStreak,
  totalChecks,
  history,
  onRefresh,
}: ApiHealthPanelProps) {
  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">API Health</h3>
        <button
          type="button"
          onClick={onRefresh}
          aria-label="Refresh health check"
          className="inline-flex items-center gap-1.5 rounded-md bg-accent/5 px-2.5 py-1 text-xs font-medium text-text-2 transition-colors motion-safe:transition-colors hover:bg-gray-200"
        >
          <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
          Refresh
        </button>
      </div>

      <div className="flex items-center justify-between rounded-lg border border-border bg-accent/5 p-3">
        <div className="flex items-center gap-2">
          <span
            className={`h-2.5 w-2.5 rounded-full ${isOnline ? "bg-green-400" : "bg-red-400"}`}
            aria-hidden="true"
          />
          <span className="font-mono text-sm text-foreground">GET /health</span>
        </div>
        <span className={`text-xs font-medium ${isOnline ? "text-green-400" : "text-red-500"}`}>
          {isOnline ? "Operational" : "Unavailable"}
        </span>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
        <Metric label="Response Time" value={formatLatency(latencyMs)} />
        <Metric
          label="Last Checked"
          value={lastCheckedAt ? relativeTime(new Date(lastCheckedAt).toISOString()) : "—"}
        />
        <Metric label="Fail Streak" value={String(failStreak)} danger={failStreak > 0} />
        <Metric label="Probes" value={String(totalChecks)} />
      </dl>

      <div className="mt-4">
        <p className="mb-1.5 text-[11px] uppercase tracking-wide text-text-3">
          Recent checks ({history.length})
        </p>
        <div className="flex h-8 items-end gap-0.5" role="img" aria-label="Recent health check history">
          {history.length === 0 ? (
            <span className="text-xs text-text-3">Awaiting first probe…</span>
          ) : (
            history.map((sample) => (
              <span
                key={sample.at}
                title={`${sample.ok ? "OK" : "Failed"} · ${formatLatency(sample.latencyMs)}`}
                className={`w-1.5 flex-1 rounded-sm ${sample.ok ? "bg-green-500/70" : "bg-red-500/80"}`}
                style={{ height: sample.ok ? barHeight(sample.latencyMs) : "100%" }}
              />
            ))
          )}
        </div>
      </div>
    </Card>
  );
}

/** Taller bar = slower response (visual latency cue); failed probes are full-height red. */
function barHeight(latencyMs: number | null): string {
  if (latencyMs === null) return "40%";
  const pct = Math.min(100, Math.max(25, (latencyMs / 1500) * 100));
  return `${pct}%`;
}

function Metric({ label, value, danger }: { label: string; value: string; danger?: boolean }) {
  return (
    <div>
      <dt className="text-xs text-text-3">{label}</dt>
      <dd className={`mt-0.5 font-mono text-sm ${danger ? "text-red-500" : "text-foreground"}`}>{value}</dd>
    </div>
  );
}
