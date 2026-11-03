"use client";

import Link from "next/link";
import { CheckCircle2, AlertTriangle, ArrowRight } from "lucide-react";

import { Card } from "@/components/ui/card";
import type { ObserverAlert } from "@/lib/observer";

interface ObserverStatusPanelProps {
  alerts: ObserverAlert[];
}

/**
 * Autonomous-loop status summary (25-Jul-2026, capability-first polish
 * pass) -- a single composite verdict built entirely from the already-real
 * deriveAlerts() output (same data AlertCenter.tsx renders in full). No new
 * fields, no invented severity or confidence: green when there are zero real
 * threshold breaches, amber with the most severe real alert's own message
 * when there are.
 */
export function ObserverStatusPanel({ alerts }: ObserverStatusPanelProps) {
  const worst = alerts.find((a) => a.severity === "critical") ?? alerts[0] ?? null;

  if (!worst) {
    return (
      <Card className="flex items-center gap-3 p-5">
        <CheckCircle2 className="h-6 w-6 shrink-0 text-emerald-500" aria-hidden="true" />
        <div>
          <p className="text-sm font-semibold text-foreground">Monitoring</p>
          <p className="text-xs text-text-3">No threshold breaches detected across monitored pipelines.</p>
        </div>
      </Card>
    );
  }

  return (
    <Card className="flex items-center gap-3 p-5">
      <AlertTriangle className="h-6 w-6 shrink-0 text-amber-500" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-foreground">Needs Attention</p>
        <p className="text-xs text-text-3">
          {worst.pipelineLabel} · {worst.category} — {worst.message}
        </p>
      </div>
      <Link
        href="/diagnose"
        className="flex shrink-0 items-center gap-1.5 text-xs font-semibold text-accent hover:text-accent-light"
      >
        Open Diagnoser Workspace
        <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
      </Link>
    </Card>
  );
}
