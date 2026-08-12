import { FACULTY_LEGEND } from "../lib/facultyColors";

/** Always present alongside the color-coded grids - the dataviz skill's
 * rule that identity is never color-alone for >= 2 series applies here
 * too, even though each cell also carries a visible text label. */
export default function FacultyLegend() {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 border-b border-slate-200 bg-white px-6 py-2.5 text-xs text-slate-600">
      <span className="font-medium uppercase tracking-wide text-slate-400">Faculty</span>
      {FACULTY_LEGEND.map((f) => (
        <span key={f.code} className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ backgroundColor: f.color }} />
          {f.label}
        </span>
      ))}
    </div>
  );
}
