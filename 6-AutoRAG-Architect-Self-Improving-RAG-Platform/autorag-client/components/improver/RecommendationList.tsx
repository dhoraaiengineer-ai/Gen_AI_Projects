import { FAILURE_CODE_INFO } from "@/types";
import type { Recommendation } from "@/lib/variant";

interface RecommendationListProps {
  recommendations: Recommendation[];
}

/**
 * §29.8 Improvement Recommendations. Each card shows the failure code, label, and
 * the config-change rationale (from lib/variant `FIX`). No fabricated confidence
 * or expected-impact percentages — nothing in the platform computes them.
 */
export function RecommendationList({ recommendations }: RecommendationListProps) {
  if (recommendations.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-card p-6 text-sm text-text-3">
        No recommendations — the latest run reports no active failures.
      </div>
    );
  }

  return (
    <div className="space-y-4 rounded-xl border border-border bg-card p-5">
      {recommendations.map((rec) => (
        <div key={rec.code}>
          <p className="text-xs font-semibold uppercase tracking-wide text-text-3">
            <span className="font-mono text-amber-400">{rec.code}</span> {rec.label}
          </p>
          <p className="mt-1 text-sm text-text-2">{rec.rationale}</p>
          <p className="mt-1 text-xs text-text-3">{FAILURE_CODE_INFO[rec.code].description}</p>
        </div>
      ))}
    </div>
  );
}
