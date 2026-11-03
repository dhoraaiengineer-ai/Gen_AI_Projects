"use client";

/**
 * Version Timeline — Chapter 34.7. Horizontal evolution strip of a pipeline's
 * versions (sibling pipelines in the same project), newest first. Display-only:
 * version, created date, status, and the latest-run Unified Score.
 */

import { Card } from "@/components/ui/card";
import { relativeTime } from "@/lib/format";
import { formatScore, scoreColorClasses } from "@/lib/score";
import type { PipelineWithRun } from "@/types";

interface VersionTimelineProps {
  versions: PipelineWithRun[];
  currentId: string;
}

export function VersionTimeline({ versions, currentId }: VersionTimelineProps) {
  if (versions.length === 0) return null;

  return (
    <Card className="p-5">
      <h3 className="mb-4 text-sm font-semibold text-foreground">Version Timeline</h3>
      <ol className="flex gap-3 overflow-x-auto pb-2">
        {versions.map((version) => {
          const isCurrent = version.id === currentId;
          const score = version.latest_run?.unified_score ?? null;
          return (
            <li key={version.id} className="shrink-0">
              <div
                className={`w-40 rounded-lg border p-3 ${
                  isCurrent ? "border-accent bg-accent/10" : "border-border bg-accent/5"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-sm font-bold text-foreground">v{version.current_version}</span>
                  {score !== null && (
                    <span className={`rounded px-1.5 py-0.5 text-xs font-semibold ${scoreColorClasses(score)}`}>
                      {formatScore(score)}
                    </span>
                  )}
                </div>
                <p className="mt-2 text-xs capitalize text-text-3">{version.status}</p>
                <p className="text-[11px] text-text-3">{relativeTime(version.created_at)}</p>
                {isCurrent && (
                  <p className="mt-1 text-[10px] font-medium uppercase tracking-wide text-accent">Current</p>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </Card>
  );
}
