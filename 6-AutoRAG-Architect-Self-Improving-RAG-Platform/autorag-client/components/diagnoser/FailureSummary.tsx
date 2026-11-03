import { FAILURE_CODE_INFO, isFailureCode } from "@/types";
import type { ScoreResult } from "@/types";

interface FailureSummaryProps {
  score: ScoreResult | null;
  isLoading?: boolean;
  error?: Error | null;
  onRetry?: () => void;
}

/**
 * Single-run failure breakdown, derived from `score.failure_taxonomy`.
 * Reflects only the latest run — no endpoint returns failure-type history
 * across many runs.
 */
export function FailureSummary({ score, isLoading, error, onRetry }: FailureSummaryProps) {
  if (error) {
    return (
      <Panel>
        <div className="p-8 text-center" role="alert">
          <p className="text-sm text-status-error">Unable to analyze failure: {error.message}</p>
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="mt-3 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-foreground hover:bg-accent-light"
            >
              Retry
            </button>
          )}
        </div>
      </Panel>
    );
  }

  if (isLoading) {
    return (
      <Panel>
        <div className="flex gap-2 p-4" aria-busy="true" aria-label="Analyzing failure">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-8 w-32 animate-pulse rounded-full bg-accent/5" />
          ))}
        </div>
      </Panel>
    );
  }

  if (!score) {
    return (
      <Panel>
        <div className="p-10 text-center text-sm text-text-3">
          Select a pipeline with a completed evaluation run to see its diagnosis.
        </div>
      </Panel>
    );
  }

  // A null unified_score means this run never reached Evaluator -- an empty
  // failure_taxonomy in that case means "never diagnosed," not "healthy."
  // Conflating these was a real bug: a run that failed before Evaluator ran
  // (e.g. an embeddings/ingestion error) previously showed a false "healthy"
  // verdict identical to a genuinely passing run (13-Jul-2026 fix).
  if (score.unified_score === null) {
    return (
      <Panel>
        <div className="p-10 text-center">
          <p className="text-sm font-semibold text-text-2">NO DIAGNOSIS</p>
          <p className="mt-1 text-xs text-text-3">
            This run did not produce persisted diagnosis evidence — it never reached the
            Evaluator (status: {score.status}).
          </p>
        </div>
      </Panel>
    );
  }

  const codes = score.failure_taxonomy;

  if (codes.length === 0) {
    return (
      <Panel>
        <div className="p-10 text-center text-sm text-status-success">
          No failures detected — pipeline is healthy.
        </div>
      </Panel>
    );
  }

  return (
    <Panel>
      <div className="flex flex-wrap gap-2 p-4">
        {codes.map((code) => {
          const info = isFailureCode(code) ? FAILURE_CODE_INFO[code] : null;
          return (
            <span
              key={code}
              title={info?.description ?? "Unrecognized failure code"}
              className="inline-flex items-center gap-1.5 rounded-full bg-rose-50 px-3 py-1.5 text-sm font-medium text-rose-700"
            >
              <span className="font-mono text-xs opacity-80">{code}</span>
              {info?.label ?? "Unknown"}
            </span>
          );
        })}
      </div>
    </Panel>
  );
}

function Panel({ children }: { children: React.ReactNode }) {
  return <div className="overflow-hidden rounded-xl border border-border bg-card">{children}</div>;
}
