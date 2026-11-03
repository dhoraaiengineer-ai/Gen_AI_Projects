/**
 * Improver variant derivation (F-15) — pure, React-free, cheaply unit-testable.
 *
 * `GET /api/v1/improve/{run_id}` is real (autorag-server/app/routes/improve.py)
 * and returns 3 real backend-scored candidates (Part A/E, 12-Jul-2026) — but
 * their config schema (chunk_size, k_value, rerank_top_k, embedding_model,
 * prompt_template_version — autorag-server/app/graph/nodes/improver.py
 * `_DEFAULT_CONFIG`) does not overlap at all with what this file/the
 * Configurator wizard models (chunk_strategy, dense_weight, hybrid_ratio,
 * reranker_enabled, retrieval_k). Reconciling the two would mean either the
 * Configurator persisting a genuinely different config shape or the real
 * Improver being changed to optimize retrieval knobs instead of chunking/
 * embedding ones — a real product decision, not a wiring fix. Until that's
 * resolved, this file continues to derive a single *proposed* pipeline
 * variant deterministically from the persisted `failure_taxonomy` (F-01..F-06),
 * tuning only the config knobs a pipeline actually carries. The real 3-candidate
 * backend output is shown separately (ImproverAgentOutput component) rather
 * than forced into this schema.
 *
 * Tuned config knobs here:
 *
 *   - chunk_strategy        (top-level Pipeline field)
 *   - retrieval_config.dense_weight
 *   - retrieval_config.hybrid_ratio
 *   - retrieval_config.reranker_enabled
 *   - retrieval_config.retrieval_k
 *
 * These are the real keys the Configurator wizard persists (see lib/wizard.ts
 * `RetrievalConfig`). We do NOT invent chunk_size / overlap / compression knobs
 * that no pipeline stores, and we do NOT predict numeric scores — nothing in the
 * platform computes them (CLAUDE.md Forbidden Pattern #2, Rule 50).
 *
 * The per-code transforms mirror the verbatim remediation hints in
 * autorag-server/app/graph/nodes/diagnoser.py `_rule_based_classify()`.
 */

import { FAILURE_CODE_INFO, isFailureCode } from "@/types";
import type { FailureCode, Pipeline } from "@/types";

/** The tunable subset of pipeline configuration, normalized for diffing. */
export interface PipelineConfig {
  chunk_strategy: string;
  dense_weight: number;
  hybrid_ratio: number;
  reranker_enabled: boolean;
  retrieval_k: number;
}

export type ConfigKey = keyof PipelineConfig;

/** Ordered field metadata driving both the Current config panel and the diff table. */
export const CONFIG_FIELDS: { key: ConfigKey; label: string }[] = [
  { key: "chunk_strategy", label: "Chunk Strategy" },
  { key: "dense_weight", label: "Dense Weight" },
  { key: "hybrid_ratio", label: "Hybrid Ratio" },
  { key: "reranker_enabled", label: "Reranker" },
  { key: "retrieval_k", label: "Retrieval K" },
];

/** Defaults mirror lib/wizard.ts `initialWizardState().retrieval`. */
const RETRIEVAL_DEFAULTS = {
  dense_weight: 0.5,
  hybrid_ratio: 0.5,
  reranker_enabled: true,
  retrieval_k: 5,
} as const;

/**
 * Read a normalized PipelineConfig off a real Pipeline object (never throws).
 * The backend Pipeline row has no `retrieval_config` column — only
 * `chunk_strategy` is persisted — so the retrieval knobs always start at
 * RETRIEVAL_DEFAULTS until a real per-pipeline config store exists.
 */
export function extractConfig(pipeline: Pipeline): PipelineConfig {
  return {
    chunk_strategy: pipeline.chunk_strategy ?? "semantic",
    ...RETRIEVAL_DEFAULTS,
  };
}

// ── Bounds (mirror wizard validation: hybrid/dense 0..1, retrieval_k 1..50 int) ──
const clamp01 = (v: number): number => Math.min(1, Math.max(0, v));
const clampK = (v: number): number => Math.min(50, Math.max(1, Math.round(v)));

type Transform = (config: PipelineConfig) => PipelineConfig;

/** One deterministic config fix per failure code, with the rationale shown as the card copy. */
const FIX: Record<FailureCode, { rationale: string; apply: Transform }> = {
  "F-01": {
    rationale:
      "Retrieval miss — shift toward hybrid (BM25 + dense) and enable reranking so relevant chunks surface.",
    apply: (c) => ({ ...c, hybrid_ratio: clamp01(Math.max(c.hybrid_ratio, 0.6)), reranker_enabled: true }),
  },
  "F-02": {
    rationale:
      "Context overflow — reduce retrieval_k so the compressed context fits inside the token budget.",
    apply: (c) => ({ ...c, retrieval_k: clampK(c.retrieval_k - 2) }),
  },
  "F-03": {
    rationale:
      "Hallucination — raise retrieval_k and enable reranking to ground answers in more relevant context.",
    apply: (c) => ({ ...c, retrieval_k: clampK(c.retrieval_k + 3), reranker_enabled: true }),
  },
  "F-04": {
    rationale: "Answer incomplete — retrieve more chunks to close context gaps.",
    apply: (c) => ({ ...c, retrieval_k: clampK(c.retrieval_k + 2) }),
  },
  "F-05": {
    rationale: "Latency spike — reduce retrieval_k to cut retrieval and LLM input time.",
    apply: (c) => ({ ...c, retrieval_k: clampK(c.retrieval_k - 1) }),
  },
  "F-06": {
    rationale:
      "Quality drift — sustained multi-run decline; no single-run config knob fixes this deterministically. Trigger the real Improver agent instead of a client-derived guess.",
    apply: (c) => c,
  },
};

/** Canonical apply order so overlapping codes (e.g. F-03 raises k, F-05 lowers it) are deterministic. */
const CANONICAL_ORDER: FailureCode[] = ["F-01", "F-02", "F-03", "F-04", "F-05", "F-06"];

export interface Recommendation {
  code: FailureCode;
  label: string;
  rationale: string;
}

export interface ProposedResult {
  proposed: PipelineConfig;
  changedKeys: ConfigKey[];
  recommendations: Recommendation[];
}

function fieldsEqual(a: PipelineConfig[ConfigKey], b: PipelineConfig[ConfigKey]): boolean {
  return a === b;
}

/**
 * Derive the proposed variant + change set + recommendations from a run's failures.
 * Unrecognized codes are ignored; duplicates collapse; empty input yields an
 * unchanged config with no recommendations.
 */
export function deriveProposedConfig(
  current: PipelineConfig,
  failureCodes: string[],
): ProposedResult {
  const active = new Set(failureCodes.filter(isFailureCode));
  const ordered = CANONICAL_ORDER.filter((code) => active.has(code));

  let proposed = current;
  for (const code of ordered) {
    proposed = FIX[code].apply(proposed);
  }

  const changedKeys = CONFIG_FIELDS.map((f) => f.key).filter(
    (key) => !fieldsEqual(current[key], proposed[key]),
  );

  const recommendations: Recommendation[] = ordered.map((code) => ({
    code,
    label: FAILURE_CODE_INFO[code].label,
    rationale: FIX[code].rationale,
  }));

  return { proposed, changedKeys, recommendations };
}

/** Human-friendly rendering of a single config value (used by the panels + diff table). */
export function formatConfigValue(key: ConfigKey, value: PipelineConfig[ConfigKey]): string {
  if (typeof value === "boolean") return value ? "Enabled" : "Disabled";
  if (key === "retrieval_k") return String(value);
  if (typeof value === "number") return value.toFixed(2);
  return String(value);
}
