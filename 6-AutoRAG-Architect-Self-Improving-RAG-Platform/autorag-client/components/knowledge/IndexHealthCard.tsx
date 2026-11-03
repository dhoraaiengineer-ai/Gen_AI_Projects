"use client";

/**
 * Index Health — Chapter 32.13. Rolled up from real DocumentDetail embedding_status
 * + indexed/failed chunk counts (lib/knowledge computeIndexHealth).
 */

import { Card } from "@/components/ui/card";
import { STATUS_LABEL, type IndexHealth, type IndexHealthStatus } from "@/lib/knowledge";

interface IndexHealthCardProps {
  health: IndexHealth;
}

const STATUS_STYLE: Record<IndexHealthStatus, { dot: string; text: string }> = {
  healthy: { dot: "bg-green-400", text: "text-green-400" },
  warning: { dot: "bg-amber-400", text: "text-amber-400" },
  critical: { dot: "bg-red-400", text: "text-red-500" },
};

/** A real, derived explanation — never a generic "Critical" with no context. */
function statusExplanation(health: IndexHealth): string | null {
  if (health.status === "critical") {
    return `${health.failedDocuments} document${health.failedDocuments === 1 ? "" : "s"} failed embedding and need${
      health.failedDocuments === 1 ? "s" : ""
    } reprocessing.`;
  }
  if (health.status === "warning") {
    return `${health.pendingDocuments} document${health.pendingDocuments === 1 ? "" : "s"} still processing.`;
  }
  return null;
}

export function IndexHealthCard({ health }: IndexHealthCardProps) {
  const style = STATUS_STYLE[health.status];
  const explanation = statusExplanation(health);

  const rows: { label: string; value: number }[] = [
    { label: "Indexed Documents", value: health.indexedDocuments },
    { label: "Pending Documents", value: health.pendingDocuments },
    { label: "Failed Documents", value: health.failedDocuments },
    { label: "Indexed Chunks", value: health.indexedChunks },
    { label: "Failed Chunks", value: health.failedChunks },
  ];

  return (
    <Card className="p-5">
      <div className="mb-1 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">Index Health</h3>
        <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${style.text}`}>
          <span className={`h-2 w-2 rounded-full ${style.dot}`} aria-hidden="true" />
          {STATUS_LABEL[health.status]}
        </span>
      </div>
      {explanation && <p className="mb-3 text-xs text-text-3">{explanation}</p>}
      <dl className="space-y-2.5">
        {rows.map((row) => (
          <div key={row.label} className="flex items-center justify-between">
            <dt className="text-xs text-text-3">{row.label}</dt>
            <dd className="font-mono text-sm text-foreground">{row.value.toLocaleString()}</dd>
          </div>
        ))}
      </dl>
      <div className="mt-4 space-y-2 border-t border-border pt-3">
        <div className="flex items-center justify-between">
          <dt className="text-xs text-text-3">Embedding Model</dt>
          <dd className="text-xs font-medium text-foreground">Gemini Embedding 2</dd>
        </div>
        <div className="flex items-center justify-between">
          <dt className="text-xs text-text-3">Vector Store</dt>
          <dd className="text-xs font-medium text-foreground">Supabase (pgvector)</dd>
        </div>
      </div>
    </Card>
  );
}
