import type { KeyboardEvent } from "react";
import { facultyColor } from "../lib/facultyColors";
import { highlightForEntry, type CellHighlight } from "../lib/findingHighlights";
import type { Density } from "../lib/density";
import { useGridKeyboardNav } from "../lib/gridKeyboardNav";
import type { GhostEntry } from "../lib/pendingMoves";
import { cellState } from "../lib/cellStates";
import { CellStateMarker } from "./CellStateMarker";
import { cx } from "../ui/cx";
import type { Day, Period, TimetableEntry, ViewType } from "../types";

interface Props {
  view: ViewType;
  days: Day[];
  periods: Period[];
  entries: TimetableEntry[];
  density?: Density;
  pendingEntryIds?: Set<number>;
  findingHighlights?: Map<string, CellHighlight>;
  onSelectLesson?: (entry: TimetableEntry) => void;
  /** Entries with a proposed move, shown in their ORIGINAL slot as a ghost. */
  ghostEntries?: GhostEntry[];
  /** entry_id -> how many originating findings the pending move resolves. */
  resolvingCounts?: Map<number, number>;
  /** Currently inspected lesson - stays highlighted while its drawer is open. */
  selectedEntryId?: number | null;
}

// LESSON is coloured dynamically per faculty (see facultyColor) - not listed
// here. Non-lesson blocks use semantic surfaces rather than one-off hues.
const ENTRY_STYLES: Record<string, string> = {
  BREAK: "bg-surface-sunken border-border text-text-muted",
  ASSEMBLY: "bg-accent-surface border-accent-border text-accent",
  GENERAL_PURPOSE: "bg-warning-surface border-warning-border text-warning",
  DETENTION: "bg-critical-surface border-critical-border text-critical",
  REGISTRATION: "bg-surface-sunken border-border text-text-secondary",
  OTHER: "bg-surface-sunken border-border text-text-secondary",
};

export default function TimetableGrid({
  view,
  days,
  periods,
  entries,
  density = "comfortable",
  pendingEntryIds,
  findingHighlights,
  onSelectLesson,
  ghostEntries,
  resolvingCounts,
  selectedEntryId,
}: Props) {
  const weekA = days.filter((d) => d.week_label === "A").sort((a, b) => a.day_no - b.day_no);
  const weekB = days.filter((d) => d.week_label === "B").sort((a, b) => a.day_no - b.day_no);

  const canonicalPeriods = dedupePeriodsByNumber(periods);

  const entriesByKey = new Map<string, TimetableEntry[]>();
  for (const e of entries) {
    const key = `${e.day_code}|${e.period_no}`;
    const list = entriesByKey.get(key) ?? [];
    list.push(e);
    entriesByKey.set(key, list);
  }

  const ghostsByKey = new Map<string, GhostEntry[]>();
  for (const g of ghostEntries ?? []) {
    const key = `${g.entry.day_code}|${g.entry.period_no}`;
    const list = ghostsByKey.get(key) ?? [];
    list.push(g);
    ghostsByKey.set(key, list);
  }

  const isEmpty = entries.length === 0;

  // See MasterTimetableGrid's equivalent comment - one shared scroll
  // region for both weeks, owned by the page (TimetablePage), not the
  // page itself scrolling underneath it.
  return (
    <div className="h-full overflow-auto p-6 print:h-auto print:overflow-visible print:p-0">
      {isEmpty ? (
        <div className="mx-auto max-w-lg pt-10">
          <div className="rounded-lg border border-dashed border-border bg-surface px-6 py-10 text-center">
            <p className="text-sm font-medium text-text-primary">Nothing scheduled for this entity</p>
            <p className="mt-1 text-meta">
              The loaded timetable has no lessons for this selection across the cycle. Pick another teacher, room or
              roll class above - or search from anywhere with the command palette (Ctrl K).
            </p>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-8">
          <WeekTable
            label="Week A"
            weekDays={weekA}
            periods={canonicalPeriods}
            entriesByKey={entriesByKey}
            ghostsByKey={ghostsByKey}
            view={view}
            density={density}
            pendingEntryIds={pendingEntryIds}
            findingHighlights={findingHighlights}
            onSelectLesson={onSelectLesson}
            selectedEntryId={selectedEntryId}
            resolvingCounts={resolvingCounts}
          />
          <WeekTable
            label="Week B"
            weekDays={weekB}
            periods={canonicalPeriods}
            entriesByKey={entriesByKey}
            ghostsByKey={ghostsByKey}
            view={view}
            density={density}
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

function WeekTable({
  label,
  weekDays,
  periods,
  entriesByKey,
  ghostsByKey,
  view,
  density,
  pendingEntryIds,
  findingHighlights,
  onSelectLesson,
  selectedEntryId,
  resolvingCounts,
}: {
  label: string;
  weekDays: Day[];
  periods: Period[];
  entriesByKey: Map<string, TimetableEntry[]>;
  ghostsByKey: Map<string, GhostEntry[]>;
  view: ViewType;
  density: Density;
  pendingEntryIds?: Set<number>;
  findingHighlights?: Map<string, CellHighlight>;
  onSelectLesson?: (entry: TimetableEntry) => void;
  selectedEntryId?: number | null;
  resolvingCounts?: Map<number, number>;
}) {
  const compact = density === "compact";
  const { focus, registerCell, move, focusDefault, setFocus } = useGridKeyboardNav(periods.length, weekDays.length);

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const current = focus ?? { r: 0, c: 0 };
      const p = periods[current.r];
      const d = weekDays[current.c];
      const key = `${d.code}|${p.period_no}`;
      const lesson = (entriesByKey.get(key) ?? []).find((en) => en.entry_type === "LESSON");
      if (lesson && onSelectLesson) onSelectLesson(lesson);
      return;
    }
    if (move(e.key)) e.preventDefault();
  };

  return (
    <div>
      <h2 className="mb-2 text-section-title">{label}</h2>
      <div
        className="overflow-hidden rounded-lg border border-border bg-surface"
        tabIndex={0}
        role="grid"
        aria-label={`${label} timetable grid - arrow keys to move, Enter to open a lesson`}
        onFocus={focusDefault}
        onKeyDown={handleKeyDown}
      >
        <table className="w-full border-collapse text-table">
          <thead className="sticky top-0 z-20">
            <tr>
              <th
                className={cx(
                  "sticky left-0 z-30 w-28 border-b border-r border-border-strong bg-surface-sunken text-left text-label",
                  compact ? "p-1" : "p-2",
                )}
              >
                Period
              </th>
              {weekDays.map((d) => (
                <th
                  key={d.code}
                  className={cx(
                    "border-b border-border-strong bg-surface-sunken text-left text-label",
                    compact ? "p-1" : "p-2",
                  )}
                >
                  {d.code.replace(/ [AB]$/, "")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {periods.map((p, rowIdx) => (
              <tr key={p.period_no} className="odd:bg-surface even:bg-surface-sunken/40">
                <td
                  className={cx(
                    "sticky left-0 z-10 border-b border-r border-border bg-surface-sunken align-top",
                    compact ? "p-1" : "p-2",
                  )}
                >
                  <div className="text-xs font-semibold text-text-primary">{p.name}</div>
                  {p.start_time && !compact && (
                    <div className="nums text-[11px] text-text-muted">
                      {p.start_time}&ndash;{p.finish_time}
                    </div>
                  )}
                </td>
                {weekDays.map((d, colIdx) => {
                  const key = `${d.code}|${p.period_no}`;
                  const cellEntries = entriesByKey.get(key) ?? [];
                  const cellGhosts = ghostsByKey.get(key) ?? [];
                  const focused = focus?.r === rowIdx && focus?.c === colIdx;
                  return (
                    <td
                      key={d.code}
                      ref={(el) => registerCell(rowIdx, colIdx, el)}
                      tabIndex={-1}
                      // Focus arriving from inside this cell (clicking a
                      // lesson) records the keyboard position here so arrow
                      // keys continue from where the user actually is.
                      onFocus={() => setFocus({ r: rowIdx, c: colIdx })}
                      className={cx(
                        "border-b border-border align-top",
                        compact ? "p-0.5" : "p-1",
                        focused && "ring-2 ring-inset ring-focus",
                      )}
                    >
                      <Cell
                        view={view}
                        entries={cellEntries}
                        ghosts={cellGhosts}
                        compact={compact}
                        pendingEntryIds={pendingEntryIds}
                        findingHighlights={findingHighlights}
                        onSelectLesson={onSelectLesson}
                        selectedEntryId={selectedEntryId}
                        resolvingCounts={resolvingCounts}
                      />
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// Same rationale as MasterTimetableGrid's MAX_VISIBLE_PER_CELL - a single
// packed slot shouldn't force every other cell in its row to grow with it.
const MAX_VISIBLE_PER_CELL = 4;

function Cell({
  view,
  entries,
  ghosts,
  compact,
  pendingEntryIds,
  findingHighlights,
  onSelectLesson,
  selectedEntryId,
  resolvingCounts,
}: {
  view: ViewType;
  entries: TimetableEntry[];
  ghosts: GhostEntry[];
  compact: boolean;
  pendingEntryIds?: Set<number>;
  findingHighlights?: Map<string, CellHighlight>;
  onSelectLesson?: (entry: TimetableEntry) => void;
  selectedEntryId?: number | null;
  resolvingCounts?: Map<number, number>;
}) {
  if (entries.length === 0 && ghosts.length === 0) {
    if (compact) return <div className="rounded border border-dashed border-border/70" />;
    return <div className="rounded border border-dashed border-border p-2 text-xs text-text-muted">Free</div>;
  }

  const visible = entries.slice(0, MAX_VISIBLE_PER_CELL);
  const overflow = entries.slice(MAX_VISIBLE_PER_CELL);

  return (
    <div className={entries.length + ghosts.length > 1 ? `flex flex-col ${compact ? "gap-0.5" : "gap-1"}` : undefined}>
      {visible.map((e, i) => {
        const editable = e.entry_type === "LESSON" && !!onSelectLesson;
        const pending = pendingEntryIds?.has(e.entry_id);
        const highlight = findingHighlights ? highlightForEntry(findingHighlights, e) : null;
        const state = cellState({
          highlight,
          pending: !!pending,
          resolvingCount: resolvingCounts?.get(e.entry_id) ?? 0,
        });
        const isLesson = e.entry_type === "LESSON";
        const color = isLesson ? facultyColor(e.faculty_code) : null;
        const selected = selectedEntryId === e.entry_id;
        const className = cx(
          "relative w-full rounded border text-left text-xs leading-tight transition-[box-shadow,outline-color,background-color] duration-150",
          compact ? "p-1" : "p-1.5",
          isLesson ? "border-transparent text-text-primary" : ENTRY_STYLES[e.entry_type] ?? ENTRY_STYLES.OTHER,
          editable ? "cursor-pointer hover:brightness-95 hover:shadow-sm" : "",
          selected && "ring-2 ring-inset ring-focus",
          !selected && state.className,
        );
        const style = color ? { backgroundColor: `${color}1f`, borderLeft: `3px solid ${color}` } : undefined;
        const title =
          (highlight || pending
            ? `${cellTitle(e)}${pending ? " - proposed move" : ""}`
            : cellTitle(e)) + state.titleSuffix;

        const content = (
          <>
            <CellStateMarker state={state} />
            <EntryContent view={view} entry={e} compact={compact} />
          </>
        );

        return editable ? (
          <button key={i} type="button" className={className} style={style} title={title} onClick={() => onSelectLesson!(e)}>
            {content}
          </button>
        ) : (
          <div key={i} className={className} style={style} title={title}>
            {content}
          </div>
        );
      })}
      {ghosts.map((g, i) => (
        <GhostCell
          key={`ghost-${g.entry.entry_id}-${i}`}
          ghost={g}
          compact={compact}
          onSelectLesson={onSelectLesson}
        />
      ))}
      {overflow.length > 0 && (
        <div
          className="truncate rounded bg-surface-sunken px-1.5 py-1 text-center text-[11px] font-semibold text-text-muted"
          title={`Also here: ${overflow.map((e) => e.class_code ?? entryTypeLabel(e.entry_type)).join(", ")}`}
        >
          +{overflow.length} more
        </div>
      )}
    </div>
  );
}

/** The origin slot of a proposed move: same lesson, still here in the
 *  imported source, with the draft destination spelled out. Dashed border +
 *  arrow glyph + words, so it can't be mistaken for an applied fact. */
function GhostCell({
  ghost,
  compact,
  onSelectLesson,
}: {
  ghost: GhostEntry;
  compact: boolean;
  onSelectLesson?: (entry: TimetableEntry) => void;
}) {
  const label = ghost.entry.class_code ?? ghost.entry.subject_name ?? "Lesson";
  const target = `${ghost.after.day_code ?? ghost.entry.day_code} ${ghost.after.period_code ?? ghost.entry.period_code}`;
  const title = `${label} is proposed to move to ${target}. The imported timetable still has it here - the move applies only when the change set is approved.`;

  const body = (
    <div className={cx("relative border-dashed", compact ? "p-1" : "p-1.5")}>
      <div className="truncate font-medium text-text-muted">{label}</div>
      <div className="nums truncate text-[11px] text-timetable-proposed">&rarr; {target} proposed</div>
    </div>
  );

  const className =
    "relative w-full rounded border border-dashed border-timetable-proposed bg-timetable-proposed-surface text-left text-xs leading-tight " +
    "transition-[box-shadow] duration-150 hover:shadow-sm";

  if (onSelectLesson) {
    return (
      <button type="button" className={className} title={title} onClick={() => onSelectLesson(ghost.entry)}>
        {body}
      </button>
    );
  }
  return (
    <div className={className} title={title}>
      {body}
    </div>
  );
}

function EntryContent({ view, entry, compact }: { view: ViewType; entry: TimetableEntry; compact: boolean }) {
  if (entry.entry_type !== "LESSON") {
    return (
      <div>
        <div className="truncate font-medium">{entryTypeLabel(entry.entry_type)}</div>
        {!compact && view !== "roll_class" && <div className="truncate text-[11px] opacity-75">{entry.roll_class_code}</div>}
      </div>
    );
  }

  const primary = entry.class_code ?? entry.subject_name ?? "Class";
  const teacherName =
    entry.teacher_last_name ? `${entry.teacher_last_name}, ${entry.teacher_first_name ?? ""}`.trim() : null;

  // Compact mode shows only the primary line - maximum rows-in-view is
  // the point of the toggle, and the full detail is still one click away.
  if (compact) {
    return <div className="truncate font-medium">{primary}</div>;
  }

  return (
    <div>
      <div className="truncate font-medium">{primary}</div>
      {view !== "roll_class" && <div className="truncate text-[11px] opacity-75">{entry.roll_class_code}</div>}
      {view !== "room" && entry.room_code && <div className="truncate text-[11px] opacity-75">{entry.room_code}</div>}
      {view !== "teacher" && teacherName && <div className="truncate text-[11px] opacity-75">{teacherName}</div>}
    </div>
  );
}

/** Tooltip text for a lesson: who/where/what, before any state suffix. */
function cellTitle(entry: TimetableEntry): string {
  if (entry.entry_type !== "LESSON") return entryTypeLabel(entry.entry_type);
  const teacherName = entry.teacher_last_name
    ? `${entry.teacher_last_name}, ${entry.teacher_first_name ?? ""}`.trim()
    : null;
  return [entry.class_code, entry.roll_class_code, entry.room_code, teacherName].filter(Boolean).join(" · ");
}

function entryTypeLabel(entryType: string): string {
  switch (entryType) {
    case "BREAK":
      return "Break";
    case "ASSEMBLY":
      return "Assembly";
    case "GENERAL_PURPOSE":
      return "GP";
    case "DETENTION":
      return "Detention";
    case "REGISTRATION":
      return "Registration";
    default:
      return "—";
  }
}

function dedupePeriodsByNumber(periods: Period[]): Period[] {
  const byNumber = new Map<number, Period>();
  for (const p of periods) {
    if (!byNumber.has(p.period_no)) byNumber.set(p.period_no, p);
  }
  return [...byNumber.values()].sort((a, b) => a.period_no - b.period_no);
}
