"use client";

import { Activity, Gauge, ListChecks, UserCheck } from "lucide-react";

import { StatCard } from "@/components/ui/stat-card";
import { formatScore } from "@/lib/score";
import type { DashboardKpis } from "@/lib/kpi";

interface KpiRowProps {
  kpis: DashboardKpis;
  isLoading: boolean;
}

/** Four live platform vitals — real data from the pipeline list. */
export function KpiRow({ kpis, isLoading }: KpiRowProps) {
  const v = (val: string | number) => (isLoading ? "—" : val);
  return (
    <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
      <StatCard label="Active Pipelines"  value={v(kpis.activeCount)}                                  icon={Activity}  iconColor="#0EA5E9" />
      <StatCard label="Avg Unified Score" value={v(kpis.avgScore !== null ? formatScore(kpis.avgScore) : "—")} icon={Gauge} iconColor="#10B981" />
      <StatCard label="Evaluations Today" value={v(kpis.evaluationsToday)}                             icon={ListChecks} iconColor="#F59E0B" />
      <StatCard label="Pending Approvals" value={v(kpis.pendingHitl)}                                  icon={UserCheck} iconColor="#EA580C" />
    </div>
  );
}
