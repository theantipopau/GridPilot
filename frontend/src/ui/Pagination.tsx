import { cx } from "./cx";
import { Button } from "./Button";

interface PaginationProps {
  page: number; // 1-based
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange?: (size: number) => void;
  pageSizeOptions?: number[];
  /** What is being paginated, for the live-region wording. */
  noun?: string;
  className?: string;
}

/** Explicit paging for long review queues. Deliberately plain: the queues are
 *  filtered first and paged second, and both controls must stay visible while
 *  rows scroll. */
export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [25, 50, 100],
  noun = "items",
  className,
}: PaginationProps) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const current = Math.min(page, pageCount);
  const from = total === 0 ? 0 : (current - 1) * pageSize + 1;
  const to = Math.min(total, current * pageSize);

  return (
    <div className={cx("flex flex-wrap items-center justify-between gap-3", className)}>
      <p className="nums text-meta" aria-live="polite">
        {from}&ndash;{to} of {total} {noun}
      </p>
      <div className="flex items-center gap-2">
        {onPageSizeChange && (
          <label className="flex items-center gap-1.5 text-meta">
            <span className="whitespace-nowrap">Per page</span>
            <select
              value={pageSize}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
              className="h-7 rounded-md border border-border-strong bg-surface px-1.5 text-xs text-text-primary focus:border-focus focus:outline-none focus:shadow-[0_0_0_3px_color-mix(in_oklab,var(--color-focus)_22%,transparent)]"
            >
              {pageSizeOptions.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
        )}
        <div className="flex items-center gap-1">
          <Button size="sm" disabled={current <= 1} onClick={() => onPageChange(current - 1)}>
            Previous
          </Button>
          <span className="nums px-1 text-meta">
            {current} / {pageCount}
          </span>
          <Button size="sm" disabled={current >= pageCount} onClick={() => onPageChange(current + 1)}>
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
