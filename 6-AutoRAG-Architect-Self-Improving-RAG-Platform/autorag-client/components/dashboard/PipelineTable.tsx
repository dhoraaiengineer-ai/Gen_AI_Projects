"use client";

import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";

import { PipelineStatusBadge } from "@/components/dashboard/PipelineStatusBadge";
import { pipelineDisplayName, relativeTime } from "@/lib/format";
import { formatScore, isHardBlock, scoreColorClasses } from "@/lib/score";
import type { PipelineStatus, PipelineWithRun } from "@/types";

type SortKey = "name" | "status" | "score" | "version" | "lastRun";
type SortDir = "asc" | "desc";

interface PipelineTableProps {
  pipelines: PipelineWithRun[];
  isLoading?: boolean;
  error?: Error | null;
  onRetry?: () => void;
}

const STATUS_FILTERS: Array<PipelineStatus | "all"> = [
  "all",
  "pending",
  "running",
  "ready",
  "failed",
  "decommissioned",
];

function scoreValue(p: PipelineWithRun): number {
  return p.latest_run?.unified_score ?? -1;
}

/** Sortable, filterable pipeline list. Handles loading / empty / error explicitly. */
export function PipelineTable({ pipelines, isLoading, error, onRetry }: PipelineTableProps) {
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<PipelineStatus | "all">("all");
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = pipelines.filter((p) => {
      const matchesStatus = statusFilter === "all" || p.status === statusFilter;
      const matchesQuery = q === "" || pipelineDisplayName(p).toLowerCase().includes(q);
      return matchesStatus && matchesQuery;
    });

    const dir = sortDir === "asc" ? 1 : -1;
    return [...filtered].sort((a, b) => {
      switch (sortKey) {
        case "name":
          return dir * pipelineDisplayName(a).localeCompare(pipelineDisplayName(b));
        case "status":
          return dir * a.status.localeCompare(b.status);
        case "version":
          return dir * (a.current_version - b.current_version);
        case "lastRun":
          return dir * ((a.latest_run?.finished_at ?? "").localeCompare(b.latest_run?.finished_at ?? ""));
        case "score":
        default:
          return dir * (scoreValue(a) - scoreValue(b));
      }
    });
  }, [pipelines, query, statusFilter, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "name" || key === "status" ? "asc" : "desc");
    }
  }

  if (error) {
    return (
      <Panel>
        <div className="p-8 text-center" role="alert">
          <p className="text-sm font-medium text-rose-600">Failed to load pipelines: {error.message}</p>
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="mt-3 rounded-xl bg-amber-500 px-3.5 py-1.5 text-sm font-bold text-white hover:bg-amber-600"
            >
              Retry
            </button>
          )}
        </div>
      </Panel>
    );
  }

  if (isLoading) {
    return (
      <Panel>
        <div className="space-y-2 p-4" aria-busy="true" aria-label="Loading pipelines">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-10 animate-pulse rounded-xl bg-stone-100" />
          ))}
        </div>
      </Panel>
    );
  }

  return (
    <Panel>
      <div className="flex flex-col gap-3 border-b border-stone-100 p-4 sm:flex-row sm:items-center">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter pipelines…"
          aria-label="Filter pipelines by name"
          className="w-full rounded-xl border border-stone-200 bg-stone-50 px-3 py-2 text-sm text-stone-900 placeholder:text-stone-400 focus:border-amber-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-amber-500/15 sm:max-w-xs"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as PipelineStatus | "all")}
          aria-label="Filter by status"
          className="rounded-xl border border-stone-200 bg-stone-50 px-3 py-2 text-sm font-semibold text-stone-900 focus:border-amber-500 focus:outline-none"
        >
          {STATUS_FILTERS.map((s) => (
            <option key={s} value={s}>
              {s === "all" ? "All statuses" : s}
            </option>
          ))}
        </select>
      </div>

      {rows.length === 0 ? (
        <div className="p-10 text-center text-sm font-medium text-stone-500">
          No pipelines match your filters. Create one in the{" "}
          <span className="font-bold text-orange-600">Configurator</span> to get started.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="bg-stone-100/70 text-[10px] font-bold uppercase tracking-wider text-stone-600">
              <tr className="border-b border-stone-200">
                <Th label="Pipeline" active={sortKey === "name"} dir={sortDir} onSort={() => toggleSort("name")} />
                <Th label="Status" active={sortKey === "status"} dir={sortDir} onSort={() => toggleSort("status")} />
                <Th label="Unified Score" active={sortKey === "score"} dir={sortDir} onSort={() => toggleSort("score")} />
                <Th label="Version" active={sortKey === "version"} dir={sortDir} onSort={() => toggleSort("version")} />
                <Th label="Last Run" active={sortKey === "lastRun"} dir={sortDir} onSort={() => toggleSort("lastRun")} />
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {rows.map((p) => (
                <tr key={p.id} className="transition-colors hover:bg-amber-50/30">
                  <td className="px-4 py-3">
                    <p className="font-bold text-stone-900">{p.name || `Pipeline ${p.id.slice(0, 8)}`}</p>
                    <p className="text-xs font-medium text-stone-400">v{p.current_version}</p>
                  </td>
                  <td className="px-4 py-3"><PipelineStatusBadge status={p.status} /></td>
                  <td className="px-4 py-3"><ScoreCell pipeline={p} /></td>
                  <td className="px-4 py-3 font-mono text-xs font-bold text-amber-600">{p.current_version}</td>
                  <td className="px-4 py-3 text-xs font-medium text-stone-500">{relativeTime(p.latest_run?.finished_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

function ScoreCell({ pipeline }: { pipeline: PipelineWithRun }) {
  const run = pipeline.latest_run;
  if (!run) return <span className="text-text-3">—</span>;

  if (isHardBlock(run.faithfulness_score)) {
    return (
      <span className="inline-flex items-center gap-2">
        <span className="rounded px-2 py-0.5 text-sm font-bold text-rose-600">{formatScore(run.unified_score)}</span>
        <span className="rounded bg-rose-50 px-1.5 py-0.5 text-[10px] font-bold uppercase text-rose-700 ring-1 ring-inset ring-rose-200">Hard Block</span>
      </span>
    );
  }

  // unified_score is null when the run failed before Evaluator ever ran --
  // no color band is meaningful for a score that doesn't exist.
  if (run.unified_score === null) {
    return <span className="text-stone-400">{formatScore(run.unified_score)}</span>;
  }

  return (
    <span className={`inline-flex rounded px-2 py-0.5 text-sm font-bold ${scoreColorClasses(run.unified_score)}`}>
      {formatScore(run.unified_score)}
    </span>
  );
}

function Panel({ children }: { children: React.ReactNode }) {
  return <div className="overflow-hidden rounded-3xl border border-stone-200/90 bg-white shadow-[0_2px_12px_rgba(0,0,0,0.03)]">{children}</div>;
}

interface ThProps {
  label: string;
  active: boolean;
  dir: SortDir;
  onSort: () => void;
}

function Th({ label, active, dir, onSort }: ThProps) {
  const Icon = !active ? ChevronsUpDown : dir === "asc" ? ArrowUp : ArrowDown;
  return (
    <th
      className="px-4 py-3 font-medium"
      aria-sort={active ? (dir === "asc" ? "ascending" : "descending") : "none"}
    >
      <button
        type="button"
        onClick={onSort}
        className="inline-flex items-center gap-1 hover:text-foreground"
      >
        {label}
        <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      </button>
    </th>
  );
}
