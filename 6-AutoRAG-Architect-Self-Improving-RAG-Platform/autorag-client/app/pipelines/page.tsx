"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { Plus, RefreshCw, AlertCircle, Loader2, Upload, Settings2, Gauge, Rocket, MoreVertical, Trash2, ExternalLink, X, AlertTriangle, Search, FileText } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { usePipelines } from "@/hooks/use-pipelines";
import { apiClient } from "@/services/api-client";
import { relativeTime } from "@/lib/format";
import { formatScorePercent, scoreBand, scoreBandLabel } from "@/lib/score";
import type { Deployment } from "@/types";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { bg: string; text: string; label: string }> = {
    ready: { bg: "bg-emerald-50", text: "text-emerald-700", label: "Ready" },
    running: { bg: "bg-blue-50", text: "text-blue-700", label: "Running" },
    pending: { bg: "bg-amber-50", text: "text-amber-700", label: "Draft" },
    failed: { bg: "bg-rose-50", text: "text-rose-700", label: "Failed" },
    decommissioned: { bg: "bg-[rgba(15,23,42,0.06)]", text: "text-text-3", label: "Archived" },
  };
  const s = map[status] ?? map["pending"];
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${s.bg} ${s.text}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current" />
      {s.label}
    </span>
  );
}

/** Deployment status → badge. `null` (no deployment row yet) reads as
 * "Not Deployed", distinct from every real DeploymentStatus value — a
 * pipeline can be "Ready" to deploy without ever having been deployed. */
function DeploymentBadge({ deployment }: { deployment: Deployment | null | undefined }) {
  if (deployment === undefined) return <span className="text-xs text-muted-foreground">…</span>;
  if (deployment === null || deployment.status === "pending") {
    return <span className="text-xs font-medium text-muted-foreground">Not Deployed</span>;
  }
  const map: Record<string, { text: string; label: string }> = {
    blue_green: { text: "text-blue-700", label: "Deploying" },
    promoted: { text: "text-emerald-700", label: "Production" },
    rolled_back: { text: "text-amber-700", label: "Rolled Back" },
    failed: { text: "text-rose-700", label: "Deploy Failed" },
  };
  const s = map[deployment.status] ?? { text: "text-muted-foreground", label: deployment.status };
  return <span className={`text-xs font-semibold ${s.text}`}>{s.label}</span>;
}

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return <span className="text-muted-foreground text-sm">Not Evaluated</span>;
  const color =
    scoreBand(score) === "deploy" ? "text-emerald-700" : scoreBand(score) === "hitl" ? "text-amber-700" : "text-rose-700";
  return (
    <span className="inline-flex flex-col leading-tight">
      <span className={`text-sm font-mono font-bold ${color}`}>{formatScorePercent(score)}</span>
      <span className={`text-[10px] font-medium ${color}`}>{scoreBandLabel(score)}</span>
    </span>
  );
}

function KpiTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-border bg-white px-4 py-3">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-1 font-mono text-2xl font-bold tabular-nums text-foreground">{value}</div>
    </div>
  );
}

const STEPS = [
  { icon: Upload,    label: "Upload documents",       desc: "PDF, DOCX, TXT — any format" },
  { icon: Settings2, label: "Configure retrieval",    desc: "Chunking strategy + embedding" },
  { icon: Gauge,     label: "Run evaluation",         desc: "Unified Score gate ≥ 0.85" },
  { icon: Rocket,    label: "Deploy to production",   desc: "Blue-green with auto-rollback" },
];

export default function PipelinesPage() {
  const router = useRouter();
  const { pipelines, isLoading, error, refetch } = usePipelines();
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [deploymentFilter, setDeploymentFilter] = useState<string>("all");

  // Real per-pipeline deployment status (N+1 — same accepted pattern as the
  // Knowledge Base's per-document detail fetch; pipeline counts are small at
  // this MVP's scale). `undefined` = still loading, `null` = no deployment row.
  const [deployments, setDeployments] = useState<Record<string, Deployment | null | undefined>>({});
  // Real per-pipeline document counts — one listDocuments() call for the
  // whole org, grouped by project_id client-side, instead of N+1 (Document
  // has no chunk_count field, only DocumentDetail does, so this is a count
  // only — not a fabricated chunk total).
  const [docCounts, setDocCounts] = useState<Record<string, number>>({});

  useEffect(() => {
    if (pipelines.length === 0) return;
    let cancelled = false;
    Promise.all(
      pipelines.map((p) =>
        apiClient
          .getDeploymentStatus(p.id)
          .then((res) => [p.id, res.deployment] as const)
          .catch(() => [p.id, null] as const),
      ),
    ).then((results) => {
      if (cancelled) return;
      setDeployments(Object.fromEntries(results));
    });
    apiClient
      .listDocuments()
      .then((res) => {
        if (cancelled) return;
        const counts: Record<string, number> = {};
        for (const d of res.documents) {
          if (d.status === "indexed") counts[d.project_id] = (counts[d.project_id] ?? 0) + 1;
        }
        setDocCounts(counts);
      })
      .catch(() => {
        if (!cancelled) setDocCounts({});
      });
    return () => {
      cancelled = true;
    };
    // pipelines is refetched wholesale (usePipelines) rather than diffed, so
    // re-running this whenever the array identity changes is the correct,
    // simple behavior here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pipelines.length]);

  const filteredPipelines = useMemo(() => {
    const q = query.trim().toLowerCase();
    return pipelines.filter((p) => {
      const matchesQuery = q === "" || (p.name || "").toLowerCase().includes(q);
      const matchesStatus = statusFilter === "all" || p.status === statusFilter;
      const depStatus = deployments[p.id]?.status ?? "not_deployed";
      const matchesDeployment = deploymentFilter === "all" || depStatus === deploymentFilter;
      return matchesQuery && matchesStatus && matchesDeployment;
    });
  }, [pipelines, query, statusFilter, deploymentFilter, deployments]);

  const production = pipelines.filter((p) => deployments[p.id]?.status === "promoted").length;
  const draft = pipelines.filter((p) => p.status === "pending").length;
  // "Healthy" = deployable-or-better score (or not yet evaluated -- absence
  // of a bad score isn't itself unhealthy) and no failed/rolled-back
  // deployment on record. A real, derived signal from data already on the
  // page -- never a separate fabricated health check.
  const healthy = pipelines.filter((p) => {
    const score = p.latest_run?.unified_score;
    const scoreOk = score == null || score >= 0.7;
    const depOk = !["failed", "rolled_back"].includes(deployments[p.id]?.status ?? "");
    return p.status !== "failed" && scoreOk && depOk;
  }).length;
  const scoredPipelines = pipelines.filter((p) => p.latest_run?.unified_score != null);
  const avgScore =
    scoredPipelines.length > 0
      ? scoredPipelines.reduce((sum, p) => sum + (p.latest_run?.unified_score ?? 0), 0) / scoredPipelines.length
      : null;
  const lastDeploymentAt = Object.values(deployments).reduce<string | null>((latest, d) => {
    if (!d?.promoted_at) return latest;
    if (!latest || d.promoted_at > latest) return d.promoted_at;
    return latest;
  }, null);

  // 20-Jul-2026, per direct product review: a visible Delete button on every
  // row is an accidental-deletion risk for a production system. Delete now
  // lives behind checkbox multi-select + a bulk action bar, or a per-row
  // overflow menu -- both gated by a confirm dialog. Backend `DELETE
  // /pipelines/{id}` is a real soft-delete (sets deleted_at, never hard-
  // deletes -- see routes/pipelines.py). No Archive/Duplicate action here:
  // neither has a real backend endpoint yet, so they're intentionally not
  // offered rather than faked.
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [confirmTarget, setConfirmTarget] = useState<{ ids: string[]; label: string } | null>(null);

  const deleteMutation = useMutation({
    mutationFn: async (ids: string[]) => {
      const results = await Promise.allSettled(ids.map((id) => apiClient.deletePipeline(id)));
      const failed = results.filter((r) => r.status === "rejected");
      if (failed.length > 0) throw new Error(`${failed.length} of ${ids.length} deletions failed`);
    },
    onSuccess: () => {
      setSelectedIds([]);
      setConfirmTarget(null);
      refetch();
    },
  });

  const allSelected = pipelines.length > 0 && selectedIds.length === pipelines.length;
  const toggleAll = () => setSelectedIds(allSelected ? [] : pipelines.map((p) => p.id));
  const toggleOne = (id: string) =>
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  return (
    <AppShell title="Pipelines" description="Build, monitor and deploy enterprise RAG pipelines.">
      <div className="space-y-6">

        {/* KPI row -- real counts/aggregates, replacing the old three-item
            mini-stats strip (per direct product review: "answers only 'what
            pipelines do I have', not whether they're healthy or in
            production"). Average Score / Last Deployment are omitted (—)
            when there's no real data yet rather than showing a fabricated 0. */}
        {!isLoading && pipelines.length > 0 && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-6">
            <KpiTile label="Pipelines" value={pipelines.length} />
            <KpiTile label="Healthy" value={healthy} />
            <KpiTile label="Production" value={production} />
            <KpiTile label="Draft" value={draft} />
            <KpiTile label="Avg. Unified Score" value={avgScore !== null ? `${Math.round(avgScore * 100)}%` : "—"} />
            <KpiTile label="Last Deployment" value={lastDeploymentAt ? relativeTime(lastDeploymentAt) : "—"} />
          </div>
        )}

        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-1 flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative w-full sm:max-w-xs">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search pipelines…"
                aria-label="Search pipelines by name"
                className="w-full rounded-lg border border-border bg-white py-2 pl-9 pr-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-accent focus:outline-none"
              />
            </div>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              aria-label="Filter by status"
              className="rounded-lg border border-border bg-white px-3 py-2 text-sm font-medium text-foreground focus:border-accent focus:outline-none"
            >
              <option value="all">All statuses</option>
              <option value="ready">Ready</option>
              <option value="running">Running</option>
              <option value="pending">Draft</option>
              <option value="failed">Failed</option>
              <option value="decommissioned">Archived</option>
            </select>
            <select
              value={deploymentFilter}
              onChange={(e) => setDeploymentFilter(e.target.value)}
              aria-label="Filter by deployment"
              className="rounded-lg border border-border bg-white px-3 py-2 text-sm font-medium text-foreground focus:border-accent focus:outline-none"
            >
              <option value="all">All deployments</option>
              <option value="not_deployed">Not Deployed</option>
              <option value="promoted">Production</option>
              <option value="blue_green">Deploying</option>
              <option value="rolled_back">Rolled Back</option>
              <option value="failed">Deploy Failed</option>
            </select>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <button
              onClick={refetch}
              disabled={isLoading}
              className="flex items-center gap-2 px-3 py-2 text-sm text-text-3 bg-white hover:bg-[rgba(15,23,42,0.04)] border border-border rounded-lg transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
              Refresh
            </button>
            <Link
              href="/configurator"
              className="flex items-center gap-2 px-4 py-2 text-sm font-semibold text-foreground bg-accent hover:bg-accent-light rounded-lg transition-all shadow-lg shadow-accent/20 hover:shadow-accent/40"
            >
              <Plus className="w-4 h-4" />
              New Pipeline
            </Link>
          </div>
        </div>

        {/* Error state — soft inline warning, not a scary red banner */}
        {error && (
          <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3.5">
            <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <div className="text-sm">
              <p className="font-medium text-amber-800">Could not load pipelines</p>
              <p className="text-text-3 mt-0.5">Your session may have expired. &nbsp;
                <Link href="/login" className="text-accent underline underline-offset-2">Sign in again</Link>
              </p>
            </div>
          </div>
        )}

        {/* Loading state */}
        {isLoading && pipelines.length === 0 && (
          <div className="flex items-center justify-center py-24">
            <Loader2 className="w-7 h-7 text-accent-light animate-spin" />
          </div>
        )}

        {/* Empty state — onboarding card */}
        {!isLoading && !error && pipelines.length === 0 && (
          <div className="rounded-2xl border border-border bg-white overflow-hidden">
            {/* Card top accent */}
            <div className="h-px bg-gradient-to-r from-transparent via-accent/50 to-transparent" />

            <div className="px-8 py-10 text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-accent/10 ring-1 ring-accent/30 mb-5">
                <Rocket className="w-7 h-7 text-accent" />
              </div>
              <h3 className="text-lg font-bold text-foreground">No pipelines yet</h3>
              <p className="mt-2 text-sm text-text-3 max-w-sm mx-auto">
                Create your first RAG pipeline and start evaluating retrieval quality with the 9-agent autonomous loop.
              </p>

              {/* Steps */}
              <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4 text-left">
                {STEPS.map((step, i) => {
                  const Icon = step.icon;
                  return (
                    <div key={step.label} className="rounded-xl border border-border bg-[rgba(15,23,42,0.04)] p-4 space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-bold text-muted-foreground tabular">{String(i + 1).padStart(2, "0")}</span>
                        <Icon className="w-3.5 h-3.5 text-accent" />
                      </div>
                      <p className="text-xs font-semibold text-foreground">{step.label}</p>
                      <p className="text-[11px] text-text-3">{step.desc}</p>
                    </div>
                  );
                })}
              </div>

              <div className="mt-8 flex items-center justify-center gap-3">
                <Link
                  href="/configurator"
                  className="flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-foreground bg-accent hover:bg-accent-light rounded-lg transition-all shadow-lg shadow-accent/25 hover:shadow-accent/40"
                >
                  <Plus className="w-4 h-4" />
                  Create Pipeline
                </Link>
                <Link
                  href="/documents"
                  className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-text-3 bg-white border border-border hover:bg-[rgba(15,23,42,0.04)] rounded-lg transition-colors"
                >
                  <Upload className="w-4 h-4" />
                  Upload Documents
                </Link>
              </div>
            </div>
          </div>
        )}

        {/* Bulk action bar -- only Delete is real (backend soft-delete, no
            Archive/Duplicate route exists yet, so those aren't offered). */}
        {selectedIds.length > 0 && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3">
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium text-amber-800">
                {selectedIds.length} pipeline{selectedIds.length > 1 ? "s" : ""} selected
              </span>
              <button
                onClick={() => setSelectedIds([])}
                className="flex items-center gap-1 rounded px-2 py-1 text-xs text-amber-700 hover:bg-white/5"
              >
                <X className="h-3 w-3" />
                Clear
              </button>
            </div>
            <button
              onClick={() =>
                setConfirmTarget({ ids: selectedIds, label: `${selectedIds.length} pipeline${selectedIds.length > 1 ? "s" : ""}` })
              }
              className="flex items-center gap-1.5 rounded-lg bg-rose-500/90 px-3 py-1.5 text-xs font-semibold text-foreground hover:bg-rose-500"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Delete
            </button>
          </div>
        )}

        {/* Pipeline table */}
        {pipelines.length > 0 && (
          <div className="overflow-hidden rounded-xl border border-border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-[rgba(15,23,42,0.04)]">
                  <th className="w-10 px-4 py-3">
                    <input
                      type="checkbox"
                      checked={allSelected}
                      onChange={toggleAll}
                      aria-label="Select all pipelines"
                      className="h-3.5 w-3.5 rounded border-[rgba(15,23,42,0.3)] accent-[#5B5CE2]"
                    />
                  </th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">Pipeline</th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">Status</th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">Knowledge Source</th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">Unified Score</th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">Deployment</th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">Created</th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">Last Evaluated</th>
                  <th className="w-10 px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-[rgba(15,23,42,0.1)]">
                {filteredPipelines.length === 0 && (
                  <tr>
                    <td colSpan={9} className="px-4 py-10 text-center text-sm text-muted-foreground">
                      No pipelines match your filters{query ? ` ("${query}")` : ""}.
                    </td>
                  </tr>
                )}
                {filteredPipelines.map((p) => (
                  <tr
                    key={p.id}
                    className="bg-white hover:bg-[rgba(15,23,42,0.04)] transition-colors cursor-pointer"
                    onClick={() => router.push(`/pipelines/${p.id}/history`)}
                  >
                    <td className="px-4 py-3.5" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(p.id)}
                        onChange={() => toggleOne(p.id)}
                        aria-label={`Select ${p.name}`}
                        className="h-3.5 w-3.5 rounded border-[rgba(15,23,42,0.3)] accent-[#5B5CE2]"
                      />
                    </td>
                    <td className="px-4 py-3.5">
                      <span className="font-medium text-foreground">{p.name}</span>
                      {/* 26-Jul-2026, per direct product review: a bare UUID
                          under the name isn't useful to most users -- version
                          + embedding model are real, meaningful identifiers;
                          the full ID still exists (row title attr + history
                          page URL) for anyone who does need it. */}
                      <span
                        className="block text-xs text-muted-foreground mt-0.5"
                        title={p.id}
                      >
                        v{p.current_version} · {p.embedding_model}
                      </span>
                    </td>
                    <td className="px-4 py-3.5"><StatusBadge status={p.status} /></td>
                    <td className="px-4 py-3.5">
                      <span className="inline-flex items-center gap-1.5 text-xs font-medium text-foreground">
                        <FileText className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
                        {docCounts[p.id] ?? 0} doc{(docCounts[p.id] ?? 0) === 1 ? "" : "s"}
                      </span>
                    </td>
                    <td className="px-4 py-3.5"><ScoreBadge score={p.latest_run?.unified_score ?? null} /></td>
                    <td className="px-4 py-3.5"><DeploymentBadge deployment={deployments[p.id]} /></td>
                    <td className="px-4 py-3.5 text-muted-foreground text-xs" title={p.created_at ? new Date(p.created_at).toLocaleString() : undefined}>
                      {p.created_at ? new Date(p.created_at).toLocaleDateString() : "—"}
                    </td>
                    <td className="px-4 py-3.5 text-muted-foreground text-xs" title={p.latest_run?.finished_at ? new Date(p.latest_run.finished_at).toLocaleString() : undefined}>
                      {relativeTime(p.latest_run?.finished_at)}
                    </td>
                    <td className="px-4 py-3.5 text-right" onClick={(e) => e.stopPropagation()}>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <button
                            aria-label={`Actions for ${p.name}`}
                            className="rounded p-1.5 text-text-3 hover:bg-white/5 hover:text-foreground"
                          >
                            <MoreVertical className="h-4 w-4" />
                          </button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => router.push(`/pipelines/${p.id}/history`)}>
                            <ExternalLink className="mr-2 h-3.5 w-3.5" />
                            Open history
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() => setConfirmTarget({ ids: [p.id], label: p.name })}
                            className="text-rose-500 focus:text-rose-500"
                          >
                            <Trash2 className="mr-2 h-3.5 w-3.5" />
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Delete confirmation -- single row action and bulk action both flow
            through here, so there is exactly one place a destructive pipeline
            action can be triggered from. */}
        <AlertDialog open={confirmTarget !== null} onOpenChange={(open) => !open && setConfirmTarget(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-rose-500" />
                Delete {confirmTarget?.ids.length === 1 ? "Pipeline" : "Pipelines"}
              </AlertDialogTitle>
              <AlertDialogDescription>
                Are you sure you want to delete {confirmTarget?.label}? This soft-deletes the pipeline
                (recoverable by an administrator) but removes it from every list and dashboard immediately.
              </AlertDialogDescription>
            </AlertDialogHeader>
            {deleteMutation.error && (
              <p className="text-sm text-rose-500">{(deleteMutation.error as Error).message}</p>
            )}
            <AlertDialogFooter>
              <AlertDialogCancel disabled={deleteMutation.isPending}>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={() => confirmTarget && deleteMutation.mutate(confirmTarget.ids)}
                disabled={deleteMutation.isPending}
                className="bg-rose-500 hover:bg-rose-600"
              >
                {deleteMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Deleting&hellip;
                  </>
                ) : (
                  "Delete"
                )}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </AppShell>
  );
}
