"use client";

import { Download } from "lucide-react";

import type { AuditEvent } from "@/types";

interface ExportCSVButtonProps {
  items: AuditEvent[];
}

const COLUMNS: Array<keyof AuditEvent> = [
  "id",
  "event_type",
  "run_id",
  "organization_id",
  "x_trace_id",
  "created_at",
  "payload",
];

function escapeCsvCell(value: unknown): string {
  const str = value === null || value === undefined ? "" : typeof value === "object" ? JSON.stringify(value) : String(value);
  if (/[",\n]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

/**
 * Client-side CSV export of the currently loaded page of audit events.
 * There is no `/audit/export` endpoint (Chapter 25.14 describes CSV/Excel/PDF/JSON
 * export via backend), so this exports only what's already fetched — not the
 * full filtered result set across all pages.
 */
export function ExportCSVButton({ items }: ExportCSVButtonProps) {
  const handleExport = () => {
    const header = COLUMNS.join(",");
    const rows = items.map((item) => COLUMNS.map((col) => escapeCsvCell(item[col])).join(","));
    const csv = [header, ...rows].join("\n");

    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `audit-log-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <button
      type="button"
      onClick={handleExport}
      disabled={items.length === 0}
      title="Exports the currently loaded page of results"
      className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm font-medium text-text-2 hover:bg-accent/5 disabled:cursor-not-allowed disabled:opacity-40"
    >
      <Download className="h-3.5 w-3.5" aria-hidden="true" />
      Export CSV
    </button>
  );
}
