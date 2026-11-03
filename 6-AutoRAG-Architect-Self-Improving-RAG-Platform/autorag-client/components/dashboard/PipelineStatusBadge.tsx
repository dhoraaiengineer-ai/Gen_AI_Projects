import type { PipelineStatus } from "@/types";

interface PipelineStatusBadgeProps {
  status: PipelineStatus;
}

/* Semantic status colors -- translucent-tinted pills for the dark workspace
 * (ADR-009, 18-Jul-2026 dark-first reversal). Bordered pills, matching the
 * dark-theme READY/PENDING/BLOCKED spec (frontend_design.md §18). */
const STATUS_STYLES: Record<PipelineStatus, { label: string; classes: string }> = {
  draft: { label: "Draft", classes: "text-text-2 bg-accent/5 ring-1 ring-inset ring-white/10" },
  ready: { label: "Ready", classes: "text-emerald-400 bg-emerald-500/10 ring-1 ring-inset ring-emerald-500/20" },
  pending: { label: "Pending", classes: "text-amber-400 bg-amber-500/10 ring-1 ring-inset ring-amber-500/20" },
  running: { label: "Running", classes: "text-cyan-400 bg-cyan-500/10 ring-1 ring-inset ring-cyan-500/20" },
  failed: { label: "Failed", classes: "text-rose-400 bg-rose-500/10 ring-1 ring-inset ring-rose-500/20" },
  decommissioned: { label: "Decommissioned", classes: "text-text-3 bg-accent/5 ring-1 ring-inset ring-white/10" },
};

/** Pill showing a pipeline's lifecycle status (pending|running|ready|failed|decommissioned). */
export function PipelineStatusBadge({ status }: PipelineStatusBadgeProps) {
  const style = STATUS_STYLES[status] ?? STATUS_STYLES.pending;
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${style.classes}`}
      data-status={status}
    >
      {style.label}
    </span>
  );
}
