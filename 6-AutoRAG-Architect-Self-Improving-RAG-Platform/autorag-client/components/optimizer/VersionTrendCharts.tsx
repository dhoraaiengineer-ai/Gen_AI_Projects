"use client";

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

import type { PipelineVersionSummary } from "@/types";

interface VersionTrendChartsProps {
  versions: PipelineVersionSummary[];
}

const TOOLTIP_STYLE = {
  backgroundColor: "hsl(var(--card))",
  borderColor: "rgba(15,23,42,0.1)",
  borderRadius: "6px",
  fontSize: "12px",
  color: "var(--text-1)",
};

interface MetricSpec {
  key: "unified_score" | "recall" | "latency_p95_ms" | "cost_usd";
  label: string;
  color: string;
  domain?: [number, number];
  format: (v: number) => string;
}

const METRICS: MetricSpec[] = [
  { key: "unified_score", label: "Unified Score", color: "#F59E0B", domain: [0, 1], format: (v) => v.toFixed(2) },
  { key: "recall", label: "Recall", color: "#06b6d4", domain: [0, 1], format: (v) => v.toFixed(2) },
  { key: "latency_p95_ms", label: "Latency (p95)", color: "#f59e0b", format: (v) => `${(v / 1000).toFixed(1)}s` },
  { key: "cost_usd", label: "Cost / Query", color: "#10b981", format: (v) => `$${v.toFixed(4)}` },
];

/**
 * Real per-version trend charts (25-Jul-2026, capability-first polish pass).
 * Fed entirely from PipelineVersionSummary[] already fetched by
 * usePipelineVersions -- no new endpoint. Versions with a null metric (no
 * completed evaluation yet) are filtered out of that specific chart's data,
 * never plotted as 0 or interpolated.
 */
export function VersionTrendCharts({ versions }: VersionTrendChartsProps) {
  const sorted = [...versions].sort((a, b) => a.version_number - b.version_number);

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      {METRICS.map((metric) => {
        const points = sorted
          .filter((v) => v[metric.key] !== null)
          .map((v) => ({ label: `v${v.version_number}`, value: v[metric.key] as number }));

        return (
          <div key={metric.key} className="rounded-xl border border-border bg-card p-4">
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-3">{metric.label}</h3>
            {points.length < 2 ? (
              <div className="flex h-[140px] items-center justify-center text-xs text-text-3">
                Not enough evaluated versions yet
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={140}>
                <LineChart data={points} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(15,23,42,0.1)" />
                  <XAxis dataKey="label" stroke="var(--text-3)" tick={{ fontSize: 10, fill: "var(--text-3)" }} />
                  <YAxis
                    domain={metric.domain}
                    stroke="var(--text-3)"
                    tick={{ fontSize: 10, fill: "var(--text-3)" }}
                    tickFormatter={metric.format}
                    width={44}
                  />
                  <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: number) => metric.format(v)} />
                  <Line
                    type="monotone"
                    dataKey="value"
                    stroke={metric.color}
                    strokeWidth={2}
                    dot={{ r: 3, fill: metric.color }}
                    activeDot={{ r: 5 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        );
      })}
    </div>
  );
}
