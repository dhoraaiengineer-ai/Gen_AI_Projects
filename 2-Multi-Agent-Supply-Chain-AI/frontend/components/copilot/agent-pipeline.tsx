"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Check, Loader2, X } from "lucide-react";
import type { AgentId, AgentRunStatus, PipelineStep } from "@/types";
import type { StepState } from "@/hooks/use-copilot";
import { STEP_META } from "@/components/agents/agent-meta";
import { RUN_STATUS_LABEL } from "@/lib/constants";
import { cn, fmt } from "@/lib/utils";

function StatusGlyph({ status }: { status: AgentRunStatus }) {
  if (status === "completed")
    return (
      <span className="flex size-4 items-center justify-center rounded-full bg-success text-white">
        <Check className="size-2.5" strokeWidth={3} aria-hidden />
      </span>
    );
  if (status === "running") return <Loader2 className="size-4 animate-spin text-ai" aria-hidden />;
  if (status === "failed")
    return (
      <span className="flex size-4 items-center justify-center rounded-full bg-critical text-white">
        <X className="size-2.5" strokeWidth={3} aria-hidden />
      </span>
    );
  return <span className="size-4 rounded-full border-[1.5px] border-dashed border-muted-foreground/40" aria-hidden />;
}

function Node({ step, state }: { step: PipelineStep; state?: StepState }) {
  const meta = STEP_META[step];
  const status = state?.status ?? "waiting";
  const Icon = meta.icon;
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "relative flex min-w-0 flex-1 items-center gap-2.5 rounded-lg border bg-card px-3 py-2 transition-[border-color,box-shadow,background-color] duration-300",
        status === "running" && "border-ai/40 bg-ai-soft/40 shadow-[0_0_0_3px_color-mix(in_oklab,var(--ai)_8%,transparent)]",
        status === "completed" && "border-border",
        status === "waiting" && "opacity-60",
        status === "failed" && "border-critical/40",
      )}
    >
      <span
        className={cn(
          "flex size-7 shrink-0 items-center justify-center rounded-md",
          meta.kind === "agent" ? "bg-primary/[0.06] text-primary dark:bg-primary/10" : meta.kind === "human" ? "bg-warning/10 text-warning-foreground" : "bg-ai-soft text-ai",
        )}
      >
        <Icon className="size-3.5" aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <p className="truncate text-[12.5px] font-semibold">{meta.label}</p>
          <StatusGlyph status={status} />
        </div>
        <AnimatePresence mode="wait" initial={false}>
          <motion.p
            key={state?.message ?? "waiting"}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className={cn("truncate text-[11.5px]", status === "running" ? "text-ai" : "text-muted-foreground")}
          >
            {state?.message || RUN_STATUS_LABEL[status]}
            {state?.durationMs && status === "completed" ? <span className="ml-1 text-muted-foreground/70">· {fmt.ms(state.durationMs)}</span> : null}
          </motion.p>
        </AnimatePresence>
      </div>
      <span className="sr-only">
        {meta.label}: {RUN_STATUS_LABEL[status]}
      </span>
    </motion.div>
  );
}

function Connector({ active }: { active: boolean }) {
  return (
    <div className="flex justify-center py-1" aria-hidden>
      <div className={cn("h-3 w-px transition-colors duration-500", active ? "bg-ai/50" : "bg-border")} />
    </div>
  );
}

/**
 * Live view of the LangGraph run: control nodes in sequence, specialist agents grouped by stage
 * (agents in the same stage run in parallel), then approval, synthesis and validation.
 */
export function AgentPipeline({
  steps,
  stages,
  compact = false,
}: {
  steps: Partial<Record<PipelineStep, StepState>>;
  stages: AgentId[][];
  compact?: boolean;
}) {
  const done = (s: PipelineStep) => steps[s]?.status === "completed";
  const rows: { key: string; items: PipelineStep[]; label?: string }[] = [
    { key: "guard", items: ["guard"] },
    { key: "classifier", items: ["classifier"] },
    { key: "supervisor", items: ["supervisor"] },
    ...stages.map((stage, i) => ({ key: `stage-${i}`, items: stage as PipelineStep[], label: stage.length > 1 ? `Stage ${i + 1} · parallel` : `Stage ${i + 1}` })),
    ...(steps.approval ? [{ key: "approval", items: ["approval" as PipelineStep] }] : []),
    ...(steps.synthesizer ? [{ key: "synth", items: ["synthesizer" as PipelineStep] }] : []),
    ...(steps.validator ? [{ key: "validator", items: ["validator" as PipelineStep] }] : []),
  ];

  const visible = compact ? rows.filter((r) => r.items.some((s) => steps[s] && steps[s]!.status !== "waiting")) : rows;

  return (
    <div className="flex flex-col" aria-live="polite" aria-label="Agent workflow progress">
      {visible.map((row, i) => (
        <div key={row.key}>
          {i > 0 && <Connector active={visible[i - 1].items.every(done)} />}
          {row.label && <p className="mb-1 text-[10.5px] font-medium tracking-wide text-muted-foreground uppercase">{row.label}</p>}
          <div className={cn("grid gap-2", row.items.length > 1 ? "sm:grid-cols-2" : "grid-cols-1")}>
            {row.items.map((s) => (
              <Node key={s} step={s} state={steps[s]} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
