import { z } from "zod";

/** Zod mirrors of docs/API_SPEC.md response schemas. Every response is parsed before use (rules/20). */

export const MeSchema = z.object({
  id: z.string(),
  display_name: z.string(),
  role: z.enum(["vehicle_owner", "service_advisor", "technician", "warranty_admin", "admin"]),
  dealer_id: z.string().nullable(),
  dealer_name: z.string().nullable().optional(),
});
export type Me = z.infer<typeof MeSchema>;

export const TokenSchema = z.object({
  access_token: z.string(),
  token_type: z.literal("bearer"),
  expires_in: z.number(),
  user: MeSchema,
});

export const pageSchema = <T extends z.ZodTypeAny>(item: T) =>
  z.object({ items: z.array(item), next_cursor: z.string().nullable().optional() });

export const VehicleSummarySchema = z.object({
  id: z.string(),
  vin_masked: z.string(),
  model: z.string(),
  model_year: z.number(),
  plate_masked: z.string().nullable(),
  last_odometer_km: z.number().nullable(),
});
export type VehicleSummary = z.infer<typeof VehicleSummarySchema>;

export const CitationSchema = z.object({
  chunk_id: z.string(),
  source_file: z.string(),
  page: z.number(),
  section_id: z.string(),
  section_title: z.string(),
  quote: z.string(),
});
export type Citation = z.infer<typeof CitationSchema>;

export const BannerTierSchema = z.enum(["none", "info", "stop", "technician"]);

export const SafetyInfoSchema = z.object({
  safety_critical: z.boolean(),
  banner_tier: BannerTierSchema,
  banner_text: z.string().nullable(),
  required_action_quote: CitationSchema.nullable().optional(),
  escalation: z.string().nullable().optional(),
});
export type SafetyInfo = z.infer<typeof SafetyInfoSchema>;

export const RecallNoticeSchema = z.object({
  campaign_code: z.string(),
  title: z.string(),
  component_group: z.string(),
  notice: CitationSchema.nullable(),
});
export type RecallNotice = z.infer<typeof RecallNoticeSchema>;

export const StatusEventSchema = z.object({
  from_status: z.string().nullable(),
  to_status: z.string(),
  at: z.string(),
  actor_role: z.string(),
  reason: z.string().nullable().optional(),
});
export type StatusEvent = z.infer<typeof StatusEventSchema>;

export const ROStatusSchema = z.object({
  ro_ref: z.string(),
  ro_status: z.string(),
  history: z.array(StatusEventSchema),
  claim_ref: z.string().nullable().optional(),
  claim_status: z.string().nullable().optional(),
  eta: z.string().nullable().optional(),
  phrased: z.string(),
});

export const ROSummarySchema = z.object({
  id: z.string(),
  ro_ref: z.string(),
  status: z.string(),
  vehicle: z.object({ id: z.string(), model: z.string(), model_year: z.number(), vin_masked: z.string() }),
  created_at: z.string(),
  updated_at: z.string(),
});
export type ROSummary = z.infer<typeof ROSummarySchema>;

export const RODetailSchema = z.object({
  id: z.string(),
  ro_ref: z.string(),
  status: z.string(),
  dealer: z.object({ id: z.string(), name: z.string() }),
  vehicle: z.object({ id: z.string(), model: z.string(), model_year: z.number(), vin_masked: z.string() }),
  complaints: z.array(z.object({ text: z.string(), confirmed_by_advisor: z.boolean() })),
  check_in: z
    .object({
      odometer_in_km: z.number().nullable(),
      fuel_or_charge_level: z.string().nullable(),
      damage_notes: z.string().nullable(),
    })
    .nullable(),
  promised_ready_at: z.string().nullable(),
  timeline: z.array(StatusEventSchema),
});
export type RODetail = z.infer<typeof RODetailSchema>;

export const ChatReplySchema = z.object({
  conversation_id: z.string().nullable(),
  intent: z.string(),
  reply: z.string(),
  citations: z.array(CitationSchema),
  safety: SafetyInfoSchema,
  insufficient_evidence: z.boolean().nullable().optional(),
  next_question: z.string().nullable().optional(),
  options: z.array(z.string()),
  booking_draft: z.record(z.unknown()).nullable().optional(),
  ro_status: ROStatusSchema.nullable().optional(),
  recalls: z
    .array(z.object({ vehicle_id: z.string(), campaign_code: z.string(), title: z.string(), component_group: z.string() }))
    .nullable()
    .optional(),
});
export type ChatReply = z.infer<typeof ChatReplySchema>;
