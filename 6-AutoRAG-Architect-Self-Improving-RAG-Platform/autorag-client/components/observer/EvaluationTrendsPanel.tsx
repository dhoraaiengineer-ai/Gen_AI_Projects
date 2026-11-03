"use client";

/**
 * Evaluation Trends (Evaluation Center Phase 4, 24-Jul-2026) -- additive
 * panel tied to real batch-evaluation data: average Unified Score per batch
 * run (trend) and a failure-pattern breakdown (per-question status counts)
 * for the most recent batch run. Sourced from GET /batch-evaluations and
 * GET /batch-evaluations/{id} -- no new aggregation table, no fabricated
 * baseline.
 */

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { apiClient } from "@/services/api-client";
import type { BatchRun, BatchRunSummary } from "@/types";

interface EvaluationTrendsPanelProps {
  pipelineId: string | null;
}

const TOOLTIP_STYLE = {
  backgroundColor: "hsl(var(--card))",
  borderColor: "rgba(15,23,42,0.1)",
  borderRadius: "6px",
  fontSize: "12px",
};

export function EvaluationTrendsPanel({ pipelineId }: EvaluationTrendsPanelProps) {
  const [runs, setRuns] = useState<BatchRun[]>([]);
  const [trend, setTrend] = useState<{ label: string; average_score: number }[]>([]);
  const [latestSummary, setLatestSummary] = useState<BatchRunSummary | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!pipelineId) return;
    let mounted = true;
    setLoading(true);
    apiClient
      .listBatchRuns({ pipelineId, status: "completed" })
      .then(async (items) => {
        if (!mounted) return;
        setRuns(items);
        // Oldest-first, capped at the last 8 runs for a readable trend.
        const recent = [...items].reverse().slice(-8);
        const summaries = await Promise.all(
          recent.map((r) => apiClient.getBatchRun(r.id).catch(() => null)),
        );
        if (!mounted) return;
        setTrend(
          recent
            .map((r, idx) => ({ run: r, summary: summaries[idx] }))
            .filter((x): x is { run: BatchRun; summary: BatchRunSummary } => x.summary !== null)
            .map(({ run, summary }) => ({
              label: run.created_at ? new Date(run.created_at).toLocaleDateString() : run.id.slice(0, 8),
              average_score: summary.summary.average_unified_score ?? 0,
            })),
        );
        if (items.length > 0) {
          const latest = await apiClient.getBatchRun(items[0].id).catch(() => null);
          if (mounted) setLatestSummary(latest);
        }
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [pipelineId]);

  if (!pipelineId) return null;

  return (
    <section aria-labelledby="obs-eval-trends">
      <h2 id="obs-eval-trends" className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-3">
        Evaluation Trends
      </h2>

      {loading && (
        <div className="h-48 motion-safe:animate-pulse rounded-xl bg-accent/5" aria-hidden="true" />
      )}

      {!loading && runs.length === 0 && (
        <p className="rounded-xl border border-border bg-card p-6 text-center text-sm text-text-3">
          No completed batch evaluation runs for this pipeline yet.
        </p>
      )}

      {!loading && trend.length > 0 && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="mb-2 text-xs text-text-3">Average Unified Score per Batch Run</p>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={trend} margin={{ top: 4, right: 16, left: -8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(15,23,42,0.1)" />
                <XAxis dataKey="label" stroke="var(--text-3)" tick={{ fontSize: 10, fill: "var(--text-3)" }} />
                <YAxis domain={[0, 1]} stroke="var(--text-3)" tick={{ fontSize: 10, fill: "var(--text-3)" }} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Bar dataKey="average_score" fill="#F59E0B" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="rounded-xl border border-border bg-card p-4">
            <p className="mb-2 text-xs text-text-3">Latest Run — Question Status Breakdown</p>
            {latestSummary ? (
              <dl className="space-y-2">
                {Object.entries(latestSummary.summary.counts_by_status).map(([status, count]) => (
                  <div key={status} className="flex items-center justify-between text-xs">
                    <dt className="text-text-3">{status}</dt>
                    <dd className="font-mono text-foreground">{count}</dd>
                  </div>
                ))}
                <div className="flex items-center justify-between border-t border-border pt-2 text-xs">
                  <dt className="text-rose-400">Below 0.70</dt>
                  <dd className="font-mono text-rose-400">{latestSummary.summary.low_score_count}</dd>
                </div>
              </dl>
            ) : (
              <p className="text-xs text-text-3">No breakdown available.</p>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
