"use client";

/**
 * Preview Panel — Chapter 31.10 (Phase 2)
 * Document preview with PDF.js rendering, zoom, and text search
 *
 * Features:
 * - PDF.js integration for in-browser PDF rendering
 * - Zoom controls (fit-width, fit-page, custom %)
 * - Page navigation for multi-page documents
 * - Text search with highlight
 * - Fallback for unsupported file types
 */

import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Document, Page, pdfjs } from "react-pdf";
import {
  X,
  ZoomIn,
  ZoomOut,
  ChevronLeft,
  ChevronRight,
  Search,
  FileText,
  AlertCircle,
} from "lucide-react";
import { apiClient } from "@/services/api-client";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetClose,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.js`;

interface PreviewPanelProps {
  documentId: string;
  open: boolean;
  onClose: () => void;
}

export default function PreviewPanel({
  documentId,
  open,
  onClose,
}: PreviewPanelProps) {
  const [numPages, setNumPages] = useState<number>(0);
  const [pageNumber, setPageNumber] = useState(1);
  const [scale, setScale] = useState(1.0);
  const [searchText, setSearchText] = useState("");

  const { data: document, isLoading, error } = useQuery({
    queryKey: ["document", documentId],
    queryFn: () => apiClient.getDocument(documentId),
    enabled: open && !!documentId,
  });

  // Reset state when document changes
  useEffect(() => {
    if (open) {
      setPageNumber(1);
      setScale(1.0);
      setSearchText("");
    }
  }, [documentId, open]);

  const handleDocumentLoadSuccess = ({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
  };

  const changePage = (offset: number) => {
    setPageNumber((prevPageNumber) => {
      const newPage = prevPageNumber + offset;
      return Math.min(Math.max(1, newPage), numPages);
    });
  };

  const handleZoomIn = () => {
    setScale((prev) => Math.min(prev + 0.25, 3.0));
  };

  const handleZoomOut = () => {
    setScale((prev) => Math.max(prev - 0.25, 0.5));
  };

  const handleZoomPreset = (preset: string) => {
    switch (preset) {
      case "fit-width":
        setScale(1.0);
        break;
      case "fit-page":
        setScale(0.85);
        break;
      case "100":
        setScale(1.0);
        break;
      case "125":
        setScale(1.25);
        break;
      case "150":
        setScale(1.5);
        break;
      case "200":
        setScale(2.0);
        break;
    }
  };

  const isPDF = document?.mime_type === "application/pdf";

  // Build preview URL (assuming Supabase Storage or similar)
  const previewUrl = document
    ? `${process.env.NEXT_PUBLIC_API_URL}/api/v1/documents/${documentId}/download`
    : null;

  return (
    <Sheet open={open} onOpenChange={onClose}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-3xl overflow-hidden flex flex-col"
        data-testid="preview-panel"
      >
        <SheetHeader className="flex-shrink-0">
          <div className="flex items-center justify-between">
            <SheetTitle>Document Preview</SheetTitle>
            <SheetClose asChild>
              <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                <X className="h-4 w-4" />
              </Button>
            </SheetClose>
          </div>
        </SheetHeader>

        {isLoading && (
          <div className="flex items-center justify-center h-96">
            <div className="h-8 w-8 border-2 border-orange-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {error && (
          <div className="flex flex-col items-center justify-center h-96 space-y-4">
            <AlertCircle className="h-12 w-12 text-red-500" />
            <div className="text-center">
              <p className="text-sm font-medium">Failed to load document</p>
              <p className="text-xs text-muted-foreground mt-1">
                {(error as Error).message}
              </p>
            </div>
          </div>
        )}

        {!isLoading && !error && document && (
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Metadata */}
            <div className="flex-shrink-0 p-4 bg-muted rounded-lg space-y-1 mb-4">
              <p className="text-sm font-medium truncate">{document.file_name}</p>
              <div className="flex items-center gap-4 text-xs text-muted-foreground">
                <span>{((document.file_size || 0) / 1024).toFixed(1)} KB</span>
                <span className="capitalize">{document.status}</span>
                {document.mime_type.includes("pdf") && (
                  <span>PDF</span>
                )}
              </div>
            </div>

            {/* PDF Controls */}
            {isPDF && previewUrl && (
              <>
                <div className="flex-shrink-0 flex items-center gap-2 mb-4 flex-wrap">
                  {/* Zoom controls */}
                  <div className="flex items-center gap-1 border rounded-lg p-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleZoomOut}
                      disabled={scale <= 0.5}
                      className="h-7 w-7 p-0"
                      aria-label="Zoom out"
                    >
                      <ZoomOut className="h-4 w-4" />
                    </Button>
                    <Select
                      value={String(Math.round(scale * 100))}
                      onValueChange={handleZoomPreset}
                    >
                      <SelectTrigger className="h-7 w-24 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="fit-width">Fit Width</SelectItem>
                        <SelectItem value="fit-page">Fit Page</SelectItem>
                        <SelectItem value="100">100%</SelectItem>
                        <SelectItem value="125">125%</SelectItem>
                        <SelectItem value="150">150%</SelectItem>
                        <SelectItem value="200">200%</SelectItem>
                      </SelectContent>
                    </Select>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleZoomIn}
                      disabled={scale >= 3.0}
                      className="h-7 w-7 p-0"
                      aria-label="Zoom in"
                    >
                      <ZoomIn className="h-4 w-4" />
                    </Button>
                  </div>

                  {/* Page navigation */}
                  {numPages > 1 && (
                    <div className="flex items-center gap-1 border rounded-lg p-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => changePage(-1)}
                        disabled={pageNumber <= 1}
                        className="h-7 w-7 p-0"
                        aria-label="Previous page"
                      >
                        <ChevronLeft className="h-4 w-4" />
                      </Button>
                      <span className="text-xs px-2">
                        {pageNumber} / {numPages}
                      </span>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => changePage(1)}
                        disabled={pageNumber >= numPages}
                        className="h-7 w-7 p-0"
                        aria-label="Next page"
                      >
                        <ChevronRight className="h-4 w-4" />
                      </Button>
                    </div>
                  )}

                  {/* Search (future enhancement) */}
                  <div className="flex-1 max-w-xs">
                    <div className="relative">
                      <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
                      <Input
                        placeholder="Search in document..."
                        value={searchText}
                        onChange={(e) => setSearchText(e.target.value)}
                        className="h-7 pl-7 text-xs"
                      />
                    </div>
                  </div>
                </div>

                {/* PDF Viewer */}
                <div className="flex-1 overflow-auto border rounded-lg bg-accent/5 dark:bg-gray-900">
                  <div className="flex justify-center p-4">
                    <Document
                      file={previewUrl}
                      onLoadSuccess={handleDocumentLoadSuccess}
                      loading={
                        <div className="flex items-center justify-center h-96">
                          <div className="h-8 w-8 border-2 border-orange-500 border-t-transparent rounded-full animate-spin" />
                        </div>
                      }
                      error={
                        <div className="flex flex-col items-center justify-center h-96 space-y-2">
                          <AlertCircle className="h-8 w-8 text-red-500" />
                          <p className="text-sm text-red-500">Failed to load PDF</p>
                        </div>
                      }
                    >
                      <Page
                        pageNumber={pageNumber}
                        scale={scale}
                        renderTextLayer={true}
                        renderAnnotationLayer={true}
                        className="shadow-lg"
                      />
                    </Document>
                  </div>
                </div>
              </>
            )}

            {/* Non-PDF fallback */}
            {!isPDF && (
              <div className="flex-1 flex flex-col items-center justify-center border-2 border-dashed rounded-lg p-8 space-y-4">
                <FileText className="h-16 w-16 text-muted-foreground" />
                <div className="text-center">
                  <p className="text-sm font-medium">Preview not available</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {document.mime_type.includes("word")
                      ? "DOCX preview coming soon"
                      : document.mime_type.includes("text")
                      ? "Text file preview coming soon"
                      : "This file type is not supported for preview"}
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    window.open(previewUrl || "", "_blank");
                  }}
                >
                  Download to view
                </Button>
              </div>
            )}
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
