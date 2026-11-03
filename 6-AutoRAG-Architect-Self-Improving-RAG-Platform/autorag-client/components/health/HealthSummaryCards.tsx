"use client";

/**
 * Health summary cards — Chapter 33.5 top row. All values derived from the live
 * /health probe series (lib/health). SLA target is a static reference (99.9%),
 * clearly labelled as a target, not a measured figure.
 *
 * 19-Jul-2026: rebuilt on the shared StatCard, matching the pattern now used
 * consistently across Dashboard, Documents, and every other summary-tile grid
 * in the app ("have a consistent pattern in all pages").
 */

import { Activity, Gauge, ShieldCheck, TriangleAlert } from "lucide-react";

import { StatCard } from "@/components/ui/stat-card";
import {
  STATUS_LABEL,
  formatLatency,
  formatUptime,
  type OverallStatus,
} from "@/lib/health";

interface HealthSummaryCardsProps {
  status: OverallStatus;
  uptimeRatio: number;
  latencyMs: number | null;
  alerts: number;
}

/** Documented availability target (reference only — not a measured value). */
const SLA_TARGET = "99.9%";

const STATUS_COLOR: Record<OverallStatus, string> = {
  healthy: "#10B981",
  warning: "#F59E0B",
  critical: "#F43F5E",
};

export function HealthSummaryCards({ status, uptimeRatio, latencyMs, alerts }: HealthSummaryCardsProps) {
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <StatCard label="Overall Health" value={STATUS_LABEL[status]} icon={ShieldCheck} iconColor={STATUS_COLOR[status]} />
      <StatCard
        label="Session Uptime"
        value={formatUptime(uptimeRatio)}
        icon={Activity}
        iconColor="#06B6D4"
        delta={{ value: `SLA target ${SLA_TARGET}`, direction: "up" }}
      />
      <StatCard label="API Latency" value={formatLatency(latencyMs)} icon={Gauge} iconColor="#8B5CF6" />
      <StatCard
        label="Active Alerts"
        value={alerts}
        icon={TriangleAlert}
        iconColor={alerts > 0 ? "#F43F5E" : "var(--text-3)"}
      />
    </div>
  );
}
