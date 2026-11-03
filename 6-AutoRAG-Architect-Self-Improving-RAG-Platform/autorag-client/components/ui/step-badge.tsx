import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

export type StepState = "done" | "active" | "blocked" | "todo";

interface StepBadgeProps {
  step: number;
  state: StepState;
  className?: string;
}

/** Numbered journey-step badge — done (check) / active (blue glow) / todo (muted). */
export function StepBadge({ step, state, className }: StepBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-lg text-[11px] font-bold",
        state === "done" && "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
        state === "active" && "bg-accent text-foreground shadow-[0_0_12px_rgba(91,92,226,0.45)]",
        state === "blocked" && "bg-rose-50 text-rose-700 ring-1 ring-rose-200",
        state === "todo" && "bg-accent/5 text-text-3 ring-1 ring-[rgba(15,23,42,0.1)]",
        className,
      )}
      aria-label={`Step ${step}${state === "done" ? " complete" : state === "active" ? " current" : state === "blocked" ? " blocked" : ""}`}
    >
      {state === "done" ? <Check className="h-3.5 w-3.5" aria-hidden="true" /> : step}
    </span>
  );
}
