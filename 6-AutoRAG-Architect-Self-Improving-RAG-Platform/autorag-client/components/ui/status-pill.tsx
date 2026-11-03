import { cn } from "@/lib/utils";

export type PillStatus = "success" | "warning" | "error" | "pending" | "running" | "idle";

/** SOT §2 semantic status colors. */
const STATUS_STYLES: Record<PillStatus, { dot: string; text: string; bg: string; defaultLabel: string }> = {
  success: { dot: "bg-emerald-500", text: "text-emerald-700", bg: "bg-emerald-50", defaultLabel: "Success" },
  warning: { dot: "bg-amber-500",   text: "text-amber-700",   bg: "bg-amber-50",   defaultLabel: "Warning" },
  error:   { dot: "bg-red-500",     text: "text-rose-700",    bg: "bg-rose-50",    defaultLabel: "Error" },
  pending: { dot: "bg-sky-500",  text: "text-sky-700",  bg: "bg-sky-50",  defaultLabel: "Pending" },
  running: { dot: "bg-amber-500 motion-safe:animate-pulse", text: "text-amber-700", bg: "bg-amber-50", defaultLabel: "Running" },
  idle:    { dot: "bg-muted-foreground",   text: "text-text-3",   bg: "bg-accent/5",  defaultLabel: "Idle" },
};

interface StatusPillProps {
  status: PillStatus;
  label?: string;
  className?: string;
}

export function StatusPill({ status, label, className }: StatusPillProps) {
  const s = STATUS_STYLES[status];
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium", s.bg, s.text, className)}>
      <span className={cn("h-1.5 w-1.5 rounded-full", s.dot)} aria-hidden="true" />
      {label ?? s.defaultLabel}
    </span>
  );
}
