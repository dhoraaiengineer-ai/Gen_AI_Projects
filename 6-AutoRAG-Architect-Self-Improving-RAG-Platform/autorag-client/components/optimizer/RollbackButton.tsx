"use client";

import { useState } from "react";
import { Loader2, RotateCcw } from "lucide-react";

import { apiClient } from "@/services/api-client";

interface RollbackButtonProps {
  pipelineId: string;
  versionNumber: number;
  onRolledBack?: () => void;
}

/**
 * Points the pipeline back at an earlier version's config -- real, reversible
 * (POST /pipelines/{id}/rollback, 20-Jul-2026 Apply Improvement feature).
 * Never touches any vector table; the next evaluation dispatch will read
 * this version's config_snapshot again via get_active_config().
 */
export function RollbackButton({ pipelineId, versionNumber, onRolledBack }: RollbackButtonProps) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function rollback() {
    setBusy(true);
    setError(null);
    try {
      await apiClient.rollbackPipeline(pipelineId, versionNumber);
      setConfirming(false);
      onRolledBack?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rollback failed");
    } finally {
      setBusy(false);
    }
  }

  if (confirming) {
    return (
      <div className="flex items-center gap-2">
        <span className="text-xs text-text-3">Roll back to this version?</span>
        <button
          type="button"
          onClick={() => void rollback()}
          disabled={busy}
          className="flex items-center gap-1 rounded-md bg-amber-500/90 px-2.5 py-1 text-xs font-semibold text-foreground hover:bg-amber-500 disabled:opacity-60"
        >
          {busy && <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />}
          Confirm
        </button>
        <button
          type="button"
          onClick={() => setConfirming(false)}
          disabled={busy}
          className="rounded-md px-2 py-1 text-xs text-text-3 hover:bg-white/5"
        >
          Cancel
        </button>
        {error && (
          <span role="alert" className="text-xs text-rose-400">
            {error}
          </span>
        )}
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={() => setConfirming(true)}
      className="flex items-center gap-1.5 rounded-md border border-border bg-accent/5 px-2.5 py-1 text-xs font-medium text-text-2 transition-colors hover:bg-accent/10"
    >
      <RotateCcw className="h-3 w-3" aria-hidden="true" />
      Rollback
    </button>
  );
}
