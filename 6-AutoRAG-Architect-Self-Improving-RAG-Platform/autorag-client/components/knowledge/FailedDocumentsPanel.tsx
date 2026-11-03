"use client";

/**
 * Failed Documents panel (Evaluation Center Phase 3a, 24-Jul-2026). Wires
 * to the already-real POST /documents/reprocess and /documents/bulk/reprocess
 * endpoints (app/routes/documents.py) -- this closes a real frontend gap,
 * not a backend one: the retry capability existed server-side but had no UI.
 */

import { useState } from "react";
import { AlertCircle, RefreshCw } from "lucide-react";

import { apiClient } from "@/services/api-client";
import { Card } from "@/components/ui/card";
import type { Document } from "@/types";

interface FailedDocumentsPanelProps {
  documents: Document[];
  onRetried: () => void;
}

export function FailedDocumentsPanel({ documents, onRetried }: FailedDocumentsPanelProps) {
  const failed = documents.filter((d) => d.status === "failed");
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [retryingAll, setRetryingAll] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (failed.length === 0) return null;

  const handleRetryOne = async (id: string) => {
    setRetryingId(id);
    setError(null);
    try {
      await apiClient.reprocessDocument(id);
      onRetried();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to retry document");
    } finally {
      setRetryingId(null);
    }
  };

  const handleRetryAll = async () => {
    setRetryingAll(true);
    setError(null);
    try {
      await apiClient.bulkReprocessDocuments(failed.map((d) => d.id));
      onRetried();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to retry documents");
    } finally {
      setRetryingAll(false);
    }
  };

  return (
    <Card className="p-5">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AlertCircle className="h-4 w-4 text-rose-500" aria-hidden="true" />
          <h3 className="text-sm font-semibold text-foreground">
            Failed Documents ({failed.length})
          </h3>
        </div>
        <button
          type="button"
          onClick={handleRetryAll}
          disabled={retryingAll}
          className="flex items-center gap-1.5 rounded-lg border border-indigo-400/40 bg-indigo-500/15 px-3 py-1.5 text-xs font-semibold text-indigo-300 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <RefreshCw
            className={`h-3.5 w-3.5 ${retryingAll ? "motion-safe:animate-spin" : ""}`}
            aria-hidden="true"
          />
          {retryingAll ? "Retrying…" : "Retry All"}
        </button>
      </div>

      {error && (
        <div role="alert" className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
          {error}
        </div>
      )}

      <div className="space-y-1.5">
        {failed.map((d) => (
          <div
            key={d.id}
            className="flex items-center justify-between rounded-lg border border-rose-400/20 bg-rose-500/5 px-3 py-2 text-xs"
          >
            <span className="truncate text-text-2">{d.file_name}</span>
            <button
              type="button"
              onClick={() => handleRetryOne(d.id)}
              disabled={retryingId === d.id}
              className="shrink-0 font-semibold text-indigo-300 hover:underline disabled:opacity-50"
            >
              {retryingId === d.id ? "Retrying…" : "Retry"}
            </button>
          </div>
        ))}
      </div>
    </Card>
  );
}
