"use client";

import { useState } from "react";
import { Loader2, Check, X } from "lucide-react";

import { apiClient } from "@/services/api-client";
import type { ConfigDiffEntry } from "@/types";
import { ConfigDiffCard } from "@/components/improver/ConfigDiffCard";

const POLL_MS = 3_000;
const MAX_POLLS = 100; // ~5 minutes, matches RunEvaluationPanel.tsx's ceiling

interface ApplyImprovementButtonProps {
  pipelineId: string;
  runId: string;
  variantId: string;
  /** Called once the re-evaluation reaches a real terminal state -- lets the
   * parent refetch pipeline/score/version data. Never called with a
   * fabricated result. */
  onApplied?: () => void;
}

type Phase = "idle" | "applying" | "rebuilding" | "completed" | "regressed" | "error";

/**
 * Applies one real Improver candidate: POST /pipelines/{id}/apply-improvement
 * -> real config diff shown immediately -> poll GET /jobs/{id} for the
 * rebuild+re-evaluation -> real new score (worse or better, never clamped).
 * "regressed" is a real, honestly-labeled outcome, not an error -- the apply
 * itself succeeded, the new configuration just scored lower.
 */
export function ApplyImprovementButton({
  pipelineId,
  runId,
  variantId,
  onApplied,
}: ApplyImprovementButtonProps) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [diff, setDiff] = useState<ConfigDiffEntry[] | null>(null);
  const [oldScore, setOldScore] = useState<number | null>(null);
  const [newScore, setNewScore] = useState<number | null>(null);

  async function apply() {
    setPhase("applying");
    setMessage("Applying configuration and rebuilding…");
    try {
      const res = await apiClient.applyImprovement(pipelineId, { run_id: runId, variant_id: variantId });
      setDiff(res.config_diff);
      setOldScore(res.old_score);
      setPhase("rebuilding");
      setMessage("Ingestion agent is re-chunking with the new configuration…");

      let pollCount = 0;
      const poll = async (): Promise<void> => {
        pollCount += 1;
        if (pollCount > MAX_POLLS) {
          setPhase("error");
          setMessage("Rebuild is taking longer than expected — check the Pipelines page.");
          return;
        }
        const job = await apiClient.pollJob(res.job_id).catch(() => null);
        if (job?.status === "completed" || job?.status === "blocked" || job?.status === "pending_approval") {
          const score = await apiClient.getScore(res.job_id).catch(() => null);
          const finalScore = score?.unified_score ?? null;
          setNewScore(finalScore);
          const improved = finalScore !== null && res.old_score !== null && finalScore > res.old_score;
          setPhase(improved || res.old_score === null ? "completed" : "regressed");
          setMessage(null);
          onApplied?.();
          return;
        }
        if (job?.status === "failed") {
          setPhase("error");
          setMessage("Re-evaluation failed — check Diagnoser for the root cause.");
          return;
        }
        setMessage(`Re-evaluating… (check ${pollCount})`);
        setTimeout(() => void poll(), POLL_MS);
      };
      setTimeout(() => void poll(), POLL_MS);
    } catch (err) {
      setPhase("error");
      setMessage(err instanceof Error ? err.message : "Could not apply this configuration");
    }
  }

  if (phase === "idle") {
    return (
      <button
        type="button"
        onClick={() => void apply()}
        className="rounded-md bg-accent px-3 py-1.5 text-xs font-semibold text-foreground transition-colors hover:bg-light_bronze-300"
      >
        Apply
      </button>
    );
  }

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border bg-accent/5 p-3">
      {(phase === "applying" || phase === "rebuilding") && (
        <div className="flex items-center gap-2 text-xs text-text-2">
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
          {message}
        </div>
      )}

      {diff && <ConfigDiffCard diff={diff} />}

      {(phase === "completed" || phase === "regressed") && (
        <div
          className={`flex items-center gap-2 text-xs font-semibold ${
            phase === "completed" ? "text-emerald-400" : "text-amber-400"
          }`}
        >
          {phase === "completed" ? (
            <Check className="h-3.5 w-3.5" aria-hidden="true" />
          ) : (
            <X className="h-3.5 w-3.5" aria-hidden="true" />
          )}
          {oldScore !== null ? oldScore.toFixed(3) : "—"} → {newScore !== null ? newScore.toFixed(3) : "—"}
          {phase === "regressed" && " (this variant scored worse — not recommended)"}
        </div>
      )}

      {phase === "error" && (
        <p role="alert" className="text-xs text-rose-400">
          {message}
        </p>
      )}
    </div>
  );
}
