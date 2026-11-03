"use client";

/**
 * System Health Dashboard — client container (Chapter 33). Focused live-only
 * scope (user-confirmed): everything shown is genuinely measured — the live
 * GET /health probe (use-system-health) plus the real pipeline count. Panels for
 * infrastructure / AI / DB / retrieval / resources / incidents are intentionally
 * NOT built: the platform exposes no per-service health endpoints, and faking
 * green statuses would violate CLAUDE.md Forbidden Pattern #2.
 */

import { useMemo } from "react";

import { usePipelines } from "@/hooks/use-pipelines";
import { useSystemHealth } from "@/hooks/use-system-health";
import { activeAlerts, deriveOverallStatus, sessionUptime } from "@/lib/health";
import { HealthSummaryCards } from "./HealthSummaryCards";
import { PlatformOverview } from "./PlatformOverview";
import { ApiHealthPanel } from "./ApiHealthPanel";

export function SystemHealthPageClient() {
  const {
    health,
    isOnline,
    latencyMs,
    lastCheckedAt,
    failStreak,
    totalChecks,
    successfulChecks,
    history,
    isInitialLoading,
    refresh,
  } = useSystemHealth();

  const { pipelines, isLoading: pipelinesLoading } = usePipelines();

  const status = useMemo(() => deriveOverallStatus(isOnline, failStreak), [isOnline, failStreak]);
  const uptime = useMemo(() => sessionUptime(successfulChecks, totalChecks), [successfulChecks, totalChecks]);
  const alerts = useMemo(() => activeAlerts(isOnline, failStreak), [isOnline, failStreak]);

  const activePipelines = pipelinesLoading
    ? null
    : pipelines.filter((p) => p.status === "ready").length;

  return (
    <div className="space-y-6">
      {isInitialLoading && (
        <span className="text-xs text-text-3" aria-live="polite">
          Running first probe…
        </span>
      )}

      <HealthSummaryCards status={status} uptimeRatio={uptime} latencyMs={latencyMs} alerts={alerts} />

      <PlatformOverview
        health={health}
        status={status}
        activePipelines={activePipelines}
        lastCheckedAt={lastCheckedAt}
      />

      <ApiHealthPanel
        isOnline={isOnline}
        latencyMs={latencyMs}
        lastCheckedAt={lastCheckedAt}
        failStreak={failStreak}
        totalChecks={totalChecks}
        history={history}
        onRefresh={refresh}
      />
    </div>
  );
}
