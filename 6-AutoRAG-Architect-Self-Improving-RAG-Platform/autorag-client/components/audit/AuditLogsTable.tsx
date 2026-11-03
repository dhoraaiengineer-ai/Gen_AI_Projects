"use client";

import { useState } from "react";
import { RefreshCw, List, GitCommitHorizontal } from "lucide-react";

import { useAuditLog } from "@/hooks/use-audit-log";
import { cn } from "@/lib/utils";
import { FilterBar } from "@/components/audit/FilterBar";
import { LogsTable } from "@/components/audit/LogsTable";
import { AuditTimeline } from "@/components/audit/AuditTimeline";
import { AuditKpiStrip } from "@/components/audit/AuditKpiStrip";
import { Pagination } from "@/components/audit/Pagination";
import { ExportCSVButton } from "@/components/audit/ExportCSVButton";
import type { AuditEventType } from "@/types";

/**
 * Client-side Audit Logs explorer (E-13; Chapter 25): Event Type + Run ID
 * filters, paginated table (25 rows/page), and CSV export of the loaded page.
 * Scoped to what `GET /api/v1/audit-log` actually supports — see the
 * AuditLogListParams/AuditLogListResponse comment in types/index.ts for the
 * gap between this and the full Chapter 25 spec (severity, timeline, KPIs).
 */
export function AuditLogsTable() {
  const [eventType, setEventType] = useState<AuditEventType | undefined>(undefined);
  const [runId, setRunId] = useState<string | undefined>(undefined);
  const [page, setPage] = useState(0);
  const [view, setView] = useState<"table" | "timeline">("table");

  const { items, count, pageSize, isLoading, error, refetch } = useAuditLog({ eventType, runId, page });

  const handleApply = (filters: { eventType: AuditEventType | undefined; runId: string | undefined }) => {
    setEventType(filters.eventType);
    setRunId(filters.runId);
    setPage(0);
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-end">
        <button
          type="button"
          onClick={refetch}
          className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm font-medium text-text-2 hover:bg-accent/5"
        >
          <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
          Refresh
        </button>
      </div>

      <AuditKpiStrip />

      <FilterBar eventType={eventType} runId={runId} onApply={handleApply} />

      <div className="flex items-center justify-between">
        <div className="inline-flex rounded-lg border border-border p-0.5">
          <button
            type="button"
            onClick={() => setView("table")}
            aria-pressed={view === "table"}
            className={cn(
              "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition-colors motion-safe:duration-150",
              view === "table" ? "bg-accent/15 text-foreground" : "text-text-3 hover:text-foreground",
            )}
          >
            <List className="h-3.5 w-3.5" aria-hidden="true" />
            Table
          </button>
          <button
            type="button"
            onClick={() => setView("timeline")}
            aria-pressed={view === "timeline"}
            className={cn(
              "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition-colors motion-safe:duration-150",
              view === "timeline" ? "bg-accent/15 text-foreground" : "text-text-3 hover:text-foreground",
            )}
          >
            <GitCommitHorizontal className="h-3.5 w-3.5" aria-hidden="true" />
            Timeline
          </button>
        </div>
        <ExportCSVButton items={items} />
      </div>

      {view === "table" ? (
        <LogsTable items={items} isLoading={isLoading} error={error} onRetry={refetch} />
      ) : (
        <AuditTimeline items={items} isLoading={isLoading} error={error} />
      )}

      <Pagination page={page} pageSize={pageSize} count={count} onPageChange={setPage} />
    </div>
  );
}
