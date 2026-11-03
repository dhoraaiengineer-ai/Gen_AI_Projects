"use client";

/**
 * Experiments Page -- client shell (F-16, Ch 30).
 *
 * Data source: apiClient.listExperiments() (real GET /experiments, Part E
 * rewiring 12-Jul-2026 -- also fixed two real bugs in that route: it returned
 * the internal run.id PK instead of the external run_id correlation ID, and
 * read a nonexistent `quality_score` column). usePipelines() supplies only
 * display metadata (name, version) per pipeline_id -- no more getScore fan-out.
 */

import { useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";

import { apiClient } from "@/services/api-client";
import { usePipelines } from "@/hooks/use-pipelines";
import {
  fromExperimentApiRecord,
  computeExperimentSummary,
  buildMetricsChartData,
} from "@/lib/experiments";
import type { ExperimentRecord } from "@/lib/experiments";
import type { ExperimentApiRecord } from "@/types";


import { ExperimentSummaryCards } from "./ExperimentSummaryCards";
import { ExperimentsTable } from "./ExperimentsTable";
import { ComparisonView } from "./ComparisonView";
import { MetricsDashboard } from "./MetricsDashboard";
import { PromotionPanel } from "./PromotionPanel";

const MAX_EXPERIMENTS = 40;

export function ExperimentsPageClient() {
  const { pipelines, isLoading: pipelinesLoading, error, refetch } = usePipelines();
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const [apiRecords, setApiRecords] = useState<ExperimentApiRecord[]>([]);
  const [experimentsLoading, setExperimentsLoading] = useState(true);
  const [experimentsError, setExperimentsError] = useState<Error | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);

  useEffect(() => {
    let mounted = true;
    setExperimentsLoading(true);
    apiClient
      .listExperiments({ limit: MAX_EXPERIMENTS })
      .then((res) => {
        if (!mounted) return;
        setApiRecords(res.experiments);
        setExperimentsError(null);
      })
      .catch((err: unknown) => {
        if (!mounted) return;
        setExperimentsError(err instanceof Error ? err : new Error("Failed to load experiments"));
      })
      .finally(() => {
        if (mounted) setExperimentsLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [refreshToken]);

  const refetchAll = () => {
    refetch();
    setRefreshToken((n) => n + 1);
  };

  const records = useMemo<ExperimentRecord[]>(() => {
    const byPipelineId = new Map(pipelines.map((p) => [p.id, p]));
    return apiRecords.map((r) => fromExperimentApiRecord(r, byPipelineId.get(r.pipeline_id)));
  }, [apiRecords, pipelines]);

  const loading = pipelinesLoading || experimentsLoading;
  const summary = useMemo(() => computeExperimentSummary(records), [records]);
  const chartData = useMemo(() => buildMetricsChartData(records), [records]);

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        if (next.size >= 2) {
          const [first] = next;
          next.delete(first);
        }
        next.add(id);
      }
      return next;
    });
  };

  const handlePromote = async (id: string) => {
    const rec = records.find((r) => r.id === id);
    if (rec) await apiClient.promote(rec.pipelineId);
  };

  const selectedRecords = records.filter((r) => selectedIds.has(r.id));
  const [compA, compB] = selectedRecords;

  return (
    <div className="space-y-6 p-6">
      {/* Title/description now come from the shared page hero (AppShell) --
          keep just the Refresh action here (26-Jul-2026). */}
      <div className="flex justify-end">
        <button
          onClick={refetchAll}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-semibold text-text-2 transition-colors motion-safe:duration-150 hover:bg-sidebar-2 disabled:opacity-40"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* Error banner */}
      {(error || experimentsError) && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-600">
          {error?.message ?? experimentsError?.message}
        </div>
      )}

      {/* Summary cards */}
      <ExperimentSummaryCards summary={summary} loading={loading} />

      {/* Experiment table */}
      <div>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground">All Experiments</h2>
          {selectedIds.size > 0 && (
            <p className="text-xs text-text-3">
              {selectedIds.size}/2 selected for comparison
            </p>
          )}
        </div>
        <ExperimentsTable
          records={records}
          selectedIds={selectedIds}
          onToggle={toggleSelect}
        />
      </div>

      {/* Comparison view -- only when 2 selected */}
      {compA && compB && <ComparisonView a={compA} b={compB} />}

      {/* Metrics dashboard */}
      <div>
        <h2 className="mb-4 text-sm font-semibold text-foreground">Metrics Dashboard</h2>
        <MetricsDashboard data={chartData} />
      </div>

      {/* Promotion queue */}
      <div>
        <h2 className="mb-2 text-sm font-semibold text-foreground">Promotion Queue</h2>
        <PromotionPanel selected={selectedRecords} onPromote={handlePromote} />
      </div>
    </div>
  );
}
