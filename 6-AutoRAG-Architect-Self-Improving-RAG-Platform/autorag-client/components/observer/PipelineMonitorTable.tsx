"use client";

/**
 * Monitored Pipelines — Chapter 27.8 (repurposed). The spec's "Production Query
 * Stream" needs a per-query log endpoint that does not exist, so rather than fake
 * individual queries this shows each monitored pipeline's real latest-run
 * telemetry: Unified Score, latency, cost, provider, status, and failure codes.
 */

import Link from "next/link";

import { Card } from "@/components/ui/card";
import { formatScore, scoreColorClasses } from "@/lib/score";
import { formatCost, formatLatencyMs, pipelineLabel, type PipelineTelemetry } from "@/lib/observer";

interface PipelineMonitorTableProps {
  telemetry: PipelineTelemetry[];
  isLoading: boolean;
}

export function PipelineMonitorTable({ telemetry, isLoading }: PipelineMonitorTableProps) {
  if (isLoading) {
    return <Card className="h-56 animate-pulse bg-accent/5" />;
  }

  if (telemetry.length === 0) {
    return (
      <Card className="p-8 text-center text-sm text-text-3">No pipelines to monitor yet.</Card>
    );
  }

  return (
    <Card className="overflow-x-auto p-0">
      <table className="w-full min-w-[720px] text-sm">
        <caption className="sr-only">Monitored pipelines with latest-run telemetry</caption>
        <thead>
          <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-text-3">
            <th scope="col" className="px-4 py-3 font-medium">Pipeline</th>
            <th scope="col" className="px-4 py-3 font-medium">Unified Score</th>
            <th scope="col" className="px-4 py-3 font-medium">Latency p95</th>
            <th scope="col" className="px-4 py-3 font-medium">Cost / Query</th>
            <th scope="col" className="px-4 py-3 font-medium">Provider</th>
            <th scope="col" className="px-4 py-3 font-medium">Failures</th>
          </tr>
        </thead>
        <tbody>
          {telemetry.map(({ pipeline, score }) => (
            <tr key={pipeline.id} className="border-b border-border/50 last:border-0 hover:bg-accent/5">
              <th scope="row" className="px-4 py-3 text-left font-medium text-foreground">
                <Link href={`/pipelines/${pipeline.id}/history`} className="hover:text-accent">
                  {pipelineLabel(pipeline)}
                </Link>
                <span className="ml-2 text-[10px] uppercase text-text-3">{pipeline.status}</span>
              </th>
              <td className="px-4 py-3">
                {score && score.unified_score !== null ? (
                  <span className={`inline-flex rounded px-2 py-0.5 text-xs font-semibold ${scoreColorClasses(score.unified_score)}`}>
                    {formatScore(score.unified_score)}
                  </span>
                ) : (
                  <span className="text-text-3">—</span>
                )}
              </td>
              <td className="px-4 py-3 font-mono text-xs text-text-2">
                {score ? formatLatencyMs(score.latency_p95_ms) : "—"}
              </td>
              <td className="px-4 py-3 font-mono text-xs text-text-2">
                {score ? formatCost(score.cost_per_query_usd) : "—"}
              </td>
              <td className="px-4 py-3 text-xs text-text-3">{score?.llm_provider_used ?? "—"}</td>
              <td className="px-4 py-3">
                {score && score.failure_taxonomy.length > 0 ? (
                  <span className="font-mono text-xs text-red-500">{score.failure_taxonomy.join(", ")}</span>
                ) : (
                  <span className="text-xs text-green-400">none</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
