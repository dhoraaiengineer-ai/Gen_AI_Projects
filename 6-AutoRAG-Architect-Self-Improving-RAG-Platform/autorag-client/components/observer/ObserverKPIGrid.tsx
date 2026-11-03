"use client";

/**
 * Observer Live KPIs — Chapter 27.7. Reuses the dashboard KPICard. Values are
 * real aggregates over monitored pipelines' latest runs (lib/observer). KPIs with
 * no backing data (queries-per-minute, active users) are not shown.
 */

import { Activity, Boxes, Coins, Gauge, ShieldAlert, Timer } from "lucide-react";

import { KPICard } from "@/components/dashboard/KPICard";
import { scoreColorClasses, formatScorePercent } from "@/lib/score";
import { formatCost, formatLatencyMs, type ObserverKPIs } from "@/lib/observer";

interface ObserverKPIGridProps {
  kpis: ObserverKPIs;
}

export function ObserverKPIGrid({ kpis }: ObserverKPIGridProps) {
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6">
      <KPICard title="Active Pipelines" value={kpis.activePipelines} icon={Boxes} />
      <KPICard
        title="Fleet Quality"
        value={formatScorePercent(kpis.avgUnifiedScore)}
        icon={Gauge}
        valueClassName={kpis.avgUnifiedScore === null ? undefined : scoreColorClasses(kpis.avgUnifiedScore).split(" ")[0]}
      />
      <KPICard title="Avg Latency p95" value={formatLatencyMs(kpis.avgLatencyMs)} icon={Timer} />
      <KPICard title="Avg Cost / Query" value={formatCost(kpis.avgCostPerQuery)} icon={Coins} />
      <KPICard title="Total Tokens" value={kpis.totalTokens.toLocaleString()} icon={Activity} />
      <KPICard
        title="Active Alerts"
        value={kpis.alertCount}
        icon={ShieldAlert}
        valueClassName={kpis.alertCount > 0 ? "text-red-500" : undefined}
      />
    </div>
  );
}
