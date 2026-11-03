"use client";

import { useMemo, useState } from "react";
import { Check, ChevronDown, ChevronRight, X } from "lucide-react";

import { apiClient } from "@/services/api-client";
import { pipelineDisplayName } from "@/lib/format";
import { formatScore, isHitlPending, scoreColorClasses } from "@/lib/score";
import type { ApprovalDecision, PipelineWithRun } from "@/types";

interface HITLApprovalQueueProps {
  pipelines: PipelineWithRun[];
  /** Called after a successful approve/reject so the parent can refetch. */
  onActionComplete?: () => void;
}

/**
 * Collapsible queue of runs awaiting human approval — score in [0.70, 0.84)
 * (CLAUDE.md §9 global gate; no per-pipeline approval_mode on the real backend).
 * Approve/Reject call POST /api/v1/hitl/approve (API_SPEC #11).
 */
export function HITLApprovalQueue({ pipelines, onActionComplete }: HITLApprovalQueueProps) {
  const [open, setOpen] = useState(true);
  const [actingId, setActingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const pending = useMemo(
    () => pipelines.filter((p) => isHitlPending(p.latest_run)),
    [pipelines],
  );

  async function act(runId: string, decision: ApprovalDecision) {
    setActingId(runId);
    setError(null);
    try {
      await apiClient.approve(runId, decision);
      onActionComplete?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approval action failed");
    } finally {
      setActingId(null);
    }
  }

  const Chevron = open ? ChevronDown : ChevronRight;

  // Empty state: collapse to one compact row instead of a header + a large
  // separately-padded empty message (13-Jul-2026 contrast correction --
  // was a near-empty ~180px box; the message now lives inline in the header row).
  if (pending.length === 0) {
    return (
      <section className="flex min-h-[76px] items-center gap-3 rounded-2xl border border-stone-200/90 bg-white px-4 py-3 shadow-[0_2px_8px_rgba(0,0,0,0.02)]">
        <h2 className="shrink-0 text-sm font-bold text-stone-900">HITL Approval Queue</h2>
        <span className="shrink-0 rounded-full bg-stone-100 px-2 py-0.5 text-xs font-semibold text-stone-500">0</span>
        <span className="truncate text-xs font-medium text-stone-500">
          No runs awaiting approval &middot; borderline evaluations (0.70&ndash;0.84) will appear here
        </span>
      </section>
    );
  }

  return (
    <section className="overflow-hidden rounded-2xl border-t-4 border-t-amber-500 border-x border-b border-stone-200/90 bg-white shadow-[0_2px_12px_rgba(0,0,0,0.03)]">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 px-5 py-3.5 text-left hover:bg-amber-50/40"
      >
        <Chevron className="h-4 w-4 text-stone-400" aria-hidden="true" />
        <h2 className="text-sm font-bold text-stone-900">HITL Approval Queue</h2>
        <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-bold text-amber-800">
          {pending.length}
        </span>
      </button>

      {open && (
        <div className="border-t border-stone-100">
          {error && (
            <p className="px-5 pt-3 text-xs font-medium text-rose-600" role="alert">
              {error}
            </p>
          )}

          <ul className="divide-y divide-stone-100">
            {pending.map((p) => {
              const run = p.latest_run!;
              const busy = actingId === run.id;
              return (
                <li key={p.id} className="flex flex-wrap items-center gap-3 px-5 py-3.5">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-bold text-stone-900">
                      {pipelineDisplayName(p)}
                    </p>
                    <p className="text-xs font-medium text-stone-500">
                      Run <span className="font-mono font-bold text-amber-600">{run.id.slice(0, 8)}</span>
                    </p>
                  </div>

                  {/* Non-null by construction: `pending` is filtered via isHitlPending(),
                      which now requires unified_score !== null. */}
                  <span className={`rounded px-2 py-0.5 text-sm font-bold ${scoreColorClasses(run.unified_score!)}`}>
                    {formatScore(run.unified_score)}
                  </span>

                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => act(run.id, "approve")}
                      className="inline-flex items-center gap-1 rounded-xl bg-amber-500 px-3 py-1.5 text-xs font-extrabold text-white transition-colors hover:bg-amber-600 disabled:opacity-50"
                    >
                      <Check className="h-3.5 w-3.5" aria-hidden="true" />
                      Approve
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => act(run.id, "reject")}
                      className="inline-flex items-center gap-1 rounded-xl border border-rose-200 bg-rose-50 px-3 py-1.5 text-xs font-extrabold text-rose-700 transition-colors hover:bg-rose-100 disabled:opacity-50"
                    >
                      <X className="h-3.5 w-3.5" aria-hidden="true" />
                      Reject
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </section>
  );
}
