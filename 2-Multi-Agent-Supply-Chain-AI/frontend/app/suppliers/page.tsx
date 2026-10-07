"use client";

import { useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { BadgeCheck, CalendarClock, Sparkles } from "lucide-react";
import type { Supplier, SupplierSort } from "@/types";
import { useSupplierRecommendation, useSuppliers } from "@/hooks/use-api";
import { PageHeader } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Segmented } from "@/components/ui/data";
import { Progress, Skeleton } from "@/components/ui/primitives";
import { Sparkline, CHART } from "@/components/charts";
import { EmptyState, ErrorState } from "@/components/shared/states";
import { RiskBadge } from "@/components/shared/status";
import { cn, fmt } from "@/lib/utils";

const SORTS: { value: SupplierSort; label: string }[] = [
  { value: "score", label: "Overall" },
  { value: "price", label: "Price" },
  { value: "leadTime", label: "Lead time" },
  { value: "reliability", label: "Reliability" },
  { value: "risk", label: "Risk" },
];

const SCOPES = [
  { value: "SKU-100", label: "SKU-100 quotes" },
  { value: "all", label: "All suppliers" },
] as const;

function daysUntil(iso: string) {
  return Math.round((new Date(iso).getTime() - Date.now()) / 86_400_000);
}

function SupplierCard({ s, recommended, rank }: { s: Supplier; recommended: boolean; rank: number }) {
  const expiresIn = daysUntil(s.contractExpiry);
  return (
    <motion.article
      layout
      transition={{ duration: 0.25 }}
      className={cn(
        "relative flex flex-col rounded-lg border bg-card p-5 shadow-card transition-shadow hover:shadow-raised",
        recommended && "border-ai/50 ring-1 ring-ai/20",
      )}
      aria-label={`${s.name}${recommended ? ", AI recommended" : ""}`}
    >
      {recommended && (
        <span className="absolute -top-2.5 left-4 inline-flex items-center gap-1 rounded-full bg-ai px-2 py-0.5 text-[10.5px] font-semibold text-white shadow-sm">
          <Sparkles className="size-3" aria-hidden /> AI recommended
        </span>
      )}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] text-muted-foreground tabular">
            #{rank} · {s.id}
          </p>
          <h3 className="truncate text-[15px] font-semibold tracking-tight">{s.name}</h3>
          <p className="text-xs text-muted-foreground">
            {s.country} · {s.region}
          </p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-semibold tracking-tight tabular">{s.score}</p>
          <p className="text-[10.5px] text-muted-foreground">score</p>
        </div>
      </div>

      <dl className="mt-4 space-y-2 text-[13px]">
        <div className="flex justify-between">
          <dt className="text-muted-foreground">Price</dt>
          <dd className="font-medium tabular">{fmt.price(s.unitPrice)}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-muted-foreground">Lead time</dt>
          <dd className="font-medium tabular">{s.leadTimeDays} days</dd>
        </div>
        <div>
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Reliability</dt>
            <dd className="font-medium tabular">{fmt.pct(s.reliability)}</dd>
          </div>
          <Progress value={s.reliability * 100} className="mt-1.5 h-1" indicatorClassName={s.reliability >= 0.95 ? "bg-success" : s.reliability >= 0.9 ? "bg-chart-1" : "bg-warning"} aria-label={`Reliability ${fmt.pct(s.reliability)}`} />
        </div>
        <div className="flex items-center justify-between">
          <dt className="text-muted-foreground">Risk</dt>
          <dd>
            <RiskBadge risk={s.risk} />
          </dd>
        </div>
      </dl>

      <div className="mt-4 flex items-end justify-between gap-3 border-t pt-3">
        <div className="min-w-0 space-y-1 text-[11.5px] text-muted-foreground">
          <p className="flex items-center gap-1">
            <BadgeCheck className="size-3.5 shrink-0" aria-hidden />
            <span className="truncate">{s.certifications.join(" · ")}</span>
          </p>
          <p className={cn("flex items-center gap-1", expiresIn < 90 && "font-medium text-warning-foreground")}>
            <CalendarClock className="size-3.5 shrink-0" aria-hidden />
            Contract {expiresIn < 90 ? `expires in ${expiresIn} days` : `to ${new Date(s.contractExpiry).toLocaleDateString("en-US", { month: "short", year: "numeric" })}`}
          </p>
        </div>
        <Sparkline data={s.trend} className="w-20 shrink-0" height={28} color={recommended ? CHART.primary : CHART.secondary} />
      </div>
    </motion.article>
  );
}

export default function SuppliersPage() {
  const [sort, setSort] = useState<SupplierSort>("score");
  const [scope, setScope] = useState<"SKU-100" | "all">("SKU-100");
  const sku = scope === "all" ? undefined : scope;
  const suppliers = useSuppliers(sort, sku);
  const rec = useSupplierRecommendation("SKU-100");
  const recommendedId = scope === "SKU-100" ? rec.data?.supplierId : undefined;
  const recommended = suppliers.data?.find((s) => s.id === recommendedId);

  return (
    <>
      <PageHeader
        title="Supplier intelligence"
        description="Compare suppliers on price, lead time, reliability and risk. Scores weight price 35%, lead time 30%, reliability 35%."
        actions={<Segmented label="Supplier scope" value={scope} onChange={setScope} options={[...SCOPES]} />}
      />

      {scope === "SKU-100" && (
        <Card className="mb-6 overflow-hidden border-ai/25">
          <div className="flex flex-col gap-4 bg-gradient-to-r from-ai-soft/70 to-transparent p-5 sm:flex-row sm:items-start">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-ai text-white shadow-sm">
              <Sparkles className="size-4" aria-hidden />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[11px] font-semibold tracking-wider text-ai uppercase">AI recommendation · SKU-100</p>
              {rec.isLoading ? (
                <div className="mt-2 space-y-2">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-3 w-1/2" />
                </div>
              ) : rec.error ? (
                <p className="mt-1 text-[13px] text-muted-foreground">The Supplier Agent couldn&apos;t produce a recommendation right now.</p>
              ) : (
                rec.data && (
                  <>
                    <p className="mt-1 text-[15px] leading-snug font-semibold">{rec.data.summary}</p>
                    <ul className="mt-2 grid gap-x-6 gap-y-1 sm:grid-cols-2">
                      {rec.data.reasons.map((r) => (
                        <li key={r} className="flex gap-2 text-[13px] text-muted-foreground">
                          <span className="mt-2 size-1 shrink-0 rounded-full bg-ai" aria-hidden />
                          {r}
                        </li>
                      ))}
                    </ul>
                  </>
                )
              )}
            </div>
            <div className="flex shrink-0 flex-col items-start gap-2 sm:items-end">
              {rec.data && <span className="text-xs font-medium text-success">{fmt.pct(rec.data.confidence)} confidence</span>}
              <Button asChild variant="outline" size="sm">
                <Link href={`/copilot?q=${encodeURIComponent("Which supplier should we choose for SKU-100?")}`}>Ask why</Link>
              </Button>
            </div>
          </div>
        </Card>
      )}

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-[13px] text-muted-foreground" aria-live="polite">
          {suppliers.data ? `${suppliers.data.length} suppliers${recommended ? ` · ${recommended.name} recommended` : ""}` : "Loading suppliers…"}
        </p>
        <Segmented label="Sort suppliers by" value={sort} onChange={setSort} options={SORTS} />
      </div>

      {suppliers.error ? (
        <Card>
          <ErrorState error={suppliers.error} what="supplier data" onRetry={() => suppliers.refetch()} />
        </Card>
      ) : suppliers.isLoading ? (
        <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i} className="p-5">
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="mt-2 h-3 w-1/3" />
              <div className="mt-5 space-y-3">
                {[0, 1, 2, 3].map((j) => (
                  <Skeleton key={j} className="h-3 w-full" />
                ))}
              </div>
            </Card>
          ))}
        </div>
      ) : !suppliers.data?.length ? (
        <Card>
          <EmptyState title="No suppliers found" description="No active suppliers are qualified for this scope. Onboard a supplier to start comparing." />
        </Card>
      ) : (
        <motion.div layout className="grid gap-5 pt-1 sm:grid-cols-2 xl:grid-cols-3">
          {suppliers.data.map((s, i) => (
            <SupplierCard key={s.id} s={s} rank={i + 1} recommended={s.id === recommendedId} />
          ))}
        </motion.div>
      )}
    </>
  );
}
