"use client";

import type { DiagnosisResponse, ImprovementResponse, ObserverViewResponse, ScoreResult } from "@/types";

interface RetryJourneyProps {
  score: ScoreResult;
  diagnosis: DiagnosisResponse | null;
  diagnosisLoading: boolean;
  improvement: ImprovementResponse | null;
  improvementLoading: boolean;
  observerView: ObserverViewResponse | null;
}

const FAILURE_LABEL: Record<string, string> = {
  "F-01": "Retrieval failure",
  "F-02": "Hallucination",
  "F-03": "Latency regression",
  "F-04": "Cost explosion",
  "F-05": "Prompt injection",
  "F-06": "Quality drift",
};

function Step({ label, color, children }: { label: string; color: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3">
      <div className="flex flex-col items-center">
        <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
        <span className="mt-1 w-px flex-1 bg-[rgba(15,23,42,0.1)]" />
      </div>
      <div className="min-w-0 flex-1 pb-4">
        <p className="text-[10px] font-semibold uppercase tracking-widest" style={{ color }}>
          {label}
        </p>
        <div className="mt-1 text-xs text-foreground">{children}</div>
      </div>
    </div>
  );
}

/**
 * Part H — Retry / Self-Improvement Journey. Only renders when a real
 * diagnosis exists (score.failure_taxonomy non-empty) -- this is an evidence
 * timeline of what actually happened, not a decorative diagram. Heuristic
 * candidate deltas are always labeled ESTIMATED (ImproverCandidate.score_type
 * is always "estimated" -- never a live re-evaluation); only a genuinely new
 * evaluation run would produce a MEASURED result.
 */
export function RetryJourney({
  score,
  diagnosis,
  diagnosisLoading,
  improvement,
  improvementLoading,
  observerView,
}: RetryJourneyProps) {
  if (score.failure_taxonomy.length === 0) return null;

  return (
    <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
      <p className="mb-4 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
        Retry / Self-Improvement Journey
      </p>

      <Step label="Evaluation" color="#5B5CE2">
        Unified Score{" "}
        <span className="font-mono font-semibold">
          {score.unified_score !== null ? score.unified_score.toFixed(4) : "Not collected"}
        </span>
      </Step>

      <Step label="Observer" color="#06B6D4">
        {observerView?.signals ? (
          <>
            Quality trend: <strong>{observerView.signals.quality_trend ?? "Not collected"}</strong>
            {observerView.signals.observation_flags && (
              <span className="ml-2 text-text-3">
                (
                {Object.entries(observerView.signals.observation_flags)
                  .filter(([, v]) => v)
                  .map(([k]) => k)
                  .join(", ") || "no flags"}
                )
              </span>
            )}
          </>
        ) : (
          <span className="text-muted-foreground">Not collected</span>
        )}
      </Step>

      <Step label="Diagnoser" color="#F59E0B">
        {diagnosisLoading ? (
          <span className="text-muted-foreground">Loading…</span>
        ) : diagnosis?.failure_type ? (
          <>
            <span className="font-mono font-semibold">{diagnosis.failure_type}</span>{" "}
            {FAILURE_LABEL[diagnosis.failure_type] ?? ""}
            {diagnosis.root_cause_analysis && (
              <p className="mt-0.5 text-text-3">{diagnosis.root_cause_analysis}</p>
            )}
          </>
        ) : (
          <span className="text-muted-foreground">Not collected</span>
        )}
      </Step>

      <Step label="Improver" color="#8B5CF6">
        {improvementLoading ? (
          <span className="text-muted-foreground">Loading…</span>
        ) : improvement?.candidates && improvement.candidates.length > 0 ? (
          <div className="space-y-1.5">
            <p>{improvement.candidates.length} candidates generated</p>
            {improvement.candidates.map((c) => (
              <div key={c.candidate_id} className="flex items-center gap-2 text-[11px]">
                <span
                  className="rounded-full px-1.5 py-0.5 font-mono font-semibold"
                  style={{
                    backgroundColor: c.selected ? "#F5F3FF" : "rgba(15,23,42,0.06)",
                    color: c.selected ? "#8B5CF6" : "var(--text-3)",
                  }}
                >
                  {c.selected ? "SELECTED" : "candidate"}
                </span>
                <span className="font-mono">{c.score_delta >= 0 ? "+" : ""}{c.score_delta.toFixed(3)}</span>
                <span
                  className="rounded bg-[rgba(245,158,11,0.12)] px-1.5 py-0.5 text-[9px] font-semibold uppercase text-[#F59E0B]"
                  title="Heuristic estimate, not a live re-evaluation"
                >
                  {c.score_type}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <span className="text-muted-foreground">Not collected</span>
        )}
      </Step>

      <div className="flex gap-3">
        <div className="flex flex-col items-center">
          <span className="h-2.5 w-2.5 rounded-full bg-[#3B82F6]" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-[#3B82F6]">
            Retry
          </p>
          <p className="mt-1 text-xs text-foreground">
            {improvementLoading ? (
              <span className="text-muted-foreground">Loading…</span>
            ) : improvement ? (
              <>
                Attempt <span className="font-mono">{improvement.improvement_attempt}</span> of 3
                (retry ceiling)
              </>
            ) : (
              <span className="text-muted-foreground">Not collected</span>
            )}
          </p>
        </div>
      </div>
    </div>
  );
}
