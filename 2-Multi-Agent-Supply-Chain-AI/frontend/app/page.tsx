"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { useActivity, useOverview, usePendingApprovals } from "@/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/primitives";
import { CHART, TrendChart } from "@/components/charts";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { HealthCard, Hero, RecommendationsCard, RiskList } from "@/components/dashboard/overview-sections";
import { ActivityFeed } from "@/components/activity/activity-feed";
import { ApprovalCard } from "@/components/copilot/approval-card";
import { ChartSkeleton, ErrorState, KpiSkeleton, ListSkeleton } from "@/components/shared/states";
import { StatusDot } from "@/components/shared/status";

export default function OverviewPage() {
  const overview = useOverview();
  const activity = useActivity();
  const approvals = usePendingApprovals();
  const data = overview.data;

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Hero />
        </div>
        {data ? (
          <HealthCard score={data.healthScore} dimensions={data.healthDimensions} />
        ) : (
          <Card className="p-5">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="mx-auto mt-6 size-28 rounded-full" />
            <div className="mt-6 space-y-3">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-3 w-full" />
              ))}
            </div>
          </Card>
        )}
      </div>

      {overview.error ? (
        <Card>
          <ErrorState error={overview.error} what="the dashboard" onRetry={() => overview.refetch()} />
        </Card>
      ) : (
        <section aria-label="Key metrics" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {data ? data.kpis.map((k) => <KpiCard key={k.id} kpi={k} />) : [0, 1, 2, 3].map((i) => <KpiSkeleton key={i} />)}
        </section>
      )}

      {!!approvals.data?.length && (
        <section aria-label="Pending approvals" className="space-y-3">
          {approvals.data.slice(0, 1).map((a) => (
            <ApprovalCard key={a.id} approval={a} compact />
          ))}
        </section>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          {data ? (
            <RiskList items={data.topRisks} />
          ) : (
            <Card>
              <ListSkeleton rows={5} />
            </Card>
          )}
        </div>
        {data ? (
          <RecommendationsCard items={data.recommendations} />
        ) : (
          <Card>
            <ListSkeleton rows={3} />
          </Card>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <div>
              <CardTitle>Supply vs. demand</CardTitle>
              <CardDescription>Monthly units across all distribution centres</CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            {data ? (
              <TrendChart
                ariaLabel="Monthly supply versus demand"
                data={data.supplyDemand}
                xKey="label"
                height={280}
                series={[
                  { key: "supply", name: "Supply", color: CHART.primary },
                  { key: "demand", name: "Demand", color: CHART.warning, type: "line" },
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
              <CardTitle className="flex items-center gap-2">
                Agent activity <StatusDot tone="success" pulse label="" />
              </CardTitle>
              <CardDescription>Live from your agent workforce</CardDescription>
            </div>
            <Button asChild variant="ghost" size="xs">
              <Link href="/activity">
                All <ArrowRight />
              </Link>
            </Button>
          </CardHeader>
          <CardContent className="max-h-[332px] overflow-hidden">
            {activity.data ? <ActivityFeed events={activity.data.slice(0, 6)} compact /> : activity.error ? <ErrorState error={activity.error} what="activity" onRetry={() => activity.refetch()} /> : <ListSkeleton rows={5} />}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
