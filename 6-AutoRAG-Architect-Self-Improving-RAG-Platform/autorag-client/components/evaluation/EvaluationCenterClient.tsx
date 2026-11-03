"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  type Gauge,
  LayoutDashboard,
  PlayCircle,
  ListChecks,
  Activity,
  Table2,
  AlertTriangle,
  GitCompare,
  Settings2,
} from "lucide-react";

import { apiClient } from "@/services/api-client";
import type {
  BatchRun,
  BatchRunSummary,
  BatchEvaluation,
  EvaluationConfig,
  EvaluationDataset,
  EvaluationDatasetVersion,
  Pipeline,
  PipelineVersionSummary,
} from "@/types";

import Link from "next/link";

import { SectionCard } from "@/components/ui/section-card";
import { StatCard } from "@/components/ui/stat-card";
import { EvaluationDashboard } from "@/components/evaluation/EvaluationDashboard";
import { EvaluationKpiStrip } from "@/components/evaluation/EvaluationKpiStrip";
import { ResultDetailDrawer } from "@/components/evaluation/golden/ResultDetailDrawer";
import { VersionHistoryTable } from "@/components/optimizer/VersionHistoryTable";
import {
  METRIC_INFO,
  buildConclusion,
  deriveInsights,
  deriveRecommendations,
  formatScorePercent,
  scoreBandLabel,
  scoreColorClasses,
  type RagasMetricKey,
} from "@/lib/score";

type CenterTab =
  | "overview"
  | "run"
  | "batch"
  | "live"
  | "results"
  | "failed"
  | "compare"
  | "settings";

const TABS: { key: CenterTab; label: string; icon: typeof Gauge }[] = [
  { key: "overview", label: "Overview", icon: LayoutDashboard },
  { key: "run", label: "Run Evaluation", icon: PlayCircle },
  { key: "batch", label: "Batch Runs", icon: ListChecks },
  { key: "live", label: "Live Monitor", icon: Activity },
  { key: "results", label: "Results", icon: Table2 },
  { key: "failed", label: "Failed Questions", icon: AlertTriangle },
  { key: "compare", label: "Compare Runs", icon: GitCompare },
  { key: "settings", label: "Settings", icon: Settings2 },
];

/** Evaluation Center (Phase 2d, 24-Jul-2026) -- extends the existing
 * single-question Evaluation Dashboard with golden-dataset batch evaluation.
 * No new top-level route: this replaces EvaluationDashboard as /evaluation's
 * root client component, and "Run Evaluation" preserves the original
 * single-question dashboard verbatim as one tab among several. */
const TAB_KEYS = TABS.map((t) => t.key);

export function EvaluationCenterClient() {
  // Deep-link support: /evaluate?tab=run redirects here so the "Evaluate"
  // nav item actually opens the single-question flow instead of always
  // landing on Overview (25-Jul-2026 fix, per user report -- "Evaluate"
  // is meaningless if it never opens the Run Evaluation tab).
  const searchParams = useSearchParams();
  const initialTab = searchParams.get("tab");
  const [tab, setTab] = useState<CenterTab>(
    initialTab && (TAB_KEYS as string[]).includes(initialTab) ? (initialTab as CenterTab) : "overview",
  );
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [pipelineId, setPipelineId] = useState<string>("");

  useEffect(() => {
    apiClient
      .listPipelines()
      .then((items) => {
        setPipelines(items);
        setPipelineId((prev) => prev || items[0]?.id || "");
      })
      .catch(() => setPipelines([]));
  }, []);

  return (
    <div className="space-y-6">
      {/* Title/description now come from the shared page hero (AppShell) --
          keep just the pipeline selector here (26-Jul-2026). */}
      {pipelines.length > 0 && (
        <div className="flex justify-end">
          <select
            value={pipelineId}
            onChange={(e) => setPipelineId(e.target.value)}
            aria-label="Pipeline"
            className="rounded-lg border border-border bg-card px-3 py-2 text-xs text-foreground"
          >
            {pipelines.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
      )}

      {pipelineId && <EvaluationKpiStrip pipelineId={pipelineId} />}

      <div className="flex flex-wrap gap-1 border-b border-border text-xs">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex items-center gap-1.5 border-b-[3px] px-3 py-2 transition-colors motion-safe:duration-150 ${
              tab === key ? "border-accent font-bold text-foreground" : "border-transparent font-medium text-text-3 hover:text-foreground"
            }`}
          >
            <Icon className="h-3.5 w-3.5" aria-hidden="true" />
            {label}
          </button>
        ))}
      </div>

      {tab === "overview" && <OverviewTab pipelineId={pipelineId} />}
      {tab === "run" && <EvaluationDashboard />}
      {tab === "batch" && <BatchRunsTab pipelineId={pipelineId} />}
      {tab === "live" && <LiveMonitorTab pipelineId={pipelineId} />}
      {tab === "results" && <ResultsTab pipelineId={pipelineId} />}
      {tab === "failed" && <FailedQuestionsTab pipelineId={pipelineId} />}
      {tab === "compare" && <CompareRunsTab pipelineId={pipelineId} />}
      {tab === "settings" && <SettingsTab pipelineId={pipelineId} />}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Overview
// ─────────────────────────────────────────────────────────────────────────

function OverviewTab({ pipelineId }: { pipelineId: string }) {
  const [runs, setRuns] = useState<BatchRun[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!pipelineId) return;
    setLoading(true);
    apiClient
      .listBatchRuns({ pipelineId, status: undefined })
      .then(setRuns)
      .catch(() => setRuns([]))
      .finally(() => setLoading(false));
  }, [pipelineId]);

  const active = runs.filter((r) => r.status === "queued" || r.status === "running");
  const recent = runs.slice(0, 5);

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <SectionCard title="Queue Status" description="Batch runs currently queued or in progress">
        {loading && <div className="h-16 motion-safe:animate-pulse rounded-lg bg-accent/5" aria-hidden="true" />}
        {!loading && active.length === 0 && (
          <p className="text-xs text-text-3">No active batch runs.</p>
        )}
        {active.map((r) => (
          <div key={r.id} className="flex items-center justify-between border-b border-border py-2 text-xs last:border-0">
            <span className="font-mono text-text-2">{r.id.slice(0, 8)}</span>
            <StatusBadge status={r.status} />
          </div>
        ))}
      </SectionCard>

      <SectionCard title="Recent Batch Runs" description="Most recent runs for this pipeline">
        {!loading && recent.length === 0 && (
          <p className="text-xs text-text-3">No batch runs yet — start one from the Batch Runs tab.</p>
        )}
        {recent.map((r) => (
          <div key={r.id} className="flex items-center justify-between border-b border-border py-2 text-xs last:border-0">
            <span className="font-mono text-text-2">{r.id.slice(0, 8)}</span>
            <span className="text-text-3">
              {r.created_at ? new Date(r.created_at).toLocaleString() : ""}
            </span>
            <StatusBadge status={r.status} />
          </div>
        ))}
      </SectionCard>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    queued: "border-slate-400/30 bg-slate-400/10 text-text-2",
    running: "border-amber-400/30 bg-amber-400/10 text-amber-400",
    completed: "border-emerald-400/30 bg-emerald-400/10 text-emerald-400",
    cancelled: "border-slate-400/30 bg-slate-400/10 text-text-3",
    failed: "border-rose-400/30 bg-rose-400/10 text-rose-400",
  };
  return (
    <span className={`rounded-full border px-2 py-0.5 font-semibold ${styles[status] ?? styles.queued}`}>
      {status}
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Batch Runs
// ─────────────────────────────────────────────────────────────────────────

function BatchRunsTab({ pipelineId }: { pipelineId: string }) {
  const [datasets, setDatasets] = useState<EvaluationDataset[]>([]);
  const [datasetId, setDatasetId] = useState("");
  const [versions, setVersions] = useState<EvaluationDatasetVersion[]>([]);
  const [versionId, setVersionId] = useState("");
  const [configs, setConfigs] = useState<EvaluationConfig[]>([]);
  const [configId, setConfigId] = useState("");
  const [runs, setRuns] = useState<BatchRun[]>([]);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [datasetsLoaded, setDatasetsLoaded] = useState(false);

  useEffect(() => {
    apiClient
      .listDatasets()
      .then(setDatasets)
      .catch(() => setDatasets([]))
      .finally(() => setDatasetsLoaded(true));
  }, []);

  useEffect(() => {
    if (!datasetId) return;
    apiClient.listDatasetVersions(datasetId).then(setVersions).catch(() => setVersions([]));
  }, [datasetId]);

  useEffect(() => {
    if (!pipelineId) return;
    apiClient.listEvaluationConfigs(pipelineId).then(setConfigs).catch(() => setConfigs([]));
  }, [pipelineId]);

  const refreshRuns = useCallback(() => {
    if (!pipelineId) return;
    apiClient.listBatchRuns({ pipelineId }).then(setRuns).catch(() => setRuns([]));
  }, [pipelineId]);

  useEffect(() => {
    refreshRuns();
  }, [refreshRuns]);

  const publishedVersions = versions.filter((v) => v.lifecycle_status === "published");

  const handleStart = async () => {
    if (!pipelineId || !versionId) return;
    setStarting(true);
    setError(null);
    try {
      await apiClient.startBatchRun({
        dataset_version_id: versionId,
        pipeline_id: pipelineId,
        config_id: configId || undefined,
      });
      refreshRuns();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start batch run");
    } finally {
      setStarting(false);
    }
  };

  const handleCancel = async (id: string) => {
    try {
      await apiClient.cancelBatchRun(id);
      refreshRuns();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to cancel batch run");
    }
  };

  const handleResume = async (id: string) => {
    try {
      await apiClient.resumeBatchRun(id);
      refreshRuns();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to resume batch run");
    }
  };

  return (
    <div className="space-y-4">
      <SectionCard title="Start a Batch Run" description="Run every approved golden question in a published dataset version against the selected pipeline">
        {error && (
          <div role="alert" className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-xs text-rose-700">
            {error}
          </div>
        )}
        {datasetsLoaded && datasets.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border bg-card px-4 py-6 text-center">
            <p className="text-xs font-semibold text-foreground">No Evaluation Datasets found.</p>
            <p className="mx-auto mt-1 max-w-sm text-xs leading-relaxed text-text-3">
              Batch Evaluation runs a pipeline against every question in a published Golden
              Dataset — create one or import questions from a CSV/JSON/JSONL file to get started.
            </p>
            <div className="mt-3 flex justify-center gap-2">
              <Link
                href="/datasets"
                className="rounded-lg bg-amber-500 px-4 py-2 text-xs font-semibold text-white transition-colors motion-safe:duration-200 hover:bg-amber-600"
              >
                Create Dataset
              </Link>
              <Link
                href="/datasets"
                className="rounded-lg border border-border bg-card px-4 py-2 text-xs font-semibold text-foreground transition-colors motion-safe:duration-200 hover:bg-surface-subtle"
              >
                Import Dataset
              </Link>
            </div>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <select
                value={datasetId}
                onChange={(e) => {
                  setDatasetId(e.target.value);
                  setVersionId("");
                }}
                aria-label="Dataset"
                className="rounded-lg border border-border bg-card px-3 py-2 text-xs text-foreground"
              >
                <option value="">Select dataset…</option>
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
              <select
                value={versionId}
                onChange={(e) => setVersionId(e.target.value)}
                aria-label="Dataset version"
                disabled={!datasetId}
                className="rounded-lg border border-border bg-card px-3 py-2 text-xs text-foreground disabled:opacity-50"
              >
                <option value="">Select published version…</option>
                {publishedVersions.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.version_label}
                  </option>
                ))}
              </select>
              <select
                value={configId}
                onChange={(e) => setConfigId(e.target.value)}
                aria-label="Evaluation config (optional)"
                className="rounded-lg border border-border bg-card px-3 py-2 text-xs text-foreground"
              >
                <option value="">Default config</option>
                {configs.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
            {datasetId && publishedVersions.length === 0 && (
              <div className="mt-2 flex flex-wrap items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                <span>
                  This dataset has no published version. Publish a version before running Batch
                  Evaluation.
                </span>
                <Link href="/datasets" className="font-semibold underline underline-offset-2 hover:text-amber-800">
                  Go to Dataset
                </Link>
              </div>
            )}
            <button
              type="button"
              onClick={handleStart}
              disabled={starting || !versionId}
              className="mt-3 flex items-center gap-2 rounded-lg border border-amber-400/40 bg-amber-500/15 px-4 py-2 text-xs font-semibold text-amber-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {starting ? "Starting…" : "Start Batch Run"}
            </button>
          </>
        )}
      </SectionCard>

      <SectionCard title="Batch Run Queue" description="All batch runs for this pipeline">
        {runs.length === 0 && <p className="text-xs text-text-3">No batch runs yet.</p>}
        <div className="space-y-2">
          {runs.map((r) => (
            <div key={r.id} className="flex items-center justify-between rounded-lg border border-border bg-card px-3 py-2 text-xs">
              <span className="font-mono text-text-2">{r.id.slice(0, 8)}</span>
              <StatusBadge status={r.status} />
              <span className="text-text-3">
                {r.created_at ? new Date(r.created_at).toLocaleString() : ""}
              </span>
              <div className="flex gap-3">
                {(r.status === "queued" || r.status === "running") && (
                  <button onClick={() => handleCancel(r.id)} className="font-semibold text-rose-400 hover:underline">
                    Cancel
                  </button>
                )}
                {r.status === "failed" && (
                  <button onClick={() => handleResume(r.id)} className="font-semibold text-amber-700 hover:underline">
                    Resume
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </SectionCard>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Live Monitor
// ─────────────────────────────────────────────────────────────────────────

function LiveMonitorTab({ pipelineId }: { pipelineId: string }) {
  const [runs, setRuns] = useState<BatchRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [results, setResults] = useState<BatchEvaluation[]>([]);

  useEffect(() => {
    if (!pipelineId) return;
    apiClient
      .listBatchRuns({ pipelineId, status: "running" })
      .then((items) => {
        setRuns(items);
        setSelectedRunId((prev) => prev || items[0]?.id || "");
      })
      .catch(() => setRuns([]));
  }, [pipelineId]);

  useEffect(() => {
    if (!selectedRunId) return;
    const poll = () => apiClient.listBatchRunResults(selectedRunId).then(setResults).catch(() => {});
    poll();
    const interval = setInterval(poll, 4000);
    return () => clearInterval(interval);
  }, [selectedRunId]);

  return (
    <SectionCard
      title="Live Monitor"
      description="Poll a running batch run's per-question progress"
      actions={
        <select
          value={selectedRunId}
          onChange={(e) => setSelectedRunId(e.target.value)}
          aria-label="Running batch run"
          className="rounded-lg border border-border bg-card px-3 py-1.5 text-xs text-foreground"
        >
          <option value="">Select a running batch run…</option>
          {runs.map((r) => (
            <option key={r.id} value={r.id}>
              {r.id.slice(0, 8)}
            </option>
          ))}
        </select>
      }
    >
      {!selectedRunId && <p className="text-xs text-text-3">No batch run currently running for this pipeline.</p>}
      <div className="space-y-1">
        {results.map((r) => (
          <div key={r.id} className="flex items-center justify-between border-b border-border py-1.5 text-xs last:border-0">
            <span className="font-mono text-text-3">{r.golden_question_id.slice(0, 8)}</span>
            <StatusBadge status={r.status} />
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Results
// ─────────────────────────────────────────────────────────────────────────

function ResultsTab({ pipelineId }: { pipelineId: string }) {
  const [runs, setRuns] = useState<BatchRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [summary, setSummary] = useState<BatchRunSummary | null>(null);
  const [results, setResults] = useState<BatchEvaluation[]>([]);
  const [drawerId, setDrawerId] = useState<string | null>(null);
  const [rerunning, setRerunning] = useState(false);
  const [showLowScoringOnly, setShowLowScoringOnly] = useState(false);

  useEffect(() => {
    if (!pipelineId) return;
    apiClient
      .listBatchRuns({ pipelineId, status: "completed" })
      .then((items) => {
        setRuns(items);
        setSelectedRunId((prev) => prev || items[0]?.id || "");
      })
      .catch(() => setRuns([]));
  }, [pipelineId]);

  useEffect(() => {
    if (!selectedRunId) return;
    apiClient.getBatchRun(selectedRunId).then(setSummary).catch(() => setSummary(null));
    apiClient.listBatchRunResults(selectedRunId).then(setResults).catch(() => setResults([]));
  }, [selectedRunId]);

  const selectedRun = runs.find((r) => r.id === selectedRunId) ?? summary?.batch_run ?? null;
  const metricAverages = summary?.summary.metric_averages;
  const insights = metricAverages ? deriveInsights(metricAverages) : { strengths: [], weaknesses: [] };
  const recommendations = metricAverages ? deriveRecommendations(metricAverages) : [];
  const conclusion = buildConclusion(summary?.summary.average_unified_score ?? null, insights);

  const durationLabel = (() => {
    if (!selectedRun?.started_at || !selectedRun?.completed_at) return "—";
    const ms = new Date(selectedRun.completed_at).getTime() - new Date(selectedRun.started_at).getTime();
    const minutes = Math.floor(ms / 60_000);
    const seconds = Math.round((ms % 60_000) / 1000);
    return `${minutes}m ${seconds}s`;
  })();

  const handleExport = async (format: "csv" | "json") => {
    if (!selectedRunId) return;
    const blob = await apiClient.exportBatchRun(selectedRunId, format);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `batch-run-${selectedRunId.slice(0, 8)}.${format}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleRunAgain = async () => {
    if (!selectedRun) return;
    setRerunning(true);
    try {
      const newRun = await apiClient.startBatchRun({
        dataset_version_id: selectedRun.dataset_version_id,
        pipeline_id: selectedRun.pipeline_id,
        config_id: selectedRun.config_id ?? undefined,
      });
      setRuns((prev) => [newRun, ...prev]);
      setSelectedRunId(newRun.id);
    } finally {
      setRerunning(false);
    }
  };

  const visibleResults = showLowScoringOnly
    ? results.filter((r) => r.unified_score !== null && r.unified_score < 0.7)
    : results;

  return (
    <div className="space-y-4">
      <SectionCard
        title="Results"
        description="Completed batch run results — click a row for detail"
        actions={
          <select
            value={selectedRunId}
            onChange={(e) => setSelectedRunId(e.target.value)}
            aria-label="Completed batch run"
            className="rounded-lg border border-border bg-card px-3 py-1.5 text-xs text-foreground"
          >
            <option value="">Select a completed batch run…</option>
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                {r.id.slice(0, 8)} — {r.created_at ? new Date(r.created_at).toLocaleDateString() : ""}
              </option>
            ))}
          </select>
        }
      >
        {!summary && <p className="text-xs text-text-3">Select a completed batch run above.</p>}

        {summary && (
          <div className="space-y-5">
            {/* 1. Evaluation Summary header */}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatCard label="Pipeline" value={selectedRun?.pipeline_id.slice(0, 8) ?? "—"} />
              <StatCard label="Questions" value={results.length} />
              <StatCard label="Duration" value={durationLabel} />
              <StatCard
                label="Overall Score"
                value={formatScorePercent(summary.summary.average_unified_score)}
                className={
                  summary.summary.average_unified_score !== null
                    ? scoreColorClasses(summary.summary.average_unified_score)
                    : undefined
                }
              />
            </div>
            {summary.summary.average_unified_score !== null && (
              <p className="text-xs font-semibold text-foreground">
                {scoreBandLabel(summary.summary.average_unified_score)}
              </p>
            )}

            {/* 2. Overall Metrics */}
            {metricAverages && (
              <div>
                <h3 className="eyebrow mb-2">Overall Metrics</h3>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
                  {(Object.keys(METRIC_INFO) as RagasMetricKey[]).map((key) => {
                    const value = metricAverages[key];
                    return (
                      <div
                        key={key}
                        title={METRIC_INFO[key].description}
                        className="rounded-lg border border-border bg-card px-3 py-2"
                      >
                        <div className="eyebrow mb-1">{METRIC_INFO[key].label}</div>
                        <div className="font-mono text-lg font-bold text-foreground">
                          {value !== null ? value.toFixed(2) : "—"}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* 3. Executive Insights */}
            {(insights.strengths.length > 0 || insights.weaknesses.length > 0) && (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs">
                  <div className="mb-1 font-semibold text-emerald-700">Strengths</div>
                  {insights.strengths.length === 0 && <p className="text-emerald-700/70">None yet</p>}
                  {insights.strengths.map((s) => (
                    <p key={s} className="text-emerald-700">
                      ✓ {s}
                    </p>
                  ))}
                </div>
                <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs">
                  <div className="mb-1 font-semibold text-amber-700">Weaknesses</div>
                  {insights.weaknesses.length === 0 && <p className="text-amber-700/70">None found</p>}
                  {insights.weaknesses.map((w) => (
                    <p key={w} className="text-amber-700">
                      ⚠ {w}
                    </p>
                  ))}
                </div>
              </div>
            )}

            {/* 4. Per Question Analysis */}
            <div>
              <div className="mb-2 flex items-center justify-between">
                <h3 className="eyebrow">Per Question Analysis</h3>
                <label className="flex items-center gap-1.5 text-[11px] text-text-3">
                  <input
                    type="checkbox"
                    checked={showLowScoringOnly}
                    onChange={(e) => setShowLowScoringOnly(e.target.checked)}
                  />
                  Low-scoring only (&lt; 0.70)
                </label>
              </div>
              {visibleResults.length === 0 && (
                <p className="text-xs text-text-3">No results match this filter.</p>
              )}
              <div className="space-y-1">
                {visibleResults.map((r) => (
                  <button
                    key={r.id}
                    onClick={() => setDrawerId(r.id)}
                    className="flex w-full items-center justify-between rounded-lg border border-border bg-card px-3 py-2 text-left text-xs hover:bg-accent/5"
                  >
                    <span className="font-mono text-text-3">{r.golden_question_id.slice(0, 8)}</span>
                    <StatusBadge status={r.status} />
                    {r.status === "failed" && r.error_message ? (
                      <span className="max-w-xs truncate text-rose-600">{r.error_message}</span>
                    ) : (
                      <span className="font-mono text-foreground">
                        {r.unified_score !== null ? r.unified_score.toFixed(3) : "—"}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            </div>

            {/* 5. Recommendations */}
            {recommendations.length > 0 && (
              <div>
                <h3 className="eyebrow mb-2">Recommendations</h3>
                <ul className="space-y-1 text-xs text-text-2">
                  {recommendations.map((r) => (
                    <li key={r}>• {r}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* 6. Evaluation Conclusion */}
            <div className="rounded-lg border border-border bg-accent/5 px-3 py-2 text-xs text-text-2">
              {conclusion}
            </div>

            {/* 7. Next Steps / Quick Actions */}
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setShowLowScoringOnly(true)}
                className="rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-semibold text-text-2 hover:bg-accent/5"
              >
                Review Low-Scoring Questions
              </button>
              <button
                type="button"
                onClick={() => void handleExport("csv")}
                className="rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-semibold text-text-2 hover:bg-accent/5"
              >
                Export CSV
              </button>
              <button
                type="button"
                onClick={() => void handleExport("json")}
                className="rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-semibold text-text-2 hover:bg-accent/5"
              >
                Export JSON
              </button>
              <button
                type="button"
                onClick={() => void handleRunAgain()}
                disabled={rerunning}
                className="rounded-lg border border-amber-400/40 bg-amber-500/15 px-3 py-1.5 text-xs font-semibold text-amber-700 disabled:opacity-50"
              >
                {rerunning ? "Starting…" : "Run Again"}
              </button>
              <Link
                href="/experiments"
                className="rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-semibold text-text-2 hover:bg-accent/5"
              >
                Compare Pipeline Versions
              </Link>
              <Link
                href="/deploy"
                className="rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-semibold text-text-2 hover:bg-accent/5"
              >
                Deploy Pipeline
              </Link>
            </div>
          </div>
        )}
      </SectionCard>

      <ResultDetailDrawer batchEvaluationId={drawerId} onClose={() => setDrawerId(null)} />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Failed Questions
// ─────────────────────────────────────────────────────────────────────────

function FailedQuestionsTab({ pipelineId }: { pipelineId: string }) {
  const [runs, setRuns] = useState<BatchRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [summary, setSummary] = useState<BatchRunSummary | null>(null);
  const [drawerId, setDrawerId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!pipelineId) return;
    apiClient
      .listBatchRuns({ pipelineId, status: "completed" })
      .then((items) => {
        setRuns(items);
        setSelectedRunId((prev) => prev || items[0]?.id || "");
      })
      .catch(() => setRuns([]));
  }, [pipelineId]);

  useEffect(() => {
    if (!selectedRunId) return;
    apiClient.getBatchRun(selectedRunId).then(setSummary).catch(() => setSummary(null));
  }, [selectedRunId]);

  const handleReview = async (id: string, reviewStatus: "approved" | "rejected") => {
    try {
      await apiClient.reviewBatchResult(id, { review_status: reviewStatus });
      const s = await apiClient.getBatchRun(selectedRunId);
      setSummary(s);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to review result");
    }
  };

  return (
    <SectionCard
      title="Failed Questions"
      description="Worst-scoring questions from a completed batch run, with a human-review workflow"
      actions={
        <select
          value={selectedRunId}
          onChange={(e) => setSelectedRunId(e.target.value)}
          aria-label="Completed batch run"
          className="rounded-lg border border-border bg-card px-3 py-1.5 text-xs text-foreground"
        >
          <option value="">Select a completed batch run…</option>
          {runs.map((r) => (
            <option key={r.id} value={r.id}>
              {r.id.slice(0, 8)}
            </option>
          ))}
        </select>
      }
    >
      {error && (
        <div role="alert" className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-xs text-rose-700">
          {error}
        </div>
      )}
      {summary && summary.worst_scoring.length === 0 && (
        <p className="text-xs text-text-3">No low-scoring questions in this run.</p>
      )}
      <div className="space-y-2">
        {summary?.worst_scoring.map((r) => (
          <div key={r.id} className="rounded-lg border border-rose-400/20 bg-rose-500/5 px-3 py-2 text-xs">
            <div className="flex items-center justify-between">
              <button onClick={() => setDrawerId(r.id)} className="font-mono text-text-2 hover:underline">
                {r.golden_question_id.slice(0, 8)}
              </button>
              <span className="font-mono font-bold text-rose-400">
                {r.unified_score !== null ? r.unified_score.toFixed(3) : "—"}
              </span>
            </div>
            {r.review_status === "unreviewed" && (
              <div className="mt-2 flex gap-3">
                <button onClick={() => handleReview(r.id, "approved")} className="font-semibold text-emerald-500 hover:underline">
                  Approve
                </button>
                <button onClick={() => handleReview(r.id, "rejected")} className="font-semibold text-rose-500 hover:underline">
                  Reject
                </button>
              </div>
            )}
            {r.review_status !== "unreviewed" && (
              <span className="mt-1 inline-block text-text-3">reviewed: {r.review_status}</span>
            )}
          </div>
        ))}
      </div>

      <ResultDetailDrawer batchEvaluationId={drawerId} onClose={() => setDrawerId(null)} />
    </SectionCard>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Compare Runs — reuses VersionHistoryTable, not duplicated
// ─────────────────────────────────────────────────────────────────────────

function CompareRunsTab({ pipelineId }: { pipelineId: string }) {
  const [versions, setVersions] = useState<PipelineVersionSummary[]>([]);
  const [currentVersion, setCurrentVersion] = useState(1);

  useEffect(() => {
    if (!pipelineId) return;
    apiClient
      .listPipelineVersions(pipelineId)
      .then((res) => setVersions(res.versions))
      .catch(() => setVersions([]));
    apiClient
      .getPipeline(pipelineId)
      .then((detail) => setCurrentVersion(detail.pipeline.current_version ?? 1))
      .catch(() => {});
  }, [pipelineId]);

  return (
    <SectionCard title="Compare Runs" description="Version history for the selected pipeline — same table as the Evolution page">
      <VersionHistoryTable pipelineId={pipelineId} versions={versions} currentVersion={currentVersion} />
    </SectionCard>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Settings — EvaluationConfig CRUD
// ─────────────────────────────────────────────────────────────────────────

function SettingsTab({ pipelineId }: { pipelineId: string }) {
  const [configs, setConfigs] = useState<EvaluationConfig[]>([]);
  const [name, setName] = useState("");
  const [topK, setTopK] = useState("");
  const [chunkSize, setChunkSize] = useState("");
  const [creating, setCreating] = useState(false);

  const refresh = useCallback(() => {
    apiClient.listEvaluationConfigs(pipelineId || undefined).then(setConfigs).catch(() => setConfigs([]));
  }, [pipelineId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleCreate = async () => {
    if (!name.trim()) return;
    setCreating(true);
    try {
      await apiClient.createEvaluationConfig({
        name: name.trim(),
        pipeline_id: pipelineId || undefined,
        top_k: topK ? Number(topK) : undefined,
        chunk_size: chunkSize ? Number(chunkSize) : undefined,
      });
      setName("");
      setTopK("");
      setChunkSize("");
      refresh();
    } finally {
      setCreating(false);
    }
  };

  return (
    <SectionCard title="Evaluation Configs" description="Persisted, reusable batch-run configuration — a new row is created rather than editing in place, so past runs stay reproducible">
      <div className="mb-4 grid grid-cols-1 gap-2 sm:grid-cols-4">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Config name"
          className="rounded-lg border border-border bg-card px-3 py-2 text-xs text-foreground placeholder-muted-foreground"
        />
        <input
          value={topK}
          onChange={(e) => setTopK(e.target.value)}
          placeholder="top_k"
          type="number"
          className="rounded-lg border border-border bg-card px-3 py-2 text-xs text-foreground placeholder-muted-foreground"
        />
        <input
          value={chunkSize}
          onChange={(e) => setChunkSize(e.target.value)}
          placeholder="chunk_size"
          type="number"
          className="rounded-lg border border-border bg-card px-3 py-2 text-xs text-foreground placeholder-muted-foreground"
        />
        <button
          type="button"
          onClick={handleCreate}
          disabled={creating || !name.trim()}
          className="rounded-lg border border-amber-400/40 bg-amber-500/15 px-3 py-2 text-xs font-semibold text-amber-700 disabled:opacity-50"
        >
          {creating ? "Saving…" : "Create Config"}
        </button>
      </div>

      {configs.length === 0 && <p className="text-xs text-text-3">No saved configs yet.</p>}
      <div className="space-y-1">
        {configs.map((c) => (
          <div key={c.id} className="flex items-center justify-between rounded-lg border border-border bg-card px-3 py-2 text-xs">
            <span className="text-foreground">{c.name}</span>
            <span className="text-text-3">
              top_k={c.top_k ?? "—"} · chunk_size={c.chunk_size ?? "—"}
            </span>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}
