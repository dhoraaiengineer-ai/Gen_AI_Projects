"use client";

import { useEffect, useState } from "react";
import { Gauge, ShieldCheck, Target, Timer, ListChecks, Rocket } from "lucide-react";

import { StatCard } from "@/components/ui/stat-card";
import { apiClient } from "@/services/api-client";
import { formatScore, isHardBlock, scoreBand } from "@/lib/score";
import type { PipelineDetail, ScoreResult } from "@/types";

interface EvaluationKpiStripProps {
  pipelineId: string;
}

/**
 * Persistent metrics strip for Evaluation Center (25-Jul-2026, per external
 * review feedback: "the top of the Evaluation page feels empty"). Real data
 * only -- GET /pipelines/{id} for the latest run's unified_score/faithfulness,
 * GET /score/{run_id} for recall/latency_p95_ms, GET /evaluation/batch-runs
 * for a real count. No fabricated numbers, no illustrative placeholders.
 */
export function EvaluationKpiStrip({ pipelineId }: EvaluationKpiStripProps) {
  const [detail, setDetail] = useState<PipelineDetail | null>(null);
  const [score, setScore] = useState<ScoreResult | null>(null);
  const [batchCount, setBatchCount] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!pipelineId) {
      setDetail(null);
      setScore(null);
      setBatchCount(null);
      setLoading(false);
      return;
    }
    let mounted = true;
    setLoading(true);

    (async () => {
      try {
        const [d, runs] = await Promise.all([
          apiClient.getPipeline(pipelineId),
          apiClient.listBatchRuns({ pipelineId, status: undefined }),
        ]);
        if (!mounted) return;
        setDetail(d);
        setBatchCount(runs.length);
        setScore(d.latest_run ? await apiClient.getScore(d.latest_run.id).catch(() => null) : null);
      } catch {
        if (mounted) {
          setDetail(null);
          setBatchCount(null);
          setScore(null);
        }
      } finally {
        if (mounted) setLoading(false);
      }
    })();

    return () => {
      mounted = false;
    };
  }, [pipelineId]);

  const unifiedScore = detail?.latest_run?.unified_score ?? null;
  const faithfulness = detail?.latest_run?.faithfulness_score ?? null;
  const latencyLabel = score?.latency_p95_ms != null ? `${(score.latency_p95_ms / 1000).toFixed(1)}s` : "—";

  let gateLabel = "—";
  let gateColor = "#94A3B8";
  if (!loading && unifiedScore !== null) {
    if (isHardBlock(faithfulness)) {
      gateLabel = "BLOCKED";
      gateColor = "#F43F5E";
    } else {
      const band = scoreBand(unifiedScore);
      gateLabel = band === "deploy" ? "PASS" : band === "hitl" ? "HITL" : "BLOCKED";
      gateColor = band === "deploy" ? "#10B981" : band === "hitl" ? "#F59E0B" : "#F43F5E";
    }
  }

  const v = (val: string | number) => (loading ? "—" : val);

  return (
    <div className="grid grid-cols-2 gap-4 pb-6 sm:grid-cols-3 xl:grid-cols-6">
      <StatCard label="Unified Score"  value={v(formatScore(unifiedScore))} icon={Gauge}       iconColor="#F59E0B" />
      <StatCard label="Faithfulness"   value={v(formatScore(faithfulness))} icon={ShieldCheck} iconColor="#10B981" />
      <StatCard label="Recall"         value={v(formatScore(score?.recall ?? null))} icon={Target} iconColor="#EA580C" />
      <StatCard label="Latency (p95)"  value={v(latencyLabel)}              icon={Timer}       iconColor="#0EA5E9" />
      <StatCard label="Batch Runs"     value={v(batchCount ?? "—")}         icon={ListChecks}  iconColor="#06B6D4" />
      <StatCard label="Deployment Gate" value={v(gateLabel)}                icon={Rocket}      iconColor={gateColor} />
    </div>
  );
}
