"use client";

/**
 * Configuration Comparison — Chapter 34.9. Diffs the real, persisted config of
 * two selected versions; only changed rows are highlighted. Fields the frozen
 * Pipeline schema does not carry (prompt, temperature, embedding model) are not
 * shown — no fabrication.
 */

import { ArrowRight } from "lucide-react";

import { Card } from "@/components/ui/card";
import { diffConfigs, extractConfigView } from "@/lib/pipeline-history";
import type { PipelineWithRun } from "@/types";

interface VersionComparisonProps {
  versionA: PipelineWithRun | null;
  versionB: PipelineWithRun | null;
}

export function VersionComparison({ versionA, versionB }: VersionComparisonProps) {
  if (!versionA || !versionB) {
    return (
      <Card className="p-8 text-center text-sm text-text-3">
        Select two versions in the table above to compare their configuration.
      </Card>
    );
  }

  if (versionA.id === versionB.id) {
    return (
      <Card className="p-8 text-center text-sm text-text-3">
        Pick two different versions to see a comparison.
      </Card>
    );
  }

  const rows = diffConfigs(extractConfigView(versionA), extractConfigView(versionB));
  const changedCount = rows.filter((r) => r.changed).length;

  return (
    <Card className="overflow-x-auto p-0">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h3 className="text-sm font-semibold text-foreground">Configuration Comparison</h3>
        <span className="text-xs text-text-3">
          {changedCount === 0 ? "Identical configuration" : `${changedCount} field${changedCount === 1 ? "" : "s"} changed`}
        </span>
      </div>
      <table className="w-full min-w-[520px] text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-text-3">
            <th scope="col" className="px-4 py-3 font-medium">Field</th>
            <th scope="col" className="px-4 py-3 font-medium">v{versionA.current_version}</th>
            <th scope="col" className="px-4 py-3 font-medium">v{versionB.current_version}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.key}
              className={`border-b border-border/50 last:border-0 ${row.changed ? "bg-amber-500/5" : ""}`}
            >
              <th scope="row" className="px-4 py-3 text-left font-medium text-text-2">{row.label}</th>
              <td className="px-4 py-3 font-mono text-text-3">{row.aValue}</td>
              <td className="px-4 py-3 font-mono">
                {row.changed ? (
                  <span className="inline-flex items-center gap-1.5 font-semibold text-amber-400">
                    <ArrowRight className="h-3 w-3" aria-hidden="true" />
                    {row.bValue}
                  </span>
                ) : (
                  <span className="text-gray-300">{row.bValue}</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
