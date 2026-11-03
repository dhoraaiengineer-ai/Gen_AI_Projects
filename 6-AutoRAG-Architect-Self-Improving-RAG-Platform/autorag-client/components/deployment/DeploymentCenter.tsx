"use client";

import { useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";

import { usePipelines } from "@/hooks/use-pipelines";
import { useDeployment } from "@/hooks/use-deployment";
import { apiClient } from "@/services/api-client";
import { pipelineDisplayName } from "@/lib/format";
import { scoreBand, DEPLOY_GATE, formatScorePercent } from "@/lib/score";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { UnifiedScoreGauge } from "@/components/evaluation/UnifiedScoreGauge";
import { CostLatencyPanel } from "@/components/evaluation/CostLatencyPanel";
import { BlueGreenBar } from "@/components/deployment/BlueGreenBar";
import { DeployActionButtons } from "@/components/deployment/DeployActionButtons";
import { DeploymentHistory } from "@/components/deployment/DeploymentHistory";
import { CurrentVsCandidate } from "@/components/deployment/CurrentVsCandidate";
import type { ScoreResult } from "@/types";

/**
 * Client-side Deployment Center (E-12; Chapter 24): pipeline selector,
 * deployment readiness gate, live Blue/Green status, deploy/promote/rollback
 * controls, and deployment history — all live-polled via hooks/use-deployment.ts.
 */
export function DeploymentCenter() {
  const { pipelines, isLoading: pipelinesLoading } = usePipelines();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedId && pipelines.length > 0) setSelectedId(pipelines[0].id);
  }, [pipelines, selectedId]);

  const pipeline = pipelines.find((p) => p.id === selectedId) ?? null;
  const { current, history, isLoading: deployLoading, error: deployError, refetch } = useDeployment(selectedId);
  // Real "current production" deployment -- the most recent one with
  // status "promoted" in the real history list (newest-first per
  // DeploymentHistory.tsx). No run_id exists on Deployment, so only its
  // unified_score_at_deploy snapshot is usable for comparison.
  const currentProductionDeployment = history.find((d) => d.status === "promoted") ?? null;

  const [score, setScore] = useState<ScoreResult | null>(null);
  useEffect(() => {
    let cancelled = false;
    setScore(null);
    if (pipeline?.latest_run) {
      apiClient
        .getScore(pipeline.latest_run.id)
        .then((result) => {
          if (!cancelled) setScore(result);
        })
        .catch(() => {
          if (!cancelled) setScore(null);
        });
    }
    return () => {
      cancelled = true;
    };
  }, [pipeline?.latest_run]);

  return (
    <div className="space-y-6">
      {/* Pipeline selector */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
        <label htmlFor="deploy-pipeline-select" className="eyebrow">
          Pipeline
        </label>
        <select
          id="deploy-pipeline-select"
          value={selectedId ?? ""}
          onChange={(e) => setSelectedId(e.target.value || null)}
          disabled={pipelinesLoading || pipelines.length === 0}
          className="w-full max-w-sm rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-amber-500/40 disabled:opacity-50"
        >
          {pipelines.length === 0 && <option value="">No pipelines available</option>}
          {pipelines.map((p) => (
            <option key={p.id} value={p.id}>
              {pipelineDisplayName(p)}
            </option>
          ))}
        </select>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-accent/5 px-2.5 py-1 text-xs font-medium text-text-3">
          <ShieldCheck className="h-3.5 w-3.5 text-amber-500" aria-hidden="true" />
          production
        </span>
      </div>

      {!pipeline ? (
        <Card>
          <CardContent className="p-10 text-center text-sm text-text-3">
            Select a pipeline to view its deployment status.
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Deployment Readiness */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm text-foreground">Deployment Readiness</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-[220px_1fr]">
                <div className="flex flex-col items-center justify-center rounded-lg border border-border bg-accent/5 p-4">
                  <UnifiedScoreGauge score={pipeline.latest_run?.unified_score ?? 0} />
                </div>
                <ReadinessBanner unifiedScore={pipeline.latest_run?.unified_score ?? null} />
              </div>
              {score && <CostLatencyPanel score={score} />}
            </CardContent>
          </Card>

          {score && <CurrentVsCandidate currentDeployment={currentProductionDeployment} candidateScore={score} />}

          {/* Blue/Green status + actions */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm text-foreground">Blue/Green Traffic Split</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <BlueGreenBar status={current?.status} />
              <DeployActionButtons pipeline={pipeline} current={current} onActionComplete={refetch} />
            </CardContent>
          </Card>

          {/* Deployment history */}
          <section aria-labelledby="deploy-history-heading">
            <h2 id="deploy-history-heading" className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-3">
              Deployment History
            </h2>
            <DeploymentHistory deployments={history} isLoading={deployLoading} error={deployError} onRetry={refetch} />
          </section>
        </>
      )}
    </div>
  );
}

function ReadinessBanner({ unifiedScore }: { unifiedScore: number | null }) {
  if (unifiedScore === null) {
    return (
      <div className="flex items-center rounded-lg border border-border bg-accent/5 px-5 py-4">
        <p className="text-sm text-text-3">No completed evaluation run for this pipeline yet.</p>
      </div>
    );
  }

  const band = scoreBand(unifiedScore);
  const containerClass =
    band === "deploy"
      ? "border-status-success/40 bg-status-success/10"
      : band === "hitl"
      ? "border-status-warning/40 bg-status-warning/10"
      : "border-status-error/40 bg-status-error/10";
  const textClass =
    band === "deploy" ? "text-status-success" : band === "hitl" ? "text-status-warning" : "text-status-error";
  const label = band === "deploy" ? "Deploy Eligible" : band === "hitl" ? "HITL Approval Required" : "Hard Block";
  const sublabel =
    band === "deploy"
      ? `Score ${formatScorePercent(unifiedScore)} exceeds the ${Math.round(DEPLOY_GATE * 100)}% deployment gate.`
      : band === "hitl"
      ? `Score ${formatScorePercent(unifiedScore)} is in the HITL band (70–84%). Approval token required.`
      : `Score ${formatScorePercent(unifiedScore)} is below 70%. Diagnoser + Improver loop required.`;

  return (
    <div className={`flex items-center justify-between rounded-lg border px-5 py-4 ${containerClass}`}>
      <div>
        <p className={`text-base font-bold ${textClass}`}>{label}</p>
        <p className={`mt-0.5 text-xs opacity-80 ${textClass}`}>{sublabel}</p>
      </div>
      <span className={`font-mono text-2xl font-bold ${textClass}`}>{formatScorePercent(unifiedScore)}</span>
    </div>
  );
}
