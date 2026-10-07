"use client";

import { motion } from "framer-motion";
import { CircleCheck, FileText, Gauge, ShieldAlert, ShieldCheck, Timer, Zap } from "lucide-react";
import type { RecommendationReport } from "@/types";
import type { StreamMetrics } from "@/hooks/use-copilot";
import { STEP_META } from "@/components/agents/agent-meta";
import { RiskBadge } from "@/components/shared/status";
import { ForecastChart } from "@/components/charts";
import { Tooltip } from "@/components/ui/primitives";
import { cn, fmt } from "@/lib/utils";

/** Renders "[1]" markers as superscript citation chips that reference the Sources list. */
export function CitedText({ text, className }: { text: string; className?: string }) {
  const parts = text.split(/(\[\d+\])/g);
  return (
    <p className={className}>
      {parts.map((part, i) => {
        const m = part.match(/^\[(\d+)\]$/);
        return m ? (
          <a
            key={i}
            href={`#source-${m[1]}`}
            className="mx-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded bg-ai-soft px-1 align-text-top text-[10px] font-semibold text-ai no-underline hover:bg-ai hover:text-white"
            aria-label={`Source ${m[1]}`}
          >
            {m[1]}
          </a>
        ) : (
          <span key={i}>{part}</span>
        );
      })}
    </p>
  );
}

function Section({ title, children, className }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={cn("space-y-2", className)}>
      <h4 className="text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">{title}</h4>
      {children}
    </section>
  );
}

const CONFIDENCE_TONE = { high: "text-success", medium: "text-warning-foreground", low: "text-critical" } as const;

/** Decision-support report. Shows reasoning summaries and evidence — never private chain-of-thought. */
export function ReportCard({ report, metrics }: { report: RecommendationReport; metrics?: StreamMetrics }) {
  const isRecommendation = report.reasoning.length > 0 || report.evidence.length > 0 || !!report.supplier;
  return (
    <motion.article
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="overflow-hidden rounded-lg border bg-card shadow-card"
      aria-label="Copilot recommendation"
    >
      {/* Header */}
      <div className="border-b bg-gradient-to-b from-ai-soft/50 to-transparent px-5 py-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-semibold tracking-wider text-ai uppercase">{isRecommendation ? "Recommendation" : "Answer"}</span>
          {isRecommendation && <RiskBadge risk={report.riskLevel} />}
          <span className={cn("ml-auto inline-flex items-center gap-1 text-xs font-medium", CONFIDENCE_TONE[report.confidence.level])}>
            <Gauge className="size-3.5" aria-hidden />
            {report.confidence.level === "high" ? "High" : report.confidence.level === "medium" ? "Medium" : "Low"} confidence · {fmt.pct(report.confidence.score)}
          </span>
        </div>
        <h3 className="mt-1.5 text-[17px] leading-snug font-semibold tracking-tight">{report.headline}</h3>
        <CitedText text={report.summary} className="mt-1.5 text-[13.5px] leading-relaxed text-muted-foreground" />
      </div>

      <div className="grid gap-6 px-5 py-5 lg:grid-cols-[1fr_280px]">
        <div className="min-w-0 space-y-5">
          {report.reasoning.length > 0 && (
            <Section title="Why">
              <ul className="space-y-1.5">
                {report.reasoning.map((r, i) => (
                  <li key={i} className="flex gap-2 text-[13px] leading-relaxed">
                    <span className="mt-2 size-1 shrink-0 rounded-full bg-muted-foreground/60" aria-hidden />
                    <CitedText text={r} />
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {report.evidence.length > 0 && (
            <Section title="Evidence">
              <dl className="grid gap-px overflow-hidden rounded-md border bg-border sm:grid-cols-2">
                {report.evidence.map((e) => (
                  <div key={e.label} className="bg-card px-3 py-2.5">
                    <dt className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
                      {e.label}
                      <span className="rounded bg-muted px-1 text-[10px]">{STEP_META[e.source].short}</span>
                    </dt>
                    <dd className="mt-0.5 text-[13.5px] font-semibold tabular">{e.value}</dd>
                  </div>
                ))}
              </dl>
            </Section>
          )}

          {report.table && (
            <Section title={report.table.title}>
              <div className="overflow-x-auto rounded-md border">
                <table className="w-full text-[12.5px]">
                  <thead className="bg-muted/60">
                    <tr>
                      {report.table.columns.map((c) => (
                        <th key={c} className="px-3 py-2 text-left font-medium whitespace-nowrap text-muted-foreground">
                          {c}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {report.table.rows.map((row, i) => (
                      <tr key={i} className="border-t">
                        {row.map((cell, j) => (
                          <td key={j} className={cn("px-3 py-2 whitespace-nowrap tabular", j === 0 && "font-mono text-xs")}>
                            {String(cell)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>
          )}

          {report.forecast && (
            <Section title="Forecast">
              <div className="rounded-md border p-3">
                <ForecastChart points={report.forecast} height={220} />
              </div>
            </Section>
          )}

          {report.impact.length > 0 && (
            <Section title="Expected impact">
              <ul className="grid gap-1.5 sm:grid-cols-2">
                {report.impact.map((i) => (
                  <li key={i} className="flex items-start gap-2 text-[13px]">
                    <CircleCheck className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
                    {i}
                  </li>
                ))}
              </ul>
            </Section>
          )}
        </div>

        <aside className="space-y-5">
          {report.supplier && (
            <Section title="Recommended supplier">
              <div className="rounded-md border p-3.5">
                <p className="text-sm font-semibold">{report.supplier.name}</p>
                <dl className="mt-2.5 space-y-1.5 text-[13px]">
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Unit price</dt>
                    <dd className="font-medium tabular">{fmt.price(report.supplier.unitPrice)}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Lead time</dt>
                    <dd className="font-medium tabular">{report.supplier.leadTimeDays} days</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Reliability</dt>
                    <dd className="font-medium tabular">{fmt.pct(report.supplier.reliability)}</dd>
                  </div>
                </dl>
              </div>
            </Section>
          )}

          {report.sources.length > 0 && (
            <Section title="Sources">
              <ol className="space-y-1.5">
                {report.sources.map((s) => (
                  <li key={s.n} id={`source-${s.n}`} className="flex gap-2 rounded-md text-[12.5px] target:bg-ai-soft">
                    <span className="flex h-4 min-w-4 items-center justify-center rounded bg-ai-soft text-[10px] font-semibold text-ai">{s.n}</span>
                    <span className="min-w-0">
                      <span className="flex items-center gap-1 font-medium">
                        <FileText className="size-3 shrink-0 text-muted-foreground" aria-hidden />
                        <span className="truncate">{s.title}</span>
                      </span>
                      <span className="text-muted-foreground">{s.location}</span>
                    </span>
                  </li>
                ))}
              </ol>
            </Section>
          )}

          <Section title="Agents involved">
            <div className="flex flex-wrap gap-1.5">
              {report.agentsInvolved.map((a) => {
                const meta = STEP_META[a];
                return (
                  <span key={a} className="inline-flex items-center gap-1 rounded-md border bg-card px-1.5 py-0.5 text-[11.5px] font-medium">
                    <meta.icon className="size-3 text-muted-foreground" aria-hidden />
                    {meta.short}
                  </span>
                );
              })}
            </div>
          </Section>
        </aside>
      </div>

      {/* Footer: guardrail verdict + streaming metrics (evaluated on every run) */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t bg-muted/30 px-5 py-2.5 text-[11.5px] text-muted-foreground">
        <span className={cn("inline-flex items-center gap-1 font-medium", report.guard.status === "grounded" ? "text-success" : "text-warning-foreground")}>
          {report.guard.status === "grounded" ? <ShieldCheck className="size-3.5" aria-hidden /> : <ShieldAlert className="size-3.5" aria-hidden />}
          {report.guard.status === "grounded" ? "Grounded · figures verified" : `Flagged: ${report.guard.reasons.join(", ")}`}
        </span>
        {metrics?.ttfeMs !== undefined && (
          <Tooltip content="Time to first event — how fast the user sees progress">
            <span className="inline-flex items-center gap-1 tabular">
              <Zap className="size-3" aria-hidden /> TTFE {fmt.ms(metrics.ttfeMs)}
            </span>
          </Tooltip>
        )}
        {metrics?.ttftMs !== undefined && (
          <Tooltip content="Time to first token of the answer">
            <span className="tabular">TTFT {fmt.ms(metrics.ttftMs)}</span>
          </Tooltip>
        )}
        {metrics?.totalMs !== undefined && (
          <span className="inline-flex items-center gap-1 tabular">
            <Timer className="size-3" aria-hidden /> Total {fmt.ms(metrics.totalMs)}
          </span>
        )}
        {metrics?.tokensPerSec !== undefined && <span className="tabular">{metrics.tokensPerSec} tok/s</span>}
        <span className="ml-auto font-mono">{report.requestId}</span>
      </div>
    </motion.article>
  );
}
