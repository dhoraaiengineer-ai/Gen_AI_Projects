"use client";

/**
 * AI Knowledge Summary — real answer generation via GET /api/v1/query
 * (retrieve -> rerank -> LLM generation, prompt-constrained to "answer using
 * only the provided context"). User-triggered (not automatic) since it's a
 * separate billed LLM call on top of the free retrieval-only search above.
 *
 * Deliberately does NOT show a confidence score, "Grounded: Yes/No" badge,
 * hallucination-risk indicator, or a "chunks used vs ignored" breakdown —
 * none of those exist on this endpoint's real response. Fabricating them
 * would be exactly the kind of unverifiable claim this project's own
 * marketing-page reviews this session got corrected for; the honest
 * source-count line ("Sources: N pages") is the only summary-quality signal
 * shown, because it's the only one actually backed by real data.
 */

import { useState } from "react";
import { Brain, Copy, Check, FileText, Sparkles, AlertTriangle } from "lucide-react";

import { Card } from "@/components/ui/card";
import { apiClient } from "@/services/api-client";
import type { QueryAnswerResult } from "@/types";

interface AiSummaryPanelProps {
  pipelineId: string | null;
  query: string;
  hasSearched: boolean;
  hasResults: boolean;
}

export function AiSummaryPanel({ pipelineId, query, hasSearched, hasResults }: AiSummaryPanelProps) {
  const [result, setResult] = useState<QueryAnswerResult | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [askedFor, setAskedFor] = useState<string | null>(null);

  if (!hasSearched) return null;

  async function generate() {
    if (!pipelineId || !query) return;
    setIsGenerating(true);
    setError(null);
    setResult(null);
    setAskedFor(query);
    try {
      const res = await apiClient.queryAnswer({ pipeline_id: pipelineId, query });
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Summary generation failed");
    } finally {
      setIsGenerating(false);
    }
  }

  function handleCopy() {
    if (!result) return;
    navigator.clipboard.writeText(result.answer);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  const pages = result
    ? Array.from(new Set(result.citations.map((c) => c.page).filter((p): p is number => p !== null))).sort(
        (a, b) => a - b,
      )
    : [];

  return (
    <Card className="p-5">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <Brain className="h-4 w-4 text-accent" aria-hidden="true" />
          AI Knowledge Summary
        </h2>
        {!isGenerating && (
          <button
            type="button"
            onClick={generate}
            disabled={!hasResults}
            title={!hasResults ? "No retrieved chunks to summarize" : undefined}
            className="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-accent-light disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Sparkles className="h-3.5 w-3.5" />
            {result ? "Regenerate Summary" : "Generate AI Summary"}
          </button>
        )}
      </div>

      {!hasResults && !result && (
        <p className="text-xs text-text-3">
          No summary can be generated — no relevant chunks were retrieved for this query. Try broader
          keywords or a different pipeline.
        </p>
      )}

      {isGenerating && (
        <div className="space-y-2" aria-label="Generating summary">
          <div className="h-3 w-2/3 animate-pulse rounded bg-accent/10" />
          <div className="h-3 w-full animate-pulse rounded bg-accent/10" />
          <div className="h-3 w-5/6 animate-pulse rounded bg-accent/10" />
        </div>
      )}

      {error && !isGenerating && (
        <div className="flex items-start gap-2 rounded-md border border-red-500/20 bg-red-500/5 p-3 text-xs text-red-600">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {result && !isGenerating && !error && (
        <div className="space-y-4">
          <div>
            <span className="text-[11px] font-medium uppercase tracking-wide text-text-3">Question</span>
            <p className="text-sm text-foreground">{askedFor}</p>
          </div>

          <div>
            <span className="text-[11px] font-medium uppercase tracking-wide text-text-3">Summary</span>
            <p className="mt-1 whitespace-pre-wrap text-sm text-text-2">{result.answer}</p>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-3">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[11px] font-medium text-text-3">Sources:</span>
              {pages.length > 0 ? (
                pages.map((p) => (
                  <span
                    key={p}
                    className="inline-flex items-center gap-1 rounded-full bg-accent/5 px-2 py-0.5 text-[11px] text-text-2"
                  >
                    <FileText className="h-3 w-3" /> Page {p}
                  </span>
                ))
              ) : (
                <span className="text-[11px] text-text-3">
                  {result.retrieval_count} chunk{result.retrieval_count === 1 ? "" : "s"} used
                </span>
              )}
              <span className="font-mono text-[11px] text-text-3">· {result.latency_ms}ms</span>
            </div>
            <button
              type="button"
              onClick={handleCopy}
              className="inline-flex items-center gap-1 text-xs text-text-3 hover:text-foreground"
            >
              {copied ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
              {copied ? "Copied" : "Copy Summary"}
            </button>
          </div>
        </div>
      )}
    </Card>
  );
}
