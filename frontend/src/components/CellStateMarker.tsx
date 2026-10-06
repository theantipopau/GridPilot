import { cx } from "../ui/cx";
import type { CellState } from "../lib/cellStates";

/** The glyph half of the cell-state pair (lib/cellStates.ts). 12px, top-right
 *  of the cell, never overlapping the class code at the cell's left edge. */
export function CellStateMarker({ state }: { state: CellState }) {
  if (!state.kind) return null;

  const tone =
    state.kind === "conflict"
      ? state.severity === "critical"
        ? "text-timetable-conflict"
        : state.severity === "warning"
          ? "text-warning"
          : "text-information"
      : state.kind === "proposed-resolves"
        ? "text-timetable-resolved"
        : "text-timetable-proposed";

  return (
    <span aria-hidden="true" className={cx("absolute right-0.5 top-0.5 flex h-3 w-3 items-center justify-center", tone)}>
      {state.kind === "conflict" ? (
        <svg viewBox="0 0 12 12" className="h-3 w-3" fill="none">
          <path
            d="M6 1.5 11 10.5H1L6 1.5Z"
            fill="currentColor"
            fillOpacity="0.18"
            stroke="currentColor"
            strokeWidth="1.25"
            strokeLinejoin="round"
          />
          <path d="M6 5v2.2" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
          <circle cx="6" cy="8.9" r="0.7" fill="currentColor" />
        </svg>
      ) : state.kind === "proposed-resolves" ? (
        <svg viewBox="0 0 12 12" className="h-3 w-3" fill="none">
          <path d="m2 6.4 2.6 2.6L10 3.4" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ) : (
        <svg viewBox="0 0 12 12" className="h-3 w-3" fill="none">
          <path d="M2 6h7.2M6.6 3.2 9.6 6l-3 2.8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      )}
    </span>
  );
}
