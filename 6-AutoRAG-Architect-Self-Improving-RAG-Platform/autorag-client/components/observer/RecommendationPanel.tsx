"use client";

/**
 * Recommendation Engine — Chapter 27.15. Informational only; the Observer never
 * modifies pipelines. Recommendations are DERIVED from each run's failure_taxonomy
 * (lib/observer deriveRecommendations), linking out to the Diagnoser for detail.
 */

import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { Card } from "@/components/ui/card";
import type { ObserverRecommendation } from "@/lib/observer";

interface RecommendationPanelProps {
  recommendations: ObserverRecommendation[];
}

export function RecommendationPanel({ recommendations }: RecommendationPanelProps) {
  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">Recommendations</h3>
        <span className="text-[11px] uppercase tracking-wide text-text-3">Informational</span>
      </div>

      {recommendations.length === 0 ? (
        <p className="rounded-lg border border-border bg-accent/5 p-4 text-sm text-text-3">
          No optimization signals — no active failures across monitored pipelines.
        </p>
      ) : (
        <ul className="space-y-3">
          {recommendations.map((rec) => (
            <li key={rec.id} className="rounded-lg border border-border bg-accent/5 p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-text-3">
                <span className="font-mono text-amber-400">{rec.code}</span> {rec.codeLabel}
                <span className="ml-2 font-normal normal-case text-text-3">{rec.pipelineLabel}</span>
              </p>
              <p className="mt-1 text-sm text-text-2">{rec.text}</p>
            </li>
          ))}
        </ul>
      )}

      <Link
        href="/diagnose"
        className="mt-4 inline-flex items-center gap-1.5 text-xs font-medium text-accent hover:text-accent-light"
      >
        Open Diagnoser Workspace
        <ArrowRight className="h-3 w-3" aria-hidden="true" />
      </Link>
    </Card>
  );
}
