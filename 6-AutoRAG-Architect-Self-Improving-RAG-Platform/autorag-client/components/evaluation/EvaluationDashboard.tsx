"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshCw, Search } from "lucide-react";

import { apiClient } from "@/services/api-client";
import { isHardBlock, scoreBand, DEPLOY_GATE } from "@/lib/score";
import type { ScoreResult } from "@/types";

import { SectionCard } from "@/components/ui/section-card";
import { UnifiedScoreGauge } from "@/components/evaluation/UnifiedScoreGauge";
import { RAGASMetrics, extractRAGASMetrics } from "@/components/evaluation/RAGASMetrics";
import { HallucinationScore } from "@/components/evaluation/HallucinationScore";
import { EvalHistoryChart } from "@/components/evaluation/EvalHistoryChart";
import type { EvalHistoryEntry } from "@/components/evaluation/EvalHistoryChart";
import { CostLatencyPanel } from "@/components/evaluation/CostLatencyPanel";
import { RunEvaluationPanel } from "@/components/evaluation/RunEvaluationPanel";
import { ScoreProvenance } from "@/components/evaluation/ScoreProvenance";

export function EvaluationDashboard() {
  const [runId, setRunId] = useState("");
  const [score, setScore] = useState<ScoreResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Real evaluation history for the currently-loaded pipeline (replaces the
  // previous hardcoded MOCK_HISTORY — 12-Jul-2026 "no mock data" directive).
  const [history, setHistory] = useState<EvalHistoryEntry[]>([]);

  const fetchScore = useCallback(async (id: string) => {
    const trimmed = id.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    try {
      const result = await apiClient.getScore(trimmed);
      setScore(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load evaluation results");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!score?.pipeline_id) return;
    let mounted = true;
    apiClient
      .getEvaluationHistory(score.pipeline_id)
      .then((res) => {
        if (!mounted) return;
        // Oldest first for the chart's left-to-right timeline.
        const items = [...res.items].reverse();
        setHistory(
          items
            .filter((i) => i.unified_score !== null && i.faithfulness !== null)
            .map((i, idx) => ({
              label: `Run ${idx + 1}`,
              unified_score: i.unified_score as number,
              faithfulness: i.faithfulness as number,
            })),
        );
      })
      .catch(() => setHistory([]));
    return () => {
      mounted = false;
    };
  }, [score?.pipeline_id]);

  // faithfulness and unified_score are computed together in the same Evaluator
  // step (evaluator.py) -- non-null here is provably safe once unified_score
  // is non-null (checked by the `score.unified_score !== null` render gate below).
  const ragas =
    score && score.faithfulness !== null
      ? extractRAGASMetrics(score.faithfulness, score.ragas_metrics)
      : null;
  const faithfulnessBlocked = score ? isHardBlock(score.faithfulness) : false;
  // score.unified_score is null when a run fails before Evaluator ever runs
  // (e.g. an ingestion/embedding error) -- band is only meaningful once a
  // real score exists (13-Jul-2026 fix, see types/index.ts ScoreResult).
  const band = score && score.unified_score !== null ? scoreBand(score.unified_score) : null;

  return (
    // No own PageHeader here -- this renders as EvaluationCenterClient's
    // "Run Evaluation" tab, directly below that component's single shared
    // PageHeader ("Evaluation Center"). A second nested header here duplicated
    // it (25-Jul-2026 fix, per external review feedback).
    <div className="space-y-6">
      {/* One-click run — no run_id needed */}
      <RunEvaluationPanel
        onScoreLoaded={(id, result) => {
          setRunId(id);
          setScore(result);
          setError(null);
        }}
      />

      {/* Manual run_id lookup (secondary path) */}
      <details className="group">
        <summary className="cursor-pointer text-xs font-medium text-text-3 hover:text-foreground">
          Look up a past run by ID…
        </summary>
        <div className="mt-3 flex gap-3">
          <input
            type="text"
            value={runId}
            onChange={(e) => setRunId(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && fetchScore(runId)}
            placeholder="Paste a run_id…"
            aria-label="Evaluation run ID"
            className="flex-1 rounded-lg border border-border bg-card px-4 py-2 text-sm text-foreground placeholder-muted-foreground outline-none focus:ring-2 focus:ring-amber-500/30 focus:border-amber-400"
          />
          <button
            type="button"
            onClick={() => fetchScore(runId)}
            disabled={loading || !runId.trim()}
            className="flex items-center gap-2 rounded-lg border border-border bg-card px-5 py-2 text-sm font-semibold text-foreground hover:bg-accent/5 disabled:cursor-not-allowed disabled:opacity-50 motion-safe:transition-colors"
            aria-busy={loading}
          >
            {loading ? <RefreshCw className="h-4 w-4 motion-safe:animate-spin" aria-hidden="true" /> : <Search className="h-4 w-4" aria-hidden="true" />}
            {loading ? "Loading…" : "Load"}
          </button>
        </div>
      </details>

      {error && (
        <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      )}

      {loading && (
        <div className="space-y-4" aria-hidden="true">
          <div className="h-40 motion-safe:animate-pulse rounded-xl bg-accent/5" />
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-28 motion-safe:animate-pulse rounded-xl bg-accent/5" />
            ))}
          </div>
        </div>
      )}

      {score && !loading && score.unified_score === null && (
        <div className="animate-fade-in rounded-xl border border-border bg-card p-6 text-center">
          <p className="text-sm font-semibold text-text-3">NO EVALUATION RESULT</p>
          <p className="mt-1 text-xs text-text-3">
            Not collected — this run (status: {score.status}) did not reach the Evaluator, so no
            deployment threshold was evaluated.
          </p>
        </div>
      )}

      {score && !loading && score.unified_score !== null && band && (
        <div className="animate-fade-in space-y-6">
          <DeploymentGateBanner
            score={score.unified_score}
            adversarialPassed={score.adversarial_passed}
            faithfulnessBlocked={faithfulnessBlocked}
            band={band}
          />

          <ScoreProvenance score={score} />

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[240px_1fr]">
            <SectionCard compact className="flex flex-col items-center justify-center">
              <h2 className="eyebrow mb-4">Unified Score</h2>
              <UnifiedScoreGauge score={score.unified_score} />
            </SectionCard>
            <section aria-labelledby="ragas-heading">
              <h2 id="ragas-heading" className="eyebrow mb-3">RAGAS Metrics</h2>
              {ragas && <RAGASMetrics metrics={ragas} />}
            </section>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <section aria-labelledby="hallucination-heading">
              <h2 id="hallucination-heading" className="eyebrow mb-3">Adversarial Safety</h2>
              <HallucinationScore passed={score.adversarial_passed} failureTaxonomy={score.failure_taxonomy} />
            </section>
            <section aria-labelledby="cost-heading">
              <h2 id="cost-heading" className="eyebrow mb-3">Cost &amp; Latency (Rule 86)</h2>
              <CostLatencyPanel score={score} />
            </section>
          </div>
        </div>
      )}

      <section aria-labelledby="history-heading">
        <h2 id="history-heading" className="eyebrow mb-3">Evaluation History</h2>
        <div className="panel-card p-4">
          {score?.pipeline_id ? (
            <EvalHistoryChart history={history} />
          ) : (
            <p className="py-8 text-center text-sm text-text-3">
              Run an evaluation above to see this pipeline&apos;s real score history.
            </p>
          )}
        </div>
      </section>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Deployment gate banner — verdict + what happens next
// ─────────────────────────────────────────────────────────────────────────────

interface DeploymentGateBannerProps {
  score: number;
  adversarialPassed: boolean;
  faithfulnessBlocked: boolean;
  band: ReturnType<typeof scoreBand>;
}

function DeploymentGateBanner({ score, adversarialPassed, faithfulnessBlocked, band }: DeploymentGateBannerProps) {
  const eligible = band === "deploy" && adversarialPassed && !faithfulnessBlocked;
  const hitl = band === "hitl" && adversarialPassed && !faithfulnessBlocked;

  const containerClass = eligible
    ? "border-emerald-200 bg-emerald-50"
    : hitl
      ? "border-amber-200 bg-amber-50"
      : "border-rose-200 bg-rose-50";
  const textClass = eligible ? "text-emerald-700" : hitl ? "text-amber-700" : "text-rose-700";

  const label = eligible ? "Deploy Eligible" : hitl ? "HITL Approval Required" : "Hard Block — Deployment Not Allowed";
  const next = eligible
    ? "Next: go to Deploy (Step 4) — this pipeline can promote automatically."
    : hitl
      ? "Next: go to Deploy (Step 4) and approve or reject this run."
      : "Next: check Diagnose for the root cause — the Improver agent will suggest a better configuration.";

  const sublabel = faithfulnessBlocked
    ? "Faithfulness < 0.5: non-bypassable hard block regardless of total score."
    : !adversarialPassed
      ? "Adversarial benchmark failed: fabricated answer detected."
      : band === "hitl"
        ? `Score ${score.toFixed(2)} is in the HITL band (0.70 – 0.84).`
        : band === "retry"
          ? `Score ${score.toFixed(2)} is below 0.70.`
          : `Score ${score.toFixed(2)} exceeds the ${DEPLOY_GATE} deployment gate.`;

  return (
    <div role="status" aria-live="polite" className={`flex items-center justify-between gap-4 rounded-xl border px-5 py-4 ${containerClass}`}>
      <div>
        <p className={`text-base font-bold ${textClass}`}>{label}</p>
        <p className={`mt-0.5 text-xs ${textClass} opacity-80`}>{sublabel}</p>
        <p className="mt-1.5 text-xs font-medium text-text-3">{next}</p>
      </div>
      <span className={`font-mono text-3xl font-bold tabular-nums ${textClass}`} aria-label={`Unified Score: ${score.toFixed(3)}`}>
        {score.toFixed(3)}
      </span>
    </div>
  );
}
