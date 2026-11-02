import { z } from "zod";

import { CitationSchema, SafetyInfoSchema } from "./schemas";

/** Mirrors docs/API_SPEC.md §3.8 (diagnosis + findings). */
export const DTC_FORMAT = /^[PBCU][0-9A-F]{4}$/;

export const DiagnosisResultSchema = z.object({
  dtc_meanings: z.array(
    z.object({ code: z.string(), meaning_quote: CitationSchema.nullable().optional(), not_found: z.boolean() }),
  ),
  hypotheses: z.array(
    z.object({
      rank: z.number(),
      cause: z.string(),
      evidence: z.string(),
      citations: z.array(CitationSchema).min(1),
      confidence: z.number(),
      next_test: CitationSchema.nullable().optional(),
    }),
  ),
  matched_tsbs: z.array(
    z.object({
      tsb_code: z.string(),
      title: z.string(),
      op_code: z.string().nullable(),
      match_reason: z.enum(["dtc", "keyword"]),
      matched_terms: z.array(z.string()),
      source: CitationSchema.nullable(),
    }),
  ),
  insufficient_evidence: z.boolean(),
  safety: SafetyInfoSchema,
  ai_label: z.string(),
  refusal_reason: z.string().nullable().optional(),
  dropped_hypotheses: z.number(),
});
export type DiagnosisResult = z.infer<typeof DiagnosisResultSchema>;

export const FindingOutSchema = z.object({ finding_id: z.string(), replayed: z.boolean() });

export const FindingSummarySchema = z.object({
  id: z.string(),
  dtcs: z.array(z.string()),
  confirmed_hypothesis: z.string().nullable(),
  op_codes_performed: z.array(z.string()),
  actual_hours: z.string().nullable(),
  parts_used: z.array(z.record(z.string())),
  created_at: z.string(),
});

/** Split free text ("p0301, P0420 c0035") into upper-case codes; report the ones that are not valid DTCs. */
export function parseDtcs(text: string): { codes: string[]; invalid: string[] } {
  const codes = [...new Set(text.split(/[\s,;]+/).map((c) => c.trim().toUpperCase()).filter(Boolean))];
  return { codes, invalid: codes.filter((c) => !DTC_FORMAT.test(c)) };
}
