import { ArrowRight } from "lucide-react";

import { CONFIG_FIELDS, formatConfigValue } from "@/lib/variant";
import type { ConfigKey, PipelineConfig } from "@/lib/variant";

interface ComparisonTableProps {
  current: PipelineConfig;
  proposed: PipelineConfig;
  changedKeys: ConfigKey[];
}

/**
 * §29.10 Configuration Comparison — current vs proposed, side by side.
 * Only modified rows are highlighted (spec: "Highlight only modified values").
 */
export function ComparisonTable({ current, proposed, changedKeys }: ComparisonTableProps) {
  const changed = new Set(changedKeys);

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-card">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-text-3">
            <th scope="col" className="px-5 py-3 font-medium">Field</th>
            <th scope="col" className="px-5 py-3 font-medium">Current</th>
            <th scope="col" className="px-5 py-3 font-medium">Proposed</th>
          </tr>
        </thead>
        <tbody>
          {CONFIG_FIELDS.map((field) => {
            const isChanged = changed.has(field.key);
            return (
              <tr
                key={field.key}
                className={`border-b border-border/50 last:border-0 ${isChanged ? "bg-amber-500/5" : ""}`}
              >
                <th scope="row" className="px-5 py-3 text-left font-medium text-text-2">
                  {field.label}
                </th>
                <td className="px-5 py-3 font-mono text-text-3">
                  {formatConfigValue(field.key, current[field.key])}
                </td>
                <td className="px-5 py-3 font-mono">
                  {isChanged ? (
                    <span className="inline-flex items-center gap-1.5 font-semibold text-amber-400">
                      <ArrowRight className="h-3 w-3" aria-hidden="true" />
                      {formatConfigValue(field.key, proposed[field.key])}
                    </span>
                  ) : (
                    <span className="text-gray-300">
                      {formatConfigValue(field.key, proposed[field.key])}
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
