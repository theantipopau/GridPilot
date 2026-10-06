import { FACULTY_LEGEND } from "../lib/facultyColors";
import { cx } from "../ui/cx";

/** Always present alongside the color-coded grids - identity is never
 *  colour-alone (every cell also carries its class code as visible text),
 *  and neither is STATE: the right-hand keys pair each state with the glyph
 *  and border pattern the cell actually uses, so the grid stays readable
 *  with any form of colour-vision deficiency. */
export default function FacultyLegend({ className }: { className?: string }) {
  return (
    <div
      className={cx(
        "flex flex-wrap items-center gap-x-5 gap-y-1.5 border-b border-border bg-surface px-6 py-2 text-xs text-text-secondary",
        className,
      )}
    >
      <span className="text-label">Faculty</span>
      {FACULTY_LEGEND.map((f) => (
        <span key={f.code} className="flex items-center gap-1.5">
          <span aria-hidden="true" className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ backgroundColor: f.color }} />
          {f.label}
        </span>
      ))}

      <span aria-hidden="true" className="mx-1 hidden h-4 w-px bg-border sm:block" />
      <span className="text-label">Cell state</span>
      <span className="flex items-center gap-1.5">
        <span aria-hidden="true" className="h-3 w-4 shrink-0 rounded-sm border border-border bg-surface" />
        Live - imported source
      </span>
      <span className="flex items-center gap-1.5">
        <span
          aria-hidden="true"
          className="h-3 w-4 shrink-0 rounded-sm border-2 border-dashed border-timetable-proposed bg-timetable-proposed-surface"
        />
        <span className="text-timetable-proposed">&rarr;</span> Proposed (draft)
      </span>
      <span className="flex items-center gap-1.5">
        <span
          aria-hidden="true"
          className="flex h-3 w-4 shrink-0 items-center justify-center rounded-sm border border-timetable-conflict bg-timetable-conflict-surface text-[9px] text-timetable-conflict"
        >
          ▲
        </span>
        Open finding
      </span>
      <span className="flex items-center gap-1.5">
        <span
          aria-hidden="true"
          className="flex h-3 w-4 shrink-0 items-center justify-center rounded-sm border border-timetable-resolved bg-timetable-resolved-surface text-[9px] text-timetable-resolved"
        >
          ✓
        </span>
        Resolved by draft
      </span>
      <span className="flex items-center gap-1.5 text-text-muted">
        A dashed cell never means applied - approval is what changes the source.
      </span>
    </div>
  );
}
