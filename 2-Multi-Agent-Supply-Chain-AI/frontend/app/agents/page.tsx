"use client";

import { CheckCircle2, CircleAlert, Clock, Cpu, Gauge, ListChecks, UserCheck, Wrench, Zap } from "lucide-react";
import type { AgentInfo } from "@/types";
import { useAgents } from "@/hooks/use-api";
import { PageHeader } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/primitives";
import { CHART, Sparkline } from "@/components/charts";
import { STEP_META } from "@/components/agents/agent-meta";
import { Stat } from "@/components/shared/stat";
import { ErrorState } from "@/components/shared/states";
import { StatusDot } from "@/components/shared/status";
import { cn, fmt, timeAgo } from "@/lib/utils";

/** How the graph routes work — a static map shown above the agent cards. */
function GraphMap() {
  const steps = [
    { label: "Input guardrails", sub: "Injection · PII/PHI · scope" },
    { label: "Intent classifier", sub: "Structured output" },
    { label: "Supervisor", sub: "Plan · route · parallelise" },
    { label: "Specialist agents", sub: "Bounded tool loops" },
    { label: "Human approval", sub: "Policy thresholds" },
    { label: "Synthesizer", sub: "Report from evidence" },
    { label: "Output validator", sub: "Numbers · citations" },
  ];
  return (
    <Card className="mb-6 p-5">
      <p className="text-sm font-semibold">Orchestration graph</p>
      <p className="mt-0.5 text-[13px] text-muted-foreground">Every request flows through the same governed LangGraph pipeline. Agents only call tools they are authorised to use.</p>
      <ol className="mt-4 grid gap-2 sm:grid-cols-4 lg:grid-cols-7">
        {steps.map((s, i) => (
          <li key={s.label} className="relative rounded-md border bg-muted/30 px-3 py-2.5">
            <span className="text-[10.5px] font-medium text-muted-foreground tabular">{String(i + 1).padStart(2, "0")}</span>
            <p className="text-[12.5px] font-semibold">{s.label}</p>
            <p className="text-[11px] text-muted-foreground">{s.sub}</p>
          </li>
        ))}
      </ol>
    </Card>
  );
}

function AgentCard({ agent }: { agent: AgentInfo }) {
  const meta = STEP_META[agent.id];
  const tone = agent.status === "operational" ? "success" : agent.status === "degraded" ? "warning" : "critical";
  return (
    <article className="flex flex-col rounded-lg border bg-card shadow-card transition-shadow hover:shadow-raised" aria-label={agent.name}>
      <div className="flex items-start gap-3 p-5 pb-4">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/[0.06] text-primary dark:bg-primary/10 dark:text-foreground">
          <meta.icon className="size-5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <h3 className="truncate text-[15px] font-semibold tracking-tight">{agent.name}</h3>
            <StatusDot tone={tone} pulse={agent.status === "operational"} label={agent.status === "operational" ? "Operational" : agent.status === "degraded" ? "Degraded" : "Offline"} className="shrink-0 text-xs font-medium" />
          </div>
          <p className="mt-1 text-[13px] leading-snug text-muted-foreground">{agent.purpose}</p>
        </div>
      </div>

      <dl className="grid grid-cols-3 border-y text-center">
        <div className="px-2 py-3">
          <dt className="text-[11px] text-muted-foreground">Avg latency</dt>
          <dd className="mt-0.5 text-[15px] font-semibold tabular">{fmt.ms(agent.avgLatencyMs)}</dd>
          <dd className="text-[10.5px] text-muted-foreground tabular">p95 {fmt.ms(agent.p95LatencyMs)}</dd>
        </div>
        <div className="border-x px-2 py-3">
          <dt className="text-[11px] text-muted-foreground">Success rate</dt>
          <dd className={cn("mt-0.5 text-[15px] font-semibold tabular", agent.successRate >= 0.98 ? "text-success" : "text-warning-foreground")}>{fmt.pct(agent.successRate, 1)}</dd>
          <dd className="text-[10.5px] text-muted-foreground">last 30 days</dd>
        </div>
        <div className="px-2 py-3">
          <dt className="text-[11px] text-muted-foreground">Tasks</dt>
          <dd className="mt-0.5 text-[15px] font-semibold tabular">{fmt.compact(agent.tasksCompleted)}</dd>
          <dd className="text-[10.5px] text-muted-foreground tabular">{agent.tasksToday} today</dd>
        </div>
      </dl>

      <div className="space-y-4 p-5 pt-4">
        <div className="flex items-center justify-between gap-3">
          <span className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
            <Cpu className="size-3.5" aria-hidden /> {agent.model}
          </span>
          <Sparkline data={agent.latencyTrend} className="w-24" height={22} color={CHART.secondary} />
        </div>
        <div>
          <p className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
            <Wrench className="size-3" aria-hidden /> Tools
          </p>
          <div className="flex flex-wrap gap-1.5">
            {agent.tools.map((t) => (
              <code key={t} className="rounded bg-muted px-1.5 py-0.5 font-mono text-[11px]">
                {t}
              </code>
            ))}
          </div>
        </div>
        <div>
          <p className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
            <Clock className="size-3" aria-hidden /> Recent activity
          </p>
          <ul className="space-y-1.5">
            {agent.recentActivity.slice(0, 3).map((a) => (
              <li key={a.timestamp + a.message} className="flex items-start gap-2 text-[12.5px]">
                {a.outcome === "escalated" ? (
                  <UserCheck className="mt-0.5 size-3.5 shrink-0 text-warning-foreground" aria-label="Escalated" />
                ) : a.outcome === "failed" ? (
                  <CircleAlert className="mt-0.5 size-3.5 shrink-0 text-critical" aria-label="Failed" />
                ) : (
                  <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-success" aria-label="Succeeded" />
                )}
                <span className="min-w-0 flex-1 leading-snug">{a.message}</span>
                <span className="shrink-0 text-[11px] text-muted-foreground">{timeAgo(a.timestamp)}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </article>
  );
}

export default function AgentsPage() {
  const { data, isLoading, error, refetch } = useAgents();
  const operational = data?.filter((a) => a.status === "operational").length ?? 0;
  const totalToday = data?.reduce((s, a) => s + a.tasksToday, 0) ?? 0;
  const avgSuccess = data ? data.reduce((s, a) => s + a.successRate, 0) / data.length : 0;
  const avgLatency = data ? data.reduce((s, a) => s + a.avgLatencyMs, 0) / data.length : 0;

  return (
    <>
      <PageHeader title="Agent Center" description="Status, performance and tool access for every AI agent in the workforce." />
      <section aria-label="Agent summary" className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Agents operational" value={data && `${operational} / ${data.length}`} hint="1 degraded: web search latency" icon={ListChecks} tone="success" loading={isLoading} />
        <Stat label="Tasks today" value={data && fmt.int(totalToday)} hint="Across all agents" icon={Zap} tone="ai" loading={isLoading} />
        <Stat label="Success rate" value={data && fmt.pct(avgSuccess, 1)} hint="Completed without error" icon={CheckCircle2} loading={isLoading} />
        <Stat label="Avg agent latency" value={data && fmt.ms(avgLatency)} hint="Per specialist step" icon={Gauge} loading={isLoading} />
      </section>
      <GraphMap />
      {error ? (
        <Card>
          <ErrorState error={error} what="agent status" onRetry={() => refetch()} />
        </Card>
      ) : (
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {data
            ? data.map((a) => <AgentCard key={a.id} agent={a} />)
            : Array.from({ length: 6 }).map((_, i) => (
                <Card key={i} className="p-5">
                  <div className="flex gap-3">
                    <Skeleton className="size-10" />
                    <div className="flex-1 space-y-2">
                      <Skeleton className="h-4 w-2/3" />
                      <Skeleton className="h-3 w-full" />
                    </div>
                  </div>
                  <Skeleton className="mt-5 h-16 w-full" />
                  <Skeleton className="mt-4 h-20 w-full" />
                </Card>
              ))}
        </div>
      )}
    </>
  );
}
