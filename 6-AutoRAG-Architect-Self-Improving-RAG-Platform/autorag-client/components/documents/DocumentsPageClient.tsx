"use client";

/**
 * Documents Management — Client Container (Phase 4 Enhanced)
 * Chapter 31.15 Component Hierarchy
 *
 * Phase 2 Enhancements:
 * - BulkOperations panel with multi-select actions
 * - ProcessingStatus component for live pipeline tracking
 * - Checkbox selection state management
 *
 * Phase 4 Enhancements:
 * - Server-side pagination with page controls
 * - Column sorting (name, date, size, status)
 * - Debounced search input
 * - Advanced filters (date range, file type, status multi-select)
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/services/api-client";
import type { DocumentFilters } from "@/types";
import { usePipelines } from "@/hooks/use-pipelines";

import SummaryCards from "./SummaryCards";
import UploadPanel from "./UploadPanel";
import SearchFilters from "./SearchFilters";
import DocumentsTable from "./DocumentsTable";
import BulkOperations from "./BulkOperations";
import Pagination from "./Pagination";

/** Default number of documents per page */
const DEFAULT_PAGE_SIZE = 20;

/**
 * Documents Management page client component
 *
 * Orchestrates all document management features with full pagination,
 * sorting, filtering, and bulk operations support.
 *
 * @returns Documents management page JSX
 */
export default function DocumentsPageClient() {
  // Pipeline the uploaded documents attach to. Same picker pattern as
  // RunEvaluationPanel.tsx (Evaluation) / DiagnoserWorkspace.tsx / Deploy --
  // defaults to the first real pipeline once loaded (14-Jul-2026 fix: this
  // previously defaulted to "", which the backend rejects with "badly formed
  // hexadecimal UUID string" -- live-confirmed broken for any pipeline other
  // than a pre-seeded one with a matching env var).
  const { pipelines, isLoading: pipelinesLoading } = usePipelines();
  const searchParams = useSearchParams();
  // Configurator step 2 links here as /documents?pipeline_id=<id> once the
  // wizard has created a real draft pipeline (16-Jul-2026) -- prefer that
  // over defaulting to the first pipeline in the list.
  const requestedPipelineId = searchParams.get("pipeline_id");
  const [activePipelineId, setActivePipelineId] = useState<string>("");
  useEffect(() => {
    if (activePipelineId || pipelines.length === 0) return;
    if (requestedPipelineId && pipelines.some((p) => p.id === requestedPipelineId)) {
      setActivePipelineId(requestedPipelineId);
    } else {
      setActivePipelineId(pipelines[0].id);
    }
  }, [pipelines, activePipelineId, requestedPipelineId]);

  // Configurator step 2 navigates here, off the wizard entirely. "Finish
  // Pipeline Setup" links back into the wizard at step 3 (Chunking) --
  // /configurator?pipeline_id=<id> -- reusing its existing Back/Continue
  // navigation through Retrieval/Generation/Review, rather than skipping
  // straight to launch (would hide those steps from the user) or requiring
  // a full "resume draft" system (deferred to Version 5 -- docs/roadmap/VERSION_5_ROADMAP.md §2).
  const activePipeline = pipelines.find((p) => p.id === activePipelineId);
  const [filters, setFilters] = useState<DocumentFilters>({
    page: 1,
    page_size: DEFAULT_PAGE_SIZE,
    sort_by: "uploaded_at",
    sort_order: "desc",
  });
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  const {
    data,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["documents", filters],
    queryFn: () => apiClient.listDocuments(filters),
  });

  const documents = data?.documents ?? [];
  const totalCount = data?.total ?? 0;
  const totalPages = Math.ceil(totalCount / (filters.page_size ?? DEFAULT_PAGE_SIZE));

  const handlePageChange = (newPage: number) => {
    setFilters(prev => ({ ...prev, page: newPage }));
    setSelectedIds([]); // Clear selection on page change
  };

  const handleSortChange = (sortBy: DocumentFilters["sort_by"]) => {
    setFilters(prev => ({
      ...prev,
      sort_by: sortBy,
      sort_order: prev.sort_by === sortBy && prev.sort_order === "asc" ? "desc" : "asc",
      page: 1, // Reset to first page on sort change
    }));
  };

  return (
    <>
      <SummaryCards documents={documents} isLoading={isLoading} />

      <div className="panel-card flex flex-wrap items-center gap-3 px-5 py-4">
        <label htmlFor="doc-pipeline" className="eyebrow shrink-0">
          Upload To Pipeline
        </label>
        <select
          id="doc-pipeline"
          value={activePipelineId}
          onChange={(e) => setActivePipelineId(e.target.value)}
          disabled={pipelinesLoading}
          className="min-w-0 flex-1 rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-amber-500/30 focus:border-amber-400"
        >
          {pipelines.length === 0 && <option value="">No pipelines yet — create one first</option>}
          {pipelines.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name || p.id.slice(0, 8)} · v{p.current_version}
            </option>
          ))}
        </select>
      </div>

      {activePipeline?.status === "draft" && (
        <div className="panel-card flex flex-wrap items-center justify-between gap-3 border-l-4 border-l-[#2563EB] px-5 py-4">
          <div>
            <p className="text-sm font-semibold text-foreground">This pipeline is still a draft</p>
            <p className="mt-0.5 text-xs text-text-2">
              Review chunking, retrieval, and generation settings, then launch the 9-agent loop.
            </p>
          </div>
          <Link
            href={`/configurator?pipeline_id=${activePipelineId}`}
            className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-foreground transition-colors motion-safe:duration-150 hover:bg-light_bronze-300"
          >
            Finish Pipeline Setup
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        </div>
      )}

      <UploadPanel
        onUploadComplete={refetch}
        projectId={activePipelineId}
        pipelinesLoading={pipelinesLoading || !activePipelineId}
      />
      <SearchFilters
        filters={filters}
        onFiltersChange={(newFilters) => {
          setFilters({ ...newFilters, page: 1 }); // Reset to first page on filter change
          setSelectedIds([]); // Clear selection on filter change
        }}
        totalResults={totalCount}
      />

      {/* Phase 2: Bulk Operations Panel */}
      <BulkOperations
        selectedIds={selectedIds}
        onClearSelection={() => setSelectedIds([])}
      />

      <DocumentsTable
        documents={documents}
        isLoading={isLoading}
        error={error as Error | null}
        onRefresh={refetch}
        selectedIds={selectedIds}
        onSelectionChange={setSelectedIds}
        // Phase 4: Sorting props
        sortBy={filters.sort_by}
        sortOrder={filters.sort_order}
        onSortChange={handleSortChange}
      />

      {/* Phase 4: Pagination Controls */}
      {totalPages > 1 && (
        <Pagination
          currentPage={filters.page ?? 1}
          totalPages={totalPages}
          totalItems={totalCount}
          pageSize={filters.page_size ?? DEFAULT_PAGE_SIZE}
          onPageChange={handlePageChange}
        />
      )}
    </>
  );
}
