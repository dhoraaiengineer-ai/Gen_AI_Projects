"use client";

import { useId } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ForecastPoint } from "@/types";
import { cn, fmt, formatDate } from "@/lib/utils";

export const CHART = {
  primary: "var(--chart-1)",
  secondary: "var(--chart-2)",
  tertiary: "var(--chart-3)",
  success: "var(--chart-4)",
  warning: "var(--chart-5)",
  critical: "var(--critical)",
  muted: "var(--muted-foreground)",
};

type Formatter = (v: number) => string;
// eslint-disable-next-line @typescript-eslint/no-explicit-any -- chart rows are heterogeneous records
type ChartRow = Record<string, any>;

interface TooltipPayload {
  name?: string;
  value?: number | [number, number];
  color?: string;
  dataKey?: string | number;
}

/** Consistent tooltip card for every chart. */
function ChartTooltip({
  active,
  payload,
  label,
  format = fmt.int,
  labelFormat,
}: {
  active?: boolean;
  payload?: TooltipPayload[];
  label?: string | number;
  format?: Formatter;
  labelFormat?: (l: string) => string;
}) {
  if (!active || !payload?.length) return null;
  const rows = payload.filter((p) => p.value !== undefined && p.value !== null && p.dataKey !== "band");
  return (
    <div className="min-w-36 rounded-lg border bg-popover px-3 py-2 text-xs shadow-raised">
      <p className="mb-1.5 font-medium text-foreground">{labelFormat ? labelFormat(String(label)) : label}</p>
      <div className="space-y-1">
        {rows.map((p) => (
          <div key={String(p.dataKey)} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5 text-muted-foreground">
              <span className="size-2 rounded-full" style={{ background: p.color }} />
              {p.name}
            </span>
            <span className="font-medium tabular text-foreground">{typeof p.value === "number" ? format(p.value) : "—"}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

const axisProps = { tickLine: false, axisLine: false, tickMargin: 8 } as const;

/** Tiny inline trend line for KPI cards and tables. */
export function Sparkline({ data, color = CHART.primary, className, height = 32 }: { data: number[]; color?: string; className?: string; height?: number }) {
  const id = useId().replace(/:/g, "");
  const points = data.map((value, i) => ({ i, value }));
  return (
    <div className={cn("w-full", className)} style={{ height }} aria-hidden>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={points} margin={{ top: 2, right: 0, bottom: 2, left: 0 }}>
          <defs>
            <linearGradient id={`spark-${id}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.18} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <YAxis hide domain={["dataMin", "dataMax"]} />
          <Area type="monotone" dataKey="value" stroke={color} strokeWidth={1.5} fill={`url(#spark-${id})`} isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export interface SeriesDef {
  key: string;
  name: string;
  color: string;
  type?: "area" | "line" | "bar";
  dashed?: boolean;
  stackId?: string;
}

/** General time-series chart: areas, lines and bars on one axis. */
export function TrendChart({
  data,
  xKey,
  series,
  height = 260,
  format = fmt.int,
  yFormat,
  legend = true,
  referenceY,
  ariaLabel,
}: {
  data: ChartRow[];
  xKey: string;
  series: SeriesDef[];
  height?: number;
  format?: Formatter;
  yFormat?: Formatter;
  legend?: boolean;
  referenceY?: { value: number; label: string };
  ariaLabel: string;
}) {
  const id = useId().replace(/:/g, "");
  return (
    <div role="img" aria-label={ariaLabel} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <defs>
            {series
              .filter((s) => (s.type ?? "area") === "area")
              .map((s) => (
                <linearGradient key={s.key} id={`fill-${id}-${s.key}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={s.color} stopOpacity={0.16} />
                  <stop offset="100%" stopColor={s.color} stopOpacity={0.01} />
                </linearGradient>
              ))}
          </defs>
          <CartesianGrid vertical={false} />
          <XAxis dataKey={xKey} {...axisProps} minTickGap={16} />
          <YAxis {...axisProps} width={52} tickFormatter={(v: number) => (yFormat ?? fmt.compact)(v)} />
          <Tooltip content={<ChartTooltip format={format} />} cursor={{ stroke: "var(--border)" }} />
          {legend && <Legend iconType="circle" iconSize={7} wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />}
          {referenceY && (
            <ReferenceLine y={referenceY.value} stroke={CHART.muted} strokeDasharray="4 4" label={{ value: referenceY.label, position: "insideTopRight", fontSize: 11, fill: CHART.muted }} />
          )}
          {series.map((s) => {
            const type = s.type ?? "area";
            if (type === "bar")
              return <Bar key={s.key} dataKey={s.key} name={s.name} fill={s.color} stackId={s.stackId} radius={s.stackId ? 0 : [3, 3, 0, 0]} maxBarSize={28} />;
            if (type === "line")
              return <Line key={s.key} dataKey={s.key} name={s.name} stroke={s.color} strokeWidth={2} dot={false} strokeDasharray={s.dashed ? "5 4" : undefined} type="monotone" />;
            return (
              <Area key={s.key} dataKey={s.key} name={s.name} stroke={s.color} strokeWidth={2} fill={`url(#fill-${id}-${s.key})`} type="monotone" strokeDasharray={s.dashed ? "5 4" : undefined} />
            );
          })}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Horizontal bar list — for category breakdowns where labels are long. */
export function HorizontalBars({
  data,
  labelKey,
  valueKey,
  color = CHART.primary,
  format = fmt.int,
  height = 240,
  ariaLabel,
}: {
  data: ChartRow[];
  labelKey: string;
  valueKey: string;
  color?: string;
  format?: Formatter;
  height?: number;
  ariaLabel: string;
}) {
  return (
    <div role="img" aria-label={ariaLabel} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid horizontal={false} />
          <XAxis type="number" {...axisProps} tickFormatter={(v: number) => fmt.compact(v)} />
          <YAxis type="category" dataKey={labelKey} {...axisProps} width={128} interval={0} />
          <Tooltip content={<ChartTooltip format={format} />} cursor={{ fill: "var(--muted)" }} />
          <Bar dataKey={valueKey} name="Value" fill={color} radius={[0, 3, 3, 0]} maxBarSize={18} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Historical actuals + forecast with a shaded confidence interval and a "today" marker. */
export function ForecastChart({ points, height = 320 }: { points: ForecastPoint[]; height?: number }) {
  const id = useId().replace(/:/g, "");
  const data = points.map((p) => ({ ...p, band: p.lower !== undefined && p.upper !== undefined ? [p.lower, p.upper] : undefined }));
  const today = points.find((p) => p.forecast !== undefined && p.actual !== undefined)?.date;
  return (
    <div role="img" aria-label="Historical demand and forecast with confidence interval" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 12, right: 8, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={`hist-${id}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={CHART.secondary} stopOpacity={0.18} />
              <stop offset="100%" stopColor={CHART.secondary} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="date" {...axisProps} minTickGap={40} tickFormatter={(d: string) => formatDate(d)} />
          <YAxis {...axisProps} width={48} tickFormatter={(v: number) => fmt.compact(v)} />
          <Tooltip content={<ChartTooltip labelFormat={(d) => formatDate(d, { weekday: "short", month: "short", day: "numeric" })} />} cursor={{ stroke: "var(--border)" }} />
          <Legend iconType="circle" iconSize={7} wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
          <Area dataKey="band" name="80% confidence" stroke="none" fill={CHART.primary} fillOpacity={0.1} type="monotone" legendType="square" />
          <Area dataKey="actual" name="Historical" stroke={CHART.secondary} strokeWidth={1.5} fill={`url(#hist-${id})`} type="monotone" dot={false} />
          <Line dataKey="forecast" name="Forecast" stroke={CHART.primary} strokeWidth={2} strokeDasharray="5 4" dot={false} type="monotone" />
          {today && <ReferenceLine x={today} stroke={CHART.muted} strokeDasharray="3 3" label={{ value: "Today", position: "insideTopLeft", fontSize: 11, fill: CHART.muted }} />}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Simple multi-line chart (e.g. carrier on-time trends). */
export function MultiLine({
  data,
  xKey,
  series,
  height = 220,
  format = fmt.int,
  ariaLabel,
}: {
  data: ChartRow[];
  xKey: string;
  series: SeriesDef[];
  height?: number;
  format?: Formatter;
  ariaLabel: string;
}) {
  return (
    <div role="img" aria-label={ariaLabel} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey={xKey} {...axisProps} />
          <YAxis {...axisProps} width={40} domain={["auto", "auto"]} />
          <Tooltip content={<ChartTooltip format={format} />} />
          <Legend iconType="circle" iconSize={7} wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
          {series.map((s) => (
            <Line key={s.key} dataKey={s.key} name={s.name} stroke={s.color} strokeWidth={2} dot={false} type="monotone" />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
