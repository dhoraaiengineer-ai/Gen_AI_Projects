"use client";

import { relativeTime } from "@/lib/format";
import { EventTypeBadge } from "@/components/audit/LogsTable";
import type { AuditEvent } from "@/types";

interface AuditTimelineProps {
  items: AuditEvent[];
  isLoading?: boolean;
  error?: Error | null;
}

/**
 * Chronological alternate view of the same page of real AuditEvent rows
 * LogsTable renders (25-Jul-2026, capability-first polish pass) -- no new
 * data, just a different layout ordered by the already-real created_at.
 */
export function AuditTimeline({ items, isLoading, error }: AuditTimelineProps) {
  if (error) return null; // LogsTable already surfaces the error state below

  if (isLoading) {
    return (
      <div className="space-y-3 rounded-xl border border-border bg-card p-4" aria-busy="true" aria-label="Loading timeline">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-8 animate-pulse rounded-md bg-accent/5" />
        ))}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-card p-10 text-center text-sm text-text-3">
        No matching audit events.
      </div>
    );
  }

  return (
    <ol className="relative border-l border-border pl-5">
      {items.map((event) => (
        <li key={event.id} className="mb-5 last:mb-0">
          <span
            className="absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full bg-accent"
            aria-hidden="true"
          />
          <div className="flex flex-wrap items-center gap-2">
            <EventTypeBadge eventType={event.event_type} />
            <span className="text-xs text-text-3">{relativeTime(event.created_at)}</span>
          </div>
          {event.run_id && (
            <p className="mt-1 font-mono text-xs text-text-3">run {event.run_id.slice(0, 8)}</p>
          )}
        </li>
      ))}
    </ol>
  );
}
