/**
 * Retrieval Explorer — Chapter 22 Implementation
 * Route: /retrieve
 * Purpose: Inspect and test the 4-stage retrieval pipeline
 * Team: Team 9 (Saurabh Kumar, Manju Yadav)
 * Task: E-10
 */

'use client';

import { useState } from 'react';
import { QueryPanel } from '@/components/retrieval/QueryPanel';
import { RetrievalPipeline } from '@/components/retrieval/RetrievalPipeline';
import { SearchResults } from '@/components/retrieval/SearchResults';
import { MetricsDashboard } from '@/components/retrieval/MetricsDashboard';
import { DebugPanel } from '@/components/retrieval/DebugPanel';
import { AppShell } from '@/components/layout/AppShell';
import { apiClient } from '@/services/api-client';
import type { RetrievalRequest, RetrievalResult } from '@/types';

export default function RetrievePage() {
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<RetrievalResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleExecuteRetrieval = async (request: RetrievalRequest) => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await apiClient.queryRetrieval(request);
      setResult(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Retrieval failed — please try again.';
      setError(message);
      console.error('Retrieval failed:', err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AppShell
      mode="builder"
      title="Retrieval Explorer"
      description="Inspect every stage of the retrieval pipeline — from query rewrite to final context delivery."
    >
      <div className="p-4 md:p-6">
        {/* Main Content */}
        <div className="grid grid-cols-1 gap-6">
          {/* Query Panel */}
          <QueryPanel onExecute={handleExecuteRetrieval} isLoading={isLoading} />

          {/* Error state */}
          {error && (
            <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-sm text-red-600">
              {error}
            </div>
          )}

          {/* Results Section - Only shown after query execution */}
          {result && (
            <>
              {/* Retrieval Pipeline Visualization */}
              <RetrievalPipeline stages={result.stages} />

              {/* Search Results */}
              <SearchResults chunks={result.retrieved_chunks} rawQuery={result.raw_query} />

              {/* Metrics Dashboard */}
              <MetricsDashboard result={result} />

              {/* Debug Panel - Collapsible */}
              <DebugPanel result={result} />
            </>
          )}
        </div>
      </div>
    </AppShell>
  );
}
