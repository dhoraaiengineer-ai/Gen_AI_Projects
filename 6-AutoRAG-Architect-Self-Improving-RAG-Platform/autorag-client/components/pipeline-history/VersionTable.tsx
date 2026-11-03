"use client";

/**
 * Version Inventory — Chapter 34.8. Real per-version fields only. Author and
 * environment columns from the spec are dropped: the frozen Pipeline schema
 * carries no `created_by` or `environment`. The two "Compare" checkboxes drive
 * the Configuration Comparison panel (max two selections).
 */

import { Card } from "@/components/ui/card";
import { relativeTime } from "@/lib/format";
import { formatScore, scoreColorClasses } from "@/lib/score";
import type { PipelineWithRun } from "@/types";

interface VersionTableProps {
  versions: PipelineWithRun[];
  currentId: string;
  compareIds: string[];
  onToggleCompare: (id: string) => void;
  isLoading: boolean;
}

export function VersionTable({ versions, currentId, compareIds, onToggleCompare, isLoading }: VersionTableProps) {
  if (isLoading) {
    return <Card className="h-56 animate-pulse bg-accent/5" />;
  }

  if (versions.length === 0) {
    return (
      <Card className="p-8 text-center text-sm text-text-3">
        No versions found for this pipeline&apos;s project.
      </Card>
    );
  }

  return (
    <Card className="overflow-x-auto p-0">
      <table className="w-full min-w-[560px] text-sm">
        <caption className="sr-only">Pipeline version inventory</caption>
        <thead>
          <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-text-3">
            <th scope="col" className="px-4 py-3 font-medium">Compare</th>
            <th scope="col" className="px-4 py-3 font-medium">Version</th>
            <th scope="col" className="px-4 py-3 font-medium">Status</th>
            <th scope="col" className="px-4 py-3 font-medium">Unified Score</th>
            <th scope="col" className="px-4 py-3 font-medium">Created</th>
          </tr>
        </thead>
        <tbody>
          {versions.map((version) => {
            const isCurrent = version.id === currentId;
            const checked = compareIds.includes(version.id);
            const disabled = !checked && compareIds.length >= 2;
            const score = version.latest_run?.unified_score ?? null;
            return (
              <tr
                key={version.id}
                className={`border-b border-border/50 last:border-0 ${isCurrent ? "bg-accent/5" : ""}`}
              >
                <td className="px-4 py-3">
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={disabled}
                    onChange={() => onToggleCompare(version.id)}
                    aria-label={`Select version ${version.current_version} to compare`}
                    className="h-4 w-4 accent-accent disabled:opacity-40"
                  />
                </td>
                <th scope="row" className="px-4 py-3 text-left font-mono font-medium text-foreground">
                  v{version.current_version}
                  {isCurrent && <span className="ml-2 text-[10px] uppercase text-accent">current</span>}
                </th>
                <td className="px-4 py-3 capitalize text-text-2">{version.status}</td>
                <td className="px-4 py-3">
                  {score === null ? (
                    <span className="text-text-3">—</span>
                  ) : (
                    <span className={`inline-flex rounded px-2 py-0.5 text-xs font-semibold ${scoreColorClasses(score)}`}>
                      {formatScore(score)}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-xs text-text-3">{relativeTime(version.created_at)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Card>
  );
}
