"use client";

/**
 * Search & Filters — Chapter 31.13 (Phase 4 Enhanced)
 * Search by name/tags/category; filter by type/status/date/size
 * Phase 4: Added debounced search (500ms delay)
 */

import { useState, useEffect, useRef } from "react";
import { Search, Filter, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { DocumentFilters, DocumentStatus, FileType } from "@/types";

/**
 * Search and filter controls for Documents table
 * @interface SearchFiltersProps
 */
interface SearchFiltersProps {
  /** Current active filters */
  filters: DocumentFilters;
  /** Callback when any filter changes */
  onFiltersChange: (filters: DocumentFilters) => void;
  /** Total number of documents matching current filters */
  totalResults: number;
}

/** Debounce delay for search input (milliseconds) */
const SEARCH_DEBOUNCE_MS = 500;

export default function SearchFilters({
  filters,
  onFiltersChange,
  totalResults,
}: SearchFiltersProps) {
  // Phase 4: Local search state for immediate UI feedback
  const [localSearch, setLocalSearch] = useState(filters.search || "");
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Phase 4: Debounced search handler
  const handleSearchChange = (search: string) => {
    setLocalSearch(search);

    // Clear previous timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    // Set new timer to update filters after delay
    debounceTimerRef.current = setTimeout(() => {
      onFiltersChange({ ...filters, search: search || undefined });
    }, SEARCH_DEBOUNCE_MS);
  };

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  const handleStatusChange = (status: string) => {
    onFiltersChange({
      ...filters,
      status: (status as DocumentStatus) || undefined,
    });
  };

  const handleTypeChange = (type: string) => {
    onFiltersChange({ ...filters, mime_type: (type as FileType) || undefined });
  };

  /**
   * Phase 4: Date range filter handlers
   * Converts date input to ISO string format expected by backend
   */
  const handleDateAfterChange = (date: string) => {
    onFiltersChange({
      ...filters,
      uploaded_after: date || undefined,
      page: 1, // Reset to first page on filter change
    });
  };

  const handleDateBeforeChange = (date: string) => {
    onFiltersChange({
      ...filters,
      uploaded_before: date || undefined,
      page: 1, // Reset to first page on filter change
    });
  };

  /**
   * Clear all filters and reset to initial state
   * Phase 4: Preserves pagination defaults (page=1, page_size, sort_by, sort_order)
   */
  const clearFilters = () => {
    setLocalSearch(""); // Clear local search input immediately
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }
    onFiltersChange({
      page: 1,
      page_size: filters.page_size,
      sort_by: filters.sort_by,
      sort_order: filters.sort_order,
    });
  };

  const hasActiveFilters =
    filters.search ||
    filters.status ||
    filters.mime_type ||
    filters.uploaded_after ||
    filters.uploaded_before;

  return (
    <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center">
      {/* Search Input (Phase 4: Debounced) */}
      <div className="relative flex-1 w-full">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search documents..."
          value={localSearch}
          onChange={(e) => handleSearchChange(e.target.value)}
          className="pl-9"
          data-testid="search-input"
          aria-label="Search documents"
        />
      </div>

      {/* Status Filter */}
      <Select
        value={filters.status || "all"}
        onValueChange={handleStatusChange}
      >
        <SelectTrigger className="w-full sm:w-40" data-testid="status-filter">
          <Filter className="h-4 w-4 mr-2" />
          <SelectValue placeholder="All Status" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Status</SelectItem>
          <SelectItem value="uploaded">Uploaded</SelectItem>
          <SelectItem value="processing">Processing</SelectItem>
          <SelectItem value="indexed">Indexed</SelectItem>
          <SelectItem value="failed">Failed</SelectItem>
          <SelectItem value="archived">Archived</SelectItem>
        </SelectContent>
      </Select>

      {/* File Type Filter */}
      <Select
        value={filters.mime_type || "all"}
        onValueChange={handleTypeChange}
      >
        <SelectTrigger className="w-full sm:w-40">
          <SelectValue placeholder="All Types" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Types</SelectItem>
          <SelectItem value="application/pdf">PDF</SelectItem>
          <SelectItem value="application/vnd.openxmlformats-officedocument.wordprocessingml.document">
            DOCX
          </SelectItem>
          <SelectItem value="text/plain">TXT</SelectItem>
          <SelectItem value="text/markdown">Markdown</SelectItem>
          <SelectItem value="text/html">HTML</SelectItem>
          <SelectItem value="text/csv">CSV</SelectItem>
        </SelectContent>
      </Select>

      {/* Phase 4: Date Range Filters */}
      <div className="flex gap-2 w-full sm:w-auto">
        <Input
          type="date"
          placeholder="From date"
          value={filters.uploaded_after || ""}
          onChange={(e) => handleDateAfterChange(e.target.value)}
          className="w-full sm:w-40"
          aria-label="Filter by uploaded after date"
        />
        <Input
          type="date"
          placeholder="To date"
          value={filters.uploaded_before || ""}
          onChange={(e) => handleDateBeforeChange(e.target.value)}
          className="w-full sm:w-40"
          aria-label="Filter by uploaded before date"
        />
      </div>

      {/* Clear Filters */}
      {hasActiveFilters && (
        <Button
          variant="ghost"
          size="sm"
          onClick={clearFilters}
          className="w-full sm:w-auto"
        >
          <X className="h-4 w-4 mr-2" />
          Clear
        </Button>
      )}

      {/* Results Count */}
      <div className="text-sm text-muted-foreground whitespace-nowrap">
        {totalResults} {totalResults === 1 ? "document" : "documents"}
      </div>
    </div>
  );
}
