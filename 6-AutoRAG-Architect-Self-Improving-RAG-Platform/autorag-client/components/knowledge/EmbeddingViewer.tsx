"use client";

/**
 * Embedding Viewer — Chapter 32.12. Provider/model/dimensions come from the FROZEN
 * platform contract (CLAUDE.md: Gemini Embedding 2, 768 dims), not a fabricated
 * per-document value. Per-document embedding_status is real (DocumentDetail).
 * Vector visualization / clustering are marked "future" in the spec — not built.
 */

import { Card } from "@/components/ui/card";
import type { DocumentDetail } from "@/types";

interface EmbeddingViewerProps {
  detail: DocumentDetail | null;
}

/** Frozen contract values — embedding dimensions locked at 768 (CLAUDE.md §11). */
const EMBEDDING_MODEL = {
  provider: "Google",
  model: "Gemini Embedding 2",
  dimensions: 768,
} as const;

const STATUS_TEXT: Record<DocumentDetail["embedding_status"], string> = {
  complete: "text-green-400",
  processing: "text-amber-400",
  pending: "text-text-3",
  failed: "text-red-500",
};

export function EmbeddingViewer({ detail }: EmbeddingViewerProps) {
  return (
    <Card className="p-5">
      <h3 className="mb-4 text-sm font-semibold text-foreground">Embedding Model</h3>
      <dl className="space-y-2.5">
        <Row label="Provider" value={EMBEDDING_MODEL.provider} />
        <Row label="Model" value={EMBEDDING_MODEL.model} />
        <Row label="Dimensions" value={String(EMBEDDING_MODEL.dimensions)} />
        <div className="flex items-center justify-between">
          <dt className="text-xs text-text-3">Status (selected doc)</dt>
          <dd
            className={`font-mono text-sm capitalize ${
              detail ? STATUS_TEXT[detail.embedding_status] : "text-gray-300"
            }`}
          >
            {detail ? detail.embedding_status : "—"}
          </dd>
        </div>
      </dl>
    </Card>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <dt className="text-xs text-text-3">{label}</dt>
      <dd className="font-mono text-sm text-foreground">{value}</dd>
    </div>
  );
}
