"use client";

import { useState } from "react";

import { APPROVED_AUDIT_EVENT_TYPES } from "@/types";
import type { AuditEventType } from "@/types";

interface FilterBarProps {
  eventType: AuditEventType | undefined;
  runId: string | undefined;
  onApply: (filters: { eventType: AuditEventType | undefined; runId: string | undefined }) => void;
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Event Type + Run ID filters only (Chapter 25's Severity/User/Date-range/
 * Pipeline filters have no backing column on the real `audit_log` table —
 * see app/models/audit_log.py).
 */
export function FilterBar({ eventType, runId, onApply }: FilterBarProps) {
  const [eventTypeDraft, setEventTypeDraft] = useState(eventType ?? "");
  const [runIdDraft, setRunIdDraft] = useState(runId ?? "");
  const [runIdError, setRunIdError] = useState<string | null>(null);

  const handleApply = () => {
    if (runIdDraft && !UUID_RE.test(runIdDraft)) {
      setRunIdError("Run ID must be a valid UUID.");
      return;
    }
    setRunIdError(null);
    onApply({
      eventType: eventTypeDraft ? (eventTypeDraft as AuditEventType) : undefined,
      runId: runIdDraft || undefined,
    });
  };

  const handleClear = () => {
    setEventTypeDraft("");
    setRunIdDraft("");
    setRunIdError(null);
    onApply({ eventType: undefined, runId: undefined });
  };

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 sm:flex-row sm:items-end sm:gap-4">
      <div className="flex flex-col gap-1">
        <label htmlFor="audit-event-type" className="text-xs font-medium text-text-3">
          Event Type
        </label>
        <select
          id="audit-event-type"
          value={eventTypeDraft}
          onChange={(e) => setEventTypeDraft(e.target.value)}
          className="w-full min-w-[200px] rounded-md border border-border bg-accent/5 px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none"
        >
          <option value="">All event types</option>
          {APPROVED_AUDIT_EVENT_TYPES.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="audit-run-id" className="text-xs font-medium text-text-3">
          Run ID
        </label>
        <input
          id="audit-run-id"
          type="text"
          value={runIdDraft}
          onChange={(e) => setRunIdDraft(e.target.value.trim())}
          placeholder="UUID"
          className="w-full min-w-[240px] rounded-md border border-border bg-accent/5 px-3 py-2 font-mono text-sm text-foreground focus:border-accent focus:outline-none"
        />
        {runIdError && <p className="text-xs text-status-error">{runIdError}</p>}
      </div>

      <div className="flex gap-2">
        <button
          type="button"
          onClick={handleApply}
          className="rounded-md bg-accent px-3 py-2 text-sm font-medium text-foreground hover:bg-accent-light"
        >
          Apply Filters
        </button>
        <button
          type="button"
          onClick={handleClear}
          className="rounded-md border border-border px-3 py-2 text-sm font-medium text-text-2 hover:bg-accent/5"
        >
          Clear
        </button>
      </div>
    </div>
  );
}
