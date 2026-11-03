'use client';

/**
 * MetricsDashboard — real retrieval latency + Recall@5 provenance.
 * Rewritten 13-Jul-2026: the previous version rendered 6 stage-timing
 * fields (rewrite_time_ms/search_time_ms/compression_time_ms/etc.) that no
 * backend route ever computed — fabricated numbers. POST /api/v1/retrieve
 * only ever produces 4 real stage timings (rewrite is a pass-through and
 * always ~0ms; there's no separate dense/bm25 breakdown, only the fused
 * hybrid_merge stage) plus a real MEASURED/NOT_COLLECTED Recall@5.
 */

import { Clock, Zap, AlertTriangle, Gauge } from 'lucide-react';
import type { RetrievalResult, RetrievalStage } from '@/types';

interface MetricsDashboardProps {
  result?: RetrievalResult;
}

export function MetricsDashboard({ result }: MetricsDashboardProps) {
  if (!result) {
    return (
      <div className="bg-card border border-border rounded-2xl p-6">
        <h2 className="text-xl font-semibold text-foreground mb-4">Performance & Recall</h2>
        <div className="bg-accent/5 border border-border rounded-lg p-8 text-center">
          <Clock className="w-12 h-12 text-text-3 mx-auto mb-3" />
          <p className="text-text-3 text-sm">
            Run a retrieval query to see real latency and Recall@5 provenance
          </p>
        </div>
      </div>
    );
  }

  const latencyStatus =
    result.total_latency_ms < 1000
      ? { color: 'text-[#10B981]', label: 'Excellent' }
      : result.total_latency_ms < 3000
        ? { color: 'text-[#F59E0B]', label: 'Good' }
        : { color: 'text-[#EF4444]', label: 'Slow' };

  return (
    <div className="space-y-4">
      <div className="bg-card border border-border rounded-2xl p-6">
        <h2 className="text-xl font-semibold text-foreground mb-6 flex items-center gap-2">
          <Zap className="w-5 h-5 text-accent" />
          Performance
        </h2>

        {/* Total Latency */}
        <div className="bg-gradient-to-br from-light_bronze-900 to-papaya_whip-900 border-2 border-accent rounded-xl p-6 mb-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-text-3">Total Latency</span>
            <span className={`text-xs font-semibold px-2.5 py-1 rounded-md ${latencyStatus.color} bg-opacity-10`}>
              {latencyStatus.label}
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className={`text-4xl font-bold font-mono ${latencyStatus.color}`}>
              {result.total_latency_ms}
            </span>
            <span className="text-lg text-text-3">ms</span>
          </div>
          {result.total_latency_ms >= 3000 && (
            <div className="mt-3 flex items-start gap-2 text-xs text-[#EF4444]">
              <AlertTriangle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
              <p>Latency exceeds the 3000ms SLA threshold.</p>
            </div>
          )}
        </div>

        {/* Real stage breakdown — exactly what POST /retrieve computes, no more */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {result.stages.map((stage) => (
            <StageCard key={stage.stage_name} stage={stage} totalMs={result.total_latency_ms} />
          ))}
        </div>
      </div>

      {/* Recall@5 provenance — prominent, not buried in debug JSON */}
      <div className="bg-card border border-border rounded-2xl p-6">
        <h2 className="text-xl font-semibold text-foreground mb-4 flex items-center gap-2">
          <Gauge className="w-5 h-5 text-accent" />
          Recall@5
        </h2>
        {result.recall_at_5_measured && result.recall_at_5 !== null ? (
          <div className="flex items-center justify-between rounded-lg border border-emerald-200 bg-emerald-50 px-5 py-4">
            <div>
              <p className="text-base font-bold text-emerald-800">MEASURED</p>
              <p className="mt-0.5 text-xs text-emerald-700/80">
                {result.relevant_ids?.length ?? 0} curated ground-truth chunk(s) for this query
              </p>
            </div>
            <span className="font-mono text-2xl font-bold text-emerald-800">
              {result.recall_at_5.toFixed(3)}
            </span>
          </div>
        ) : (
          <div className="rounded-lg border border-border bg-accent/5 px-5 py-4">
            <p className="text-sm font-semibold text-foreground">NOT_COLLECTED</p>
            <p className="mt-1 text-xs text-text-3">
              No curated ground truth exists for this pipeline/query — Recall@5 is only measured for
              the golden-path demo document today. This is a real, documented scope limit, not a
              placeholder value.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

const STAGE_LABELS: Record<string, string> = {
  rewrite: 'Rewrite',
  embedding: 'Embedding',
  hybrid_merge: 'Hybrid Search',
  reranker: 'Rerank',
};

function StageCard({ stage, totalMs }: { stage: RetrievalStage; totalMs: number }) {
  const percentage = totalMs > 0 ? (stage.latency_ms / totalMs) * 100 : 0;
  const color =
    stage.status === 'skipped'
      ? 'text-text-3'
      : stage.latency_ms < 100
        ? 'text-[#10B981]'
        : stage.latency_ms < 500
          ? 'text-[#F59E0B]'
          : 'text-[#EF4444]';

  return (
    <div className="bg-accent/5 border border-border rounded-lg p-3 transition-all motion-safe:hover:border-accent">
      <p className="text-xs text-text-3 mb-1">{STAGE_LABELS[stage.stage_name] ?? stage.stage_name}</p>
      <div className="flex items-baseline gap-1 mb-1">
        <span className={`text-lg font-bold font-mono ${color}`}>{stage.latency_ms}</span>
        <span className="text-xs text-text-3">ms</span>
      </div>
      <div className="flex items-center gap-2">
        <div className="flex-1 h-1.5 bg-accent/5 rounded-full overflow-hidden">
          <div
            className="h-full bg-accent rounded-full transition-all duration-500"
            style={{ width: `${Math.min(percentage, 100)}%` }}
          />
        </div>
        <span className="text-xs text-text-3 font-mono">{percentage.toFixed(0)}%</span>
      </div>
    </div>
  );
}
