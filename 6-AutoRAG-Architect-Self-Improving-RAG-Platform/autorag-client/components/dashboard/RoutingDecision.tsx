"use client";

import { DEPLOY_GATE, FAITHFULNESS_HARD_BLOCK, HITL_LOWER, scoreBand } from "@/lib/score";
import type { ScoreResult } from "@/types";

interface RoutingDecisionProps {
  score: ScoreResult;
}

type Band = "deploy" | "hitl" | "retry";

const BAND_META: Record<Band, { label: string; color: string; bg: string }> = {
  deploy: { label: "AUTO DEPLOY", color: "#10B981", bg: "rgba(16,185,129,0.12)" },
  hitl: { label: "HITL REQUIRED", color: "#F59E0B", bg: "rgba(245,158,11,0.12)" },
  retry: { label: "IMPROVE / RETRY", color: "#F43F5E", bg: "rgba(244,63,94,0.12)" },
};

/**
 * Part H — Routing Decision. The core product-story surface: explains WHY the
 * graph chose Deploy / HITL / Improve. Implements the null-score routing rule
 * (Part G's crash-class fix): unified_score === null is never evaluated
 * against the 0.85/0.70 threshold bands or treated as a hard block -- it's an
 * honest "no evaluation result" state, distinct from a real low score.
 */
export function RoutingDecision({ score }: RoutingDecisionProps) {
  const faithfulnessBlocked = score.faithfulness !== null && score.faithfulness < FAITHFULNESS_HARD_BLOCK;
  const adversarialBlocked = !score.adversarial_passed;
  const hasHardGateBlock = faithfulnessBlocked || adversarialBlocked;

  // Null score: no band can be computed, and no hard gate can be evaluated
  // either (faithfulness/adversarial are only meaningful once Evaluator ran).
  if (score.unified_score === null) {
    return (
      <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
        <p className="mb-3 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
          Routing Decision
        </p>
        <div className="rounded-lg border border-border bg-card p-4 text-center">
          <p className="text-sm font-semibold text-text-3">NO EVALUATION RESULT</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Not collected — this run (status: {score.status}) did not reach the Evaluator, so no
            routing decision was made.
          </p>
        </div>
      </div>
    );
  }

  const band: Band = hasHardGateBlock ? "retry" : scoreBand(score.unified_score);
  const meta = BAND_META[band];

  const bands: { key: Band; label: string; range: string }[] = [
    { key: "deploy", label: "AUTO DEPLOY", range: `≥ ${DEPLOY_GATE}` },
    { key: "hitl", label: "HITL", range: `${HITL_LOWER}–${DEPLOY_GATE - 0.01}` },
    { key: "retry", label: "IMPROVE", range: `< ${HITL_LOWER}` },
  ];

  return (
    <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
          Routing Decision
        </p>
        <span className="font-mono text-lg font-bold text-foreground">
          {score.unified_score.toFixed(4)}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-2">
        {bands.map((b) => {
          const active = b.key === band;
          return (
            <div
              key={b.key}
              className="rounded-lg border p-2 text-center"
              style={{
                borderColor: active ? BAND_META[b.key].color : "rgba(15,23,42,0.1)",
                backgroundColor: active ? BAND_META[b.key].bg : "hsl(var(--card))",
              }}
            >
              <p
                className="text-[10px] font-semibold uppercase tracking-wide"
                style={{ color: active ? BAND_META[b.key].color : "var(--text-3)" }}
              >
                {b.label}
              </p>
              <p className="mt-0.5 font-mono text-[10px] text-text-3">{b.range}</p>
            </div>
          );
        })}
      </div>

      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-3">
        <span>
          Faithfulness Gate:{" "}
          <strong style={{ color: faithfulnessBlocked ? "#F43F5E" : "#10B981" }}>
            {score.faithfulness === null ? "Not collected" : faithfulnessBlocked ? "BLOCKED" : "PASS"}
          </strong>
        </span>
        <span>
          Adversarial Gate:{" "}
          <strong style={{ color: adversarialBlocked ? "#F43F5E" : "#10B981" }}>
            {adversarialBlocked ? "BLOCKED" : "PASS"}
          </strong>
        </span>
      </div>

      <div
        className="mt-3 rounded-lg p-3"
        style={{ backgroundColor: meta.bg }}
      >
        <p className="text-sm font-bold" style={{ color: meta.color }}>
          {hasHardGateBlock ? "HARD BLOCK — DEPLOYMENT NOT ALLOWED" : meta.label}
        </p>
        <p className="mt-0.5 text-[11px] text-text-3">
          Source: Evaluator → Observer → Routing Policy
        </p>
      </div>
    </div>
  );
}
