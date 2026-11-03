"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Legend,
} from "recharts";

export interface EvalHistoryEntry {
  label: string;
  unified_score: number;
  faithfulness: number;
}

interface EvalHistoryChartProps {
  history: EvalHistoryEntry[];
}

const TOOLTIP_STYLE = {
  backgroundColor: "hsl(var(--card))",
  borderColor: "rgba(15,23,42,0.1)",
  borderRadius: "6px",
  fontSize: "12px",
  color: "var(--text-1)",
};

export function EvalHistoryChart({ history }: EvalHistoryChartProps) {
  if (history.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center rounded-lg border border-border bg-accent/5">
        <p className="text-sm text-text-3">No evaluation history yet</p>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={history} margin={{ top: 4, right: 16, left: -8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(15,23,42,0.1)" />
        <XAxis
          dataKey="label"
          stroke="var(--text-3)"
          tick={{ fontSize: 11, fill: "var(--text-3)" }}
        />
        <YAxis
          domain={[0, 1]}
          stroke="var(--text-3)"
          tick={{ fontSize: 11, fill: "var(--text-3)" }}
          tickFormatter={(v: number) => v.toFixed(1)}
        />
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        <Legend
          wrapperStyle={{ fontSize: "11px", color: "var(--text-3)" }}
        />

        {/* Deployment gate line */}
        <ReferenceLine
          y={0.85}
          stroke="#10b981"
          strokeDasharray="4 2"
          label={{ value: "Gate 0.85", position: "insideTopRight", fontSize: 10, fill: "#10b981" }}
        />
        {/* Faithfulness hard-block line */}
        <ReferenceLine
          y={0.5}
          stroke="#ef4444"
          strokeDasharray="4 2"
          label={{ value: "Block 0.50", position: "insideTopRight", fontSize: 10, fill: "#ef4444" }}
        />

        <Line
          type="monotone"
          dataKey="unified_score"
          name="Unified Score"
          stroke="#F59E0B"
          strokeWidth={2}
          dot={{ r: 3, fill: "#F59E0B" }}
          activeDot={{ r: 5 }}
        />
        <Line
          type="monotone"
          dataKey="faithfulness"
          name="Faithfulness"
          stroke="#06b6d4"
          strokeWidth={1.5}
          dot={{ r: 2, fill: "#06b6d4" }}
          strokeDasharray="4 2"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
