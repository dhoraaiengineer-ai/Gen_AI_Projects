"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Activity, ArrowRight, BookOpen, FlaskConical, HeartPulse, TrendingUp, type LucideIcon } from "lucide-react";

import { EvalHistoryChart, type EvalHistoryEntry } from "@/components/evaluation/EvalHistoryChart";
import { HITLApprovalQueue } from "@/components/dashboard/HITLApprovalQueue";
import { JourneySteps, type JourneyProgress } from "@/components/dashboard/JourneySteps";
import { KpiRow } from "@/components/dashboard/KpiRow";
import { NeedsAttention } from "@/components/dashboard/NeedsAttention";
import { PipelineTable } from "@/components/dashboard/PipelineTable";
import { WelcomeHero } from "@/components/dashboard/WelcomeHero";
import { usePipelines } from "@/hooks/use-pipelines";
import { computeDashboardKpis } from "@/lib/kpi";
import { DEPLOY_GATE } from "@/lib/score";
import { apiClient } from "@/services/api-client";

// autorag-server/app/main.py:86-99 seeds this fixed-UUID pipeline on every
// local-mode backend startup so ConfiguratorWizard.listProjects() always has
// a usable ID. It isn't something the current user created, so it must not
// count toward "has this user built their first pipeline" -- otherwise every
// fresh local login sees hasPipeline: true and the journey CTA skips straight
// to Upload Documents, bypassing the 6-step Configurator entirely.
const SEEDED_DEMO_PIPELINE_ID = "01960000-0000-7000-8000-000000000001";

/**
 * Home / Welcome dashboard (Redesign Phase 2).
 * One hero, one guided journey, live vitals, then the working panels.
 * Deep-dive views (agents, observability, history) live on their own routes.
 */
export function DashboardView() {
  const { pipelines, isLoading, error, refetch } = usePipelines();
  // Excludes the auto-seeded "Local Demo Pipeline" (see SEEDED_DEMO_PIPELINE_ID
  // above) from every dashboard computation and list -- it isn't a pipeline the
  // current user created, so it must never count toward their journey progress,
  // KPIs, or pipeline table, especially during a live demo.
  const realPipelines = useMemo(
    () => pipelines.filter((p) => p.id !== SEEDED_DEMO_PIPELINE_ID),
    [pipelines],
  );
  const [documentCount, setDocumentCount] = useState<number | null>(null);
  const [pipelineFilter, setPipelineFilter] = useState<"5" | "10" | "all">("5");

  // Lightweight one-shot documents count for journey step 2.
  useEffect(() => {
    let mounted = true;
    apiClient
      .listDocuments({ page: 1, page_size: 1 })
      .then((res) => {
        if (mounted) setDocumentCount(res.total ?? res.documents?.length ?? 0);
      })
      .catch(() => {
        if (mounted) setDocumentCount(0);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const kpis = useMemo(() => computeDashboardKpis(realPipelines), [realPipelines]);

  // Dashboard defaults to the 5 most recently touched pipelines so a fleet of
  // 20+ pipelines doesn't push the rest of the page off-screen -- the filter
  // dropdown lets the user expand to 10 or all without leaving the page.
  // Real `updated_at` sort, no fabrication, just a display-count cap.
  const sortedPipelines = useMemo(
    () => [...realPipelines].sort((a, b) => b.updated_at.localeCompare(a.updated_at)),
    [realPipelines],
  );
  const recentPipelines = useMemo(
    () => (pipelineFilter === "all" ? sortedPipelines : sortedPipelines.slice(0, Number(pipelineFilter))),
    [sortedPipelines, pipelineFilter],
  );

  // Unified Score trend for the most-recently-active pipeline. No fleet-wide
  // history endpoint exists (apiClient.getEvaluationHistory is per-pipeline),
  // so this mirrors EvaluationDashboard.tsx's exact real-data fetch/transform
  // rather than aggregating or fabricating a fleet-wide series.
  const [scoreHistory, setScoreHistory] = useState<EvalHistoryEntry[]>([]);
  const trendPipelineId = sortedPipelines[0]?.id ?? null;
  useEffect(() => {
    if (!trendPipelineId) {
      setScoreHistory([]);
      return;
    }
    let mounted = true;
    apiClient
      .getEvaluationHistory(trendPipelineId)
      .then((res) => {
        if (!mounted) return;
        const items = [...res.items].reverse();
        setScoreHistory(
          items
            .filter((i) => i.unified_score !== null && i.faithfulness !== null)
            .map((i, idx) => ({
              label: `Run ${idx + 1}`,
              unified_score: i.unified_score as number,
              faithfulness: i.faithfulness as number,
            })),
        );
      })
      .catch(() => setScoreHistory([]));
    return () => {
      mounted = false;
    };
  }, [trendPipelineId]);

  // Most recent evaluation timestamp across all pipelines -- real data for
  // the hero's "Last Evaluation" chip, never fabricated.
  const lastEvalAt = useMemo(() => {
    const timestamps = realPipelines
      .map((p) => p.latest_run?.finished_at)
      .filter((t): t is string => Boolean(t));
    return timestamps.length > 0 ? timestamps.sort().at(-1)! : null;
  }, [realPipelines]);

  const progress: JourneyProgress = useMemo(
    () => ({
      hasPipeline: realPipelines.length > 0,
      hasDocuments: (documentCount ?? 0) > 0,
      // Requires a real, non-null score -- not just a run record's existence.
      // A `latest_run` can be non-null while still `running`, or `failed`/
      // `blocked` before ever reaching the Evaluator (both leave
      // `unified_score: null`, types/index.ts:97-101). Matching the KPI
      // row's own truth condition here (lib/kpi.ts) prevents this step from
      // showing "complete" while Avg Unified Score reads "--" (13-Jul-2026 fix).
      hasEvaluation: realPipelines.some((p) => p.latest_run !== null && p.latest_run.unified_score !== null),
      hasBlockedEvaluation: realPipelines.some(
        (p) =>
          p.latest_run !== null &&
          p.latest_run.unified_score === null &&
          (p.latest_run.status === "failed" || p.latest_run.status === "blocked"),
      ),
      hasDeployment: realPipelines.some(
        (p) =>
          p.status === "ready" &&
          p.latest_run !== null &&
          p.latest_run.unified_score !== null &&
          p.latest_run.unified_score >= DEPLOY_GATE,
      ),
    }),
    [realPipelines, documentCount],
  );

  return (
    // Design 2 is now the app-wide standard (14-Jul-2026) -- the shared
    // AppShell .page-bg already carries the darker canvas, no per-page
    // override needed anymore.
    <div className="flex flex-col gap-8">
      <WelcomeHero
        progress={progress}
        lastEvalAt={lastEvalAt}
        pipelineCount={isLoading ? null : realPipelines.length}
        documentCount={documentCount}
      />

      {/* Guided journey */}
      <section>
        <div className="mb-3 flex items-baseline justify-between">
          <h2 className="text-lg font-extrabold tracking-tight text-stone-900">Your journey</h2>
          <span className="text-xs font-medium text-stone-500">4 steps from document to deployed pipeline</span>
        </div>
        <JourneySteps progress={progress} />
      </section>

      {/* Live vitals + trend */}
      <section>
        <div className="mb-3 flex items-baseline justify-between">
          <h2 className="text-lg font-extrabold tracking-tight text-stone-900">Platform vitals</h2>
          <Link href="/observe" className="text-xs font-bold text-orange-600 hover:text-orange-700">
            Full observability →
          </Link>
        </div>
        <KpiRow kpis={kpis} isLoading={isLoading} />
        <div className="mt-4 rounded-3xl border border-stone-200/90 bg-white px-6 py-5 shadow-[0_2px_12px_rgba(0,0,0,0.03)]">
          <div className="mb-4 flex items-center justify-between border-b border-stone-100 pb-3">
            <div className="flex items-center gap-2">
              <span className="rounded-xl border border-amber-200/80 bg-amber-50 p-2 text-amber-600">
                <TrendingUp className="h-4 w-4" aria-hidden="true" />
              </span>
              <div>
                <h3 className="text-sm font-bold text-stone-900">Unified Score Trend</h3>
                <p className="text-[11px] font-medium text-stone-500">
                  {sortedPipelines[0]
                    ? `Most recently active pipeline: ${sortedPipelines[0].name || sortedPipelines[0].id.slice(0, 8)}`
                    : "No pipelines yet"}
                </p>
              </div>
            </div>
            {sortedPipelines[0] && (
              <Link href="/evaluation" className="text-xs font-bold text-orange-600 hover:text-orange-700">
                Full evaluation history →
              </Link>
            )}
          </div>
          <EvalHistoryChart history={scoreHistory} />
        </div>
      </section>

      {/* Needs attention — approvals waiting + real threshold-breach alerts */}
      <section>
        <div className="mb-3 flex items-baseline justify-between">
          <h2 className="text-lg font-extrabold tracking-tight text-stone-900">Needs attention</h2>
        </div>
        <div className="flex flex-col gap-3">
          <HITLApprovalQueue pipelines={realPipelines} onActionComplete={refetch} />
          <NeedsAttention pipelines={realPipelines} isLoading={isLoading} />
        </div>
      </section>

      {/* Pipelines */}
      <section className="rounded-3xl border border-stone-200/90 bg-white px-6 py-5 shadow-[0_2px_12px_rgba(0,0,0,0.03)]">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-extrabold tracking-tight text-stone-900">
              {pipelineFilter === "all" ? "All Pipelines" : "Recent Pipelines"}
            </h2>
            <p className="mt-0.5 text-xs font-medium text-stone-500">
              {pipelineFilter === "all"
                ? "Every pipeline with its latest evaluation score"
                : `Showing ${recentPipelines.length} of ${realPipelines.length}, most recently updated first`}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <label htmlFor="pipeline-filter" className="sr-only">
              Number of pipelines to show
            </label>
            <select
              id="pipeline-filter"
              value={pipelineFilter}
              onChange={(e) => setPipelineFilter(e.target.value as "5" | "10" | "all")}
              className="rounded-xl border border-stone-200 bg-white px-2.5 py-1.5 text-xs font-bold text-stone-900 shadow-2xs outline-none focus:border-amber-500"
            >
              <option value="5">Recent 5</option>
              <option value="10">Recent 10</option>
              <option value="all">All ({realPipelines.length})</option>
            </select>
            <Link href="/pipelines" className="text-xs font-bold text-orange-600 hover:text-orange-700">
              Full history →
            </Link>
          </div>
        </div>
        <PipelineTable pipelines={recentPipelines} isLoading={isLoading} error={error} onRetry={refetch} />
      </section>

      {/* Deep-dive shortcuts */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {(
          [
            { label: "Observer",       href: "/observe",     desc: "Latency, cost, and SLO trend monitoring", icon: Activity, accent: "border-t-orange-500", chip: "bg-orange-100 text-orange-600" },
            { label: "Knowledge Base", href: "/knowledge",   desc: "Search and browse your indexed corpus",   icon: BookOpen, accent: "border-t-indigo-500", chip: "bg-indigo-100 text-indigo-600" },
            { label: "Experiments",    href: "/experiments", desc: "Compare evaluation runs side by side",    icon: FlaskConical, accent: "border-t-emerald-500", chip: "bg-emerald-100 text-emerald-600" },
            { label: "System Health",  href: "/health",      desc: "Live service and dependency status",      icon: HeartPulse, accent: "border-t-amber-500", chip: "bg-amber-100 text-amber-700" },
          ] satisfies Array<{ label: string; href: string; desc: string; icon: LucideIcon; accent: string; chip: string }>
        ).map((s) => (
          <Link
            key={s.href}
            href={s.href}
            className={`group flex flex-col justify-between gap-3 rounded-2xl border-t-2 ${s.accent} border-x border-b border-stone-200/90 bg-white px-4 py-4 shadow-[0_2px_8px_rgba(0,0,0,0.02)] transition-all hover:shadow-md`}
          >
            <div>
              <span className={`mb-3 flex h-10 w-10 items-center justify-center rounded-xl ${s.chip}`}>
                <s.icon className="h-5 w-5" aria-hidden="true" />
              </span>
              <div className="text-base font-bold text-stone-900">{s.label}</div>
              <div className="mt-0.5 text-xs font-medium leading-relaxed text-stone-500">{s.desc}</div>
            </div>
            <span className="mt-auto inline-flex w-full items-center justify-center gap-1.5 rounded-xl border border-stone-200 bg-stone-100 px-3 py-2 text-xs font-extrabold text-stone-800 transition-colors group-hover:bg-stone-200">
              Open
              <ArrowRight className="h-3.5 w-3.5 transition-transform motion-safe:duration-150 group-hover:translate-x-0.5" aria-hidden="true" />
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}
