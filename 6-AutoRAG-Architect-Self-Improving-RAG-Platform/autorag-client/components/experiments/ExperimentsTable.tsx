"use client";

import { scoreColorClasses, formatScorePercent } from "@/lib/score";
import type { ExperimentRecord, ExperimentStatus } from "@/lib/experiments";

interface Props {
  records: ExperimentRecord[];
  selectedIds: Set<string>;
  onToggle: (id: string) => void;
}

const STATUS_CLASSES: Record<ExperimentStatus, string> = {
  completed: "text-green-400 bg-green-900/30",
  running: "text-blue-400 bg-blue-900/30",
  failed: "text-red-400 bg-red-900/30",
  promoted: "text-purple-400 bg-purple-900/30",
  archived: "text-text-3 bg-accent/5",
};

export function ExperimentsTable({ records, selectedIds, onToggle }: Props) {
  if (records.length === 0) {
    return (
      <div className="flex h-32 items-center justify-center rounded-lg border border-border text-text-3">
        No experiment runs found for this pipeline.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-card text-left text-xs font-medium uppercase tracking-wide text-text-3">
            <th className="px-4 py-3 w-8">
              <span className="sr-only">Select</span>
            </th>
            <th className="px-4 py-3">Pipeline</th>
            <th className="px-4 py-3">Version</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3 text-right">Unified Score</th>
            <th className="px-4 py-3 text-right">Latency (p95)</th>
            <th className="px-4 py-3 text-right">Cost / query</th>
            <th className="px-4 py-3">Date</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-neutral-800">
          {records.map((rec) => (
            <tr
              key={rec.id}
              className="bg-accent/5 transition-colors hover:bg-accent/5"
            >
              <td className="px-4 py-3">
                <input
                  type="checkbox"
                  aria-label={`Select ${rec.pipelineName} v${rec.version}`}
                  checked={selectedIds.has(rec.id)}
                  onChange={() => onToggle(rec.id)}
                  className="rounded border-border bg-accent/5 text-orange-500"
                />
              </td>
              <td className="px-4 py-3 font-medium text-neutral-100">{rec.pipelineName}</td>
              <td className="px-4 py-3 font-mono text-text-2">v{rec.version}</td>
              <td className="px-4 py-3">
                <span
                  className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ${STATUS_CLASSES[rec.status]}`}
                >
                  {rec.status}
                </span>
              </td>
              <td className="px-4 py-3 text-right font-mono">
                {rec.unifiedScore !== null ? (
                  <span
                    className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-semibold ${scoreColorClasses(rec.unifiedScore)}`}
                  >
                    {formatScorePercent(rec.unifiedScore)}
                  </span>
                ) : (
                  <span className="text-neutral-600">—</span>
                )}
              </td>
              <td className="px-4 py-3 text-right font-mono text-text-2">
                {rec.latencyMs !== null ? `${Math.round(rec.latencyMs)} ms` : "—"}
              </td>
              <td className="px-4 py-3 text-right font-mono text-text-2">
                {rec.costUsd !== null ? `$${rec.costUsd.toFixed(4)}` : "—"}
              </td>
              <td className="px-4 py-3 text-text-3">
                {new Date(rec.createdAt).toLocaleDateString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
