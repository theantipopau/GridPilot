import type { ReactNode } from "react";
import { cx } from "./cx";

export type SortDirection = "asc" | "desc";
export interface SortState {
  key: string;
  direction: SortDirection;
}

export interface DataTableColumn<T> {
  key: string;
  header: ReactNode;
  render: (row: T) => ReactNode;
  align?: "left" | "right" | "center";
  /** CSS width, e.g. "12rem" - keeps numeric columns from breathing. */
  width?: string;
  sortable?: boolean;
  /** Applies tabular numerals so figures align down the column. */
  numeric?: boolean;
  /** Drops the column below this viewport width (narrow-window behaviour). */
  hideBelow?: "sm" | "md" | "lg";
}

interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  /** Accessible name for the table - required when the page heading doesn't
   *  already describe it. */
  caption: string;
  sort?: SortState | null;
  onSortChange?: (sort: SortState) => void;
  onRowClick?: (row: T) => void;
  selectedKey?: string | null;
  density?: "compact" | "comfortable";
  stickyHeader?: boolean;
  emptyState?: ReactNode;
  /** Rendered under the table (totals, pagination). */
  footer?: ReactNode;
  className?: string;
  /** Previous page name for the frozen-header wrapper's scroll container. */
  maxHeight?: string;
}

const HIDE_CLASS: Record<NonNullable<DataTableColumn<unknown>["hideBelow"]>, string> = {
  sm: "hidden sm:table-cell",
  md: "hidden md:table-cell",
  lg: "hidden lg:table-cell",
};

/** The one table pattern for entity/list data: consistent header treatment,
 *  optional sorting with aria-sort, sticky header, zebra-free quiet rows,
 *  row selection and a keyboard-operable row click. Timetable grids are
 *  deliberately NOT this component - they are a different data shape. */
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  caption,
  sort,
  onSortChange,
  onRowClick,
  selectedKey,
  density = "comfortable",
  stickyHeader = true,
  emptyState,
  footer,
  className,
  maxHeight,
}: DataTableProps<T>) {
  const cellPad = density === "compact" ? "px-2.5 py-1.5" : "px-3 py-2";

  const toggleSort = (key: string) => {
    if (!onSortChange) return;
    const direction: SortDirection = sort?.key === key && sort.direction === "asc" ? "desc" : "asc";
    onSortChange({ key, direction });
  };

  if (rows.length === 0 && emptyState) {
    return (
      <div className={cx("rounded-lg border border-border bg-surface", className)}>
        <div className="p-3">{emptyState}</div>
        {footer}
      </div>
    );
  }

  return (
    <div className={cx("overflow-hidden rounded-lg border border-border bg-surface", className)}>
      <div className={cx("overflow-auto", maxHeight ?? "max-h-[70vh]")} data-scroll-region>
        <table className="w-full border-collapse text-table">
          <caption className="sr-only">{caption}</caption>
          <thead className={stickyHeader ? "sticky top-0 z-10" : undefined}>
            <tr className="bg-surface-sunken">
              {columns.map((c) => {
                const active = sort?.key === c.key;
                const ariaSort = c.sortable
                  ? active
                    ? sort!.direction === "asc"
                      ? "ascending"
                      : "descending"
                    : "none"
                  : undefined;
                return (
                  <th
                    key={c.key}
                    scope="col"
                    aria-sort={ariaSort as "ascending" | "descending" | "none" | undefined}
                    style={{ width: c.width }}
                    className={cx(
                      "border-b border-border-strong whitespace-nowrap px-3 py-2 text-left text-label",
                      c.align === "right" && "text-right",
                      c.align === "center" && "text-center",
                      c.hideBelow && HIDE_CLASS[c.hideBelow],
                    )}
                  >
                    {c.sortable && onSortChange ? (
                      <button
                        type="button"
                        onClick={() => toggleSort(c.key)}
                        className={cx(
                          "inline-flex items-center gap-1 rounded text-label transition-colors duration-150 hover:text-text-primary",
                          active && "text-brand",
                          c.align === "right" && "flex-row-reverse",
                        )}
                      >
                        {c.header}
                        <svg
                          viewBox="0 0 16 16"
                          aria-hidden="true"
                          className={cx("h-3 w-3", active ? "opacity-100" : "opacity-35")}
                          fill="none"
                        >
                          <path
                            d="M8 3.5 11 7H5l3-3.5Z"
                            fill="currentColor"
                            opacity={active && sort!.direction === "asc" ? 1 : 0.35}
                          />
                          <path
                            d="M8 12.5 5 9h6l-3 3.5Z"
                            fill="currentColor"
                            opacity={active && sort!.direction === "desc" ? 1 : 0.35}
                          />
                        </svg>
                      </button>
                    ) : (
                      c.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const key = rowKey(row);
              const selected = selectedKey === key;
              return (
                <tr
                  key={key}
                  aria-selected={onRowClick ? selected : undefined}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  className={cx(
                    "border-b border-border last:border-0 transition-colors duration-100",
                    selected ? "bg-selected" : "hover:bg-hovered",
                    onRowClick &&
                      "cursor-pointer focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus",
                  )}
                  tabIndex={onRowClick ? 0 : undefined}
                  onKeyDown={
                    onRowClick
                      ? (e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            onRowClick(row);
                          }
                        }
                      : undefined
                  }
                >
                  {columns.map((c) => (
                    <td
                      key={c.key}
                      className={cx(
                        "align-middle text-text-secondary",
                        cellPad,
                        c.align === "right" && "text-right",
                        c.align === "center" && "text-center",
                        c.numeric && "nums",
                        c.hideBelow && HIDE_CLASS[c.hideBelow],
                      )}
                    >
                      {c.render(row)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {footer && <div className="border-t border-border px-3 py-2">{footer}</div>}
    </div>
  );
}
