"use client";

import { useState } from "react";
import { Pause, Play, RotateCcw, Square, TrendingUp } from "lucide-react";

import { apiClient } from "@/services/api-client";
import { scoreBand } from "@/lib/score";
import { RollbackConfirmDialog } from "@/components/deployment/RollbackConfirmDialog";
import type { Deployment, PipelineWithRun } from "@/types";

interface DeployActionButtonsProps {
  pipeline: PipelineWithRun;
  current: Deployment | null;
  onActionComplete: () => void;
}

type ConfirmTarget = "rollback" | "stop" | null;

/**
 * Promote / Rollback / Pause / Stop controls (STARTER_KIT E-12 component list).
 * Pause and Stop are rendered per spec but disabled: the deployments table has
 * no 'paused'/'stopped' status and no agent logic backs either action yet.
 */
export function DeployActionButtons({ pipeline, current, onActionComplete }: DeployActionButtonsProps) {
  const [runId, setRunId] = useState("");
  const [taskArn, setTaskArn] = useState("");
  const [approvalToken, setApprovalToken] = useState("");
  const [busy, setBusy] = useState<"deploy" | "promote" | "rollback" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmTarget, setConfirmTarget] = useState<ConfirmTarget>(null);

  const latestRun = pipeline.latest_run;
  // unified_score is null when the run failed before Evaluator ever ran --
  // treat the same as "no run" rather than coercing to a fake "retry" band.
  const band = latestRun && latestRun.unified_score !== null ? scoreBand(latestRun.unified_score) : null;
  const canDeploy =
    (!current || ["promoted", "rolled_back", "failed"].includes(current.status)) &&
    band !== null &&
    band !== "retry";
  const needsApprovalToken = band === "hitl";
  const canPromote = current?.status === "blue_green";
  const canRollback = current?.status === "promoted";

  async function handleDeploy() {
    if (!runId.trim() || !taskArn.trim()) {
      setError("run_id and task_arn are both required to deploy.");
      return;
    }
    setBusy("deploy");
    setError(null);
    try {
      await apiClient.deploy(runId.trim(), {
        task_arn: taskArn.trim(),
        approval_token: approvalToken.trim() || undefined,
      });
      setRunId("");
      setTaskArn("");
      setApprovalToken("");
      onActionComplete();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Deploy failed");
    } finally {
      setBusy(null);
    }
  }

  async function handlePromote() {
    setBusy("promote");
    setError(null);
    try {
      await apiClient.promote(pipeline.id);
      onActionComplete();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Promote failed");
    } finally {
      setBusy(null);
    }
  }

  async function handleRollback() {
    setBusy("rollback");
    setError(null);
    try {
      await apiClient.rollback(pipeline.id, "Manual rollback triggered from Deployment Center");
      setConfirmTarget(null);
      onActionComplete();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rollback failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-4">
      {error && (
        <p role="alert" className="rounded-md bg-status-error/10 px-3 py-2 text-xs text-status-error">
          {error}
        </p>
      )}

      {canDeploy && (
        <div className="grid grid-cols-1 gap-2 rounded-lg border border-border bg-accent/5 p-3 sm:grid-cols-3">
          <input
            type="text"
            value={runId}
            onChange={(e) => setRunId(e.target.value)}
            placeholder="Evaluation run_id"
            aria-label="Evaluation run ID to deploy"
            className="rounded-md border border-border bg-card px-3 py-1.5 text-xs text-foreground placeholder:text-text-3 focus:border-accent focus:outline-none"
          />
          <input
            type="text"
            value={taskArn}
            onChange={(e) => setTaskArn(e.target.value)}
            placeholder="ECS task ARN (immutable SHA tag)"
            aria-label="Immutable ECS task ARN"
            className="rounded-md border border-border bg-card px-3 py-1.5 text-xs text-foreground placeholder:text-text-3 focus:border-accent focus:outline-none"
          />
          {needsApprovalToken ? (
            <input
              type="text"
              value={approvalToken}
              onChange={(e) => setApprovalToken(e.target.value)}
              placeholder="HITL approval token"
              aria-label="HITL approval token"
              className="rounded-md border border-border bg-card px-3 py-1.5 text-xs text-foreground placeholder:text-text-3 focus:border-accent focus:outline-none"
            />
          ) : (
            <div />
          )}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {canDeploy && (
          <button
            type="button"
            onClick={handleDeploy}
            disabled={busy !== null}
            aria-busy={busy === "deploy"}
            className="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-semibold text-foreground hover:bg-accent-light disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Play className="h-3.5 w-3.5" aria-hidden="true" />
            {busy === "deploy" ? "Deploying…" : "Deploy"}
          </button>
        )}

        <button
          type="button"
          onClick={handlePromote}
          disabled={!canPromote || busy !== null}
          aria-busy={busy === "promote"}
          title={canPromote ? undefined : "No active Blue/Green canary to promote"}
          className="inline-flex items-center gap-1.5 rounded-md bg-status-success/15 px-3 py-1.5 text-xs font-semibold text-green-400 hover:bg-status-success/25 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <TrendingUp className="h-3.5 w-3.5" aria-hidden="true" />
          {busy === "promote" ? "Promoting…" : "Promote"}
        </button>

        <button
          type="button"
          onClick={() => setConfirmTarget("rollback")}
          disabled={!canRollback || busy !== null}
          title={canRollback ? undefined : "No promoted deployment to roll back"}
          className="inline-flex items-center gap-1.5 rounded-md bg-status-error/15 px-3 py-1.5 text-xs font-semibold text-red-500 hover:bg-status-error/25 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
          Rollback
        </button>

        <button
          type="button"
          disabled
          title="Not supported by backend yet — no 'paused' deployment state exists"
          className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs font-semibold text-text-3 opacity-50"
        >
          <Pause className="h-3.5 w-3.5" aria-hidden="true" />
          Pause
        </button>

        <button
          type="button"
          disabled
          title="Not supported by backend yet — no 'stopped' deployment state exists"
          className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs font-semibold text-text-3 opacity-50"
        >
          <Square className="h-3.5 w-3.5" aria-hidden="true" />
          Stop
        </button>
      </div>

      <RollbackConfirmDialog
        open={confirmTarget === "rollback"}
        actionLabel="Rollback"
        description="This reverts the pipeline's live traffic back to the previous Blue task ARN immediately. This action is logged to the audit trail."
        busy={busy === "rollback"}
        onConfirm={handleRollback}
        onCancel={() => setConfirmTarget(null)}
      />
    </div>
  );
}
