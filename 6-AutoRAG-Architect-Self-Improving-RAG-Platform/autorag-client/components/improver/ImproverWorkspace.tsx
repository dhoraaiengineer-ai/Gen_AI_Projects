"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { usePipelines } from "@/hooks/use-pipelines";
import { useImprovement } from "@/hooks/use-improvement";
import { pipelineDisplayName } from "@/lib/format";
import { deriveProposedConfig, extractConfig } from "@/lib/variant";
import { CurrentConfiguration } from "@/components/improver/CurrentConfiguration";
import { RecommendationList } from "@/components/improver/RecommendationList";
import { ComparisonTable } from "@/components/improver/ComparisonTable";
import { PredictedImprovements } from "@/components/improver/PredictedImprovements";
import { EvaluationQueue } from "@/components/improver/EvaluationQueue";
import { ImproverAgentOutput } from "@/components/improver/ImproverAgentOutput";
import { BatchRecommendationsPanel } from "@/components/improver/BatchRecommendationsPanel";

/**
 * Client-side Improver Workspace (F-15; Chapter 29): pipeline selector, current
 * config, deterministic recommendations + proposed variant, config diff, baseline
 * metrics, and the route into Evaluation.
 *
 * Sourced entirely from the real GET /api/v1/score/{run_id} (the only endpoint
 * exposing failure_taxonomy + baseline metrics) — POST /api/v1/improve is a
 * NotImplementedError stub, so the proposed variant is derived client-side in
 * lib/variant.ts, not fetched. Consequently the spec's Variant A/B/C generator
 * (§29.9), numeric predicted scores (§29.11), and Optimization History (§29.12)
 * are intentionally not built: no backend persists variants or predictions yet.
 */
export function ImproverWorkspace() {
  const { pipelines, isLoading: pipelinesLoading } = usePipelines();
  const searchParams = useSearchParams();
  const deepLinkId = searchParams.get("pipeline_id");

  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Preselect the Diagnoser deep-link target, else the first pipeline.
  useEffect(() => {
    if (selectedId) return;
    if (deepLinkId && pipelines.some((p) => p.id === deepLinkId)) {
      setSelectedId(deepLinkId);
    } else if (pipelines.length > 0) {
      setSelectedId(pipelines[0].id);
    }
  }, [pipelines, selectedId, deepLinkId]);

  const pipeline = pipelines.find((p) => p.id === selectedId) ?? null;
  const runId = pipeline?.latest_run?.id ?? null;
  const { score, improvement, isLoading, error, refetch } = useImprovement(runId);

  const current = useMemo(() => (pipeline ? extractConfig(pipeline) : null), [pipeline]);
  const derived = useMemo(
    () => (current && score ? deriveProposedConfig(current, score.failure_taxonomy) : null),
    [current, score],
  );

  return (
    <div className="space-y-6">
      {/* Pipeline selector */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
        <label htmlFor="improve-pipeline-select" className="text-xs font-medium text-text-3">
          Pipeline
        </label>
        <select
          id="improve-pipeline-select"
          value={selectedId ?? ""}
          onChange={(e) => setSelectedId(e.target.value || null)}
          disabled={pipelinesLoading || pipelines.length === 0}
          className="w-full max-w-sm rounded-md border border-border bg-accent/5 px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none disabled:opacity-50"
        >
          {pipelines.length === 0 && <option value="">No pipelines available</option>}
          {pipelines.map((p) => (
            <option key={p.id} value={p.id}>
              {pipelineDisplayName(p)}
            </option>
          ))}
        </select>
      </div>

      {!pipeline || !current ? (
        <EmptyCard>Select a pipeline to generate an improvement variant.</EmptyCard>
      ) : !runId ? (
        <EmptyCard>
          <p>No completed evaluation run for this pipeline yet — Improver needs a real failure to work from.</p>
          <Link
            href="/evaluation"
            className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-xs font-semibold text-foreground hover:bg-accent-light"
          >
            Open Evaluation Center
            <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
          </Link>
        </EmptyCard>
      ) : isLoading ? (
        <div
          aria-label="Loading pipeline metrics"
          className="h-40 animate-pulse rounded-xl border border-border bg-card"
        />
      ) : error ? (
        <div role="alert" className="rounded-xl border border-red-500/40 bg-red-500/5 p-6 text-sm text-red-600">
          Unable to load pipeline metrics: {error.message}
          <button
            type="button"
            onClick={refetch}
            className="ml-3 rounded-md bg-accent/5 px-3 py-1 text-xs font-medium text-foreground hover:bg-gray-200"
          >
            Retry
          </button>
        </div>
      ) : score && derived ? (
        <>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Section id="improve-current" title="Current Configuration">
              <CurrentConfiguration version={String(pipeline.current_version)} config={current} score={score} />
            </Section>
            <Section id="improve-recs" title="Recommended Changes">
              <RecommendationList recommendations={derived.recommendations} />
            </Section>
          </div>

          <Section id="improve-compare" title="Configuration Comparison">
            <ComparisonTable
              current={current}
              proposed={derived.proposed}
              changedKeys={derived.changedKeys}
            />
          </Section>

          <Section id="improve-predict" title="Baseline Metrics">
            <PredictedImprovements score={score} />
          </Section>

          {improvement && (
            <Section id="improve-agent-output" title="Improver Agent Output (real, backend-scored)">
              <ImproverAgentOutput improvement={improvement} pipelineId={pipeline.id} onApplied={refetch} />
            </Section>
          )}

          <EvaluationQueue pipelineId={pipeline.id} hasChanges={derived.changedKeys.length > 0} />

          <BatchRecommendationsPanel pipelineId={pipeline.id} />
        </>
      ) : null}
    </div>
  );
}

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby={`${id}-heading`}>
      <h2
        id={`${id}-heading`}
        className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-3"
      >
        {title}
      </h2>
      {children}
    </section>
  );
}

function EmptyCard({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-border bg-card p-10 text-center text-sm text-text-3">
      {children}
    </div>
  );
}
