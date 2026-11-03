"use client";

import { useEffect, useRef, useState } from "react";
import { Play, RefreshCw } from "lucide-react";

import { usePipelines } from "@/hooks/use-pipelines";
import { apiClient } from "@/services/api-client";
import type { ScoreResult } from "@/types";

const POLL_MS = 3_000;
const MAX_POLLS = 100; // ~5 minutes

interface RunEvaluationPanelProps {
  onScoreLoaded: (runId: string, score: ScoreResult) => void;
}

/**
 * One-click evaluation: pick a pipeline → dispatch POST /evaluate →
 * poll GET /jobs/{id} → load the score. No run_id copy-pasting needed.
 */
export function RunEvaluationPanel({ onScoreLoaded }: RunEvaluationPanelProps) {
  const { pipelines, isLoading: pipelinesLoading } = usePipelines();
  const [pipelineId, setPipelineId] = useState("");
  const [query, setQuery] = useState("");
  const [phase, setPhase] = useState<"idle" | "starting" | "polling" | "error">("idle");
  const [message, setMessage] = useState<string | null>(null);
  const pollCount = useRef(0);

  // Default to the first pipeline once loaded.
  useEffect(() => {
    if (!pipelineId && pipelines.length > 0) setPipelineId(pipelines[0].id);
  }, [pipelines, pipelineId]);

  async function runEvaluation() {
    if (!pipelineId) return;
    setPhase("starting");
    setMessage("Dispatching evaluation to the 9-agent loop…");
    try {
      const { run_id, job_id } = await apiClient.startEvaluation(pipelineId, query.trim());
      setPhase("polling");
      pollCount.current = 0;

      const poll = async (): Promise<void> => {
        pollCount.current += 1;
        if (pollCount.current > MAX_POLLS) {
          setPhase("error");
          setMessage("Evaluation is taking longer than expected — check the job on the Pipelines page.");
          return;
        }
        const job = await apiClient.pollJob(job_id).catch(() => null);
        // "blocked" is a real terminal outcome (e.g. faithfulness hard block)
        // -- the run has a genuine score, it's just deploy-ineligible.
        // "pending_approval" (P0.5, 12-Jul-2026) also has a real score --
        // Evaluator ran, only Deployer is paused awaiting human approval.
        if (
          job?.status === "completed" ||
          job?.status === "blocked" ||
          job?.status === "pending_approval"
        ) {
          setMessage("Loading score…");
          const score = await apiClient.getScore(run_id);
          setPhase("idle");
          setMessage(
            job.status === "pending_approval"
              ? "Score is 0.70–0.84 — awaiting human approval before deployment."
              : null,
          );
          onScoreLoaded(run_id, score);
          return;
        }
        if (job?.status === "failed") {
          setPhase("error");
          setMessage("Evaluation failed — see Diagnose for the root cause.");
          return;
        }
        setMessage(`Evaluating… the Evaluator agent is scoring your pipeline (check ${pollCount.current})`);
        setTimeout(() => void poll(), POLL_MS);
      };
      setTimeout(() => void poll(), POLL_MS);
    } catch (err) {
      setPhase("error");
      setMessage(err instanceof Error ? err.message : "Could not start evaluation");
    }
  }

  const busy = phase === "starting" || phase === "polling";

  return (
    <div className="panel-card flex flex-col gap-3 px-5 py-4">
      <div className="flex flex-wrap items-center gap-3">
        <label htmlFor="eval-pipeline" className="eyebrow shrink-0">
          Pipeline
        </label>
        <select
          id="eval-pipeline"
          value={pipelineId}
          onChange={(e) => setPipelineId(e.target.value)}
          disabled={busy || pipelinesLoading}
          className="min-w-0 flex-1 rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-amber-500/30 focus:border-amber-400"
        >
          {pipelines.length === 0 && <option value="">No pipelines yet — create one first</option>}
          {pipelines.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name || p.id.slice(0, 8)} · v{p.current_version}
            </option>
          ))}
        </select>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <label htmlFor="eval-query" className="eyebrow shrink-0">
          Query
        </label>
        <input
          id="eval-query"
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={busy}
          placeholder="Leave blank to use the golden-path demo question (attention-is-all-you-need.pdf only)"
          className="min-w-0 flex-1 rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground placeholder-muted-foreground outline-none focus:ring-2 focus:ring-amber-500/30 focus:border-amber-400"
        />
        <button
          type="button"
          onClick={() => void runEvaluation()}
          disabled={busy || !pipelineId}
          aria-busy={busy}
          className="flex items-center gap-2 rounded-lg bg-amber-500 px-5 py-2 text-sm font-semibold text-white transition-colors motion-safe:duration-150 hover:bg-amber-600 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? <RefreshCw className="h-4 w-4 motion-safe:animate-spin" aria-hidden="true" /> : <Play className="h-4 w-4" aria-hidden="true" />}
          {busy ? "Evaluating…" : "Run Evaluation"}
        </button>
      </div>
      {message && (
        <p role="status" aria-live="polite" className={phase === "error" ? "text-xs text-rose-600" : "text-xs text-text-3"}>
          {message}
        </p>
      )}
    </div>
  );
}
