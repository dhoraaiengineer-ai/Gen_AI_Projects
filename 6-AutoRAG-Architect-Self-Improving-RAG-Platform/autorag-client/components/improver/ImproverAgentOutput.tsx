"use client";

import type { ImprovementResponse } from "@/types";
import { ApplyImprovementButton } from "@/components/improver/ApplyImprovementButton";

interface ImproverAgentOutputProps {
  improvement: ImprovementResponse;
  pipelineId: string;
  onApplied?: () => void;
}

/**
 * Real backend Improver Agent output (Part E, 12-Jul-2026) — GET /improve/{run_id}.
 * Separate from the config comparison above (lib/variant.ts), which tunes a
 * different config schema (retrieval knobs) than what the real Improver
 * actually optimizes (chunking/embedding hyperparameters) — see lib/variant.ts's
 * header comment for why the two aren't reconciled into one view yet.
 * score_type is always "estimated" here — the Improver's heuristic scoring,
 * not a live re-evaluation of each candidate.
 */
export function ImproverAgentOutput({ improvement, pipelineId, onApplied }: ImproverAgentOutputProps) {
  if (!improvement.candidates || improvement.candidates.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-card p-6 text-center">
        <p className="text-sm font-semibold text-text-2">NO IMPROVEMENT CANDIDATES</p>
        <p className="mt-1 text-xs text-text-3">
          This run did not produce persisted Improver candidates. {improvement.message}
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <table className="w-full text-left text-sm">
        <thead className="text-xs uppercase tracking-wide text-text-3">
          <tr className="border-b border-border">
            <th className="px-4 py-3 font-medium">Candidate</th>
            <th className="px-4 py-3 font-medium">Estimated Score</th>
            <th className="px-4 py-3 font-medium">Δ vs. current</th>
            <th className="px-4 py-3 font-medium">Chunk Size</th>
            <th className="px-4 py-3 font-medium">k</th>
            <th className="px-4 py-3 font-medium">Selected</th>
            <th className="px-4 py-3 font-medium">Apply</th>
          </tr>
        </thead>
        <tbody>
          {improvement.candidates.map((c) => (
            <tr key={c.candidate_id} className="border-b border-border/60 align-top">
              <td className="px-4 py-3 font-mono text-xs text-text-3">
                {c.candidate_id.slice(0, 8)}
              </td>
              <td className="px-4 py-3 font-mono text-foreground">
                {c.score.toFixed(3)}{" "}
                <span className="text-[10px] uppercase text-text-3">est.</span>
              </td>
              <td className="px-4 py-3 font-mono text-text-2">
                {c.score_delta >= 0 ? "+" : ""}
                {c.score_delta.toFixed(3)}
              </td>
              <td className="px-4 py-3 font-mono text-text-2">
                {String(c.config?.chunk_size ?? "—")}
              </td>
              <td className="px-4 py-3 font-mono text-text-2">
                {String(c.config?.k_value ?? "—")}
              </td>
              <td className="px-4 py-3">
                {c.selected && (
                  <span
                    className="rounded-full px-2 py-0.5 text-xs font-medium"
                    style={{ backgroundColor: "#F5F3FF", color: "#8B5CF6" }}
                    title="Selected by the Improver's heuristic, not a live re-evaluation"
                  >
                    Selected (Estimated)
                  </span>
                )}
              </td>
              <td className="px-4 py-3">
                <ApplyImprovementButton
                  pipelineId={pipelineId}
                  runId={improvement.run_id}
                  variantId={c.candidate_id}
                  onApplied={onApplied}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
