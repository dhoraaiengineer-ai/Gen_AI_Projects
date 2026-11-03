"use client";

/**
 * Platform Overview — Chapter 33.7. Real values from GET /health
 * (service/version/environment/status) plus the live pipeline count. Fields with
 * no backing data (Active Users, Running Services) are omitted rather than faked —
 * the platform exposes no endpoint for them.
 */

import { Card } from "@/components/ui/card";
import { relativeTime } from "@/lib/format";
import { STATUS_LABEL, STATUS_TEXT, type OverallStatus } from "@/lib/health";
import type { SystemHealth } from "@/types";

interface PlatformOverviewProps {
  health: SystemHealth | null;
  status: OverallStatus;
  activePipelines: number | null;
  lastCheckedAt: number | null;
}

export function PlatformOverview({ health, status, activePipelines, lastCheckedAt }: PlatformOverviewProps) {
  const rows: { label: string; value: string; className?: string }[] = [
    { label: "Overall Status", value: STATUS_LABEL[status], className: STATUS_TEXT[status] },
    { label: "Service", value: health?.service ?? "—" },
    { label: "Platform Version", value: health?.version ? `v${health.version}` : "—" },
    { label: "Environment", value: health?.environment ?? "—" },
    { label: "Active Pipelines", value: activePipelines === null ? "—" : String(activePipelines) },
    { label: "Last Checked", value: lastCheckedAt ? relativeTime(new Date(lastCheckedAt).toISOString()) : "—" },
  ];

  return (
    <Card className="p-5">
      <h3 className="mb-4 text-sm font-semibold text-foreground">Platform Overview</h3>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
        {rows.map((row) => (
          <div key={row.label}>
            <dt className="text-xs font-medium uppercase tracking-wide text-text-3">{row.label}</dt>
            <dd className={`mt-1 font-mono text-sm ${row.className ?? "text-foreground"}`}>{row.value}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}
