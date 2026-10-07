"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowRight, Sparkles } from "lucide-react";
import type { HealthDimension, InventoryItem, Recommendation } from "@/types";
import { useCurrentUser } from "@/hooks/use-api";
import { useClientValue } from "@/hooks/use-client-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/primitives";
import { Composer } from "@/components/copilot/composer";
import { SuggestedPrompts } from "@/components/copilot/copilot-panel";
import { STEP_META } from "@/components/agents/agent-meta";
import { EmptyState } from "@/components/shared/states";
import { RiskBadge } from "@/components/shared/status";
import { cn, fmt, greeting, timeAgo } from "@/lib/utils";

/** Hero: greeting + the Copilot entry point. The Copilot is the first thing the user can act on. */
export function Hero() {
  const router = useRouter();
  const { data: user } = useCurrentUser();
  // Greeting depends on the viewer's local clock, so compute it after mount (never during prerender).
  const hello = useClientValue(() => greeting(new Date()), "Welcome back");
  const ask = (q: string) => router.push(`/copilot?q=${encodeURIComponent(q)}`);
  return (
    <Card className="relative overflow-hidden">
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.55] dark:opacity-30"
        style={{
          background:
            "radial-gradient(600px 220px at 100% 0%, color-mix(in oklab, var(--ai) 9%, transparent), transparent 70%), radial-gradient(500px 200px at 0% 100%, color-mix(in oklab, var(--chart-1) 5%, transparent), transparent 70%)",
        }}
        aria-hidden
      />
      <CardContent className="relative px-6 py-6 sm:px-7">
        <p className="text-[13px] text-muted-foreground">
          {hello}
          {user ? `, ${user.name.split(" ")[0]}` : ""} 👋
        </p>
        <h1 className="mt-1 text-[22px] font-semibold tracking-tight sm:text-2xl">Your AI supply-chain command center</h1>
        <p className="mt-1.5 max-w-xl text-[13.5px] leading-relaxed text-muted-foreground">
          Monitor operations, identify risks and let AI recommend the next best action.
        </p>
        <div className="mt-5 max-w-2xl">
          <Composer onSubmit={ask} placeholder="Ask anything about your supply chain…" />
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button asChild variant="ai" size="sm">
            <Link href="/copilot">
              <Sparkles /> Ask AI Copilot
            </Link>
          </Button>
          <SuggestedPrompts onPick={ask} prompts={["Which products are at risk of stockout?", "Show delayed shipments."]} />
        </div>
      </CardContent>
    </Card>
  );
}

function healthTone(score: number) {
  return score >= 95 ? "bg-success" : score >= 90 ? "bg-chart-1" : score >= 80 ? "bg-warning" : "bg-critical";
}

/** Health score ring with its contributing dimensions. */
export function HealthCard({ score, dimensions }: { score: number; dimensions: HealthDimension[] }) {
  const radius = 44;
  const circumference = 2 * Math.PI * radius;
  return (
    <Card className="h-full">
      <CardHeader>
        <div>
          <CardTitle>Supply chain health</CardTitle>
          <CardDescription>Composite of four service dimensions</CardDescription>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-5 sm:flex-row sm:items-center lg:flex-col lg:items-stretch xl:flex-row xl:items-center">
        <div className="relative mx-auto size-[112px] shrink-0" role="img" aria-label={`Health score ${score} out of 100`}>
          <svg viewBox="0 0 112 112" className="size-full -rotate-90">
            <circle cx="56" cy="56" r={radius} fill="none" stroke="var(--muted)" strokeWidth="9" />
            <motion.circle
              cx="56"
              cy="56"
              r={radius}
              fill="none"
              stroke="var(--success)"
              strokeWidth="9"
              strokeLinecap="round"
              strokeDasharray={circumference}
              initial={{ strokeDashoffset: circumference }}
              animate={{ strokeDashoffset: circumference * (1 - score / 100) }}
              transition={{ duration: 1, ease: "easeOut" }}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-2xl font-semibold tracking-tight tabular">{score.toFixed(1)}</span>
            <span className="text-[11px] text-muted-foreground">of 100</span>
          </div>
        </div>
        <ul className="flex-1 space-y-3">
          {dimensions.map((d) => (
            <li key={d.label}>
              <div className="mb-1 flex justify-between text-[12.5px]">
                <span className="text-muted-foreground">{d.label}</span>
                <span className="font-medium tabular">{d.score.toFixed(1)}</span>
              </div>
              <Progress value={d.score} indicatorClassName={healthTone(d.score)} aria-label={`${d.label} ${d.score}`} />
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

/** Critical risks — the SKUs that need action now. */
export function RiskList({ items }: { items: InventoryItem[] }) {
  return (
    <Card className="h-full">
      <CardHeader>
        <div>
          <CardTitle>Critical risks</CardTitle>
          <CardDescription>Products that will run out before replenishment arrives</CardDescription>
        </div>
        <Button asChild variant="ghost" size="xs">
          <Link href="/inventory?risk=critical">
            View all <ArrowRight />
          </Link>
        </Button>
      </CardHeader>
      <CardContent className="px-0 pb-2">
        {!items.length ? (
          <EmptyState tone="positive" title="No inventory risks detected." description="Your inventory is currently healthy." action={{ label: "View Inventory", href: "/inventory" }} />
        ) : (
          <ul className="divide-y">
            {items.map((i) => {
              const coverPct = Math.min(100, (i.daysOfCover / i.leadTimeDays) * 100);
              return (
                <li key={i.sku} className="flex flex-col gap-2 px-5 py-3 transition-colors hover:bg-muted/40 sm:flex-row sm:items-center sm:gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs text-muted-foreground">{i.sku}</span>
                      <RiskBadge risk={i.risk} />
                    </div>
                    <p className="mt-0.5 truncate text-[13.5px] font-medium">{i.name}</p>
                  </div>
                  <div className="w-full sm:w-44">
                    <div className="mb-1 flex justify-between text-[11.5px]">
                      <span className="text-muted-foreground">Cover vs lead time</span>
                      <span className="font-medium tabular">
                        {i.daysOfCover}d / {i.leadTimeDays}d
                      </span>
                    </div>
                    <Progress value={coverPct} indicatorClassName={i.risk === "critical" ? "bg-critical" : "bg-warning"} aria-label={`${i.daysOfCover} days of cover against ${i.leadTimeDays} day lead time`} />
                  </div>
                  <Button asChild variant="outline" size="xs" className="self-start sm:self-center">
                    <Link href={`/copilot?q=${encodeURIComponent(`Give me a complete recommendation for ${i.sku}`)}`}>
                      <Sparkles className="text-ai" /> Resolve
                    </Link>
                  </Button>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

/** AI recommendations feed: next best actions with confidence and the agents behind them. */
export function RecommendationsCard({ items }: { items: Recommendation[] }) {
  return (
    <Card className="h-full">
      <CardHeader>
        <div>
          <CardTitle className="flex items-center gap-1.5">
            <Sparkles className="size-4 text-ai" aria-hidden /> AI recommendations
          </CardTitle>
          <CardDescription>Next best actions from your agents</CardDescription>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {items.map((r) => (
          <Link
            key={r.id}
            href={r.sku ? `/copilot?q=${encodeURIComponent(`Give me a complete recommendation for ${r.sku}`)}` : "/copilot"}
            className="block rounded-md border p-3.5 transition-[border-color,box-shadow] hover:border-ai/30 hover:shadow-card"
          >
            <div className="flex items-center justify-between gap-2">
              <RiskBadge risk={r.risk} />
              <span className="text-[11px] text-muted-foreground">{timeAgo(r.createdAt)}</span>
            </div>
            <p className="mt-2 text-[13.5px] leading-snug font-semibold">{r.title}</p>
            <p className="mt-1 text-[12.5px] leading-snug text-muted-foreground">{r.detail}</p>
            <div className="mt-2.5 flex items-center justify-between gap-2">
              <div className="flex -space-x-1">
                {r.agents.map((a) => {
                  const Icon = STEP_META[a].icon;
                  return (
                    <span key={a} title={STEP_META[a].label} className="flex size-5 items-center justify-center rounded-full border-2 border-card bg-secondary text-primary dark:text-foreground">
                      <Icon className="size-2.5" aria-hidden />
                    </span>
                  );
                })}
              </div>
              <span className={cn("text-[11.5px] font-medium", r.confidence >= 0.85 ? "text-success" : "text-muted-foreground")}>
                {fmt.pct(r.confidence)} confidence
              </span>
            </div>
            <p className="mt-2 border-t pt-2 text-[12px] font-medium text-foreground/80">{r.impact}</p>
          </Link>
        ))}
      </CardContent>
    </Card>
  );
}
