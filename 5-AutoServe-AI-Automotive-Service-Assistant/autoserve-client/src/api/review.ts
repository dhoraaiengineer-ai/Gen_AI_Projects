import { z } from "zod";

import { VehicleContextSchema } from "./advisor";
import { CitationSchema } from "./schemas";

/** Mirrors docs/API_SPEC.md §3.7 (estimate/workflow) and §3.9–3.10 (warranty, review). */
export const AI_LABEL = "AI-generated preliminary assessment — not a decision.";

export const EstimateLineSchema = z.object({
  id: z.string(),
  kind: z.enum(["labour", "part", "tax"]),
  op_code: z.string().nullable(),
  part_number: z.string().nullable(),
  description: z.string(),
  qty: z.string(),
  hours: z.string().nullable(),
  unit_price: z.string(),
  amount: z.string(),
  pay_type: z.enum(["warranty", "recall", "customer"]),
  display_status: z.enum(["decision_needed", "pending_warranty_review", "recall", "tax"]),
  owner_decision: z.enum(["approved", "declined"]).nullable(),
});
export type EstimateLine = z.infer<typeof EstimateLineSchema>;

export const EstimateViewSchema = z.object({
  estimable: z.boolean(),
  lines: z.array(EstimateLineSchema),
  totals: z.record(z.string()),
  ro_status: z.string(),
  ai_label: z.string(),
});
export type EstimateView = z.infer<typeof EstimateViewSchema>;

export const WorkflowRunSchema = z.object({
  thread_id: z.string(),
  route: z.string().nullable(),
  reasons: z.array(z.string()),
  ro_status: z.string(),
  waiting_for: z.string().nullable(),
  claim: z.object({ id: z.string(), claim_ref: z.string(), status: z.string() }).nullable().optional(),
  trace: z.array(z.record(z.unknown())),
  replayed: z.boolean(),
});

export const DecisionOutSchema = z.object({ status: z.string(), decision_id: z.string(), replayed: z.boolean() });
export const SendOutSchema = z.object({ status: z.string(), notification_ids: z.array(z.string()), replayed: z.boolean() });
export const TransitionOutSchema = z.object({ id: z.string(), status: z.string(), replayed: z.boolean() });

export const ClaimRowSchema = z.object({
  id: z.string(),
  claim_ref: z.string(),
  status: z.string(),
  ro_id: z.string(),
  ro_ref: z.string(),
  model: z.string(),
  model_year: z.number(),
  risk_level: z.enum(["none", "low", "medium", "high"]),
  age_days: z.number(),
  total_claimed: z.string().nullable(),
});
export type ClaimRow = z.infer<typeof ClaimRowSchema>;

export const FieldRowSchema = z.object({
  id: z.string(),
  document_id: z.string(),
  doc_class: z.string().nullable(),
  name: z.string(),
  value: z.string().nullable(),
  confidence: z.number(),
  source_page: z.number(),
  validation_status: z.string(),
  needs_human_verification: z.boolean(),
  previous_value: z.string().nullable(),
  edit_reason: z.string().nullable(),
});
export type FieldRow = z.infer<typeof FieldRowSchema>;

export const FlagRowSchema = z.object({
  id: z.string(),
  detector_id: z.string(),
  severity: z.string(),
  evidence: z.record(z.unknown()),
  explanation: z.string(),
  status: z.string(),
});

export const WorkspaceSchema = z.object({
  summary: z.record(z.unknown()),
  vehicle_context: VehicleContextSchema,
  diagnosis: z.record(z.unknown()),
  extracted_fields: z.array(FieldRowSchema),
  checklist: z.record(z.string()),
  warranty_rules: z.array(
    z.object({ rule_id: z.string(), result: z.string(), inputs: z.record(z.unknown()), clause: CitationSchema.nullable() }),
  ),
  estimate: z.array(
    z.object({
      kind: z.string(),
      code: z.string().nullable(),
      description: z.string(),
      qty: z.string(),
      amount: z.string(),
      pay_type: z.string(),
      owner_decision: z.string().nullable(),
    }),
  ),
  risk_indicators: z.array(FlagRowSchema),
  audit_trail: z.array(
    z.object({
      seq: z.number(),
      occurred_at: z.string(),
      actor_role: z.string(),
      action: z.string(),
      entity_type: z.string(),
      summary: z.string(),
    }),
  ),
  allowed_decisions: z.array(z.string()),
  ai_label: z.string(),
});
export type Workspace = z.infer<typeof WorkspaceSchema>;

export const ClaimDecisionOutSchema = z.object({
  status: z.string(),
  decision_id: z.string(),
  oem_ack: z.record(z.unknown()).nullable().optional(),
  replayed: z.boolean(),
});
export const DraftSchema = z.object({ draft: z.string(), ai_label: z.string() });
