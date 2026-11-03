"use client";

/**
 * Semantic Search — Chapter 32.9. Backed by the REAL 4-stage retrieval stack
 * (apiClient.queryRetrieval), which is per-pipeline — hence the pipeline selector
 * (user-confirmed scope model). Submitting runs a real similarity search over the
 * indexed knowledge and returns scored chunks.
 */

import { useEffect, useState } from "react";
import { Search, History } from "lucide-react";

import { Card } from "@/components/ui/card";
import { pipelineDisplayName } from "@/lib/format";
import type { PipelineWithRun } from "@/types";

const RECENT_SEARCHES_KEY = "autorag.kb.recentSearches";
const MAX_RECENT_SEARCHES = 5;

function loadRecentSearches(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(RECENT_SEARCHES_KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

function saveRecentSearch(query: string, current: string[]): string[] {
  const next = [query, ...current.filter((q) => q !== query)].slice(0, MAX_RECENT_SEARCHES);
  if (typeof window !== "undefined") {
    window.localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(next));
  }
  return next;
}

interface SemanticSearchProps {
  pipelines: PipelineWithRun[];
  pipelineId: string | null;
  onPipelineChange: (id: string | null) => void;
  onSearch: (query: string) => void;
  isSearching: boolean;
}

export function SemanticSearch({
  pipelines,
  pipelineId,
  onPipelineChange,
  onSearch,
  isSearching,
}: SemanticSearchProps) {
  const [query, setQuery] = useState("");
  const [recentSearches, setRecentSearches] = useState<string[]>([]);

  useEffect(() => {
    setRecentSearches(loadRecentSearches());
  }, []);

  const canSearch = Boolean(pipelineId) && query.trim().length > 0 && !isSearching;

  function submitQuery(q: string) {
    const trimmed = q.trim();
    if (!trimmed || !pipelineId || isSearching) return;
    setQuery(trimmed);
    setRecentSearches(saveRecentSearch(trimmed, recentSearches));
    onSearch(trimmed);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    submitQuery(query);
  }

  return (
    <Card className="p-4">
      <form onSubmit={handleSubmit} className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="w-full sm:w-56">
          <label htmlFor="kb-pipeline" className="mb-1 block text-xs font-medium text-text-3">
            Search Scope
          </label>
          <select
            id="kb-pipeline"
            value={pipelineId ?? ""}
            onChange={(e) => onPipelineChange(e.target.value || null)}
            disabled={pipelines.length === 0}
            className="w-full rounded-md border border-border bg-accent/5 px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none disabled:opacity-50"
          >
            {pipelines.length === 0 && <option value="">No pipelines</option>}
            {pipelines.map((p) => (
              <option key={p.id} value={p.id}>
                {pipelineDisplayName(p)}
              </option>
            ))}
          </select>
        </div>

        <div className="relative flex-1">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-3"
            aria-hidden="true"
          />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask a question about your documents…"
            aria-label="Semantic search query"
            className="w-full rounded-md border border-border bg-accent/5 py-2 pl-9 pr-3 text-sm text-foreground placeholder:text-text-3 focus:border-accent focus:outline-none"
          />
        </div>

        <button
          type="submit"
          disabled={!canSearch}
          className="shrink-0 rounded-md bg-accent px-4 py-2 text-sm font-medium text-foreground transition-colors motion-safe:transition-colors hover:bg-accent-light disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isSearching ? "Searching…" : "Search"}
        </button>
      </form>
      {!pipelineId && pipelines.length > 0 && (
        <p className="mt-2 text-xs text-text-3">Select a pipeline to scope semantic search.</p>
      )}
      {recentSearches.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-border pt-3">
          <span className="inline-flex items-center gap-1 text-xs text-text-3">
            <History className="h-3.5 w-3.5" aria-hidden="true" />
            Recent:
          </span>
          {recentSearches.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => submitQuery(q)}
              className="rounded-full border border-border bg-accent/5 px-2.5 py-1 text-xs text-text-2 transition-colors hover:bg-accent/10"
            >
              {q}
            </button>
          ))}
        </div>
      )}
    </Card>
  );
}
