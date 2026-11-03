import Link from "next/link";
import { ArrowRight } from "lucide-react";

interface EvaluationQueueProps {
  pipelineId: string;
  hasChanges: boolean;
}

/**
 * §29.13 Evaluation Queue. Deployment is never allowed directly from the Improver —
 * every variant must pass through the Evaluation Dashboard first. Distinct from
 * ApplyImprovementButton/ImproverAgentOutput (which apply one specific real
 * Improver candidate via POST /pipelines/{id}/apply-improvement, added
 * 20-Jul-2026): this queue is the generic "re-run the whole pipeline through a
 * fresh evaluation" path, so it routes to the existing Evaluation page rather
 * than a server-side queue (mirrors the Diagnoser's "Send to Improver" deep-link
 * pattern).
 */
export function EvaluationQueue({ pipelineId, hasChanges }: EvaluationQueueProps) {
  return (
    <div className="flex flex-col gap-4 rounded-xl border border-border bg-card p-5 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <p className="text-sm font-medium text-foreground">Ready to validate this variant?</p>
        <p className="mt-1 text-xs text-text-3">
          {hasChanges
            ? "Run the proposed configuration through the Evaluation Dashboard to measure its real Unified Score before deployment."
            : "No configuration changes to evaluate — the proposed variant matches the current pipeline."}
        </p>
      </div>
      <Link
        href={`/evaluate?pipeline_id=${pipelineId}`}
        aria-disabled={!hasChanges}
        tabIndex={hasChanges ? undefined : -1}
        className={`inline-flex shrink-0 items-center gap-1.5 rounded-md px-4 py-2 text-sm font-medium transition-colors motion-safe:transition-colors ${
          hasChanges
            ? "bg-accent text-foreground hover:bg-accent-light"
            : "pointer-events-none bg-accent/5 text-text-3"
        }`}
      >
        Queue for Evaluation
        <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
      </Link>
    </div>
  );
}
