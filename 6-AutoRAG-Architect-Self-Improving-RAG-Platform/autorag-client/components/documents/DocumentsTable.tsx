"use client";

/**
 * Documents Table — Chapter 31.9 (Phase 4 Enhancement)
 * Main data table with columns: name, type, size, uploaded by, date, status, chunks, actions
 * Phase 2: Added checkbox selection for bulk operations
 * Phase 4: Added sortable column headers with visual indicators
 */

import { useState } from "react";
import {
  Download,
  Eye,
  RefreshCw,
  Archive,
  Trash2,
  MoreVertical,
  FileText,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
} from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/services/api-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { Document, DocumentStatus } from "@/types";
import MetadataDrawer from "./MetadataDrawer";
import dynamic from "next/dynamic";
const PreviewPanel = dynamic(() => import("./PreviewPanel"), { ssr: false });

/**
 * Documents table component props
 * @interface DocumentsTableProps
 */
interface DocumentsTableProps {
  /** Array of documents to display */
  documents: Document[];
  /** Loading state indicator */
  isLoading: boolean;
  /** Error object if fetch failed */
  error: Error | null;
  /** Callback to refresh the table data */
  onRefresh: () => void;
  /** Array of selected document IDs (for bulk operations) */
  selectedIds: string[];
  /** Callback when selection changes */
  onSelectionChange: (ids: string[]) => void;
  /** Current sort column (Phase 4) */
  sortBy?: "file_name" | "uploaded_at" | "file_size" | "status";
  /** Current sort direction (Phase 4) */
  sortOrder?: "asc" | "desc";
  /** Callback when sort column changes (Phase 4) */
  onSortChange: (sortBy: "file_name" | "uploaded_at" | "file_size" | "status") => void;
}

export default function DocumentsTable({
  documents,
  isLoading,
  error,
  onRefresh,
  selectedIds,
  onSelectionChange,
  sortBy,
  sortOrder,
  onSortChange,
}: DocumentsTableProps) {
  const queryClient = useQueryClient();
  const [previewDocId, setPreviewDocId] = useState<string | null>(null);
  const [metadataDocId, setMetadataDocId] = useState<string | null>(null);

  const reprocessMutation = useMutation({
    mutationFn: (docId: string) => apiClient.reprocessDocument(docId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (docId: string) => apiClient.deleteDocument(docId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
  });

  // Checkbox selection handlers
  const isAllSelected = documents.length > 0 && selectedIds.length === documents.length;
  const isSomeSelected = selectedIds.length > 0 && selectedIds.length < documents.length;

  const handleSelectAll = () => {
    if (isAllSelected) {
      onSelectionChange([]);
    } else {
      onSelectionChange(documents.map((doc) => doc.id));
    }
  };

  const handleSelectOne = (docId: string) => {
    if (selectedIds.includes(docId)) {
      onSelectionChange(selectedIds.filter((id) => id !== docId));
    } else {
      onSelectionChange([...selectedIds, docId]);
    }
  };

  const getStatusBadge = (status: DocumentStatus) => {
    const variants: Record<DocumentStatus, { variant: "default" | "secondary" | "destructive" | "outline"; label: string }> = {
      uploaded: { variant: "secondary", label: "Uploaded" },
      validating: { variant: "outline", label: "Validating" },
      chunking: { variant: "outline", label: "Chunking" },
      embedding: { variant: "outline", label: "Embedding" },
      indexed: { variant: "default", label: "Indexed" },
      failed: { variant: "destructive", label: "Failed" },
      archived: { variant: "secondary", label: "Archived" },
    };

    const config = variants[status];
    return (
      <Badge variant={config.variant} className={status === "indexed" ? "bg-green-500" : ""}>
        {config.label}
      </Badge>
    );
  };

  /**
   * Real per-document PII evidence (migration 0012, P0.7 follow-up,
   * 13-Jul-2026) — page_count is null until ingestion_node has processed
   * this document at least once; distinct from "0 redactions found" (a
   * real, valid measurement). Never shows original/truncated PII values.
   */
  const getPiiBadge = (doc: Document) => {
    if (doc.page_count === null) {
      return <span className="text-xs text-muted-foreground">Not yet ingested</span>;
    }
    if (doc.pii_redaction_count === 0) {
      return (
        <Badge variant="outline" className="text-xs text-muted-foreground">
          None found
        </Badge>
      );
    }
    return (
      <Badge
        variant="outline"
        className="border-stone-200 bg-stone-100 text-xs text-stone-700"
        title={Object.entries(doc.pii_counts_by_type)
          .map(([type, count]) => `${type}: ${count}`)
          .join(", ")}
      >
        Redacted · {doc.pii_redaction_count}
      </Badge>
    );
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  const getFileTypeIcon = (_mimeType: string) => {
    // All files use FileText icon for consistency
    return <FileText className="h-4 w-4 text-muted-foreground" />;
  };

  /**
   * Sortable header component (Phase 4)
   *
   * Renders a clickable column header with sort indicators:
   * - ArrowUpDown (inactive column)
   * - ArrowUp (active, ascending)
   * - ArrowDown (active, descending)
   *
   * Active column is highlighted in orange.
   *
   * @param label - Display text for the column header
   * @param sortKey - Database column key for sorting
   */
  const SortableHeader = ({
    label,
    sortKey,
  }: {
    label: string;
    sortKey: "file_name" | "uploaded_at" | "file_size" | "status";
  }) => {
    const isActive = sortBy === sortKey;
    const Icon = !isActive
      ? ArrowUpDown
      : sortOrder === "asc"
      ? ArrowUp
      : ArrowDown;

    return (
      <button
        onClick={() => onSortChange(sortKey)}
        className="flex items-center gap-1 hover:text-foreground transition-colors"
      >
        {label}
        <Icon className={`h-4 w-4 ${isActive ? "text-orange-500" : "text-muted-foreground"}`} />
      </button>
    );
  };

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-500 mb-4">Failed to load documents: {error.message}</p>
        <Button onClick={onRefresh} variant="outline">
          Retry
        </Button>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-2">
        <div className="h-12 bg-muted rounded-lg animate-pulse" />
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="h-16 bg-muted rounded-lg animate-pulse" />
        ))}
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="text-center py-12 border-2 border-dashed rounded-lg">
        <FileText className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
        <h3 className="text-lg font-semibold mb-2">No documents uploaded</h3>
        <p className="text-muted-foreground">
          Get started by uploading your first document above
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="border rounded-lg">
        <Table aria-label="Documents table">
          <TableHeader>
            <TableRow>
              <TableHead className="w-12">
                <Checkbox
                  checked={isAllSelected}
                  onCheckedChange={handleSelectAll}
                  aria-label="Select all documents"
                  className={isSomeSelected ? "data-[state=checked]:bg-orange-500" : ""}
                />
              </TableHead>
              <TableHead>
                <SortableHeader label="Name" sortKey="file_name" />
              </TableHead>
              <TableHead>Type</TableHead>
              <TableHead>
                <SortableHeader label="Size" sortKey="file_size" />
              </TableHead>
              <TableHead>
                <SortableHeader label="Uploaded" sortKey="uploaded_at" />
              </TableHead>
              <TableHead>
                <SortableHeader label="Status" sortKey="status" />
              </TableHead>
              <TableHead>PII</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {documents.map((doc) => (
              <TableRow key={doc.id}>
                <TableCell>
                  <Checkbox
                    checked={selectedIds.includes(doc.id)}
                    onCheckedChange={() => handleSelectOne(doc.id)}
                    aria-label={`Select ${doc.file_name}`}
                  />
                </TableCell>
                <TableCell className="font-medium">
                  <div className="flex items-center gap-2">
                    {getFileTypeIcon(doc.mime_type)}
                    <span className="truncate max-w-xs">{doc.file_name}</span>
                  </div>
                </TableCell>
                <TableCell>
                  {doc.mime_type.includes("pdf")
                    ? "PDF"
                    : doc.mime_type.includes("word")
                    ? "DOCX"
                    : doc.mime_type.includes("text")
                    ? "TXT"
                    : "Other"}
                </TableCell>
                <TableCell>{formatFileSize(doc.file_size)}</TableCell>
                <TableCell>{formatDate(doc.uploaded_at)}</TableCell>
                <TableCell>{getStatusBadge(doc.status)}</TableCell>
                <TableCell>{getPiiBadge(doc)}</TableCell>
                <TableCell className="text-right">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="sm">
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        onClick={() => setPreviewDocId(doc.id)}
                        data-testid="preview-button"
                      >
                        <Eye className="h-4 w-4 mr-2" />
                        Preview
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => setMetadataDocId(doc.id)}
                        data-testid="metadata-button"
                      >
                        <FileText className="h-4 w-4 mr-2" />
                        Metadata
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => reprocessMutation.mutate(doc.id)}
                        data-testid="reprocess-button"
                      >
                        <RefreshCw className="h-4 w-4 mr-2" />
                        Reprocess
                      </DropdownMenuItem>
                      <DropdownMenuItem>
                        <Download className="h-4 w-4 mr-2" />
                        Download
                      </DropdownMenuItem>
                      <DropdownMenuItem>
                        <Archive className="h-4 w-4 mr-2" />
                        Archive
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => deleteMutation.mutate(doc.id)}
                        className="text-red-500"
                      >
                        <Trash2 className="h-4 w-4 mr-2" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Preview Panel */}
      {previewDocId && (
        <PreviewPanel
          documentId={previewDocId}
          open={!!previewDocId}
          onClose={() => setPreviewDocId(null)}
        />
      )}

      {/* Metadata Drawer */}
      {metadataDocId && (
        <MetadataDrawer
          documentId={metadataDocId}
          open={!!metadataDocId}
          onClose={() => setMetadataDocId(null)}
        />
      )}
    </>
  );
}
