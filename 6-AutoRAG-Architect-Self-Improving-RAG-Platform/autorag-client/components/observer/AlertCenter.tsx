"use client";

/**
 * Alert Center — Chapter 27.14. Alerts are DERIVED from real threshold breaches
 * (lib/observer deriveAlerts): faithfulness hard-block, adversarial failure,
 * Unified Score below gate/HITL, latency SLA. Empty = positive confirmation (§27.20).
 */

import { CheckCircle2 } from "lucide-react";

import { Card } from "@/components/ui/card";
import type { AlertSeverity, ObserverAlert } from "@/lib/observer";

interface AlertCenterProps {
  alerts: ObserverAlert[];
}

const SEVERITY_STYLE: Record<AlertSeverity, { dot: string; text: string; label: string }> = {
  critical: { dot: "bg-red-400", text: "text-red-500", label: "Critical" },
  warning: { dot: "bg-amber-400", text: "text-amber-400", label: "Warning" },
  info: { dot: "bg-sky-400", text: "text-sky-400", label: "Info" },
};

export function AlertCenter({ alerts }: AlertCenterProps) {
  return (
    <Card className="p-5">
      <h3 className="mb-4 text-sm font-semibold text-foreground">Alert Center</h3>

      {alerts.length === 0 ? (
        <div className="flex items-center gap-2 rounded-lg border border-border bg-accent/5 p-4 text-sm text-green-400">
          <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
          All monitored pipelines within thresholds.
        </div>
      ) : (
        <ul className="space-y-2.5">
          {alerts.map((alert) => {
            const style = SEVERITY_STYLE[alert.severity];
            return (
              <li key={alert.id} className="flex items-start gap-3 rounded-lg border border-border bg-accent/5 p-3">
                <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${style.dot}`} aria-hidden="true" />
                <div className="min-w-0">
                  <p className="text-sm text-foreground">
                    <span className={`font-medium ${style.text}`}>{alert.category}</span>
                    <span className="text-text-3"> · {alert.pipelineLabel}</span>
                  </p>
                  <p className="text-xs text-text-3">{alert.message}</p>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
