"use client";

/**
 * Observer Dashboard — client container.
 *
 * A dedicated `GET /observe?pipeline_id=` route exists (Part B, 12-Jul-2026)
 * but is scoped to one pipeline's observer_signals + short history — this view
 * is a fleet-wide monitor across many pipelines, a different shape with no
 * matching aggregate backend endpoint. Production telemetry here is genuinely
 * aggregated from each pipeline's latest evaluation run: usePipelines() for
 * the fleet + latest_run ids, then a bounded getScore fan-out for latency/
 * cost/tokens/failures (real persisted data — getScore's failure_taxonomy
 * shape bug fixed 12-Jul-2026, see app/routes/score.py). KPIs, alerts, and
 * recommendations are derived purely (lib/observer) from those real values,
 * not fabricated. Drift detection (§27.13) and the live per-query stream
 * (§27.8) are omitted — no historical baseline and no query-log endpoint
 * (documented, not faked).
 */

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/services/api-client";
import { usePipelines } from "@/hooks/use-pipelines";
import { pipelineDisplayName } from "@/lib/format";
import {
  buildChartData,
  computeObserverKPIs,
  deriveAlerts,
  deriveRecommendations,
  type PipelineTelemetry,
} from "@/lib/observer";
import { ObserverKPIGrid } from "./ObserverKPIGrid";
import { ObserverCharts } from "./ObserverCharts";
import { PipelineMonitorTable } from "./PipelineMonitorTable";
import { AlertCenter } from "./AlertCenter";
import { RecommendationPanel } from "./RecommendationPanel";
import { ObserverSignalsPanel } from "./ObserverSignalsPanel";
import { EvaluationTrendsPanel } from "./EvaluationTrendsPanel";
import { ObserverStatusPanel } from "./ObserverStatusPanel";
import { ProductionQualityTable } from "./ProductionQualityTable";

/** Cap the getScore fan-out so a large fleet doesn't fire unbounded requests (§27.24). */
const MAX_MONITORED = 40;

export function ObserverDashboardClient() {
  const { pipelines, isLoading: pipelinesLoading, error, refetch } = usePipelines();

  const monitored = useMemo(() => pipelines.slice(0, MAX_MONITORED), [pipelines]);
  const runIds = useMemo(
    () => monitored.map((p) => p.latest_run?.id).filter((id): id is string => Boolean(id)),
    [monitored],
  );

  const { data: scores = [], isLoading: scoresLoading } = useQuery({
    queryKey: ["observer-scores", runIds],
    queryFn: () => Promise.all(runIds.map((id) => apiClient.getScore(id))),
    enabled: runIds.length > 0,
  });

  const telemetry = useMemo<PipelineTelemetry[]>(() => {
    const byRun = new Map(scores.map((s) => [s.run_id, s]));
    return monitored.map((pipeline) => ({
      pipeline,
      score: pipeline.latest_run ? byRun.get(pipeline.latest_run.id) ?? null : null,
    }));
  }, [monitored, scores]);

  const kpis = useMemo(() => computeObserverKPIs(telemetry), [telemetry]);
  const alerts = useMemo(() => deriveAlerts(telemetry), [telemetry]);
  const recommendations = useMemo(() => deriveRecommendations(telemetry), [telemetry]);
  const chartData = useMemo(() => buildChartData(telemetry), [telemetry]);

  const isLoading = pipelinesLoading || (runIds.length > 0 && scoresLoading);

  // ── Per-pipeline real Observer signals (GET /observe) — a drill-down into
  // one pipeline's qualitative signals, distinct from the fleet-wide
  // quantitative KPIs above (see file header for why these are separate). ──
  const [selectedPipelineId, setSelectedPipelineId] = useState<string | null>(null);
  useEffect(() => {
    if (!selectedPipelineId && monitored.length > 0) setSelectedPipelineId(monitored[0].id);
  }, [monitored, selectedPipelineId]);

  const selectedPipeline = monitored.find((p) => p.id === selectedPipelineId) ?? null;
  const selectedTelemetry = telemetry.find((t) => t.pipeline.id === selectedPipelineId) ?? null;

  const { data: observerData, isLoading: observerLoading } = useQuery({
    queryKey: ["observer-signals", selectedPipelineId],
    queryFn: () => apiClient.getObserverView(selectedPipelineId as string),
    enabled: Boolean(selectedPipelineId),
  });

  return (
    <div className="space-y-6">
      {error ? (
        <div role="alert" className="rounded-xl border border-red-500/40 bg-red-500/5 p-6 text-sm text-red-600">
          Unable to load pipelines: {error.message}
          <button
            type="button"
            onClick={refetch}
            className="ml-3 rounded-md bg-white/10 px-3 py-1 text-xs font-medium text-foreground hover:bg-white/20"
          >
            Retry
          </button>
        </div>
      ) : (
        <>
          <ObserverStatusPanel alerts={alerts} />

          <ObserverKPIGrid kpis={kpis} />

          <ObserverCharts data={chartData} />

          <section aria-labelledby="obs-monitor">
            <h2 id="obs-monitor" className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-3">
              Monitored Pipelines
            </h2>
            <PipelineMonitorTable telemetry={telemetry} isLoading={isLoading} />
          </section>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <AlertCenter alerts={alerts} />
            <RecommendationPanel recommendations={recommendations} />
          </div>

          <section aria-labelledby="obs-signals">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h2 id="obs-signals" className="text-xs font-semibold uppercase tracking-wide text-text-3">
                Real-Time Quality Signals
              </h2>
              {monitored.length > 0 && (
                <select
                  value={selectedPipelineId ?? ""}
                  onChange={(e) => setSelectedPipelineId(e.target.value || null)}
                  className="rounded-md border border-border bg-accent/5 px-2 py-1 text-xs text-foreground focus:border-accent focus:outline-none"
                >
                  {monitored.map((p) => (
                    <option key={p.id} value={p.id}>
                      {pipelineDisplayName(p)}
                    </option>
                  ))}
                </select>
              )}
            </div>
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <ObserverSignalsPanel
                data={observerData}
                isLoading={observerLoading}
                pipelineName={selectedPipeline ? pipelineDisplayName(selectedPipeline) : ""}
              />
              <div>
                <p className="mb-2 text-[11px] uppercase tracking-wide text-text-3">Production Quality</p>
                <ProductionQualityTable score={selectedTelemetry?.score ?? null} />
              </div>
            </div>
          </section>

          <EvaluationTrendsPanel pipelineId={selectedPipelineId} />
        </>
      )}
    </div>
  );
}
