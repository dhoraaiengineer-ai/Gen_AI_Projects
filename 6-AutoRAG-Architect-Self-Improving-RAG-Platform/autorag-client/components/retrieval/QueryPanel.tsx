'use client';

/**
 * QueryPanel — Retrieval query input and execution
 * Chapter 22.8: Query Panel
 * Supports natural language query, saved queries, query history
 */

import { useState } from 'react';
import { Search, Loader2 } from 'lucide-react';
import { usePipelines } from '@/hooks/use-pipelines';
import { pipelineDisplayName } from '@/lib/format';
import type { RetrievalRequest } from '@/types';

interface QueryPanelProps {
  onExecute?: (request: RetrievalRequest) => void;
  isLoading?: boolean;
}

export function QueryPanel({ onExecute, isLoading = false }: QueryPanelProps) {
  const { pipelines, isLoading: pipelinesLoading } = usePipelines();
  const [query, setQuery] = useState('');
  const [selectedPipeline, setSelectedPipeline] = useState('');
  const [topK, setTopK] = useState(5);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!query.trim() || !selectedPipeline) {
      return;
    }

    const request: RetrievalRequest = {
      pipeline_id: selectedPipeline,
      query: query.trim(),
      top_k: topK,
    };

    onExecute?.(request);
  };

  return (
    <div className="bg-card border border-border rounded-2xl p-6">
      <h2 className="text-xl font-semibold text-foreground mb-4 flex items-center gap-2">
        <Search className="w-5 h-5 text-accent" />
        Query Input
      </h2>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Pipeline Selector */}
        <div>
          <label htmlFor="pipeline" className="block text-sm font-medium text-text-3 mb-2">
            Pipeline
          </label>
          <select
            id="pipeline"
            value={selectedPipeline}
            onChange={(e) => setSelectedPipeline(e.target.value)}
            className="w-full bg-accent/5 border border-border rounded-lg px-4 py-2.5 text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500 transition-colors"
            disabled={isLoading || pipelinesLoading}
          >
            <option value="">
              {pipelinesLoading
                ? "Loading pipelines…"
                : pipelines.length === 0
                  ? "No pipelines available"
                  : "Select a pipeline…"}
            </option>
            {pipelines.map((p) => (
              <option key={p.id} value={p.id}>
                {pipelineDisplayName(p)}
              </option>
            ))}
          </select>
        </div>

        {/* Query Input */}
        <div>
          <label htmlFor="query" className="block text-sm font-medium text-text-3 mb-2">
            Natural Language Query
          </label>
          <textarea
            id="query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Enter your query... (e.g., How do I reset my password?)"
            rows={3}
            className="w-full bg-accent/5 border border-border rounded-lg px-4 py-3 text-foreground placeholder-[#64748B] focus:outline-none focus:ring-2 focus:ring-amber-500 resize-none transition-colors"
            disabled={isLoading}
          />
          {!query && (
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <span className="text-xs text-text-3">Try:</span>
              {["What was the company's revenue?", "Summarize the risk factors.", "What are the key financial metrics?"].map(
                (example) => (
                  <button
                    key={example}
                    type="button"
                    onClick={() => setQuery(example)}
                    disabled={isLoading}
                    className="rounded-full border border-border bg-accent/5 px-2.5 py-1 text-[11px] text-text-2 transition-colors hover:bg-accent/10"
                  >
                    {example}
                  </button>
                ),
              )}
            </div>
          )}
        </div>

        {/* Advanced Options */}
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <label htmlFor="topK" className="block text-sm font-medium text-text-3 mb-2">
              Top-K Results
            </label>
            <input
              id="topK"
              type="number"
              min={1}
              max={20}
              value={topK}
              onChange={(e) => setTopK(parseInt(e.target.value) || 5)}
              className="w-full bg-accent/5 border border-border rounded-lg px-4 py-2.5 text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500 transition-colors"
              disabled={isLoading}
            />
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-3 pt-2">
          <button
            type="submit"
            disabled={isLoading || !query.trim() || !selectedPipeline}
            className="bg-accent hover:bg-light_bronze-300 disabled:bg-accent/5 disabled:text-text-3 text-foreground px-6 py-2.5 rounded-lg font-medium transition-colors flex items-center gap-2"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Running Retrieval...
              </>
            ) : (
              <>
                <Search className="w-4 h-4" />
                Run Retrieval
              </>
            )}
          </button>

          <button
            type="button"
            onClick={() => {
              setQuery('');
              setSelectedPipeline('');
              setTopK(5);
            }}
            disabled={isLoading}
            className="bg-transparent border border-border hover:border-accent text-text-3 hover:text-foreground px-6 py-2.5 rounded-lg font-medium transition-colors"
          >
            Clear
          </button>
        </div>
      </form>

      {/* Info Banner */}
      <div className="mt-4 p-3 bg-accent/5 border border-border rounded-lg">
        <p className="text-xs text-text-3">
          <span className="font-semibold text-accent">Tip:</span> Runs real hybrid search
          (dense + BM25 + RRF fusion) and reranking — no answer is generated here, this is a
          retrieval-only inspector.
        </p>
      </div>
    </div>
  );
}
