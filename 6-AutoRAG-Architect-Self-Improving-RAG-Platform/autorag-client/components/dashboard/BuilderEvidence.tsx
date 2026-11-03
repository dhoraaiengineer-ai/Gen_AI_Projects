"use client";

import type { NodeTraceEntry, Pipeline } from "@/types";

interface BuilderEvidenceProps {
  pipeline: Pipeline;
  entry: NodeTraceEntry | undefined;
}

// Frozen embedding-dimension contract (DB_SCHEMA.md, pgvector table columns) --
// a real, documented constant, not a fabricated display value.
const EMBEDDING_DIMENSIONS = 768;

function num(value: unknown): number | null {
  return typeof value === "number" ? value : null;
}
function str(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

/**
 * Part H — Builder Evidence. Sourced from the builder node_trace entry's real
 * extras plus the pipeline's real embedding_model/chunk_strategy. Batch
 * count/size render "Not collected" -- no real backend field carries them yet.
 */
export function BuilderEvidence({ pipeline, entry }: BuilderEvidenceProps) {
  const chunksIndexed = num(entry?.chunks_indexed);
  const retrievalStrategy = str(entry?.retrieval_strategy);
  const indexTarget = str(entry?.vector_table) ?? str(entry?.index_target);

  const rows: [string, string][] = [
    ["Embedding Model", pipeline.embedding_model],
    ["Dimensions", `${EMBEDDING_DIMENSIONS} (frozen contract)`],
    ["Chunks Indexed", chunksIndexed !== null ? chunksIndexed.toLocaleString() : "Not collected"],
    ["Retrieval Strategy", retrievalStrategy ?? "Not exposed"],
    ["Index Target", indexTarget ?? "Not exposed"],
    ["Chunk Strategy", pipeline.chunk_strategy ?? "Not collected"],
  ];

  return (
    <div className="mt-3 rounded-lg border border-border bg-card p-3">
      <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
        Builder Evidence
      </p>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 sm:grid-cols-3">
        {rows.map(([label, value]) => (
          <div key={label} className="min-w-0">
            <dt className="text-[10px] text-muted-foreground">{label}</dt>
            <dd className="truncate font-mono text-[11px] font-medium text-foreground">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
