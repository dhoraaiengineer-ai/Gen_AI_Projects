"use client";

import { AlertTriangle } from "lucide-react";

interface RollbackConfirmDialogProps {
  open: boolean;
  actionLabel: string;
  description: string;
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * Accessible confirmation modal gating Rollback (and Stop, once supported).
 * No shared modal primitive exists yet in components/ui/ — this is a small,
 * self-contained implementation rather than a new dependency.
 */
export function RollbackConfirmDialog({
  open,
  actionLabel,
  description,
  busy,
  onConfirm,
  onCancel,
}: RollbackConfirmDialogProps) {
  if (!open) return null;

  return (
    <div
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="rollback-confirm-title"
      aria-describedby="rollback-confirm-description"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
    >
      <div className="w-full max-w-sm rounded-xl border border-border bg-card p-6 shadow-xl">
        <div className="flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-status-error/15">
            <AlertTriangle className="h-5 w-5 text-status-error" aria-hidden="true" />
          </span>
          <div>
            <h2 id="rollback-confirm-title" className="text-sm font-semibold text-foreground">
              Confirm {actionLabel}
            </h2>
            <p id="rollback-confirm-description" className="mt-1 text-xs text-text-3">
              {description}
            </p>
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="rounded-md border border-border px-3 py-1.5 text-xs font-medium text-text-2 hover:bg-accent/5 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            aria-busy={busy}
            className="rounded-md bg-status-error px-3 py-1.5 text-xs font-semibold text-foreground hover:bg-status-critical disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? "Working…" : `Yes, ${actionLabel}`}
          </button>
        </div>
      </div>
    </div>
  );
}
