import type { ReactNode } from "react";
import { cx } from "./cx";

export interface FilterChip {
  id: string;
  label: string;
  /** Removes this one filter - chips are always individually dismissible. */
  onRemove?: () => void;
}

interface FilterBarProps {
  /** SearchInput instance. */
  search?: ReactNode;
  /** Summary chips describing every active constraint. */
  chips?: FilterChip[];
  onClearAll?: () => void;
  /** Extra controls (selects, segmented tabs, buttons) on the right. */
  children?: ReactNode;
  /** "12 of 402" style count, announced politely when it changes. */
  count?: ReactNode;
  className?: string;
  /** Sticky under the page header on long queues. */
  sticky?: boolean;
}

/** One row that holds every way of narrowing a list: search, chips, controls,
 *  result count. Keeps queues comparable across pages - the same furniture in
 *  Findings, Composite Review, Room Constraints and Teacher Capabilities. */
export function FilterBar({ search, chips = [], onClearAll, children, count, className, sticky }: FilterBarProps) {
  const hasChips = chips.length > 0;
  return (
    <div
      className={cx(
        "flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border border-border bg-surface px-3 py-2.5",
        sticky && "sticky top-0 z-20 shadow-[0_1px_0_var(--color-border)]",
        className,
      )}
    >
      {search}
      {hasChips && (
        <div className="flex flex-wrap items-center gap-1.5">
          {chips.map((chip) => (
            <span
              key={chip.id}
              className="inline-flex items-center gap-1 rounded-full border border-brand-border bg-brand-surface px-2 py-0.5 text-[11px] font-medium text-brand"
            >
              {chip.label}
              {chip.onRemove && (
                <button
                  type="button"
                  aria-label={`Remove filter ${chip.label}`}
                  onClick={chip.onRemove}
                  className="-mr-0.5 rounded-full px-0.5 transition-opacity duration-150 hover:opacity-70"
                >
                  <svg viewBox="0 0 16 16" className="h-3 w-3" fill="none" aria-hidden="true">
                    <path d="m4 4 8 8M12 4l-8 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  </svg>
                </button>
              )}
            </span>
          ))}
          {onClearAll && (
            <button
              type="button"
              onClick={onClearAll}
              className="rounded-full px-2 py-0.5 text-[11px] font-medium text-text-muted underline-offset-2 transition-colors duration-150 hover:text-brand hover:underline"
            >
              Clear all
            </button>
          )}
        </div>
      )}
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
      {count != null && (
        <span aria-live="polite" className="nums ml-auto whitespace-nowrap text-meta">
          {count}
        </span>
      )}
    </div>
  );
}
