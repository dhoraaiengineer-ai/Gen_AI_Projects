/**
 * Pagination Component — Phase 4
 * Server-side pagination controls for Documents table
 *
 * Features:
 * - Previous/Next navigation
 * - Page number buttons (with ellipsis for large page counts)
 * - Jump to first/last page
 * - Items per page display
 */

import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * Pagination component props
 * @interface PaginationProps
 */
export interface PaginationProps {
  /** Current active page (1-indexed) */
  currentPage: number;
  /** Total number of pages available */
  totalPages: number;
  /** Total number of items across all pages */
  totalItems: number;
  /** Number of items displayed per page */
  pageSize: number;
  /** Callback fired when page changes */
  onPageChange: (page: number) => void;
}

/**
 * Pagination component for Documents table
 *
 * Provides navigation controls for paginated data with:
 * - First/last page buttons
 * - Previous/next navigation
 * - Direct page number selection
 * - Ellipsis for large page counts
 * - Accessible button labels
 *
 * @param props - PaginationProps
 * @returns Pagination controls JSX
 */
export default function Pagination({
  currentPage,
  totalPages,
  totalItems,
  pageSize,
  onPageChange,
}: PaginationProps) {
  const startItem = (currentPage - 1) * pageSize + 1;
  const endItem = Math.min(currentPage * pageSize, totalItems);

  /**
   * Generate page numbers with ellipsis for large page counts
   * Shows max 7 page buttons with smart ellipsis placement
   * @returns Array of page numbers and ellipsis markers
   */
  const getPageNumbers = () => {
    const pages: (number | string)[] = [];
    const maxVisible = 7; // Show max 7 page buttons

    if (totalPages <= maxVisible) {
      // Show all pages if total is small
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      // Always show first page
      pages.push(1);

      if (currentPage > 3) {
        pages.push("...");
      }

      // Show pages around current
      const start = Math.max(2, currentPage - 1);
      const end = Math.min(totalPages - 1, currentPage + 1);

      for (let i = start; i <= end; i++) {
        pages.push(i);
      }

      if (currentPage < totalPages - 2) {
        pages.push("...");
      }

      // Always show last page
      pages.push(totalPages);
    }

    return pages;
  };

  return (
    <div className="flex items-center justify-between px-6 py-4 border-t border-slate-200">
      {/* Results info */}
      <div className="text-sm text-text-3">
        Showing <span className="font-medium text-slate-900">{startItem}</span> to{" "}
        <span className="font-medium text-slate-900">{endItem}</span> of{" "}
        <span className="font-medium text-slate-900">{totalItems}</span> results
      </div>

      {/* Page controls */}
      <div className="flex items-center gap-2">
        {/* First page */}
        <Button
          variant="outline"
          size="icon"
          onClick={() => onPageChange(1)}
          disabled={currentPage === 1}
          aria-label="Go to first page"
        >
          <ChevronsLeft className="h-4 w-4" />
        </Button>

        {/* Previous page */}
        <Button
          variant="outline"
          size="icon"
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage === 1}
          aria-label="Go to previous page"
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>

        {/* Page numbers */}
        <div className="flex items-center gap-1">
          {getPageNumbers().map((page, idx) =>
            page === "..." ? (
              <span key={`ellipsis-${idx}`} className="px-2 text-text-3">
                ...
              </span>
            ) : (
              <Button
                key={page}
                variant={currentPage === page ? "default" : "outline"}
                size="sm"
                onClick={() => onPageChange(page as number)}
                className="min-w-[36px]"
              >
                {page}
              </Button>
            )
          )}
        </div>

        {/* Next page */}
        <Button
          variant="outline"
          size="icon"
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage === totalPages}
          aria-label="Go to next page"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>

        {/* Last page */}
        <Button
          variant="outline"
          size="icon"
          onClick={() => onPageChange(totalPages)}
          disabled={currentPage === totalPages}
          aria-label="Go to last page"
        >
          <ChevronsRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
