import type { KeyboardEvent } from "react";
import { facultyColor } from "../lib/facultyColors";
import { highlightForEntry, type CellHighlight } from "../lib/findingHighlights";
import type { Density } from "../lib/density";
import { useGridKeyboardNav } from "../lib/gridKeyboardNav";
import type { GhostEntry } from "../lib/pendingMoves";
import { cellState } from "../lib/cellStates";
import { CellStateMarker } from "./CellStateMarker";
import { cx } from "../ui/cx";
import type { Day, Period, ReferenceData, TimetableEntry, ViewType } from "../types";

interface RowSpec {
  code: string;
  label: string;
}

interface Props {
  axis: ViewType;
  reference: ReferenceData;
  entries: TimetableEntry[];
  density?: Density;
  pendingEntryIds?: Set<number>;
  findingHighlights?: Map<string, CellHighlight>;
  onSelectLesson?: (entry: TimetableEntry) => void;
  /** Entries with a proposed move, shown in their ORIGINAL slot as a ghost. */
  ghostEntries?: GhostEntry[];
  /** entry_id -> how many originating findings the pending move resolves. */
  resolvingCounts?: Map<number, number>;
  selectedEntryId?: number | null;
  /** Filter to rows that actually have an open finding - the 51 x 50 grid is
   *  dense; this is how a timetabler finds the rows that need work. */
  onlyRowsWithFindings?: boolean;
}

const AXIS_FIELD: Record<ViewType, (e: TimetableEntry) => string | null> = {
  teacher: (e) => e.teacher_code,
  room: (e) => e.room_code,
  roll_class: (e) => e.roll_class_code,
};

function rowsForAxis(reference: ReferenceData, axis: ViewType): RowSpec[] {
  if (axis === "teacher") {
    return reference.teachers.map((t) => ({
      code: t.code,
      label: t.last_name ? `${t.last_name}, ${t.first_name ?? ""}`.trim() : t.code,
    }));
  }
  if (axis === "room") {
    return reference.rooms.map((r) => ({ code: r.code, label: r.name || r.code }));
  }
  return reference.roll_classes.map((rc) => ({ code: rc.code, label: rc.code }));
}

function dedupePeriodsByNumber(periods: Period[]): Period[] {
  const byNumber = new Map<number, Period>();
  for (const p of periods) {
    if (!byNumber.has(p.period_no)) byNumber.set(p.period_no, p);
  }
  return [...byNumber.values()].sort((a, b) => a.period_no - b.period_no);
}

export default function MasterTimetableGrid({
  axis,
  reference,
  entries,
  density = "comfortable",
  pendingEntryIds,
  findingHighlights,
  onSelectLesson,
  ghostEntries,
  resolvingCounts,
  selectedEntryId,
  onlyRowsWithFindings,
}: Props) {
  const allRows = rowsForAxis(reference, axis);
  const canonicalPeriods = dedupePeriodsByNumber(reference.periods);
  const weekA = reference.days.filter((d) => d.week_label === "A").sort((a, b) => a.day_no - b.day_no);
  const weekB = reference.days.filter((d) => d.week_label === "B").sort((a, b) => a.day_no - b.day_no);
  const axisField = AXIS_FIELD[axis];

  const entriesByRowKey = new Map<string, TimetableEntry[]>();
  for (const e of entries) {
    const rowCode = axisField(e);
    if (!rowCode) continue;
    const key = `${rowCode}|${e.day_code}|${e.period_no}`;
    const list = entriesByRowKey.get(key) ?? [];
    list.push(e);
    entriesByRowKey.set(key, list);
  }

  const ghostsByRowKey = new Map<string, GhostEntry[]>();
  for (const g of ghostEntries ?? []) {
    const rowCode = axisField(g.entry);
    if (!rowCode) continue;
    const key = `${rowCode}|${g.entry.day_code}|${g.entry.period_no}`;
    const list = ghostsByRowKey.get(key) ?? [];
    list.push(g);
    ghostsByRowKey.set(key, list);
  }

  // "Rows with findings" is computed from the same highlight index the cells
  // use - a row qualifies when any of its cells would show a conflict marker,
  // so the filter can never disagree with what's on screen.
  const rows = onlyRowsWithFindings
    ? allRows.filter((row) => {
        for (const [key, list] of entriesByRowKey) {
          if (!key.startsWith(`${row.code}|`)) continue;
          for (const e of list) {
            if (findingHighlights && highlightForEntry(findingHighlights, e)) return true;
          }
        }
        return false;
      })
    : allRows;

  return (
    <div className="h-full overflow-auto p-6 print:h-auto print:overflow-visible print:p-0">
      {rows.length === 0 ? (
        <div className="mx-auto max-w-lg pt-10">
          <div className="rounded-lg border border-dashed border-border bg-surface px-6 py-10 text-center">
            <p className="text-sm font-medium text-text-primary">No rows match this filter</p>
            <p className="mt-1 text-meta">
              {onlyRowsWithFindings
                ? "No row on this axis currently carries an open finding. Clear the filter to see the whole timetable."
                : "Nothing to show for this axis."}
            </p>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-8">
          <MasterWeekTable
            label="Week A"
            weekDays={weekA}
            periods={canonicalPeriods}
            rows={rows}
            axis={axis}
            density={density}
            entriesByRowKey={entriesByRowKey}
            ghostsByRowKey={ghostsByRowKey}
            pendingEntryIds={pendingEntryIds}
            findingHighlights={findingHighlights}
            onSelectLesson={onSelectLesson}
            selectedEntryId={selectedEntryId}
            resolvingCounts={resolvingCounts}
          />
          <MasterWeekTable
            label="Week B"
            weekDays={weekB}
            periods={canonicalPeriods}
            rows={rows}
            axis={axis}
            density={density}
            entriesByRowKey={entriesByRowKey}
            ghostsByRowKey={ghostsByRowKey}
            pendingEntryIds={pendingEntryIds}
            findingHighlights={findingHighlights}
            onSelectLesson={onSelectLesson}
            selectedEntryId={selectedEntryId}
            resolvingCounts={resolvingCounts}
          />
        </div>
      )}
    </div>
  );
}

function MasterWeekTable({
  label,
  weekDays,
  periods,
  rows,
  axis,
  density,
  entriesByRowKey,
  ghostsByRowKey,
  pendingEntryIds,
  findingHighlights,
  onSelectLesson,
  selectedEntryId,
  resolvingCounts,
}: {
  label: string;
  weekDays: Day[];
  periods: Period[];
  rows: RowSpec[];
  axis: ViewType;
  density: Density;
  entriesByRowKey: Map<string, TimetableEntry[]>;
  ghostsByRowKey: Map<string, GhostEntry[]>;
  pendingEntryIds?: Set<number>;
  findingHighlights?: Map<string, CellHighlight>;
  onSelectLesson?: (entry: TimetableEntry) => void;
  selectedEntryId?: number | null;
  resolvingCounts?: Map<number, number>;
}) {
  const compact = density === "compact";
  const totalCols = weekDays.length * periods.length;
  // Called unconditionally, before the weekDays.length===0 early return -
  // React Hooks must run in the same order on every render.
  const { focus, registerCell, move, focusDefault, setFocus } = useGridKeyboardNav(rows.length, totalCols);

  if (weekDays.length === 0) return null;

  const colToDayPeriod = (c: number) => ({
    day: weekDays[Math.floor(c / periods.length)],
    period: periods[c % periods.length],
  });

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const current = focus ?? { r: 0, c: 0 };
      const row = rows[current.r];
      const { day, period } = colToDayPeriod(current.c);
      const key = `${row.code}|${day.code}|${period.period_no}`;
      const lesson = (entriesByRowKey.get(key) ?? []).find((en) => en.entry_type === "LESSON");
      if (lesson && onSelectLesson) onSelectLesson(lesson);
      return;
    }
    if (move(e.key)) e.preventDefault();
  };

  return (
    <div>
      <h2 className="mb-2 text-section-title">{label}</h2>
      <div
        className="overflow-hidden rounded-lg border border-border bg-surface shadow-sm"
        tabIndex={0}
        role="grid"
        aria-label={`${label} timetable grid - arrow keys to move, Enter to open a lesson`}
        onFocus={focusDefault}
        onKeyDown={handleKeyDown}
      >
        <table className="w-full border-collapse text-xs">
          <thead className="sticky top-0 z-10">
            <tr>
              <th
                className={cx(
                  "sticky left-0 z-20 w-44 border-b-2 border-r border-border-strong bg-surface-sunken text-left text-label",
                  compact ? "p-1" : "p-2",
                )}
              >
                {axis === "teacher" ? "Teacher" : axis === "room" ? "Room" : "Roll class"}
              </th>
              {weekDays.map((d) => (
                <th
                  key={d.code}
                  colSpan={periods.length}
                  className={cx(
                    "border-b-2 border-l border-border-strong bg-surface-sunken text-center text-label",
                    compact ? "p-1" : "p-1.5",
                  )}
                >
                  {d.code.replace(/ [AB]$/, "")}
                </th>
              ))}
            </tr>
            <tr>
              <th className="sticky left-0 z-20 border-b border-r border-border-strong bg-surface p-1" />
              {weekDays.map((d) =>
                periods.map((p, pIdx) => (
                  <th
                    key={`${d.code}-${p.period_no}`}
                    // Group separators (day boundaries) are border weight, not
                    // hue: readable without colour perception.
                    className={cx(
                      "nums border-b bg-surface p-1 text-center font-normal text-text-muted",
                      pIdx === 0 ? "border-l-2 border-l-border-strong" : "border-l border-l-border",
                    )}
                    title={p.name}
                  >
                    {p.name.length > 4 ? p.period_no : p.name}
                  </th>
                )),
              )}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIdx) => (
              <tr key={row.code} className="group even:bg-surface-sunken/40">
                {/* The frozen label column needs its own opaque surface (it
                    scrolls over content) but a plain surface erases the row
                    striping right where the eye needs it most - at the label.
                    Inherit the stripe instead, and use a real shadow rather
                    than a 1px border so the frozen edge reads as a layer. */}
                <td
                  className={cx(
                    "sticky-col-edge sticky left-0 z-10 max-w-[11rem] truncate border-b border-border bg-surface font-medium text-text-secondary group-even:bg-surface-sunken/40",
                    compact ? "p-1" : "p-2",
                  )}
                  title={row.label}
                >
                  {row.label}
                </td>
                {weekDays.map((d, dIdx) =>
                  periods.map((p, pIdx) => {
                    const key = `${row.code}|${d.code}|${p.period_no}`;
                    const cellEntries = entriesByRowKey.get(key) ?? [];
                    const cellGhosts = ghostsByRowKey.get(key) ?? [];
                    const colIdx = dIdx * periods.length + pIdx;
                    return (
                      <MasterCell
                        key={`${d.code}-${p.period_no}`}
                        axis={axis}
                        entries={cellEntries}
                        ghosts={cellGhosts}
                        firstOfDay={pIdx === 0}
                        compact={compact}
                        focused={focus?.r === rowIdx && focus?.c === colIdx}
                        registerCell={(el) => registerCell(rowIdx, colIdx, el)}
                        onCellFocus={() => setFocus({ r: rowIdx, c: colIdx })}
                        pendingEntryIds={pendingEntryIds}
                        findingHighlights={findingHighlights}
                        onSelectLesson={onSelectLesson}
                        selectedEntryId={selectedEntryId}
                        resolvingCounts={resolvingCounts}
                      />
                    );
                  }),
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// A shared physical space (a hall, an "Assisi Centre"-style multi-purpose
// room) can host a dozen+ parallel classes in one slot. Rendering all of
// them stacked would balloon that one cell's height - and every other cell
// in the same table row - so what renders inline is capped and the rest is
// summarised. Row heights stay predictable however packed a cell is.
const MAX_VISIBLE_PER_CELL = 4;

function MasterCell({
  axis,
  entries,
  ghosts,
  firstOfDay,
  compact,
  focused,
  registerCell,
  onCellFocus,
  pendingEntryIds,
  findingHighlights,
  onSelectLesson,
  selectedEntryId,
  resolvingCounts,
}: {
  axis: ViewType;
  entries: TimetableEntry[];
  ghosts: GhostEntry[];
  firstOfDay: boolean;
  compact: boolean;
  focused: boolean;
  registerCell: (el: HTMLTableCellElement | null) => void;
  /** Focus arrived inside this cell - record the keyboard position so arrow
   *  keys continue from where the user clicked. */
  onCellFocus: () => void;
  pendingEntryIds?: Set<number>;
  findingHighlights?: Map<string, CellHighlight>;
  onSelectLesson?: (entry: TimetableEntry) => void;
  selectedEntryId?: number | null;
  resolvingCounts?: Map<number, number>;
}) {
  const borderClass = firstOfDay ? "border-l-2 border-l-border-strong" : "border-l border-l-border";
  // Keyboard focus ring - distinct from the conflict/proposed markers applied
  // to individual lesson buttons inside the cell, since this marks the whole
  // cell as the current keyboard position, not a lesson's state. tabIndex=-1
  // keeps every cell out of normal Tab order - only reachable via the grid
  // wrapper's arrow-key handler (lib/gridKeyboardNav.ts).
  const focusRingClass = focused ? "ring-2 ring-inset ring-focus" : "";

  // An empty cell is left genuinely empty. A "·" repeated across ~2,000
  // free slots is noise competing with the lessons that actually matter.
  if (entries.length === 0 && ghosts.length === 0) {
    return <td ref={registerCell} tabIndex={-1} onFocus={onCellFocus} className={cx("border-b p-1", borderClass, focusRingClass)} />;
  }

  const visible = entries.slice(0, MAX_VISIBLE_PER_CELL);
  const overflow = entries.slice(MAX_VISIBLE_PER_CELL);

  return (
    <td
      ref={registerCell}
      tabIndex={-1}
      onFocus={onCellFocus}
      className={cx("border-b align-top", borderClass, compact ? "p-px" : "p-[3px]", focusRingClass)}
    >
      <div className={cx("flex flex-col", compact ? "gap-px" : "gap-[3px]")}>
        {visible.map((e, i) => {
          const primary = cellPrimary(e);
          // Compact mode drops the secondary line entirely - the point of the
          // toggle is maximum rows-in-view, and the full detail is still one
          // click away via the tooltip/inspector.
          const secondary = compact ? null : cellSecondary(axis, e);
          const editable = e.entry_type === "LESSON" && !!onSelectLesson;
          const pending = pendingEntryIds?.has(e.entry_id);
          const highlight = findingHighlights ? highlightForEntry(findingHighlights, e) : null;
          const state = cellState({
            highlight,
            pending: !!pending,
            resolvingCount: resolvingCounts?.get(e.entry_id) ?? 0,
          });
          const color = e.entry_type === "LESSON" ? facultyColor(e.faculty_code) : null;
          const selected = selectedEntryId === e.entry_id;
          const paddingClass = compact ? "py-px pl-1 pr-0.5" : "py-1 pl-1.5 pr-1";
          const className = cx(
            "relative w-full truncate rounded-sm text-left leading-tight transition-[box-shadow,outline-color] duration-150",
            paddingClass,
            e.entry_type === "LESSON" ? "text-text-primary" : "bg-surface-sunken text-text-muted",
            editable ? "cursor-pointer hover:brightness-95" : "",
            selected ? "ring-2 ring-inset ring-focus" : state.className,
          );
          const style = color
            ? { backgroundColor: `${color}1f`, borderLeft: `3px solid ${color}` }
            : undefined;
          const content = (
            <>
              <CellStateMarker state={state} />
              <div className="truncate font-medium">{primary}</div>
              {secondary && <div className="truncate text-[11px] opacity-75">{secondary}</div>}
            </>
          );
          const title = cellTitle(e) + (pending ? " - proposed move" : "") + state.titleSuffix;
          return editable ? (
            <button key={i} type="button" className={className} style={style} onClick={() => onSelectLesson!(e)} title={title}>
              {content}
            </button>
          ) : (
            <div key={i} className={className} style={style} title={title}>
              {content}
            </div>
          );
        })}
        {ghosts.map((g, i) => {
          const label = cellPrimary(g.entry);
          const target = `${g.after.day_code ?? g.entry.day_code} ${g.after.period_code ?? g.entry.period_code}`;
          const title = `${label} is proposed to move to ${target}. The imported timetable still has it here - the move applies only when the change set is approved.`;
          const body = (
            <div className={cx("relative truncate", compact ? "py-px pl-1 pr-0.5" : "py-1 pl-1.5 pr-1")}>
              <div className="truncate font-medium text-text-muted">{label}</div>
              <div className="nums truncate text-[10px] text-timetable-proposed">&rarr; {target} proposed</div>
            </div>
          );
          const ghostClass =
            "relative w-full cursor-pointer rounded-sm border border-dashed border-timetable-proposed bg-timetable-proposed-surface text-left leading-tight text-text-muted hover:shadow-sm";
          return onSelectLesson ? (
            <button key={`ghost-${i}`} type="button" className={ghostClass} title={title} onClick={() => onSelectLesson(g.entry)}>
              {body}
            </button>
          ) : (
            <div key={`ghost-${i}`} className={ghostClass} title={title}>
              {body}
            </div>
          );
        })}
        {overflow.length > 0 && (
          <div
            className="truncate rounded-sm bg-surface-sunken py-0.5 pl-1.5 pr-1 text-left text-[10px] font-semibold text-text-muted"
            title={`Also here: ${overflow.map((e) => cellPrimary(e)).join(", ")}`}
          >
            +{overflow.length} more
          </div>
        )}
      </div>
    </td>
  );
}

function cellPrimary(e: TimetableEntry): string {
  if (e.entry_type !== "LESSON") return e.entry_type.slice(0, 3);
  return e.class_code ?? "—";
}

function cellSecondary(axis: ViewType, e: TimetableEntry): string | null {
  if (e.entry_type !== "LESSON") return null;
  if (axis === "room") return e.teacher_code ?? null;
  if (axis === "teacher") return e.room_code ?? null;
  return [e.teacher_code, e.room_code].filter(Boolean).join(" · ") || null;
}

function cellTitle(e: TimetableEntry): string {
  if (e.entry_type !== "LESSON") return e.entry_type;
  const teacherName = e.teacher_last_name ? `${e.teacher_last_name}, ${e.teacher_first_name ?? ""}`.trim() : null;
  return [e.class_code, e.roll_class_code, e.room_code, teacherName].filter(Boolean).join(" · ");
}
