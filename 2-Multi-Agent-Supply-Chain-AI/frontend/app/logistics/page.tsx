"use client";

import { useState } from "react";
import { AlertTriangle, CheckCircle2, Clock, MapPin, Plane, Search, Ship, TrainFront, Truck, Package } from "lucide-react";
import type { ShipmentStatus, TransportMode } from "@/types";
import { useLogisticsSummary, useShipments } from "@/hooks/use-api";
import { PageHeader } from "@/components/layout/app-shell";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Segmented, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/data";
import { Progress, Switch, Label } from "@/components/ui/primitives";
import { CHART, Sparkline, TrendChart } from "@/components/charts";
import { Stat } from "@/components/shared/stat";
import { ChartSkeleton, EmptyState, ErrorState, TableSkeleton } from "@/components/shared/states";
import { cn, fmt, formatDate } from "@/lib/utils";

const MODE_ICON: Record<TransportMode, typeof Ship> = { ocean: Ship, air: Plane, road: Truck, rail: TrainFront };

const STATUS: Record<ShipmentStatus, { label: string; className: string; icon: typeof Clock }> = {
  in_transit: { label: "In transit", className: "bg-info/10 text-info ring-info/20", icon: Truck },
  delayed: { label: "Delayed", className: "bg-critical/10 text-critical ring-critical/20", icon: AlertTriangle },
  at_customs: { label: "At customs", className: "bg-warning/10 text-warning-foreground ring-warning/25", icon: Clock },
  pending: { label: "Pending pickup", className: "bg-muted text-muted-foreground ring-border", icon: Package },
  delivered: { label: "Delivered", className: "bg-success/10 text-success ring-success/20", icon: CheckCircle2 },
};

const FILTERS: { value: ShipmentStatus | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "delayed", label: "Delayed" },
  { value: "in_transit", label: "In transit" },
  { value: "at_customs", label: "Customs" },
  { value: "delivered", label: "Delivered" },
];

function StatusPill({ status }: { status: ShipmentStatus }) {
  const s = STATUS[status];
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium ring-1 ring-inset", s.className)}>
      <s.icon className="size-3" aria-hidden />
      {s.label}
    </span>
  );
}

/** Lane view — an optional, compact alternative to a full map so geography never dominates the page. */
function LaneMap({ lanes }: { lanes: { origin: string; destination: string; shipments: number; delayed: number }[] }) {
  const max = Math.max(...lanes.map((l) => l.shipments), 1);
  return (
    <ul className="space-y-3">
      {lanes.map((l) => (
        <li key={`${l.origin}-${l.destination}`} className="text-[12.5px]">
          <div className="flex items-center justify-between gap-2">
            <span className="flex min-w-0 items-center gap-1.5">
              <MapPin className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
              <span className="truncate">
                {l.origin} <span className="text-muted-foreground">→</span> {l.destination}
              </span>
            </span>
            <span className="shrink-0 tabular">
              {l.shipments}
              {l.delayed > 0 && <span className="ml-1.5 font-medium text-critical">{l.delayed} delayed</span>}
            </span>
          </div>
          <div className="mt-1 flex h-1.5 overflow-hidden rounded-full bg-muted">
            <div className="bg-chart-1" style={{ width: `${((l.shipments - l.delayed) / max) * 100}%` }} />
            <div className="bg-critical" style={{ width: `${(l.delayed / max) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

export default function LogisticsPage() {
  const [status, setStatus] = useState<ShipmentStatus | "all">("delayed");
  const [search, setSearch] = useState("");
  const [showLanes, setShowLanes] = useState(true);
  const summary = useLogisticsSummary();
  const shipments = useShipments(status, search);
  const s = summary.data;

  return (
    <>
      <PageHeader title="Logistics" description="Shipment visibility, delays, carrier performance and delivery forecast." />

      <section aria-label="Logistics summary" className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Active shipments" value={s && fmt.int(s.active)} hint={s && `${fmt.usdCompact(s.inTransitValue)} in transit`} icon={Truck} loading={summary.isLoading} />
        <Stat label="Delayed" value={s && fmt.int(s.delayed)} hint={s && `Avg delay ${s.avgDelayDays} days`} icon={AlertTriangle} tone="critical" loading={summary.isLoading} />
        <Stat label="On-time delivery" value={s && fmt.pct(s.onTimeRate, 1)} hint="Last 30 days · target 95%" icon={CheckCircle2} tone="success" loading={summary.isLoading} />
        <Stat label="Carriers" value={s && String(s.carriers.length)} hint="Ocean, air, road and rail" icon={Ship} loading={summary.isLoading} />
      </section>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card className={cn(showLanes ? "lg:col-span-2" : "lg:col-span-3")}>
          <CardHeader>
            <div>
              <CardTitle>Delivery forecast</CardTitle>
              <CardDescription>Expected arrivals over the next 14 days, and arrivals at risk</CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Switch id="lanes" checked={showLanes} onCheckedChange={setShowLanes} />
              <Label htmlFor="lanes" className="text-xs text-muted-foreground">
                Lane view
              </Label>
            </div>
          </CardHeader>
          <CardContent>
            {s ? (
              <TrendChart
                ariaLabel="Expected deliveries over the next 14 days"
                data={s.deliveryForecast}
                xKey="label"
                height={250}
                series={[
                  { key: "expected", name: "Expected arrivals", color: CHART.primary, type: "bar", stackId: "a" },
                  { key: "atRisk", name: "At risk", color: CHART.critical, type: "bar", stackId: "a" },
                ]}
              />
            ) : summary.error ? (
              <ErrorState error={summary.error} what="logistics data" onRetry={() => summary.refetch()} />
            ) : (
              <ChartSkeleton />
            )}
          </CardContent>
        </Card>
        {showLanes && (
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Active lanes</CardTitle>
                <CardDescription>Shipments by route</CardDescription>
              </div>
            </CardHeader>
            <CardContent>{s ? <LaneMap lanes={s.lanes} /> : <ChartSkeleton className="h-56" />}</CardContent>
          </Card>
        )}
      </div>

      <Card className="mt-6">
        <CardHeader>
          <div>
            <CardTitle>Carrier performance</CardTitle>
            <CardDescription>On-time rate, transit time and cost per carrier</CardDescription>
          </div>
        </CardHeader>
        {s ? (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Carrier</TableHead>
                <TableHead>Mode</TableHead>
                <TableHead className="text-right">On-time</TableHead>
                <TableHead className="text-right">Avg transit</TableHead>
                <TableHead className="text-right">Cost / kg</TableHead>
                <TableHead className="text-right">Active</TableHead>
                <TableHead>12-month trend</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {[...s.carriers]
                .sort((a, b) => b.onTimeRate - a.onTimeRate)
                .map((c) => {
                  const Icon = MODE_ICON[c.mode];
                  return (
                    <TableRow key={c.carrier}>
                      <TableCell className="font-medium">{c.carrier}</TableCell>
                      <TableCell>
                        <span className="inline-flex items-center gap-1.5 text-muted-foreground capitalize">
                          <Icon className="size-3.5" aria-hidden /> {c.mode}
                        </span>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="ml-auto flex w-32 items-center gap-2">
                          <Progress value={c.onTimeRate * 100} className="h-1" indicatorClassName={c.onTimeRate >= 0.93 ? "bg-success" : c.onTimeRate >= 0.88 ? "bg-chart-1" : "bg-warning"} aria-label={`On-time ${fmt.pct(c.onTimeRate)}`} />
                          <span className="w-10 text-right font-medium tabular">{fmt.pct(c.onTimeRate)}</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-right tabular">{c.avgTransitDays} d</TableCell>
                      <TableCell className="text-right tabular">{fmt.price(c.costPerKg)}</TableCell>
                      <TableCell className="text-right tabular">{c.activeShipments}</TableCell>
                      <TableCell>
                        <Sparkline data={c.trend} className="w-24" height={24} />
                      </TableCell>
                    </TableRow>
                  );
                })}
            </TableBody>
          </Table>
        ) : (
          <TableSkeleton rows={6} cols={6} />
        )}
      </Card>

      <Card className="mt-6">
        <CardHeader className="pb-3">
          <div>
            <CardTitle>Shipments</CardTitle>
            <CardDescription>Inbound purchase-order shipments</CardDescription>
          </div>
        </CardHeader>
        <div className="flex flex-col gap-2 border-b px-5 py-3 sm:flex-row sm:items-center">
          <div className="relative sm:w-72">
            <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
            <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Shipment, SKU, carrier, route" className="pl-8" aria-label="Search shipments" />
          </div>
          <Segmented label="Filter by status" value={status} onChange={setStatus} options={FILTERS} className="sm:ml-auto" />
        </div>
        {shipments.isLoading ? (
          <TableSkeleton rows={8} cols={7} />
        ) : shipments.error ? (
          <ErrorState error={shipments.error} what="shipments" onRetry={() => shipments.refetch()} />
        ) : !shipments.data?.length ? (
          <EmptyState
            tone={status === "delayed" ? "positive" : "neutral"}
            title={status === "delayed" ? "No delayed shipments." : "No shipments match"}
            description={status === "delayed" ? "All inbound shipments are on schedule." : "Try a different search or status filter."}
            action={{ label: "Show all shipments", onClick: () => { setStatus("all"); setSearch(""); } }}
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Shipment</TableHead>
                <TableHead>SKU</TableHead>
                <TableHead>Route</TableHead>
                <TableHead>Carrier</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Progress</TableHead>
                <TableHead className="text-right">ETA</TableHead>
                <TableHead>Latest event</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {shipments.data.slice(0, 40).map((x) => {
                const Icon = MODE_ICON[x.mode];
                return (
                  <TableRow key={x.id}>
                    <TableCell>
                      <p className="font-mono text-xs font-medium">{x.id}</p>
                      <p className="font-mono text-[11px] text-muted-foreground">{x.poNumber}</p>
                    </TableCell>
                    <TableCell>
                      <p className="font-mono text-xs">{x.sku}</p>
                      <p className="max-w-40 truncate text-[11.5px] text-muted-foreground">{x.product}</p>
                    </TableCell>
                    <TableCell className="text-[12.5px]">
                      {x.origin} <span className="text-muted-foreground">→</span> {x.destination}
                    </TableCell>
                    <TableCell>
                      <span className="inline-flex items-center gap-1.5 text-[12.5px]">
                        <Icon className="size-3.5 text-muted-foreground" aria-hidden />
                        {x.carrier}
                      </span>
                    </TableCell>
                    <TableCell>
                      <StatusPill status={x.status} />
                    </TableCell>
                    <TableCell>
                      <Progress value={x.progress} className="h-1 w-20" indicatorClassName={x.status === "delayed" ? "bg-critical" : x.status === "delivered" ? "bg-success" : "bg-chart-1"} aria-label={`${x.progress}% complete`} />
                    </TableCell>
                    <TableCell className="text-right">
                      <p className="tabular">{formatDate(x.eta)}</p>
                      {x.delayDays > 0 && <p className="text-[11px] font-medium text-critical">+{x.delayDays}d late</p>}
                    </TableCell>
                    <TableCell className="max-w-60 truncate text-[12.5px] text-muted-foreground">{x.lastEvent}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </Card>
    </>
  );
}
