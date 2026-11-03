interface PaginationProps {
  page: number;
  pageSize: number;
  count: number;
  onPageChange: (page: number) => void;
}

/** Prev/Next pagination — fixed 25 rows/page (Team 9 STARTER_KIT acceptance criteria). */
export function Pagination({ page, pageSize, count, onPageChange }: PaginationProps) {
  const start = count === 0 ? 0 : page * pageSize + 1;
  const end = Math.min((page + 1) * pageSize, count);
  const hasNext = end < count;
  const hasPrev = page > 0;

  return (
    <div className="flex items-center justify-between px-1 text-sm text-text-3">
      <span>
        {count === 0 ? "0 results" : `${start}–${end} of ${count}`}
      </span>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => onPageChange(page - 1)}
          disabled={!hasPrev}
          className="rounded-md border border-border px-3 py-1.5 text-xs font-medium text-text-2 hover:bg-accent/5 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Previous
        </button>
        <button
          type="button"
          onClick={() => onPageChange(page + 1)}
          disabled={!hasNext}
          className="rounded-md border border-border px-3 py-1.5 text-xs font-medium text-text-2 hover:bg-accent/5 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Next
        </button>
      </div>
    </div>
  );
}
