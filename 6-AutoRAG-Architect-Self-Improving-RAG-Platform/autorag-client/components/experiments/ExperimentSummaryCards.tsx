"use client";

/* 19-Jul-2026: rebuilt on the shared StatCard, matching the pattern now used
 * consistently across Dashboard, Documents, Health, and Knowledge Base
 * ("have a consistent pattern in all pages") -- replaces the page-local
 * Card function that had no icon well/top accent bar. */

import { FlaskConical, Play, CheckCircle2, Trophy, Clock } from "lucide-react";

import { StatCard } from "@/components/ui/stat-card";
import { formatScorePercent } from "@/lib/score";
import type { ExperimentSummary } from "@/lib/experiments";

interface Props {
  summary: ExperimentSummary;
  loading?: boolean;
}

export function ExperimentSummaryCards({ summary, loading }: Props) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="d2-kpi-tile h-20 animate-pulse" />
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
      <StatCard label="Total Experiments" value={summary.total} icon={FlaskConical} iconColor="#0EA5E9" />
      <StatCard
        label="Active"
        value={summary.active}
        icon={Play}
        iconColor="#06B6D4"
        delta={{ value: "currently running", direction: "up" }}
      />
      <StatCard
        label="Completed"
        value={summary.completed}
        icon={CheckCircle2}
        iconColor="#10B981"
        delta={{ value: "with evaluation", direction: "up" }}
      />
      <StatCard
        label="Best Unified Score"
        value={formatScorePercent(summary.bestUnifiedScore)}
        icon={Trophy}
        iconColor="#F59E0B"
        delta={
          summary.bestUnifiedScore !== null && summary.bestUnifiedScore >= 0.85
            ? { value: "Deploy eligible", direction: "up" }
            : undefined
        }
      />
      <StatCard
        label="Avg Latency"
        value={summary.avgLatencyMs !== null ? `${Math.round(summary.avgLatencyMs)} ms` : "—"}
        icon={Clock}
        iconColor="#EA580C"
        delta={{ value: "p95 across scored runs", direction: "up" }}
      />
    </div>
  );
}
