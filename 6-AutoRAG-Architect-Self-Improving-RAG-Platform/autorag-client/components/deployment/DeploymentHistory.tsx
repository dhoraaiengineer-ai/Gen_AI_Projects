import { formatScore, isHardBlock, scoreColorClasses } from "@/lib/score";
import { relativeTime } from "@/lib/format";
import type { Deployment, DeploymentStatus } from "@/types";

interface DeploymentHistoryProps {
  deployments: Deployment[];
  isLoading?: boolean;
  error?: Error | null;
  onRetry?: () => void;
}

const STATUS_STYLES: Record<DeploymentStatus, { label: string; classes: string }> = {
  pending: { label: "Pending", classes: "text-blue-700 bg-blue-50" },
  blue_green: { label: "Blue/Green Canary", classes: "text-amber-700 bg-amber-50" },
  promoted: { label: "Promoted", classes: "text-emerald-700 bg-emerald-50" },
  rolled_back: { label: "Rolled Back", classes: "text-rose-700 bg-rose-50" },
  failed: { label: "Failed", classes: "text-rose-700 bg-rose-50" },
};

function DeploymentStatusBadge({ status }: { status: DeploymentStatus }) {
  const style = STATUS_STYLES[status];
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${style.classes}`}>
      {style.label}
    </span>
  );
}

/** Newest-first deployment history table (Chapter 24 — DeploymentHistory). */
export function DeploymentHistory({ deployments, isLoading, error, onRetry }: DeploymentHistoryProps) {
  if (error) {
    return (
      <Panel>
        <div className="p-8 text-center" role="alert">
          <p className="text-sm text-status-error">Failed to load deployment history: {error.message}</p>
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
        <div className="space-y-2 p-4" aria-busy="true" aria-label="Loading deployment history">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-10 animate-pulse rounded-md bg-accent/5" />
          ))}
        </div>
      </Panel>
    );
  }

  if (deployments.length === 0) {
    return (
      <Panel>
        <div className="p-10 text-center text-sm text-text-3">
          No deployments yet for this pipeline.
        </div>
      </Panel>
    );
  }

  return (
    <Panel>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="text-xs uppercase tracking-wide text-text-3">
            <tr className="border-b border-border">
              <th className="px-4 py-3 font-medium">Deployment</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Unified Score</th>
              <th className="px-4 py-3 font-medium">Deployed</th>
              <th className="px-4 py-3 font-medium">Promoted / Rolled Back</th>
            </tr>
          </thead>
          <tbody>
            {deployments.map((d) => (
              <tr key={d.id} className="border-b border-border/60 hover:bg-accent/5">
                <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{d.id.slice(0, 8)}</td>
                <td className="px-4 py-3">
                  <DeploymentStatusBadge status={d.status} />
                </td>
                <td className="px-4 py-3">
                  <ScoreCell score={d.unified_score_at_deploy} />
                </td>
                <td className="px-4 py-3 text-xs text-text-3">{relativeTime(d.deployed_at)}</td>
                <td className="px-4 py-3 text-xs text-text-3">
                  {relativeTime(d.promoted_at ?? d.rolled_back_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function ScoreCell({ score }: { score: number | null }) {
  if (score === null) return <span className="text-text-3">—</span>;
  if (isHardBlock(score)) {
    return <span className="rounded px-2 py-0.5 text-sm font-semibold text-red-600">{formatScore(score)}</span>;
  }
  return (
    <span className={`inline-flex rounded px-2 py-0.5 text-sm font-semibold ${scoreColorClasses(score)}`}>
      {formatScore(score)}
    </span>
  );
}

function Panel({ children }: { children: React.ReactNode }) {
  return <div className="overflow-hidden rounded-xl border border-border bg-card">{children}</div>;
}
