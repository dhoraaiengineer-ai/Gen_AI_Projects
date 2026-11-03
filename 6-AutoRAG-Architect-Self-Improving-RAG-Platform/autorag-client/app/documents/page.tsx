/**
 * Documents Management — F-17
 *
 * Upload, organize, validate, and manage knowledge sources for RAG pipelines.
 * Acts as the gateway into the Knowledge Base.
 */

import { Suspense } from "react";
import DocumentsPageClient from "@/components/documents/DocumentsPageClient";
import { AppShell } from "@/components/layout/AppShell";

export default function DocumentsPage() {
  return (
    <AppShell
      title="Upload Documents"
      description="Drop a PDF, DOCX or TXT below — the Ingestion agent parses it, masks PII, chunks it, and embeds it into your pipeline automatically."
      mode="builder"
    >
      <div className="flex flex-col gap-6">
        {/* Client Component with Suspense boundary */}
        <Suspense fallback={<DocumentsLoadingSkeleton />}>
          <DocumentsPageClient />
        </Suspense>
      </div>
    </AppShell>
  );
}

/**
 * Loading skeleton for the documents page.
 * Shown while data is fetching.
 */
function DocumentsLoadingSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Summary Cards Skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-24 bg-muted rounded-lg" />
        ))}
      </div>

      {/* Upload Panel Skeleton */}
      <div className="h-40 bg-muted rounded-lg" />

      {/* Search/Filters Skeleton */}
      <div className="flex gap-4">
        <div className="h-10 flex-1 bg-muted rounded-lg" />
        <div className="h-10 w-40 bg-muted rounded-lg" />
      </div>

      {/* Table Skeleton */}
      <div className="space-y-2">
        <div className="h-12 bg-muted rounded-lg" />
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="h-16 bg-muted rounded-lg" />
        ))}
      </div>
    </div>
  );
}
