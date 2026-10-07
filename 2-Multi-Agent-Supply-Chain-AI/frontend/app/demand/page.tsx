"use client";

import { useState } from "react";
import Link from "next/link";
import { Activity, CalendarRange, Gauge, Sparkles, Target, TrendingDown, TrendingUp, Minus } from "lucide-react";
import type { ForecastHorizon } from "@/types";
import { useDemandForecast, useForecastableSkus } from "@/hooks/use-api";
import { PageHeader } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Segmented, Select } from "@/components/ui/data";
import { ForecastChart } from "@/components/charts";
import { Stat } from "@/components/shared/stat";
import { ChartSkeleton, ErrorState } from "@/components/shared/states";
import { cn, fmt } from "@/lib/utils";

const HORIZONS: { value: ForecastHorizon; label: string }[] = [
  { value: "7d", label: "7 Days" },
  { value: "30d", label: "30 Days" },
  { value: "90d", label: "90 Days" },
  { value: "6m", label: "6 Months" },
  { value: "1y", label: "1 Year" },
];

export default function DemandPage() {
  const [sku, setSku] = useState("SKU-100");
  const [horizon, setHorizon] = useState<ForecastHorizon>("30d");
  const skus = useForecastableSkus();
  const { data, isLoading, isFetching, error, refetch } = useDemandForecast(sku, horizon);
  const TrendIcon = data?.trend.direction === "up" ? TrendingUp : data?.trend.direction === "down" ? TrendingDown : Minus;
  const maxIndex = data ? Math.max(...data.seasonality.weekdayIndex.map((w) => w.index)) : 1;

  return (
    <>
      <PageHeader
        title="Demand forecast"
        description="Historical demand, statistical forecasts with confidence intervals, trend and seasonality."
        actions={
          <>
            <Select
              label="Select SKU"
              value={sku}
              onValueChange={setSku}
              className="w-72"
              options={(skus.data ?? [{ sku: "SKU-100", name: "Lithium-Ion Battery Pack 48V" }]).map((s) => ({ value: s.sku, label: `${s.sku} · ${s.name}` }))}
            />
            <Segmented label="Forecast horizon" value={horizon} onChange={setHorizon} options={HORIZONS} />
          </>
        }
      />

      <section aria-label="Forecast summary" className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat
          label="Forecast demand"
          value={data && fmt.int(data.totalForecast)}
          hint={data && `units over ${HORIZONS.find((h) => h.value === horizon)?.label.toLowerCase()}`}
          icon={CalendarRange}
          tone="ai"
          loading={isLoading}
        />
        <Stat label="Average daily demand" value={data && fmt.int(data.dailyMean)} hint="units per day" icon={Activity} loading={isLoading} />
        <Stat
          label="Trend"
          value={data && fmt.signedPct(data.trend.pctChange)}
          hint={data && `Demand trending ${data.trend.direction}`}
          icon={TrendIcon}
          tone={data?.trend.direction === "up" ? "warning" : "neutral"}
          loading={isLoading}
        />
        <Stat
          label="Forecast accuracy"
          value={data && `${(100 - data.accuracy.mape).toFixed(1)}%`}
          hint={data && `MAPE ${data.accuracy.mape}% · bias ${fmt.signedPct(data.accuracy.bias)}`}
          icon={Target}
          tone="success"
          loading={isLoading}
        />
      </section>

      <Card className="mt-6">
        <CardHeader>
          <div>
            <CardTitle>{data ? `${data.sku} · ${data.name}` : "Forecast"}</CardTitle>
            <CardDescription>{data ? `${data.method} · 80% confidence interval` : "Loading forecast…"}</CardDescription>
          </div>
          {data && (
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset",
                data.confidence === "high" ? "bg-success/10 text-success ring-success/20" : data.confidence === "medium" ? "bg-warning/10 text-warning-foreground ring-warning/25" : "bg-critical/10 text-critical ring-critical/20",
              )}
            >
              <Gauge className="size-3.5" aria-hidden /> {data.confidence[0].toUpperCase() + data.confidence.slice(1)} confidence
            </span>
          )}
        </CardHeader>
        <CardContent className={cn("transition-opacity", isFetching && !isLoading && "opacity-60")}>
          {error ? <ErrorState error={error} what="the forecast" onRetry={() => refetch()} /> : data ? <ForecastChart points={data.points} height={340} /> : <ChartSkeleton className="h-80" />}
        </CardContent>
      </Card>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Seasonality</CardTitle>
              <CardDescription>{data?.seasonality.detected ? `Weekly cycle detected (${data.seasonality.periodDays}-day period)` : "Day-of-week demand index"}</CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            {data ? (
              <div className="flex h-40 items-end gap-2" role="img" aria-label="Day-of-week demand index">
                {data.seasonality.weekdayIndex.map((w) => (
                  <div key={w.day} className="flex flex-1 flex-col items-center gap-1.5">
                    <span className="text-[11px] font-medium tabular">{w.index.toFixed(2)}</span>
                    <div className={cn("w-full rounded-t-sm", w.index >= 1 ? "bg-chart-1" : "bg-chart-3")} style={{ height: `${(w.index / maxIndex) * 100}px` }} />
                    <span className="text-[11px] text-muted-foreground">{w.day}</span>
                  </div>
                ))}
              </div>
            ) : (
              <ChartSkeleton className="h-40" />
            )}
          </CardContent>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader>
            <div>
              <CardTitle className="flex items-center gap-1.5">
                <Sparkles className="size-4 text-ai" aria-hidden /> Demand drivers
              </CardTitle>
              <CardDescription>Summary from the Demand Forecast Agent</CardDescription>
            </div>
            <Button asChild variant="outline" size="sm">
              <Link href={`/copilot?q=${encodeURIComponent(`How much should we reorder for ${sku}?`)}`}>
                <Sparkles className="text-ai" /> Plan replenishment
              </Link>
            </Button>
          </CardHeader>
          <CardContent>
            {data ? (
              <ul className="space-y-3">
                {data.drivers.map((d) => (
                  <li key={d} className="flex gap-3 rounded-md border bg-muted/30 px-3.5 py-3 text-[13.5px]">
                    <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-ai" aria-hidden />
                    {d}
                  </li>
                ))}
              </ul>
            ) : (
              <ChartSkeleton className="h-32" />
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
