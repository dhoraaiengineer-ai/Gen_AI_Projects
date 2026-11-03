"use client";

import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import type { MetricsChartPoint } from "@/lib/experiments";
import { DEPLOY_GATE } from "@/lib/experiments";

interface Props {
  data: MetricsChartPoint[];
}

const CHART_STYLE = {
  background: "transparent",
  fontSize: 11,
  color: "var(--text-3)",
};

const TOOLTIP_CONTENT_STYLE = { background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 6, fontSize: 12, color: "var(--text-1)" };
const TOOLTIP_LABEL_STYLE = { color: "var(--text-1)" };
const AXIS_TICK = { fill: "var(--text-3)", fontSize: 11 };

export function MetricsDashboard({ data }: Props) {
  if (data.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center rounded-lg border border-border text-text-3 text-sm">
        No scored experiments to chart yet.
      </div>
    );
  }

  return (
    <div className="grid gap-6 md:grid-cols-2">
      {/* Score Trend */}
      <div className="rounded-lg border border-border bg-card p-4">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-3">
          Unified Score Trend
        </p>
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={data} style={CHART_STYLE}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(15,23,42,0.1)" />
            <XAxis dataKey="label" tick={AXIS_TICK} />
            <YAxis domain={[0, 1]} tick={AXIS_TICK} />
            <Tooltip
              contentStyle={TOOLTIP_CONTENT_STYLE}
              labelStyle={TOOLTIP_LABEL_STYLE}
            />
            <ReferenceLine y={DEPLOY_GATE} stroke="#22c55e" strokeDasharray="4 4" label={{ value: "Gate", fill: "#22c55e", fontSize: 10 }} />
            <Line type="monotone" dataKey="unified_score" stroke="#f97316" strokeWidth={2} dot={{ r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Latency Trend */}
      <div className="rounded-lg border border-border bg-card p-4">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-3">
          Latency p95 (ms)
        </p>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={data} style={CHART_STYLE}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(15,23,42,0.1)" />
            <XAxis dataKey="label" tick={AXIS_TICK} />
            <YAxis tick={AXIS_TICK} />
            <Tooltip
              contentStyle={TOOLTIP_CONTENT_STYLE}
              labelStyle={TOOLTIP_LABEL_STYLE}
            />
            <ReferenceLine y={3000} stroke="#ef4444" strokeDasharray="4 4" label={{ value: "3s SLA", fill: "#ef4444", fontSize: 10 }} />
            <Bar dataKey="latency_ms" fill="#0EA5E9" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Cost Trend */}
      <div className="rounded-lg border border-border bg-card p-4">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-3">
          Cost / Query (USD)
        </p>
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={data} style={CHART_STYLE}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(15,23,42,0.1)" />
            <XAxis dataKey="label" tick={AXIS_TICK} />
            <YAxis tickFormatter={(v: number) => `$${v.toFixed(3)}`} tick={AXIS_TICK} />
            <Tooltip
              contentStyle={TOOLTIP_CONTENT_STYLE}
              formatter={(v: number) => [`$${v.toFixed(4)}`, "Cost"]}
            />
            <Line type="monotone" dataKey="cost_usd" stroke="#a855f7" strokeWidth={2} dot={{ r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Experiment Frequency (count by version) */}
      <div className="rounded-lg border border-border bg-card p-4">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-3">
          Experiment Count by Version
        </p>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={data} style={CHART_STYLE}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(15,23,42,0.1)" />
            <XAxis dataKey="label" tick={AXIS_TICK} />
            <YAxis allowDecimals={false} tick={AXIS_TICK} />
            <Tooltip
              contentStyle={TOOLTIP_CONTENT_STYLE}
            />
            <Bar dataKey={() => 1} name="Runs" fill="#f97316" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
