"use client";

import { UnifiedScoreGauge } from "@/components/evaluation/UnifiedScoreGauge";
import { FAITHFULNESS_HARD_BLOCK } from "@/lib/score";
import { FAILURE_CODE_INFO, isFailureCode } from "@/types";
import type { FailureCode, ScoreResult } from "@/types";

interface RootCausePanelProps {
  score: ScoreResult;
}

/** Matches autorag-server/app/graph/nodes/diagnoser.py `_LATENCY_THRESHOLD_MS`. */
const LATENCY_GATE_MS = 3000;

/** Real metric/threshold that backs each failure code — no fabricated confidence score. */
function evidenceLine(code: FailureCode, score: ScoreResult): string {
  switch (code) {
    case "F-01":
      return `Recall ${score.recall !== null ? score.recall.toFixed(2) : "Unavailable"}`;
    case "F-02":
      return `Total tokens for this run: ${score.total_tokens === null ? "unknown" : score.total_tokens.toLocaleString()}`;
    case "F-03":
      return `Faithfulness ${score.faithfulness !== null ? score.faithfulness.toFixed(2) : "Unavailable"} < ${FAITHFULNESS_HARD_BLOCK} hard-block gate`;
    case "F-04":
      return `Quality ${score.quality !== null ? score.quality.toFixed(2) : "Unavailable"} (faithfulness ${score.faithfulness !== null ? score.faithfulness.toFixed(2) : "Unavailable"} is OK)`;
    case "F-05":
      return `Latency p95 ${score.latency_p95_ms !== null ? `${score.latency_p95_ms}ms` : "Unavailable"} > ${LATENCY_GATE_MS}ms SLA`;
    case "F-06":
      // Quality Drift is a multi-run signal (Observer's 5-run window) — not
      // representable from a single ScoreResult; see /observe for the real trend.
      return "Sustained score decline across recent runs — see Observer for trend detail.";
  }
}

/** Primary failure code (first in `failure_taxonomy`) + the real metric behind it. */
export function RootCausePanel({ score }: RootCausePanelProps) {
  const primaryCode = score.failure_taxonomy[0];
  const info = primaryCode && isFailureCode(primaryCode) ? FAILURE_CODE_INFO[primaryCode] : null;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[220px_1fr]">
      <div className="flex flex-col items-center justify-center rounded-lg border border-border bg-accent/5 p-4">
        {score.unified_score !== null ? (
          <UnifiedScoreGauge score={score.unified_score} />
        ) : (
          <p className="text-sm text-text-3">Not collected</p>
        )}
      </div>
      <div className="rounded-lg border border-border bg-accent/5 p-5">
        {!info || !isFailureCode(primaryCode) ? (
          <p className="text-sm text-text-3">No primary failure — pipeline passed all gates.</p>
        ) : (
          <>
            <p className="text-xs font-medium uppercase tracking-wide text-text-3">Primary Failure</p>
            <p className="mt-1 text-lg font-bold text-foreground">
              <span className="font-mono text-sm text-red-500">{primaryCode}</span> {info.label}
            </p>
            <p className="mt-2 text-sm text-text-3">{info.description}</p>
            <p className="mt-3 font-mono text-xs text-text-3">{evidenceLine(primaryCode, score)}</p>
          </>
        )}
      </div>
    </div>
  );
}
