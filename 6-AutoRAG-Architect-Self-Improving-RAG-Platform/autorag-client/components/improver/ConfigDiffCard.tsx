"use client";

import type { ConfigDiffEntry } from "@/types";

interface ConfigDiffCardProps {
  diff: ConfigDiffEntry[];
}

/**
 * Real field-by-field config diff returned by POST /pipelines/{id}/apply-improvement
 * (20-Jul-2026, Apply Improvement feature) -- OptimizerService's own diff, not a
 * client-side guess. No "expected effect" copy is shown: this service can't verify
 * what effect a change will have, only what changed -- inventing that text would be
 * a claim with nothing real behind it.
 */
export function ConfigDiffCard({ diff }: ConfigDiffCardProps) {
  if (diff.length === 0) {
    return (
      <p className="text-xs text-text-3">
        This variant matches the pipeline&apos;s current configuration — nothing to apply.
      </p>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <table className="w-full text-left text-sm">
        <thead className="text-xs uppercase tracking-wide text-text-3">
          <tr className="border-b border-border">
            <th className="px-4 py-2.5 font-medium">Field</th>
            <th className="px-4 py-2.5 font-medium">Current</th>
            <th className="px-4 py-2.5 font-medium" />
            <th className="px-4 py-2.5 font-medium">Recommended</th>
          </tr>
        </thead>
        <tbody>
          {diff.map((entry) => (
            <tr key={entry.field} className="border-b border-border last:border-0">
              <td className="px-4 py-2.5 font-mono text-xs text-text-3">{entry.field}</td>
              <td className="px-4 py-2.5 font-mono text-text-2">
                {formatValue(entry.from_value)}
              </td>
              <td className="px-4 py-2.5 text-text-3">→</td>
              <td className="px-4 py-2.5 font-mono font-semibold text-emerald-400">
                {formatValue(entry.to_value)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "On" : "Off";
  return String(value);
}
