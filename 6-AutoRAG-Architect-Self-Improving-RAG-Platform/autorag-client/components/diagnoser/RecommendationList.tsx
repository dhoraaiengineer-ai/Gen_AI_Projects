import { FAILURE_CODE_INFO, isFailureCode } from "@/types";
import type { FailureCode } from "@/types";

interface RecommendationListProps {
  codes: string[];
}

/**
 * Verbatim `remediation_hint` strings from the real rule-based branches in
 * autorag-server/app/graph/nodes/diagnoser.py `_rule_based_classify()` — the
 * actual recommendation the backend would compute, just not exposed via any
 * endpoint today. One recommendation per code (not a fabricated multi-item
 * list with invented confidence/impact scores — those aren't computed anywhere).
 */
const RECOMMENDATIONS: Record<FailureCode, string> = {
  "F-01": "Switch from dense-only to hybrid retrieval (BM25 + dense) and lower similarity threshold.",
  "F-02": "Reduce chunk_size or reduce top-k retrieval to fit context within token budget.",
  "F-03": "Increase retrieval k-value and apply cross-encoder reranking to surface more relevant context.",
  "F-04": "Review retrieved chunks and prompt template for completeness gaps.",
  "F-05": "Reduce top-k retrieval count and enable context compression to cut LLM input size.",
  "F-06": "Trigger the Improver agent to generate hyperparameter variants; review chunking strategy and embedding model version for data drift.",
};

export function RecommendationList({ codes }: RecommendationListProps) {
  const recognized = codes.filter(isFailureCode);

  if (recognized.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-card p-6 text-sm text-text-3">
        No recommendations — no active failures for this run.
      </div>
    );
  }

  return (
    <div className="space-y-4 rounded-xl border border-border bg-card p-5">
      {recognized.map((code) => (
        <div key={code}>
          <p className="text-xs font-semibold uppercase tracking-wide text-text-3">
            <span className="font-mono text-red-500">{code}</span> {FAILURE_CODE_INFO[code].label}
          </p>
          <p className="mt-1 text-sm text-text-2">{RECOMMENDATIONS[code]}</p>
        </div>
      ))}
    </div>
  );
}
