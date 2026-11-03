import { formatScore } from "@/lib/score";
import type { Deployment, ScoreResult } from "@/types";

interface CurrentVsCandidateProps {
  currentDeployment: Deployment | null;
  candidateScore: ScoreResult | null;
}

/**
 * Real Current-vs-Candidate comparison (25-Jul-2026, capability-first polish
 * pass). Deployment (the deploy-history row type) carries no run_id -- only
 * a real unified_score_at_deploy snapshot -- so "Current Production" can only
 * honestly show Unified Score, not the full metric set. Recall/Faithfulness/
 * Latency/Cost are shown for the Candidate only, where a full ScoreResult is
 * actually available; the Current column shows "—" for those rather than
 * fabricating a value.
 */
export function CurrentVsCandidate({ currentDeployment, candidateScore }: CurrentVsCandidateProps) {
  if (!candidateScore) return null;

  const currentUnified = currentDeployment?.unified_score_at_deploy ?? null;
  const candidateUnified = candidateScore.unified_score;
  const delta = currentUnified !== null && candidateUnified !== null ? candidateUnified - currentUnified : null;

  const rows: { label: string; current: string; candidate: string }[] = [
    { label: "Unified Score", current: formatScore(currentUnified), candidate: formatScore(candidateUnified) },
    { label: "Recall", current: "—", candidate: formatScore(candidateScore.recall) },
    { label: "Faithfulness", current: "—", candidate: formatScore(candidateScore.faithfulness) },
    {
      label: "Latency (p95)",
      current: "—",
      candidate: candidateScore.latency_p95_ms !== null ? `${(candidateScore.latency_p95_ms / 1000).toFixed(1)}s` : "—",
    },
    {
      label: "Cost / Query",
      current: "—",
      candidate: candidateScore.cost_per_query_usd !== null ? `$${candidateScore.cost_per_query_usd.toFixed(4)}` : "—",
    },
  ];

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">Current Production vs. Candidate</h3>
        {delta !== null && (
          <span className={`font-mono text-xs font-bold ${delta >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
            {delta >= 0 ? "+" : ""}
            {delta.toFixed(3)} Unified Score
          </span>
        )}
      </div>
      {!currentDeployment && (
        <p className="mb-3 text-xs text-text-3">No promoted deployment yet — only the candidate&apos;s real values are shown.</p>
      )}
      <table className="w-full text-left text-sm">
        <thead className="text-[10px] uppercase tracking-wide text-text-3">
          <tr className="border-b border-border">
            <th className="py-2 font-medium">Metric</th>
            <th className="py-2 font-medium">Current</th>
            <th className="py-2 font-medium">Candidate</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label} className="border-b border-border/60 last:border-0">
              <td className="py-2 text-text-2">{row.label}</td>
              <td className="py-2 font-mono text-text-3">{row.current}</td>
              <td className="py-2 font-mono font-semibold text-foreground">{row.candidate}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
