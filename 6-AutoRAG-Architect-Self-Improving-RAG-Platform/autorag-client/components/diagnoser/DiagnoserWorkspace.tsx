"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { usePipelines } from "@/hooks/use-pipelines";
import { useDiagnosis } from "@/hooks/use-diagnosis";
import { pipelineDisplayName } from "@/lib/format";
import { FailureSummary } from "@/components/diagnoser/FailureSummary";
import { RootCausePanel } from "@/components/diagnoser/RootCausePanel";
import { RecommendationList } from "@/components/diagnoser/RecommendationList";
import { EvidenceViewer } from "@/components/diagnoser/EvidenceViewer";
import { FailedQuestionAnalysisPanel } from "@/components/diagnoser/FailedQuestionAnalysisPanel";

/**
 * Client-side Diagnoser Workspace (F-14; Chapter 28): pipeline selector, failure
 * classification, root cause, recommendations, evidence, and the real per-run
 * Diagnoser verdict (confidence + remediation_hint + root_cause_analysis from
 * GET /diagnose/{run_id} — real LLM-generated content, never fabricated).
 * See types/index.ts's Diagnoser Workspace comment for why FailureTimeline /
 * SimilarFailures / per-recommendation confidence from the original spec are
 * not implemented — no backend history endpoint exists.
 */
export function DiagnoserWorkspace() {
  const { pipelines, isLoading: pipelinesLoading } = usePipelines();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedId && pipelines.length > 0) setSelectedId(pipelines[0].id);
  }, [pipelines, selectedId]);

  const pipeline = pipelines.find((p) => p.id === selectedId) ?? null;
  const runId = pipeline?.latest_run?.id ?? null;
  const { score, diagnosis, isLoading, error, refetch } = useDiagnosis(runId);

  return (
    <div className="space-y-6">
      {/* Pipeline selector */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
        <label htmlFor="diagnose-pipeline-select" className="text-xs font-medium text-text-3">
          Pipeline
        </label>
        <select
          id="diagnose-pipeline-select"
          value={selectedId ?? ""}
          onChange={(e) => setSelectedId(e.target.value || null)}
          disabled={pipelinesLoading || pipelines.length === 0}
          className="w-full max-w-sm rounded-md border border-border bg-accent/5 px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none disabled:opacity-50"
        >
          {pipelines.length === 0 && <option value="">No pipelines available</option>}
          {pipelines.map((p) => (
            <option key={p.id} value={p.id}>
              {pipelineDisplayName(p)}
            </option>
          ))}
        </select>
      </div>

      {pipeline && <FailedQuestionAnalysisPanel pipelineId={pipeline.id} />}

      {!pipeline ? (
        <div className="rounded-xl border border-border bg-card p-10 text-center text-sm text-text-3">
          Select a pipeline to view its diagnosis.
        </div>
      ) : !runId ? (
        <div className="rounded-xl border border-border bg-card p-10 text-center">
          <p className="text-sm text-text-3">
            No completed evaluation run for this pipeline yet — Diagnoser needs a real failure to
            analyze.
          </p>
          <Link
            href="/evaluation"
            className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-xs font-semibold text-foreground hover:bg-accent-light"
          >
            Open Evaluation Center
            <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
          </Link>
        </div>
      ) : (
        <>
          <FailureSummary score={score} isLoading={isLoading} error={error} onRetry={refetch} />

          {score && (
            <>
              <section aria-labelledby="diagnose-rootcause-heading">
                <h2
                  id="diagnose-rootcause-heading"
                  className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-3"
                >
                  Root Cause
                </h2>
                <RootCausePanel score={score} />
              </section>

              {diagnosis?.root_cause_analysis && (
                <section aria-labelledby="diagnose-verdict-heading">
                  <h2
                    id="diagnose-verdict-heading"
                    className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-3"
                  >
                    Diagnoser Verdict
                  </h2>
                  <div className="rounded-lg border border-border bg-accent/5 p-5 space-y-3">
                    {diagnosis.confidence !== null && (
                      <p className="text-xs text-text-3">
                        Confidence:{" "}
                        <span className="font-mono font-medium text-foreground">
                          {(diagnosis.confidence * 100).toFixed(0)}%
                        </span>
                      </p>
                    )}
                    <p className="text-sm text-foreground">{diagnosis.root_cause_analysis}</p>
                    {diagnosis.remediation_hint && (
                      <p className="text-sm text-text-3">
                        <span className="font-medium text-foreground">Remediation: </span>
                        {diagnosis.remediation_hint}
                      </p>
                    )}
                  </div>
                </section>
              )}

              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <section aria-labelledby="diagnose-recs-heading">
                  <h2
                    id="diagnose-recs-heading"
                    className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-3"
                  >
                    Recommendations
                  </h2>
                  <RecommendationList codes={score.failure_taxonomy} />
                </section>

                <section aria-labelledby="diagnose-evidence-heading">
                  <h2
                    id="diagnose-evidence-heading"
                    className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-3"
                  >
                    Evidence
                  </h2>
                  <EvidenceViewer score={score} />
                </section>
              </div>

              {score.failure_taxonomy.length > 0 && (
                <div className="flex justify-end">
                  <Link
                    href={`/improve?pipeline_id=${pipeline.id}`}
                    className="inline-flex items-center gap-1.5 rounded-md bg-accent px-4 py-2 text-sm font-medium text-foreground hover:bg-accent-light"
                  >
                    Send to Improver
                    <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
                  </Link>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
