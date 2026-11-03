"use client";

/**
 * Pipeline Version History — client container (Chapter 34).
 *
 * GET /pipelines/{id}/versions now exists (added with the 20-Jul-2026 Apply
 * Improvement feature), but this component has not been migrated to consume
 * it yet — it still shows the single pipeline itself (current_version)
 * rather than the real version list, so nothing here is fabricated, just
 * not yet wired to the newer endpoint. See lib/pipeline-history.ts.
 * Deployment History (§34.12) is the real E-12 endpoint, rendered via the reused
 * DeploymentHistory component. Restore (§34.13), Change Log reasons (§34.10),
 * and AI Improvement History (§34.14) are omitted — no backing endpoints.
 */

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { apiClient } from "@/services/api-client";
import { sortVersionsDesc } from "@/lib/pipeline-history";
import { DeploymentHistory } from "@/components/deployment/DeploymentHistory";
import type { PipelineWithRun } from "@/types";
import { VersionTimeline } from "./VersionTimeline";
import { VersionTable } from "./VersionTable";
import { VersionComparison } from "./VersionComparison";

interface PipelineHistoryPageClientProps {
  pipelineId: string;
}

export function PipelineHistoryPageClient({ pipelineId }: PipelineHistoryPageClientProps) {
  const {
    data: detail,
    isLoading: detailLoading,
    error: detailError,
    refetch: refetchDetail,
  } = useQuery({
    queryKey: ["pipeline-detail", pipelineId],
    queryFn: () => apiClient.getPipeline(pipelineId),
    // 26-Jul-2026: Launch/Retry dispatch a real background re-index (~15-30s
    // for a real document) and leave the pipeline in status "running" for
    // its duration -- without polling here, a user landing on this page
    // right after Launch would see a static, stale status forever until a
    // manual browser refresh. Stops polling once the pipeline reaches a
    // terminal status (ready/failed/anything else) so this doesn't poll
    // indefinitely for pipelines that were never re-indexing to begin with.
    refetchInterval: (query) => (query.state.data?.pipeline.status === "running" ? 3000 : false),
  });

  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);
  const handleRetryIndexing = async () => {
    setRetrying(true);
    setRetryError(null);
    try {
      await apiClient.retryIndexing(pipelineId);
      await refetchDetail();
    } catch (err) {
      setRetryError(err instanceof Error ? err.message : "Failed to retry indexing");
    } finally {
      setRetrying(false);
    }
  };

  const versions = useMemo((): PipelineWithRun[] => {
    if (!detail) return [];
    return sortVersionsDesc([{ ...detail.pipeline, latest_run: detail.latest_run }]);
  }, [detail]);
  const versionsLoading = detailLoading;

  // Deployment history (real E-12 endpoint).
  const {
    data: deployHistory,
    isLoading: deployLoading,
    error: deployError,
    refetch: refetchDeploy,
  } = useQuery({
    queryKey: ["pipeline-deployments", pipelineId],
    queryFn: () => apiClient.getDeploymentHistory(pipelineId),
  });

  // Compare selection — seed with the two newest versions once they load.
  const [compareIds, setCompareIds] = useState<string[]>([]);
  useEffect(() => {
    if (compareIds.length === 0 && versions.length > 0) {
      setCompareIds(versions.slice(0, 2).map((v) => v.id));
    }
  }, [versions, compareIds.length]);

  const toggleCompare = (id: string) => {
    setCompareIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= 2) return prev;
      return [...prev, id];
    });
  };

  const versionA = versions.find((v) => v.id === compareIds[0]) ?? null;
  const versionB = versions.find((v) => v.id === compareIds[1]) ?? null;

  if (detailError) {
    return (
      <div role="alert" className="rounded-xl border border-red-500/40 bg-red-500/5 p-6 text-sm text-red-600">
        Unable to load pipeline: {detailError instanceof Error ? detailError.message : "unknown error"}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-2">
        {detail && (
          <span className="text-sm font-medium text-text-3">
            <span className="font-mono text-foreground">v{detail.pipeline.current_version}</span>
            {" · "}
            {detail.version_count} version{detail.version_count === 1 ? "" : "s"} total
          </span>
        )}
        <Link href="/audit" className="text-xs text-accent hover:text-accent-light">
          View full audit trail →
        </Link>
      </header>

      {detail?.pipeline.status === "running" && (
        <div
          role="status"
          className="flex items-center gap-2 rounded-xl border border-cyan-500/30 bg-cyan-500/5 px-4 py-3 text-sm text-cyan-600"
        >
          <span className="h-2 w-2 animate-pulse rounded-full bg-cyan-500" aria-hidden="true" />
          Re-indexing documents into version {detail.pipeline.current_version} — this can take up to
          a minute for real documents. This page updates automatically.
        </div>
      )}

      {detail?.pipeline.status === "failed" && (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-red-500/30 bg-red-500/5 px-4 py-3 text-sm text-red-600"
        >
          <span>
            Indexing failed for version {detail.pipeline.current_version}. Check the Documents page
            for the specific error, or retry below.
          </span>
          <button
            type="button"
            onClick={() => void handleRetryIndexing()}
            disabled={retrying}
            className="shrink-0 rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-1.5 text-xs font-semibold text-red-600 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {retrying ? "Retrying…" : "Retry Indexing"}
          </button>
        </div>
      )}
      {retryError && (
        <div role="alert" className="rounded-xl border border-red-500/40 bg-red-500/5 p-3 text-xs text-red-600">
          {retryError}
        </div>
      )}

      <VersionTimeline versions={versions} currentId={pipelineId} />

      <section aria-labelledby="ph-inventory">
        <h2 id="ph-inventory" className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-3">
          Version Inventory
        </h2>
        <VersionTable
          versions={versions}
          currentId={pipelineId}
          compareIds={compareIds}
          onToggleCompare={toggleCompare}
          isLoading={detailLoading || versionsLoading}
        />
      </section>

      <section aria-labelledby="ph-compare">
        <h2 id="ph-compare" className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-3">
          Configuration Comparison
        </h2>
        <VersionComparison versionA={versionA} versionB={versionB} />
      </section>

      <section aria-labelledby="ph-deploy">
        <h2 id="ph-deploy" className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-3">
          Deployment History
        </h2>
        <DeploymentHistory
          deployments={deployHistory?.deployments ?? []}
          isLoading={deployLoading}
          error={deployError instanceof Error ? deployError : null}
          onRetry={() => void refetchDeploy()}
        />
      </section>
    </div>
  );
}
