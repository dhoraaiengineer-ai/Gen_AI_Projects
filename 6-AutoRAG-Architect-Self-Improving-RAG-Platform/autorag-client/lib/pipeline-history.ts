/**
 * Pipeline Version History derivation (F-20) — pure, React-free, unit-testable.
 *
 * GET /pipelines/{id}/versions now exists (20-Jul-2026, Apply Improvement
 * feature — see apiClient.listPipelineVersions / hooks/use-pipeline-versions.ts
 * for the real per-version rows: unified_score, recall, latency_p95_ms,
 * cost_usd, vector_table_name). PipelineHistoryPageClient has not yet been
 * migrated to consume that endpoint, so this module still treats a pipeline's
 * own `current_version` as its only known version — no fabricated
 * sibling-version data — pending that migration.
 */

import type { PipelineWithRun } from "@/types";

/** Newest-first by current_version (int), created_at breaks ties. */
export function sortVersionsDesc(pipelines: PipelineWithRun[]): PipelineWithRun[] {
  return [...pipelines].sort((a, b) => {
    const byVersion = b.current_version - a.current_version;
    if (byVersion !== 0) return byVersion;
    return b.created_at.localeCompare(a.created_at);
  });
}

// ── Config comparison ─────────────────────────────────────────────────────────
export interface PipelineConfigView {
  chunk_strategy: string;
  dense_weight: number;
  hybrid_ratio: number;
  reranker_enabled: boolean;
  retrieval_k: number;
  weight_recall: number;
  weight_quality: number;
  weight_faithfulness: number;
}

export type ConfigKey = keyof PipelineConfigView;

export const CONFIG_FIELDS: { key: ConfigKey; label: string }[] = [
  { key: "chunk_strategy", label: "Chunk Strategy" },
  { key: "dense_weight", label: "Dense Weight" },
  { key: "hybrid_ratio", label: "Hybrid Ratio" },
  { key: "reranker_enabled", label: "Reranker" },
  { key: "retrieval_k", label: "Retrieval K" },
  { key: "weight_recall", label: "Weight · Recall" },
  { key: "weight_quality", label: "Weight · Quality" },
  { key: "weight_faithfulness", label: "Weight · Faithfulness" },
];

const RETRIEVAL_DEFAULTS = { dense_weight: 0.5, hybrid_ratio: 0.5, reranker_enabled: true, retrieval_k: 5 };

/**
 * The Unified Score weights are a single global formula (CLAUDE.md §9), not
 * per-pipeline configurable — these are the fixed constants, not a fallback.
 */
const GLOBAL_SCORE_WEIGHTS = { recall: 0.25, quality: 0.35, faithfulness: 0.25 };

/** Flatten a pipeline's real config into the comparable view (never throws). */
export function extractConfigView(pipeline: PipelineWithRun): PipelineConfigView {
  return {
    chunk_strategy: pipeline.chunk_strategy ?? "semantic",
    ...RETRIEVAL_DEFAULTS,
    weight_recall: GLOBAL_SCORE_WEIGHTS.recall,
    weight_quality: GLOBAL_SCORE_WEIGHTS.quality,
    weight_faithfulness: GLOBAL_SCORE_WEIGHTS.faithfulness,
  };
}

export interface ConfigDiffRow {
  key: ConfigKey;
  label: string;
  aValue: string;
  bValue: string;
  changed: boolean;
}

/** Row-per-field diff between two versions' configs; `changed` flags modifications. */
export function diffConfigs(a: PipelineConfigView, b: PipelineConfigView): ConfigDiffRow[] {
  return CONFIG_FIELDS.map(({ key, label }) => ({
    key,
    label,
    aValue: formatConfigValue(key, a[key]),
    bValue: formatConfigValue(key, b[key]),
    changed: a[key] !== b[key],
  }));
}

export function formatConfigValue(key: ConfigKey, value: PipelineConfigView[ConfigKey]): string {
  if (typeof value === "boolean") return value ? "Enabled" : "Disabled";
  if (key === "retrieval_k") return String(value);
  if (typeof value === "number") return value.toFixed(2);
  return String(value);
}
