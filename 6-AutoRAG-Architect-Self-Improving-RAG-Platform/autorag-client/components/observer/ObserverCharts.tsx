"use client";

/**
 * Observer trends — Chapters 27.9 (Unified Score), 27.11 (Latency), 27.12 (Tokens).
 * One point per monitored pipeline from real latest-run telemetry (lib/observer
 * buildChartData). Reference lines mark the deploy gate (0.85) and latency SLA (3s).
 */

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card } from "@/components/ui/card";
import { DEPLOY_GATE } from "@/lib/score";
import { LATENCY_SLA_MS, type ChartPoint } from "@/lib/observer";

interface ObserverChartsProps {
  data: ChartPoint[];
}

const TOOLTIP_STYLE = {
  backgroundColor: "#0f172a",
  borderColor: "#334155",
  borderRadius: "6px",
  fontSize: "12px",
  color: "#f1f5f9",
};

export function ObserverCharts({ data }: ObserverChartsProps) {
  if (data.length === 0) {
    return (
      <Card className="p-8 text-center text-sm text-text-3">
        No completed runs to chart yet.
      </Card>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <Card className="p-5">
        <h3 className="mb-4 text-sm font-semibold text-foreground">Unified Score by Version</h3>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
            <XAxis dataKey="label" stroke="#64748b" tick={{ fontSize: 11, fill: "#94a3b8" }} />
            <YAxis domain={[0, 1]} stroke="#64748b" tick={{ fontSize: 11, fill: "#94a3b8" }} tickFormatter={(v: number) => v.toFixed(1)} />
            <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: "#1e293b55" }} />
            <ReferenceLine y={DEPLOY_GATE} stroke="#10b981" strokeDasharray="4 2" />
            <Bar dataKey="unified_score" radius={[4, 4, 0, 0]}>
              {data.map((point) => (
                <Cell key={point.label} fill={point.unified_score >= DEPLOY_GATE ? "#22c55e" : "#f59e0b"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Card>

      <Card className="p-5">
        <h3 className="mb-4 text-sm font-semibold text-foreground">Latency p95 by Version</h3>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data} margin={{ top: 4, right: 8, left: -8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
            <XAxis dataKey="label" stroke="#64748b" tick={{ fontSize: 11, fill: "#94a3b8" }} />
            <YAxis stroke="#64748b" tick={{ fontSize: 11, fill: "#94a3b8" }} />
            <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: "#1e293b55" }} />
            <ReferenceLine y={LATENCY_SLA_MS} stroke="#ef4444" strokeDasharray="4 2" />
            <Bar dataKey="latency_ms" radius={[4, 4, 0, 0]}>
              {data.map((point) => (
                <Cell key={point.label} fill={point.latency_ms > LATENCY_SLA_MS ? "#ef4444" : "#06b6d4"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Card>
    </div>
  );
}
