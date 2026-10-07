"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { AlertOctagon, Boxes, PackageCheck, RefreshCcw, ShieldAlert, Timer } from "lucide-react";
import type { RiskLevel } from "@/types";
import { useInventorySummary } from "@/hooks/use-api";
import { PageHeader } from "@/components/layout/app-shell";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CHART, HorizontalBars, TrendChart } from "@/components/charts";
import { Stat } from "@/components/shared/stat";
import { ChartSkeleton, ErrorState } from "@/components/shared/states";
import { InventoryTable } from "@/components/inventory/inventory-table";
import { RISK_STYLES } from "@/lib/constants";
import { cn, fmt } from "@/lib/utils";

function RiskDistribution({ data }: { data: { risk: RiskLevel; count: number }[] }) {
  const total = data.reduce((s, d) => s + d.count, 0);
  return (
    <div className="space-y-4">
      <div className="flex h-2.5 overflow-hidden rounded-full bg-muted" role="img" aria-label="Risk distribution">
        {data.map((d) => (
          <div key={d.risk} className={RISK_STYLES[d.risk].dot} style={{ width: `${(d.count / total) * 100}%` }} />
        ))}
      </div>
      <ul className="grid grid-cols-2 gap-3">
        {data.map((d) => (
          <li key={d.risk} className="rounded-md border px-3 py-2.5">
            <p className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
              <span className={cn("size-2 rounded-full", RISK_STYLES[d.risk].dot)} aria-hidden />
              {RISK_STYLES[d.risk].label}
            </p>
            <p className="mt-0.5 text-lg font-semibold tabular">{fmt.int(d.count)}</p>
            <p className="text-[11px] text-muted-foreground">{fmt.pct(d.count / total, 1)} of SKUs</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

function InventoryContent() {
  const params = useSearchParams();
  const { data, isLoading, error, refetch } = useInventorySummary();

  return (
    <>
      <PageHeader title="Inventory intelligence" description="Stock positions, stockout risk and reorder recommendations across all distribution centres." />

      <section aria-label="Inventory summary" className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6">
        <Stat label="Total SKUs" value={data && fmt.int(data.totalSkus)} hint={data && `${fmt.usdCompact(data.totalValue)} stock value`} icon={Boxes} loading={isLoading} />
        <Stat label="At risk" value={data && fmt.int(data.atRisk)} hint={data && `${data.critical} critical`} icon={AlertOctagon} tone="critical" loading={isLoading} />
        <Stat label="Stockout < 7 days" value={data && fmt.int(data.stockoutWithin7d)} hint="At current forecast demand" icon={ShieldAlert} tone="warning" loading={isLoading} />
        <Stat label="Reorder recommended" value={data && fmt.int(data.reorderRecommended)} hint="Below reorder point" icon={RefreshCcw} tone="ai" loading={isLoading} />
        <Stat label="Inventory turnover" value={data && `${data.avgTurnover}×`} hint="Annualised COGS / stock" icon={PackageCheck} tone="success" loading={isLoading} />
        <Stat label="Aged stock (90d+)" value={data && fmt.usdCompact(data.agedValue)} hint="Candidates for liquidation" icon={Timer} loading={isLoading} />
      </section>

      {error ? (
        <Card className="mt-6">
          <ErrorState error={error} what="inventory data" onRetry={() => refetch()} />
        </Card>
      ) : (
        <div className="mt-6 grid gap-6 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader>
              <div>
                <CardTitle>Inventory trend</CardTitle>
                <CardDescription>Stock value vs. safety-stock value, last 12 months</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              {data ? (
                <TrendChart
                  ariaLabel="Inventory value trend"
                  data={data.inventoryTrend}
                  xKey="label"
                  format={fmt.usd}
                  yFormat={fmt.usdCompact}
                  series={[
                    { key: "onHand", name: "Stock value", color: CHART.primary },
                    { key: "safetyStock", name: "Safety stock value", color: CHART.critical, type: "line", dashed: true },
                  ]}
                />
              ) : (
                <ChartSkeleton />
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Stockout risk</CardTitle>
                <CardDescription>SKUs by risk level</CardDescription>
              </div>
            </CardHeader>
            <CardContent>{data ? <RiskDistribution data={data.riskDistribution} /> : <ChartSkeleton className="h-48" />}</CardContent>
          </Card>
          <Card className="lg:col-span-2">
            <CardHeader>
              <div>
                <CardTitle>Category distribution</CardTitle>
                <CardDescription>Stock value by category</CardDescription>
              </div>
            </CardHeader>
            <CardContent>{data ? <HorizontalBars ariaLabel="Stock value by category" data={data.categoryDistribution} labelKey="category" valueKey="value" format={fmt.usd} /> : <ChartSkeleton />}</CardContent>
          </Card>
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Inventory aging</CardTitle>
                <CardDescription>Stock value by age</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              {data ? (
                <ul className="space-y-3">
                  {data.aging.map((a, i) => {
                    const max = Math.max(...data.aging.map((x) => x.value));
                    return (
                      <li key={a.bucket}>
                        <div className="mb-1 flex justify-between text-[12.5px]">
                          <span className="text-muted-foreground">{a.bucket}</span>
                          <span className="font-medium tabular">{fmt.usdCompact(a.value)}</span>
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-muted">
                          <div className={cn("h-full rounded-full", i === 3 ? "bg-warning" : "bg-chart-1")} style={{ width: `${(a.value / max) * 100}%` }} />
                        </div>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <ChartSkeleton className="h-40" />
              )}
            </CardContent>
          </Card>
        </div>
      )}

      <Card className="mt-6">
        <CardHeader className="pb-3">
          <div>
            <CardTitle>Products</CardTitle>
            <CardDescription>Sorted by risk. Select a recommendation to have the Copilot build a full replenishment plan.</CardDescription>
          </div>
        </CardHeader>
        <InventoryTable initialSearch={params.get("search") ?? ""} initialRisk={(params.get("risk") as RiskLevel | null) ?? "all"} />
      </Card>
    </>
  );
}

export default function InventoryPage() {
  return (
    <Suspense>
      <InventoryContent />
    </Suspense>
  );
}
