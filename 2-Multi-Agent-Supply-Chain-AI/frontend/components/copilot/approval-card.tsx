"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { CheckCircle2, Clock, UserCheck, XCircle } from "lucide-react";
import { toast } from "sonner";
import type { ApprovalRequest } from "@/types";
import { useCurrentUser, useDecideApproval } from "@/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { cn, fmt, timeUntil } from "@/lib/utils";

const CAN_APPROVE = new Set(["approver", "admin"]);

/** Human-in-the-loop checkpoint: the graph is paused until an approver decides. */
export function ApprovalCard({
  approval,
  onDecided,
  compact = false,
  className,
}: {
  approval: ApprovalRequest;
  onDecided?: (status: ApprovalRequest["status"]) => void;
  /** Compact: one-line summary with inline actions (dashboard); full: details and audit comment (Copilot). */
  compact?: boolean;
  className?: string;
}) {
  const { data: user } = useCurrentUser();
  const decide = useDecideApproval();
  const [comment, setComment] = useState("");
  const canApprove = user ? CAN_APPROVE.has(user.role) : false;
  const pending = approval.status === "pending";

  const submit = (decision: "approved" | "rejected") =>
    decide.mutate(
      { id: approval.id, decision, comment: comment || undefined },
      {
        onSuccess: () => {
          onDecided?.(decision);
          toast.success(decision === "approved" ? "PO draft approved — workflow resumed" : "PO draft rejected", {
            description: `${approval.sku} · ${approval.quantity.toLocaleString()} units from ${approval.supplier}`,
          });
        },
        onError: () => toast.error("We couldn't record your decision. Please try again."),
      },
    );

  if (compact && pending) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        role="region"
        aria-label="Approval required"
        className={cn("flex flex-col gap-3 rounded-lg border border-warning/40 bg-card px-4 py-3 shadow-card sm:flex-row sm:items-center", className)}
      >
        <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-warning/15 text-warning-foreground">
          <UserCheck className="size-4" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[13.5px] font-semibold">
            Approval required · PO draft for {approval.sku}
            <span className="ml-2 inline-flex items-center gap-1 text-[11.5px] font-normal text-muted-foreground">
              <Clock className="size-3" aria-hidden /> Expires {timeUntil(approval.expiresAt)}
            </span>
          </p>
          <p className="truncate text-[12.5px] text-muted-foreground">
            {approval.quantity.toLocaleString()} units from {approval.supplier} · <span className="font-medium text-foreground tabular">{fmt.usd(approval.value)}</span> — above the policy threshold
          </p>
        </div>
        {canApprove ? (
          <div className="flex gap-2">
            <Button size="sm" onClick={() => submit("approved")} disabled={decide.isPending}>
              <CheckCircle2 /> Approve
            </Button>
            <Button size="sm" variant="outline" onClick={() => submit("rejected")} disabled={decide.isPending}>
              Reject
            </Button>
          </div>
        ) : (
          <span className="text-[12.5px] text-muted-foreground">Awaiting approver</span>
        )}
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "rounded-lg border p-4",
        pending ? "border-warning/40 bg-warning/[0.04]" : approval.status === "approved" ? "border-success/30 bg-success/[0.04]" : "border-border",
        className,
      )}
      role="region"
      aria-label="Approval required"
    >
      <div className="flex items-start gap-3">
        <span className={cn("flex size-8 shrink-0 items-center justify-center rounded-full", pending ? "bg-warning/15 text-warning-foreground" : "bg-success/10 text-success")}>
          {pending ? <UserCheck className="size-4" aria-hidden /> : approval.status === "approved" ? <CheckCircle2 className="size-4" /> : <XCircle className="size-4" />}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold">
              {pending ? "Approval required" : approval.status === "approved" ? "Approved — PO draft created" : "Rejected — no PO created"}
            </p>
            {pending && (
              <span className="inline-flex items-center gap-1 text-[11.5px] text-muted-foreground">
                <Clock className="size-3" aria-hidden /> Expires {timeUntil(approval.expiresAt)}
              </span>
            )}
          </div>
          <p className="mt-0.5 text-[13px] text-muted-foreground">{approval.reason}</p>
          <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1.5 text-[13px] sm:grid-cols-4">
            <div>
              <dt className="text-[11.5px] text-muted-foreground">SKU</dt>
              <dd className="font-mono text-xs font-medium">{approval.sku}</dd>
            </div>
            <div>
              <dt className="text-[11.5px] text-muted-foreground">Supplier</dt>
              <dd className="font-medium">{approval.supplier}</dd>
            </div>
            <div>
              <dt className="text-[11.5px] text-muted-foreground">Quantity</dt>
              <dd className="font-medium tabular">{approval.quantity.toLocaleString()} units</dd>
            </div>
            <div>
              <dt className="text-[11.5px] text-muted-foreground">PO value</dt>
              <dd className="font-semibold tabular">{fmt.usd(approval.value)}</dd>
            </div>
          </dl>
          {pending &&
            (canApprove ? (
              <div className="mt-3 space-y-2">
                <Textarea
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="Optional comment for the audit log"
                  aria-label="Approval comment"
                  className="min-h-12 text-[13px]"
                  maxLength={500}
                />
                <div className="flex gap-2">
                  <Button size="sm" onClick={() => submit("approved")} disabled={decide.isPending}>
                    <CheckCircle2 /> Approve PO draft
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => submit("rejected")} disabled={decide.isPending}>
                    Reject
                  </Button>
                </div>
              </div>
            ) : (
              <p className="mt-3 text-[12.5px] text-muted-foreground">Waiting for an approver. You can track this in Activity.</p>
            ))}
        </div>
      </div>
    </motion.div>
  );
}
