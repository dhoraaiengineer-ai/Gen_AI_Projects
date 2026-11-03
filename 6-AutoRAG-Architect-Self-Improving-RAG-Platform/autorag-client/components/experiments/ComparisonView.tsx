"use client";

import type { ExperimentRecord, ComparisonRow } from "@/lib/experiments";
import { buildComparisonRows } from "@/lib/experiments";

interface Props {
  a: ExperimentRecord;
  b: ExperimentRecord;
}

function Cell({ value, side, winner }: { value: string; side: "a" | "b"; winner: "a" | "b" | "tie" }) {
  const isWinner = winner === side;
  return (
    <td className={`px-4 py-3 text-right font-mono ${isWinner ? "font-semibold text-green-400" : "text-text-2"}`}>
      {value}
    </td>
  );
}

export function ComparisonView({ a, b }: Props) {
  const rows: ComparisonRow[] = buildComparisonRows(a, b);

  return (
    <div className="rounded-lg border border-border">
      <div className="border-b border-border px-4 py-3">
        <h3 className="text-sm font-semibold text-neutral-200">Side-by-Side Comparison</h3>
        <p className="mt-0.5 text-xs text-text-3">
          Green value = winner for that metric. Select two experiments from the table above.
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-card text-xs font-medium uppercase tracking-wide text-text-3">
              <th className="px-4 py-3 text-left">Metric</th>
              <th className="px-4 py-3 text-right">
                {a.pipelineName} v{a.version}
              </th>
              <th className="px-4 py-3 text-right">
                {b.pipelineName} v{b.version}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-800">
            {rows.map((row) => (
              <tr key={row.metric} className="bg-accent/5 hover:bg-accent/5">
                <td className="px-4 py-3 font-medium text-text-2">{row.metric}</td>
                <Cell value={row.a} side="a" winner={row.winner} />
                <Cell value={row.b} side="b" winner={row.winner} />
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
