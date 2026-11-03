"use client";

import Link from "next/link";
import { Wand2, FileText, Gauge, Rocket, ArrowRight, Check, type LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

export interface JourneyProgress {
  hasPipeline: boolean;
  hasDocuments: boolean;
  hasEvaluation: boolean;
  /** A real run exists but failed/was blocked before producing a score (distinct from "todo"). */
  hasBlockedEvaluation: boolean;
  hasDeployment: boolean;
}

interface StepDef {
  step: number;
  title: string;
  desc: string;
  href: string;
  icon: LucideIcon;
  doneLabel: string;
}

const STEPS: StepDef[] = [
  { step: 1, title: "Create a Pipeline",  desc: "Name your pipeline and pick a chunking strategy in the 6-step wizard.", href: "/configurator", icon: Wand2,    doneLabel: "Pipeline created" },
  { step: 2, title: "Upload Documents",   desc: "Drop in a PDF — parsing, PII masking, chunking and embedding run automatically.", href: "/documents", icon: FileText, doneLabel: "Documents uploaded" },
  { step: 3, title: "Run Evaluation",     desc: "Score your pipeline with Unified Score, RAGAS and adversarial tests.", href: "/evaluation", icon: Gauge,    doneLabel: "Evaluation scored" },
  { step: 4, title: "Approve & Deploy",   desc: "Score ≥ 0.85 deploys automatically; 0.70–0.84 waits for your approval.", href: "/deploy", icon: Rocket,   doneLabel: "Deployed" },
];

type StepState = "done" | "active" | "pending" | "blocked" | "todo";

function stateFor(step: number, p: JourneyProgress): StepState {
  const done = [p.hasPipeline, p.hasDocuments, p.hasEvaluation, p.hasDeployment];
  if (done[step - 1]) return "done";
  // Step 3 only: a real run exists and genuinely failed/was blocked before
  // scoring -- distinct from "not started yet" (13-Jul-2026 fix).
  if (step === 3 && p.hasBlockedEvaluation) return "blocked";
  const firstIncomplete = done.findIndex((d) => !d) + 1;
  if (step !== firstIncomplete) return "todo";
  // Step 4 (Approve & Deploy) gets its own "pending" state, purple accent,
  // when it's the current step -- action genuinely requires human approval
  // (19-Jul-2026 review: "purple only when action is required," not a
  // permanent color for the whole step regardless of state).
  return step === 4 ? "pending" : "active";
}

const FAILED_LABEL: Record<number, string> = {
  3: "Evaluation blocked",
};

/* Accent-tinted palette on a shared KPI-tile base tone (19-Jul-2026 review
 * pass): each non-neutral state gets a genuine ~5% status-color background
 * tint layered over the base, not just a colored border -- "completed
 * cards ... 5% blue tint or 5% green tint depending on status." "pending"
 * (purple) is reserved for the Approve & Deploy step specifically when it's
 * current -- action genuinely requires human approval, not a permanent
 * step color. */
const CARD_STATE_CLASSES: Record<StepState, string> = {
  done:    "bg-white border-t-4 border-t-emerald-500 border-x border-b border-stone-200/90 shadow-[0_2px_8px_rgba(0,0,0,0.03)] hover:shadow-md",
  active:  "bg-white border-t-4 border-t-orange-500 border-x border-b border-stone-200/90 shadow-[0_2px_8px_rgba(0,0,0,0.03)] hover:shadow-md",
  pending: "bg-white border-t-4 border-t-amber-500 border-x border-b border-stone-200/90 shadow-[0_2px_8px_rgba(0,0,0,0.03)] hover:shadow-md",
  blocked: "bg-white border-t-4 border-t-rose-500 border-x border-b border-stone-200/90 shadow-[0_2px_8px_rgba(0,0,0,0.03)] hover:shadow-md",
  todo:    "bg-white border-t-4 border-t-stone-200 border-x border-b border-stone-200/90 shadow-[0_2px_8px_rgba(0,0,0,0.03)] hover:shadow-md",
};

const BADGE_STATE_CLASSES: Record<StepState, string> = {
  done: "bg-emerald-100 text-emerald-700",
  active: "bg-orange-100 text-orange-700",
  pending: "bg-amber-100 text-amber-800",
  blocked: "bg-rose-100 text-rose-700",
  todo: "bg-stone-100 text-stone-600",
};

const ICON_STATE_CLASSES: Record<StepState, string> = {
  done: "text-emerald-500",
  active: "text-orange-500",
  pending: "text-amber-500",
  blocked: "text-rose-500",
  todo: "text-stone-400",
};

const BUTTON_STATE_CLASSES: Record<StepState, string> = {
  done: "bg-stone-100 hover:bg-stone-200 text-stone-800 border border-stone-200/80",
  active: "bg-amber-500 hover:bg-amber-600 text-white shadow-xs",
  pending: "bg-amber-500 hover:bg-amber-600 text-white shadow-xs",
  blocked: "bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200",
  todo: "bg-stone-100 hover:bg-stone-200 text-stone-800 border border-stone-200/80",
};

/** Compact guided 4-step journey — every card shows live completion state,
 * connected by a thin progress line to read as one workflow, not four
 * separate feature cards (18-Jul-2026 review pass). */
export function JourneySteps({ progress }: { progress: JourneyProgress }) {
  const states = STEPS.map((s) => stateFor(s.step, progress));

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {STEPS.map((s, i) => {
        const state = states[i];
        const Icon = s.icon;
        const buttonLabel =
          state === "done" ? "Review" : state === "pending" ? "Review & Approve" : state === "active" ? "Start now" : state === "blocked" ? "Investigate" : "Open";
        return (
          <Link
            key={s.step}
            href={s.href}
            className={cn(
              "group flex flex-col justify-between gap-3 rounded-2xl p-5 transition-all motion-safe:duration-200",
              CARD_STATE_CLASSES[state],
            )}
          >
            <div>
              <div className="mb-3 flex items-center justify-between">
                <span className={cn("flex h-8 w-8 items-center justify-center rounded-xl text-xs font-black", BADGE_STATE_CLASSES[state])}>
                  {state === "done" ? <Check className="h-4 w-4" aria-hidden="true" /> : s.step}
                </span>
                <Icon className={cn("h-4 w-4", ICON_STATE_CLASSES[state])} aria-hidden="true" />
              </div>
              <h3 className="text-sm font-bold text-stone-900">{s.title}</h3>
              <p className="mt-1 text-xs font-medium leading-relaxed text-stone-500">
                {state === "done" ? `✓ ${s.doneLabel}` : state === "blocked" ? `⚠ ${FAILED_LABEL[s.step] ?? "Blocked"}` : s.desc}
              </p>
            </div>
            <span
              className={cn(
                "inline-flex w-full items-center justify-center gap-1.5 rounded-xl px-3 py-2.5 text-xs font-extrabold transition-colors",
                BUTTON_STATE_CLASSES[state],
              )}
            >
              {buttonLabel}
              <ArrowRight className="h-3.5 w-3.5 transition-transform motion-safe:duration-200 group-hover:translate-x-0.5" aria-hidden="true" />
            </span>
          </Link>
        );
      })}
    </div>
  );
}
