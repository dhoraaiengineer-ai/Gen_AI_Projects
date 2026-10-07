import type { ApprovalRequest } from "@/types";
import { daysFromNow } from "./rng";

/** In-memory approval queue for demo mode (the backend persists approvals in Postgres). */
export const approvals = new Map<string, ApprovalRequest>([
  [
    "APR-7F3A1",
    {
      id: "APR-7F3A1",
      runId: "run_demo_sku100",
      sku: "SKU-100",
      supplier: "Nordvolt Energy",
      quantity: 10_000,
      unitPrice: 11,
      value: 110_000,
      reason: "PO value $110,000 exceeds the $50,000 approval threshold (Procurement Policy §4.2)",
      expiresAt: daysFromNow(1).toISOString(),
      status: "pending",
    },
  ],
]);

export function registerApproval(approval: ApprovalRequest): void {
  approvals.set(approval.id, approval);
}
