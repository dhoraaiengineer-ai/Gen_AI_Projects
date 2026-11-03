"use client";

import { Fragment, useState } from "react";
import { Check, ChevronDown, ChevronRight, Copy } from "lucide-react";

import { relativeTime } from "@/lib/format";
import type { AuditEvent } from "@/types";

interface LogsTableProps {
  items: AuditEvent[];
  isLoading?: boolean;
  error?: Error | null;
  onRetry?: () => void;
}

/** Newest-first audit event table (Chapter 25 — Audit Events Table). */
export function LogsTable({ items, isLoading, error, onRetry }: LogsTableProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (error) {
    return (
      <Panel>
        <div className="p-8 text-center" role="alert">
          <p className="text-sm text-status-error">Failed to load audit events: {error.message}</p>
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
        <div className="space-y-2 p-4" aria-busy="true" aria-label="Loading audit events">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-10 animate-pulse rounded-md bg-accent/5" />
          ))}
        </div>
      </Panel>
    );
  }

  if (items.length === 0) {
    return (
      <Panel>
        <div className="p-10 text-center text-sm text-text-3">No matching audit events.</div>
      </Panel>
    );
  }

  return (
    <Panel>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="text-xs uppercase tracking-wide text-text-3">
            <tr className="border-b border-border">
              <th className="w-8 px-4 py-3" />
              <th className="px-4 py-3 font-medium">Timestamp</th>
              <th className="px-4 py-3 font-medium">Event Type</th>
              <th className="px-4 py-3 font-medium">Run ID</th>
              <th className="px-4 py-3 font-medium">Trace ID</th>
            </tr>
          </thead>
          <tbody>
            {items.map((event) => {
              const expanded = expandedId === event.id;
              return (
                <Fragment key={event.id}>
                  <tr
                    className="cursor-pointer border-b border-border/60 hover:bg-accent/5"
                    onClick={() => setExpandedId(expanded ? null : event.id)}
                  >
                    <td className="px-4 py-3 text-text-3">
                      {expanded ? (
                        <ChevronDown className="h-4 w-4" aria-hidden="true" />
                      ) : (
                        <ChevronRight className="h-4 w-4" aria-hidden="true" />
                      )}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-xs text-text-3">
                      {relativeTime(event.created_at)}
                    </td>
                    <td className="px-4 py-3">
                      <EventTypeBadge eventType={event.event_type} />
                    </td>
                    <td className="px-4 py-3">
                      <CopyableId value={event.run_id} />
                    </td>
                    <td className="px-4 py-3">
                      <CopyableId value={event.x_trace_id} />
                    </td>
                  </tr>
                  {expanded && (
                    <tr className="border-b border-border/60 bg-accent/5/50">
                      <td colSpan={5} className="px-4 py-3">
                        <pre className="max-h-64 overflow-auto rounded-md bg-white/5 p-3 font-mono text-xs text-text-2">
                          {JSON.stringify(event.payload, null, 2)}
                        </pre>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

// Part H semantic treatment (13-Jul-2026): pii_redacted = cyan informational
// security event, guardrail_blocked = coral critical block, cost_limit =
// amber critical policy event, deployment = emerald release event. PII
// redaction is never styled as a block — it's a successful protective action.
const EVENT_TYPE_STYLES: Record<string, string> = {
  guardrail_blocked: "text-rose-700 bg-rose-50",
  cost_limit_exceeded: "text-amber-700 bg-amber-50",
  rollback_triggered: "text-amber-700 bg-amber-50",
  hitl_rejected: "text-amber-700 bg-amber-50",
  hitl_approved: "text-emerald-700 bg-emerald-50",
  deploy_completed: "text-emerald-700 bg-emerald-50",
  pii_redacted: "text-cyan-700 bg-cyan-50",
};

/** "pipeline_created" -> "Pipeline Created" -- same real event_type value,
 * just readable. No new taxonomy invented; the 14 approved event types
 * (app/models/audit_log.py) are unchanged. */
function formatEventType(eventType: string): string {
  return eventType
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export function EventTypeBadge({ eventType }: { eventType: string }) {
  const classes = EVENT_TYPE_STYLES[eventType] ?? "text-sky-700 bg-sky-50";
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${classes}`}>
      {formatEventType(eventType)}
    </span>
  );
}

/** Monospace, truncated, click-to-copy identifier — used for Run ID / Trace ID. */
function CopyableId({ value }: { value: string | null }) {
  const [copied, setCopied] = useState(false);

  if (!value) return <span className="text-text-3">—</span>;

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    void navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      title={value}
      className="inline-flex items-center gap-1 font-mono text-xs text-text-2 hover:text-accent-light"
    >
      {value.slice(0, 8)}
      {copied ? (
        <Check className="h-3 w-3 text-status-success" aria-hidden="true" />
      ) : (
        <Copy className="h-3 w-3 opacity-60" aria-hidden="true" />
      )}
    </button>
  );
}

function Panel({ children }: { children: React.ReactNode }) {
  return <div className="overflow-hidden rounded-xl border border-border bg-card">{children}</div>;
}
