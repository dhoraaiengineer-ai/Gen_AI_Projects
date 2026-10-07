"use client";

import { useAnalytics } from "@/hooks/use-api";
import { PageHeader } from "@/components/layout/app-shell";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CHART, TrendChart } from "@/components/charts";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { ChartSkeleton, ErrorState, KpiSkeleton } from "@/components/shared/states";
import { fmt } from "@/lib/utils";

function ChartCard({ title, description, children, className }: { title: string; description: string; children: React.ReactNode; className?: string }) {
  return (
    <Card className={className}>
      <CardHeader>
        <div>
          <CardTitle>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </div>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

export default function AnalyticsPage() {
  const { data, error, refetch } = useAnalytics();

  if (error) {
    return (
      <>
        <PageHeader title="Executive analytics" />
        <Card>
          <ErrorState error={error} what="analytics" onRetry={() => refetch()} />
        </Card>
      </>
    );
  }

  return (
    <>
      <PageHeader title="Executive analytics" description={`Business impact of AI-assisted supply-chain decisions · ${data?.period ?? "Last 12 months"}`} />
      <section aria-label="Headline metrics" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {data ? data.headline.map((k) => <KpiCard key={k.id} kpi={k} />) : [0, 1, 2, 3].map((i) => <KpiSkeleton key={i} />)}
      </section>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <ChartCard title="Cost savings" description="Monthly procurement savings and expedite costs avoided">
          {data ? <TrendChart ariaLabel="Monthly cost savings" data={data.costSavings} xKey="label" format={fmt.usd} yFormat={fmt.usdCompact} legend={false} series={[{ key: "value", name: "Savings", color: CHART.success }]} /> : <ChartSkeleton />}
        </ChartCard>
        <ChartCard title="Stockout reduction" description="Stockout events per month vs. pre-AI baseline">
          {data ? (
            <TrendChart
              ariaLabel="Stockouts with AI versus baseline"
              data={data.stockouts}
              xKey="label"
              series={[
                { key: "baseline", name: "Baseline", color: CHART.tertiary, type: "line", dashed: true },
                { key: "withAi", name: "With AI", color: CHART.primary, type: "bar" },
              ]}
            />
          ) : (
            <ChartSkeleton />
          )}
        </ChartCard>
        <ChartCard title="Forecast accuracy" description="1 − weighted MAPE, 30-day horizon, against the 90% target">
          {data ? (
            <TrendChart
              ariaLabel="Forecast accuracy trend"
              data={data.forecastAccuracy}
              xKey="label"
              format={(v) => `${v.toFixed(1)}%`}
              yFormat={(v) => `${v}%`}
              legend={false}
              referenceY={{ value: 90, label: "Target 90%" }}
              series={[{ key: "accuracy", name: "Accuracy", color: CHART.primary, type: "line" }]}
            />
          ) : (
            <ChartSkeleton />
          )}
        </ChartCard>
        <ChartCard title="Delivery performance" description="Inbound deliveries on time vs. late">
          {data ? (
            <TrendChart
              ariaLabel="On-time versus late deliveries"
              data={data.deliveryPerformance}
              xKey="label"
              series={[
                { key: "onTime", name: "On time", color: CHART.primary, type: "bar", stackId: "d" },
                { key: "late", name: "Late", color: CHART.warning, type: "bar", stackId: "d" },
              ]}
            />
          ) : (
            <ChartSkeleton />
          )}
        </ChartCard>
        <ChartCard title="AI recommendations" description="Recommendations issued, automated and escalated to a human">
          {data ? (
            <TrendChart
              ariaLabel="AI recommendations, automated versus escalated"
              data={data.aiUsage}
              xKey="label"
              series={[
                { key: "automated", name: "Automated", color: CHART.primary, type: "bar", stackId: "u" },
                { key: "escalated", name: "Escalated to human", color: CHART.tertiary, type: "bar", stackId: "u" },
              ]}
            />
          ) : (
            <ChartSkeleton />
          )}
        </ChartCard>
        <ChartCard title="Supplier performance" description="On-time delivery rate by supplier, last 12 months">
          {data ? (
            <ul className="space-y-3 pt-1">
              {data.supplierPerformance.map((s) => (
                <li key={s.supplier} className="grid grid-cols-[96px_1fr_64px] items-center gap-3 text-[12.5px]">
                  <span className="truncate text-muted-foreground">{s.supplier}</span>
                  <div className="h-2 overflow-hidden rounded-full bg-muted">
                    <div className={s.onTime >= 95 ? "h-full rounded-full bg-success" : s.onTime >= 90 ? "h-full rounded-full bg-chart-1" : "h-full rounded-full bg-warning"} style={{ width: `${s.onTime}%` }} />
                  </div>
                  <span className="text-right font-medium tabular">{s.onTime}%</span>
                </li>
              ))}
            </ul>
          ) : (
            <ChartSkeleton />
          )}
        </ChartCard>
      </div>
    </>
  );
}
