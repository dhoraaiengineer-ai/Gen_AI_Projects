"use client";

/**
 * Needs Attention — Dashboard Zone C (frontend_design.md §10.1).
 * Reuses the exact same derivation ObserverDashboardClient.tsx uses:
 * a bounded getScore fan-out over the fleet's latest_run ids, then
 * lib/observer's deriveAlerts (real threshold breaches only — faithfulness
 * hard-block, adversarial failure, Unified Score below gate/HITL, latency
 * SLA). No fabricated data, no placeholder rows: an empty result renders an
 * explicit "all healthy" confirmation, not a hidden/blank section.
 */

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { CheckCircle2 } from "lucide-react";

import { apiClient } from "@/services/api-client";
import { deriveAlerts, type AlertSeverity, type PipelineTelemetry } from "@/lib/observer";
import type { PipelineWithRun } from "@/types";

interface NeedsAttentionProps {
  pipelines: PipelineWithRun[];
  isLoading: boolean;
}

/** Same cap ObserverDashboardClient.tsx uses — bounds the getScore fan-out. */
const MAX_MONITORED = 40;

const SEVERITY_STYLE: Record<AlertSeverity, { dot: string; text: string }> = {
  critical: { dot: "bg-red-400", text: "text-red-500" },
  warning: { dot: "bg-amber-400", text: "text-amber-500" },
  info: { dot: "bg-sky-400", text: "text-sky-500" },
};

export function NeedsAttention({ pipelines, isLoading }: NeedsAttentionProps) {
  const monitored = useMemo(() => pipelines.slice(0, MAX_MONITORED), [pipelines]);
  const runIds = useMemo(
    () => monitored.map((p) => p.latest_run?.id).filter((id): id is string => Boolean(id)),
    [monitored],
  );

  const { data: scores = [], isLoading: scoresLoading } = useQuery({
    queryKey: ["dashboard-needs-attention-scores", runIds],
    queryFn: () => Promise.all(runIds.map((id) => apiClient.getScore(id))),
    enabled: runIds.length > 0,
  });

  const telemetry = useMemo<PipelineTelemetry[]>(() => {
    const byRun = new Map(scores.map((s) => [s.run_id, s]));
    return monitored.map((pipeline) => ({
      pipeline,
      score: pipeline.latest_run ? byRun.get(pipeline.latest_run.id) ?? null : null,
    }));
  }, [monitored, scores]);

  const alerts = useMemo(() => deriveAlerts(telemetry), [telemetry]);
  const loading = isLoading || (runIds.length > 0 && scoresLoading);

  if (loading) {
    return (
      <div className="flex min-h-[76px] items-center rounded-2xl border border-stone-200/90 bg-white px-4 py-3 shadow-[0_2px_8px_rgba(0,0,0,0.02)]">
        <p className="text-xs font-medium text-stone-500">Checking pipeline health…</p>
      </div>
    );
  }

  if (alerts.length === 0) {
    return (
      <div className="flex min-h-[76px] items-center gap-2.5 rounded-2xl border border-emerald-200/80 bg-emerald-50/80 px-4 py-3">
        <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" aria-hidden="true" />
        <p className="text-xs font-medium leading-snug text-emerald-900">
          All monitored pipelines within thresholds — no quality, faithfulness, or latency breaches.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-stone-200/90 bg-white px-4 py-3 shadow-[0_2px_8px_rgba(0,0,0,0.02)]">
      <ul className="divide-y divide-stone-100">
        {alerts.map((alert) => {
          const style = SEVERITY_STYLE[alert.severity];
          return (
            <li key={alert.id} className="flex items-start gap-3 py-2.5 first:pt-0 last:pb-0">
              <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${style.dot}`} aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <p className="text-sm text-stone-900">
                  <span className={`font-bold ${style.text}`}>{alert.category}</span>
                  <span className="text-stone-500"> · {alert.pipelineLabel}</span>
                </p>
                <p className="text-xs font-medium text-stone-500">{alert.message}</p>
              </div>
              <Link href="/observe" className="shrink-0 text-xs font-bold text-orange-600 hover:text-orange-700">
                Diagnose →
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
