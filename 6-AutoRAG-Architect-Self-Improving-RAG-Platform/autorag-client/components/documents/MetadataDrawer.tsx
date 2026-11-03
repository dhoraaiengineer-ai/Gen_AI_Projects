"use client";

/**
 * Metadata Drawer — Chapter 31.11
 * Displays document ID, owner, tags, categories, source, timestamps, version
 */

import { X, FileText, Calendar, Tag, Layers, ScanLine } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/services/api-client";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetClose,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface MetadataDrawerProps {
  documentId: string;
  open: boolean;
  onClose: () => void;
}

export default function MetadataDrawer({
  documentId,
  open,
  onClose,
}: MetadataDrawerProps) {
  const { data: document, isLoading } = useQuery({
    queryKey: ["document", documentId],
    queryFn: () => apiClient.getDocument(documentId),
    enabled: open,
  });

  if (!open) return null;

  return (
    <Sheet open={open} onOpenChange={onClose}>
      <SheetContent side="right" className="w-full sm:max-w-md" data-testid="metadata-drawer">
        <SheetHeader>
          <SheetTitle>Document Metadata</SheetTitle>
          <SheetClose asChild>
            <Button variant="ghost" size="sm">
              <X className="h-4 w-4" />
            </Button>
          </SheetClose>
        </SheetHeader>

        {isLoading ? (
          <div className="flex items-center justify-center h-96">
            <div className="h-8 w-8 border-2 border-orange-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <div className="mt-6 space-y-6">
            {/* General Information */}
            <div>
              <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                <FileText className="h-4 w-4" />
                General Information
              </h3>
              <dl className="space-y-2 text-sm">
                <div>
                  <dt className="text-muted-foreground">Document ID</dt>
                  <dd className="font-mono text-xs">{document?.id}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">File Name</dt>
                  <dd>{document?.file_name}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Version</dt>
                  <dd>{document?.version}</dd>
                </div>
              </dl>
            </div>

            {/* Processing Information */}
            <div>
              <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                <Layers className="h-4 w-4" />
                Processing Information
              </h3>
              <dl className="space-y-2 text-sm">
                <div>
                  <dt className="text-muted-foreground">Chunk Count</dt>
                  <dd data-testid="chunk-count">{document?.chunk_count || 0}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Indexed Chunks</dt>
                  <dd>{document?.indexed_chunks || 0}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Failed Chunks</dt>
                  <dd className={document?.failed_chunks ? "text-red-500" : ""}>
                    {document?.failed_chunks || 0}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Embedding Status</dt>
                  <dd>
                    <Badge variant="outline">{document?.embedding_status}</Badge>
                  </dd>
                </div>
              </dl>
            </div>

            {/* Document Evidence — real per-document ingestion facts
                (migration 0012, P0.7 follow-up, 13-Jul-2026), persisted at
                ingestion time, not reconstructed. null page_count means
                "not yet ingested," never a fabricated 0. */}
            <div>
              <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                <Layers className="h-4 w-4" />
                Document Evidence
              </h3>
              <dl className="space-y-2 text-sm">
                <div>
                  <dt className="text-muted-foreground">Pages</dt>
                  <dd>{document?.page_count ?? "Not yet measured"}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Characters</dt>
                  <dd>{document?.char_count?.toLocaleString() ?? "Not yet measured"}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">PII Protection</dt>
                  <dd>
                    {document?.page_count == null ? (
                      <span className="text-muted-foreground">Not yet measured</span>
                    ) : document.pii_redaction_count === 0 ? (
                      <Badge variant="outline">No PII found</Badge>
                    ) : (
                      <div className="space-y-1">
                        <Badge variant="outline" className="border-stone-200 bg-stone-100 text-stone-700">
                          Redacted · {document.pii_redaction_count} total
                        </Badge>
                        <ul className="text-xs text-muted-foreground">
                          {Object.entries(document.pii_counts_by_type)
                            .filter(([, count]) => count > 0)
                            .map(([type, count]) => (
                              <li key={type}>
                                {type}: {count}
                              </li>
                            ))}
                        </ul>
                      </div>
                    )}
                  </dd>
                </div>
                {document?.page_count != null && (
                  <div>
                    <dt className="text-muted-foreground">Detector</dt>
                    <dd className="text-xs text-muted-foreground">pii-v1 · Rule 70</dd>
                  </div>
                )}
              </dl>
            </div>

            {/* OCR Information — shown only when backend populates metadata */}
            {document?.metadata && typeof document.metadata.ocr_pages_count === "number" && (
              <div>
                <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                  <ScanLine className="h-4 w-4" />
                  Extraction
                </h3>
                <dl className="space-y-2 text-sm">
                  <div>
                    <dt className="text-muted-foreground">OCR Pages</dt>
                    <dd className="flex items-center gap-2">
                      {document.metadata.ocr_pages_count as number}
                      {" / "}
                      {(document.metadata.total_pages_count as number) ?? "?"} pages
                      {(document.metadata.ocr_pages_count as number) > 0 && (
                        <Badge variant="outline" className="text-xs">Gemini OCR</Badge>
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Extraction Method</dt>
                    <dd>
                      {(document.metadata.ocr_pages_count as number) > 0
                        ? "Text layer + OCR fallback"
                        : "Text layer only"}
                    </dd>
                  </div>
                </dl>
              </div>
            )}

            {/* Tags & Categories */}
            <div>
              <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                <Tag className="h-4 w-4" />
                Tags & Categories
              </h3>
              <div className="space-y-3">
                <div>
                  <dt className="text-sm text-muted-foreground mb-1">Tags</dt>
                  <div className="flex flex-wrap gap-2">
                    {document?.tags && document.tags.length > 0 ? (
                      document.tags.map((tag) => (
                        <Badge key={tag} variant="secondary">
                          {tag}
                        </Badge>
                      ))
                    ) : (
                      <span className="text-sm text-muted-foreground">No tags</span>
                    )}
                  </div>
                </div>
                <div>
                  <dt className="text-sm text-muted-foreground mb-1">Categories</dt>
                  <div className="flex flex-wrap gap-2">
                    {document?.categories && document.categories.length > 0 ? (
                      document.categories.map((category) => (
                        <Badge key={category} variant="outline">
                          {category}
                        </Badge>
                      ))
                    ) : (
                      <span className="text-sm text-muted-foreground">No categories</span>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Timestamps */}
            <div>
              <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                <Calendar className="h-4 w-4" />
                Timestamps
              </h3>
              <dl className="space-y-2 text-sm">
                <div>
                  <dt className="text-muted-foreground">Uploaded At</dt>
                  <dd>{new Date(document?.uploaded_at || "").toLocaleString()}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Created At</dt>
                  <dd>{new Date(document?.created_at || "").toLocaleString()}</dd>
                </div>
              </dl>
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
