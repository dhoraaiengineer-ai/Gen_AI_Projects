"use client";

import { useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { ChevronDown, RotateCcw, Sparkles } from "lucide-react";
import { useCopilot, type CopilotTurn } from "@/hooks/use-copilot";
import { SUGGESTED_PROMPTS } from "@/lib/constants";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/shared/states";
import { ApiError } from "@/lib/api";
import { AgentPipeline } from "./agent-pipeline";
import { ApprovalCard } from "./approval-card";
import { Composer } from "./composer";
import { CitedText, ReportCard } from "./report-card";

export function SuggestedPrompts({ onPick, prompts = SUGGESTED_PROMPTS }: { onPick: (p: string) => void; prompts?: string[] }) {
  return (
    <div className="flex flex-wrap gap-2">
      {prompts.map((p) => (
        <button
          key={p}
          type="button"
          onClick={() => onPick(p)}
          className="cursor-pointer rounded-full border bg-card px-3 py-1.5 text-[12.5px] text-foreground/80 shadow-xs transition-colors hover:border-ai/40 hover:bg-ai-soft/50 hover:text-foreground"
        >
          {p}
        </button>
      ))}
    </div>
  );
}

function Turn({ turn, onRetry, onApprovalDecided }: { turn: CopilotTurn; onRetry: () => void; onApprovalDecided: (s: "approved" | "rejected" | "pending" | "expired") => void }) {
  const running = turn.status === "running";
  return (
    <div className="space-y-4">
      {/* User message */}
      <div className="flex justify-end">
        <p className="max-w-[80%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-[14px] text-primary-foreground">{turn.question}</p>
      </div>

      {/* Agent workflow — expanded while running, collapsible afterwards */}
      <details open={running || undefined} className="group rounded-lg border bg-card/60 shadow-card [&_summary::-webkit-details-marker]:hidden">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-4 py-2.5 text-[13px]">
          <span className="flex items-center gap-2 font-medium">
            <Sparkles className="size-4 text-ai" aria-hidden />
            {running ? "Agents are working…" : `Agent workflow${turn.intent ? ` · ${turn.intent.replace(/_/g, " ")}` : ""}`}
          </span>
          <ChevronDown className="size-4 text-muted-foreground transition-transform group-open:rotate-180" aria-hidden />
        </summary>
        <div className="border-t px-4 py-4">
          <AgentPipeline steps={turn.steps} stages={turn.stages} />
        </div>
      </details>

      {/* Streaming answer appears token-by-token before the structured report lands */}
      {running && turn.streamedText && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="rounded-lg border bg-card px-5 py-4 shadow-card">
          <p className="mb-1 text-[11px] font-semibold tracking-wider text-ai uppercase">Drafting recommendation</p>
          <CitedText text={turn.streamedText} className="text-[14px] leading-relaxed" />
          <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse-soft bg-ai align-text-bottom" aria-hidden />
        </motion.div>
      )}

      {turn.approval && <ApprovalCard approval={turn.approval} onDecided={onApprovalDecided} />}

      {turn.report && <ReportCard report={turn.report} metrics={turn.metrics} />}

      {turn.status === "error" && (
        <div className="rounded-lg border bg-card shadow-card">
          <ErrorState
            title="The copilot couldn't finish this request"
            error={new ApiError(turn.error?.message ?? "Request failed", 500, "copilot_error", turn.error?.requestId)}
            what="a recommendation"
            onRetry={onRetry}
          />
        </div>
      )}
      {turn.status === "cancelled" && <p className="text-center text-xs text-muted-foreground">Stopped. Ask again whenever you&apos;re ready.</p>}
    </div>
  );
}

/** Full Copilot conversation. `initialQuestion` lets other pages deep-link a question (?q=…). */
export function CopilotPanel({ initialQuestion }: { initialQuestion?: string }) {
  const { turns, ask, stop, reset, running, setApprovalStatus } = useCopilot();
  const endRef = useRef<HTMLDivElement>(null);
  const askedInitial = useRef(false);

  useEffect(() => {
    if (initialQuestion && !askedInitial.current) {
      askedInitial.current = true;
      void ask(initialQuestion);
    }
  }, [initialQuestion, ask]);

  const lastTurn = turns.at(-1);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns.length, lastTurn?.status, lastTurn?.report]);

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col">
      {turns.length === 0 ? (
        <div className="flex flex-col items-center py-10 text-center sm:py-16">
          <span className="flex size-12 items-center justify-center rounded-2xl bg-gradient-to-br from-[#3c6fe0] to-[#1f4fa3] text-white shadow-raised">
            <Sparkles className="size-5" aria-hidden />
          </span>
          <h2 className="mt-5 text-xl font-semibold tracking-tight">AI Supply Chain Copilot</h2>
          <p className="mt-1.5 max-w-md text-[13.5px] text-muted-foreground">
            Ask questions about inventory, demand, suppliers and logistics. Specialist agents analyse your data and policies, then
            return a verified recommendation.
          </p>
          <div className="mt-8 w-full max-w-2xl">
            <Composer onSubmit={ask} running={running} onStop={stop} autoFocus />
            <div className="mt-4 flex justify-center">
              <SuggestedPrompts onPick={ask} />
            </div>
          </div>
        </div>
      ) : (
        <>
          <div className="mb-4 flex items-center justify-between">
            <p className="text-[13px] text-muted-foreground">
              {turns.length} {turns.length === 1 ? "question" : "questions"} this session
            </p>
            <Button variant="ghost" size="sm" onClick={reset} disabled={running}>
              <RotateCcw /> New conversation
            </Button>
          </div>
          <div className="space-y-10 pb-40">
            {turns.map((t) => (
              <Turn key={t.id} turn={t} onRetry={() => ask(t.question)} onApprovalDecided={(s) => setApprovalStatus(t.id, s)} />
            ))}
            <div ref={endRef} />
          </div>
          <div className="sticky bottom-0 -mx-4 bg-gradient-to-t from-background via-background to-transparent px-4 pt-6 pb-4">
            <Composer onSubmit={ask} running={running} onStop={stop} placeholder="Ask a follow-up…" />
            <p className="mt-2 text-center text-[11px] text-muted-foreground">
              Recommendations are generated from your data and policies. Purchase orders above policy limits always require human approval.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
