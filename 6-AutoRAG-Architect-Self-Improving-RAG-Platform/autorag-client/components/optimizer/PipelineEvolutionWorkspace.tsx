"use client";

import { useEffect, useState } from "react";

import { usePipelines } from "@/hooks/use-pipelines";
import { usePipelineVersions } from "@/hooks/use-pipeline-versions";
import { useDeployment } from "@/hooks/use-deployment";
import { pipelineDisplayName } from "@/lib/format";
import type { PipelineVersionSummary } from "@/types";
import { OptimizationTimeline } from "@/components/optimizer/OptimizationTimeline";
import { VersionHistoryTable } from "@/components/optimizer/VersionHistoryTable";
import { VersionTrendCharts } from "@/components/optimizer/VersionTrendCharts";
import { DeploymentHistory } from "@/components/deployment/DeploymentHistory";

/**
 * Pipeline Evolution (20-Jul-2026, Apply Improvement feature) -- the
 * dedicated version-history + rollback screen. Same pipeline-selector
 * pattern as ImproverWorkspace.tsx. Every number on this page comes from
 * GET /pipelines/{id}/versions (real evaluation_runs/experiment_runs data,
 * migration 0015) -- a version with no completed evaluation yet shows "—",
 * never a guess.
 */
export function PipelineEvolutionWorkspace() {
  const { pipelines, isLoading: pipelinesLoading } = usePipelines();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedId && pipelines.length > 0) setSelectedId(pipelines[0].id);
  }, [pipelines, selectedId]);

  const pipeline = pipelines.find((p) => p.id === selectedId) ?? null;
  const { versions, isLoading, error, refetch } = usePipelineVersions(selectedId);
  const { history: deployments, isLoading: deploymentsLoading, error: deploymentsError, refetch: refetchDeployments } =
    useDeployment(selectedId);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
        <label htmlFor="evolution-pipeline-select" className="text-xs font-medium text-text-3">
          Pipeline
        </label>
        <select
          id="evolution-pipeline-select"
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

      {!pipeline ? (
        <EmptyCard>Select a pipeline to view its version history.</EmptyCard>
      ) : isLoading ? (
        <div
          aria-label="Loading version history"
          className="h-40 animate-pulse rounded-xl border border-border bg-card"
        />
      ) : error ? (
        <div role="alert" className="rounded-xl border border-red-500/40 bg-red-500/5 p-6 text-sm text-red-600">
          Unable to load version history: {error.message}
          <button
            type="button"
            onClick={refetch}
            className="ml-3 rounded-md bg-accent/5 px-3 py-1 text-xs font-medium text-foreground hover:bg-gray-200"
          >
            Retry
          </button>
        </div>
      ) : versions.length <= 1 ? (
        <EmptyCard>
          {pipelineDisplayName(pipeline)} has no applied-improvement history yet — apply an
          Improver recommendation from the Improver Workspace to start building a version
          history.
        </EmptyCard>
      ) : (
        <>
          <OptimizationSuccessStat versions={versions} />
          <Section title="Timeline">
            <OptimizationTimeline versions={versions} currentVersion={pipeline.current_version} />
          </Section>
          <Section title="Performance Trend">
            <VersionTrendCharts versions={versions} />
          </Section>
          <Section title="Version Details">
            <VersionHistoryTable
              pipelineId={pipeline.id}
              versions={versions}
              currentVersion={pipeline.current_version}
              onRolledBack={refetch}
            />
          </Section>
        </>
      )}

      {/* Deployment History -- real GET /deploy/history data, already used on
          the Deployment Center page; independent of version count above (a
          pipeline can have deployments regardless of how many versions it
          has applied). 25-Jul-2026 capability-first polish pass. */}
      {pipeline && (
        <Section title="Deployment History">
          <DeploymentHistory
            deployments={deployments}
            isLoading={deploymentsLoading}
            error={deploymentsError}
            onRetry={refetchDeployments}
          />
        </Section>
      )}
    </div>
  );
}

/**
 * Real "Optimization Success" stat -- derived entirely from the versions
 * already fetched for this pipeline (score_delta on any version produced by
 * an applied Improver recommendation). Scoped to a single pipeline rather
 * than a fleet-wide Dashboard number: no aggregate endpoint exists across
 * all pipelines' experiment_runs yet, and this stat needs zero new backend
 * work by staying here. v1 (never touched by apply-improvement) has no
 * score_delta and is excluded from the denominator -- it was never an
 * "optimization attempt".
 */
function OptimizationSuccessStat({ versions }: { versions: PipelineVersionSummary[] }) {
  const attempts = versions.filter((v) => v.score_delta !== null);
  if (attempts.length === 0) return null;
  const successes = attempts.filter((v) => (v.score_delta ?? 0) > 0).length;
  const pct = Math.round((successes / attempts.length) * 100);

  return (
    <div className="flex items-center gap-4 rounded-xl border border-border bg-card px-5 py-4">
      <div>
        <div className="text-[11px] font-semibold uppercase tracking-wide text-text-3">
          Optimization Success
        </div>
        <div className="mt-1 font-mono text-2xl font-bold text-foreground">
          {successes} / {attempts.length}
          <span className="ml-2 text-base font-semibold text-emerald-400">{pct}%</span>
        </div>
      </div>
      <p className="max-w-sm text-xs text-text-3">
        Applied recommendations that improved the score, out of all applied recommendations for
        this pipeline.
      </p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-3">{title}</h2>
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
