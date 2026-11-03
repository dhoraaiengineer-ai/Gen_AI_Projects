"use client";

import type { Document, NodeTraceEntry } from "@/types";

interface IngestionEvidenceProps {
  /** The real Document row matched to this run, if one was found. */
  document: Document | null;
  documentsLoading: boolean;
  /** The ingestion node's node_trace entry, if the graph reached it. */
  entry: NodeTraceEntry | undefined;
}

function num(value: unknown): number | null {
  return typeof value === "number" ? value : null;
}
function str(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

/**
 * Part H — Ingestion Evidence. Sourced from the real Document row (migration
 * 0012, persisted at ingestion time, never reconstructed from run history)
 * plus the ingestion node_trace entry's real PII fields. Parser/OCR/chunk-size/
 * token-budget fields render "Not exposed" when no real backend field carries
 * them yet -- never inferred client-side.
 */
export function IngestionEvidence({ document, documentsLoading, entry }: IngestionEvidenceProps) {
  const chunkStrategy = str(entry?.chunk_strategy);
  const tokenGuardrail = str(entry?.token_guardrail_status) ?? str(entry?.guardrail_status);
  const contextUsage = num(entry?.token_count);

  const rows: [string, string][] = [
    ["Pages", document?.page_count != null ? String(document.page_count) : documentsLoading ? "Loading…" : "Not collected"],
    ["Characters", document?.char_count != null ? document.char_count.toLocaleString() : documentsLoading ? "Loading…" : "Not collected"],
    ["PII Redactions", document ? String(document.pii_redaction_count) : documentsLoading ? "Loading…" : "Not collected"],
    ["Chunk Strategy", chunkStrategy ?? "Not exposed"],
    ["Token Guardrail", tokenGuardrail ?? "Not exposed"],
    ["Context Usage", contextUsage !== null ? `${contextUsage.toLocaleString()} tokens` : "Not exposed"],
  ];

  const piiTypes = document?.pii_counts_by_type ?? {};
  const hasPiiTypes = Object.keys(piiTypes).length > 0;

  return (
    <div className="mt-3 rounded-lg border border-border bg-card p-3">
      <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
        Ingestion Evidence
      </p>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 sm:grid-cols-3">
        {rows.map(([label, value]) => (
          <div key={label} className="min-w-0">
            <dt className="text-[10px] text-muted-foreground">{label}</dt>
            <dd className="truncate font-mono text-[11px] font-medium text-foreground">{value}</dd>
          </div>
        ))}
      </dl>
      {hasPiiTypes && (
        <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 border-t border-border pt-2 text-[10px] text-text-3">
          {Object.entries(piiTypes).map(([type, count]) => (
            <span key={type}>
              {type}: {count}
            </span>
          ))}
        </div>
      )}
      {!document && !documentsLoading && (
        <p className="mt-2 text-[11px] italic text-muted-foreground">
          No matching document evidence found for this run.
        </p>
      )}
    </div>
  );
}
