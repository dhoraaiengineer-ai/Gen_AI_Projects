/**
 * Unified Score presentation logic — the single source for score colour rules.
 * Mirrors UI/UX Design System SOT §7 "Score Color Rules" exactly. Pure functions
 * (no React) so they are cheaply unit-testable — the highest bug-risk area (Dev Notes).
 */

import type { PipelineRunSummary } from "@/types";

export const HITL_LOWER = 0.7; // inclusive lower bound for HITL band
export const DEPLOY_GATE = 0.85; // >= this is deploy-eligible
export const FAITHFULNESS_HARD_BLOCK = 0.5; // < this is a non-bypassable hard block

export type ScoreBand = "deploy" | "hitl" | "retry";

/** Classify a unified score into its governance band. */
export function scoreBand(score: number): ScoreBand {
  if (score >= DEPLOY_GATE) return "deploy";
  if (score >= HITL_LOWER) return "hitl";
  return "retry";
}

/**
 * Tailwind classes for a unified-score chip — light-first palette
 * (ADR-008, frontend_design.md §2/§18 — updated 12-Jul-2026 from the
 * original dark-theme SOT values, which read as light-text-on-dark-bg
 * and were low-contrast once the app flipped to a light workspace):
 *   >= 0.85 (deploy) → emerald
 *   >= 0.70 (hitl)   → amber
 *   <  0.70 (retry)  → rose
 */
export function scoreColorClasses(score: number): string {
  switch (scoreBand(score)) {
    case "deploy":
      return "text-emerald-700 bg-emerald-50";
    case "hitl":
      return "text-amber-700 bg-amber-50";
    case "retry":
      return "text-rose-700 bg-rose-50";
  }
}

/**
 * True when faithfulness breaches the non-bypassable hard-block gate.
 * `null` (never measured) is explicitly NOT a hard block -- it's an
 * unrelated "no data yet" state, not a failed safety check (13-Jul-2026 fix:
 * `null < 0.5` coerces to `true` in JS, silently mislabeling every
 * never-evaluated run as hard-blocked).
 */
export function isHardBlock(faithfulness: number | null): boolean {
  return faithfulness !== null && faithfulness < FAITHFULNESS_HARD_BLOCK;
}

/**
 * True when a run is awaiting human-in-the-loop approval (SOT §7 HITL queue).
 * Deployment gating is a single global score formula (CLAUDE.md §9) — there is
 * no per-pipeline approval_mode on the real backend, so any run whose score
 * falls in the HITL band is pending, unconditionally.
 */
export function isHitlPending(
  run: Pick<PipelineRunSummary, "unified_score"> | null | undefined,
): boolean {
  if (!run || run.unified_score === null) return false;
  return run.unified_score >= HITL_LOWER && run.unified_score < DEPLOY_GATE;
}

/** Format a 0–1 score as a 2-dp value, or an em dash when absent. */
export function formatScore(score: number | null | undefined): string {
  if (score === null || score === undefined || Number.isNaN(score)) return "—";
  return score.toFixed(2);
}

/** Format a 0–1 score as a whole-number percentage — "0.590" tells most
 * users nothing; "59%" does. */
export function formatScorePercent(score: number | null | undefined): string {
  if (score === null || score === undefined || Number.isNaN(score)) return "—";
  return `${Math.round(score * 100)}%`;
}

/** Short, honest label for a score band — never a bare number with no
 * context for what it means against the real deployment gates above. */
export function scoreBandLabel(score: number): string {
  switch (scoreBand(score)) {
    case "deploy":
      return "Deploy Ready";
    case "hitl":
      return "Needs Review";
    case "retry":
      return "Needs Improvement";
  }
}

// ─────────────────────────────────────────────────────────────────────────
// Evaluation Results V4 (26-Jul-2026) — rule-based Insights/Recommendations/
// Conclusion. Deliberately deterministic (threshold comparisons against real
// computed averages), not LLM-generated — avoids an extra judge call for
// content that's honestly derivable from data already on hand. See
// VERSION_5_ROADMAP.md for the AI-generated, confidence-scored V5 upgrade.
// ─────────────────────────────────────────────────────────────────────────

export type RagasMetricKey =
  | "faithfulness"
  | "context_recall"
  | "answer_relevancy"
  | "context_precision"
  | "answer_correctness";

export type MetricAverages = Record<RagasMetricKey, number | null>;

/** One-line description + label per metric — real, static, no LLM needed.
 * Powers the Overall Metrics row's tooltip/description (V4 spec item 2). */
export const METRIC_INFO: Record<RagasMetricKey, { label: string; description: string }> = {
  faithfulness: {
    label: "Faithfulness",
    description: "Measures whether the answer is supported by retrieved context.",
  },
  context_recall: {
    label: "Context Recall",
    description: "Measures whether retrieval fetched everything the answer needed.",
  },
  answer_relevancy: {
    label: "Answer Relevancy",
    description: "Measures how directly the answer addresses the question asked.",
  },
  context_precision: {
    label: "Context Precision",
    description: "Measures whether the most useful chunks were ranked first.",
  },
  answer_correctness: {
    label: "Answer Correctness",
    description: "Measures factual correctness against a known ground-truth answer.",
  },
};

export interface DerivedInsights {
  strengths: string[];
  weaknesses: string[];
}

/** Threshold-based strengths/weaknesses from real metric averages. Reuses
 * this module's own DEPLOY_GATE/HITL_LOWER bands for consistency with every
 * other score-quality judgment elsewhere in the app, rather than inventing
 * new, unrelated thresholds. */
export function deriveInsights(metricAverages: Partial<MetricAverages>): DerivedInsights {
  const strengths: string[] = [];
  const weaknesses: string[] = [];
  for (const key of Object.keys(METRIC_INFO) as RagasMetricKey[]) {
    const value = metricAverages[key];
    if (value === null || value === undefined) continue;
    const { label } = METRIC_INFO[key];
    if (value >= DEPLOY_GATE) {
      strengths.push(`Excellent ${label.toLowerCase()} (${formatScorePercent(value)})`);
    } else if (value < HITL_LOWER) {
      weaknesses.push(`${label} could improve (${formatScorePercent(value)})`);
    }
  }
  return { strengths, weaknesses };
}

/** One real, generic suggestion per below-threshold metric — explicitly
 * general guidance, not a numeric expected-impact estimate (that needs
 * historical trend data this app doesn't collect yet — real V5 scope). */
export function deriveRecommendations(
  metricAverages: Partial<MetricAverages>,
  latencyP95Ms?: number | null,
): string[] {
  const recs: string[] = [];
  if ((metricAverages.context_recall ?? 1) < HITL_LOWER) {
    recs.push("Increase Top-K to retrieve more candidate chunks.");
  }
  if ((metricAverages.context_precision ?? 1) < HITL_LOWER) {
    recs.push("Review reranking configuration — top-ranked chunks aren't the most useful ones.");
  }
  if ((metricAverages.faithfulness ?? 1) < HITL_LOWER) {
    recs.push("Review retrieved context — generated answers aren't staying grounded in it.");
  }
  if ((metricAverages.answer_correctness ?? 1) < HITL_LOWER) {
    recs.push("Review prompt instructions — answers are diverging from ground truth.");
  }
  if (latencyP95Ms !== null && latencyP95Ms !== undefined && latencyP95Ms > 3000) {
    recs.push("Enable context compression to reduce latency.");
  }
  return recs;
}

/** One templated paragraph combining the verdict + top strength/weakness —
 * composition of already-derived real values, not a separate generation
 * step (V4 spec item 8, "Evaluation Conclusion"). */
export function buildConclusion(
  averageUnifiedScore: number | null,
  insights: DerivedInsights,
): string {
  if (averageUnifiedScore === null) {
    return "No completed evaluations yet — run this dataset to see a conclusion here.";
  }
  const band = scoreBandLabel(averageUnifiedScore);
  const strength = insights.strengths[0];
  const weakness = insights.weaknesses[0];
  const parts = [`Overall assessment: ${band} (${formatScorePercent(averageUnifiedScore)}).`];
  if (strength) parts.push(strength + ".");
  if (weakness) parts.push(weakness + ".");
  return parts.join(" ");
}
