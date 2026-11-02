import { z } from "zod";

import { CitationSchema, RecallNoticeSchema } from "./schemas";

export const BoardItemSchema = z.object({
  appointment_id: z.string(),
  ro_id: z.string(),
  ro_ref: z.string(),
  ro_status: z.string(),
  slot_start: z.string(),
  vehicle_id: z.string(),
  model: z.string(),
  model_year: z.number(),
  vin_masked: z.string(),
  owner_display_name: z.string(),
  complaint_text: z.string(),
});
export type BoardItem = z.infer<typeof BoardItemSchema>;

export const RiskFlagSchema = z.object({
  id: z.string(),
  detector_id: z.string(),
  severity: z.string(),
  evidence: z.record(z.unknown()),
  explanation: z.string(),
  status: z.string(),
});

export const VehicleContextSchema = z.object({
  vehicle_id: z.string(),
  model: z.string(),
  model_year: z.number(),
  decoded: z.object({ wmi: z.string(), model: z.string(), model_year: z.number(), plant: z.string(), serial: z.string() }).nullable(),
  in_service_date: z.string().nullable(),
  service_history: z.array(
    z.object({ date: z.string(), odometer_km: z.number(), op_codes: z.array(z.string()), dealer_name: z.string() }),
  ),
  maintenance_due: z
    .object({
      status: z.enum(["ok", "overdue", "unknown"]),
      based_on: z.string(),
      due_at_km: z.number().nullable(),
      due_at_date: z.string().nullable(),
      overdue_by_km: z.number().nullable(),
      overdue_by_days: z.number().nullable(),
      current_km: z.number().nullable(),
      source: CitationSchema.nullable(),
    })
    .nullable(),
  open_recalls: z.array(RecallNoticeSchema),
  applicable_tsbs: z.array(
    z.object({
      tsb_code: z.string(),
      title: z.string(),
      op_code: z.string().nullable(),
      match_reason: z.enum(["dtc", "keyword"]),
      matched_terms: z.array(z.string()),
      source: CitationSchema.nullable(),
    }),
  ),
  warranty_coverage: z.array(
    z.object({
      coverage: z.string(),
      status: z.enum(["active", "expired", "unknown"]),
      end_date: z.string().nullable(),
      km_limit: z.number(),
      km_remaining: z.number().nullable(),
      source: CitationSchema.nullable(),
    }),
  ),
  risk_flags: z.array(RiskFlagSchema),
});
export type VehicleContext = z.infer<typeof VehicleContextSchema>;

export const CheckInResultSchema = z.object({
  ro_id: z.string(),
  ro_ref: z.string(),
  status: z.string(),
  vehicle_context: VehicleContextSchema,
  replayed: z.boolean(),
});
