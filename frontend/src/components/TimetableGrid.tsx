import type { KeyboardEvent } from "react";
import { facultyColor } from "../lib/facultyColors";
import { HIGHLIGHT_RING, highlightForEntry, type CellHighlight } from "../lib/findingHighlights";
import type { Density } from "../lib/density";
import { useGridKeyboardNav } from "../lib/gridKeyboardNav";
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
}

// LESSON is coloured dynamically per faculty (see facultyColor) - not listed
// here.
const ENTRY_STYLES: Record<string, string> = {
  BREAK: "bg-slate-100 border-slate-200 text-slate-500",
  ASSEMBLY: "bg-purple-50 border-purple-200 text-purple-900",
  GENERAL_PURPOSE: "bg-amber-50 border-amber-200 text-amber-900",
  DETENTION: "bg-rose-50 border-rose-200 text-rose-900",
  REGISTRATION: "bg-slate-50 border-slate-200 text-slate-600",
  OTHER: "bg-slate-50 border-slate-200 text-slate-600",
};

export default function TimetableGrid({
  view, days, periods, entries, density = "comfortable", pendingEntryIds, findingHighlights, onSelectLesson,
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

  // See MasterTimetableGrid's equivalent comment - one shared scroll
  // region for both weeks, owned by the page (TimetablePage), not the
  // page itself scrolling underneath it.
  return (
    <div className="h-full overflow-auto p-6">
      <div className="flex flex-col gap-8">
        <WeekTable
          label="Week A"
          weekDays={weekA}
          periods={canonicalPeriods}
          entriesByKey={entriesByKey}
          view={view}
          density={density}
          pendingEntryIds={pendingEntryIds}
          findingHighlights={findingHighlights}
          onSelectLesson={onSelectLesson}
        />
        <WeekTable
          label="Week B"
          weekDays={weekB}
          periods={canonicalPeriods}
          entriesByKey={entriesByKey}
          view={view}
          density={density}
          pendingEntryIds={pendingEntryIds}
          findingHighlights={findingHighlights}
          onSelectLesson={onSelectLesson}
        />
      </div>
    </div>
  );
}

function WeekTable({
  label,
  weekDays,
  periods,
  entriesByKey,
  view,
  density,
  pendingEntryIds,
  findingHighlights,
  onSelectLesson,
}: {
  label: string;
  weekDays: Day[];
  periods: Period[];
  entriesByKey: Map<string, TimetableEntry[]>;
  view: ViewType;
  density: Density;
  pendingEntryIds?: Set<number>;
  findingHighlights?: Map<string, CellHighlight>;
  onSelectLesson?: (entry: TimetableEntry) => void;
}) {
  const compact = density === "compact";
  const { focus, registerCell, move, focusDefault } = useGridKeyboardNav(periods.length, weekDays.length);

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
      <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">{label}</h2>
      <div
        className="rounded-lg border border-slate-200"
        tabIndex={0}
        role="grid"
        aria-label={`${label} timetable grid - arrow keys to move, Enter to open a lesson`}
        onFocus={focusDefault}
        onKeyDown={handleKeyDown}
      >
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr>
              <th
                className={`w-28 border-b border-r border-slate-200 bg-slate-50 text-left text-xs font-medium text-slate-500 ${compact ? "p-1" : "p-2"}`}
              >
                Period
              </th>
              {weekDays.map((d) => (
                <th
                  key={d.code}
                  className={`border-b border-slate-200 bg-slate-50 text-left text-xs font-medium text-slate-500 ${compact ? "p-1" : "p-2"}`}
                >
                  {d.code.replace(/ [AB]$/, "")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {periods.map((p, rowIdx) => (
              <tr key={p.period_no}>
                <td className={`border-b border-r border-slate-200 align-top text-xs text-slate-500 ${compact ? "p-1" : "p-2"}`}>
                  <div className="font-medium text-slate-700">{p.name}</div>
                  {p.start_time && !compact && (
                    <div className="text-[11px] text-ink-muted">
                      {p.start_time}&ndash;{p.finish_time}
                    </div>
                  )}
                </td>
                {weekDays.map((d, colIdx) => {
                  const key = `${d.code}|${p.period_no}`;
                  const cellEntries = entriesByKey.get(key) ?? [];
                  const focused = focus?.r === rowIdx && focus?.c === colIdx;
                  return (
                    <td
                      key={d.code}
                      ref={(el) => registerCell(rowIdx, colIdx, el)}
                      tabIndex={-1}
                      className={`border-b border-slate-200 align-top ${compact ? "p-0.5" : "p-1"} ${
                        focused ? "ring-2 ring-inset ring-sky-500" : ""
                      }`}
                    >
                      <Cell
                        view={view}
                        entries={cellEntries}
                        compact={compact}
                        pendingEntryIds={pendingEntryIds}
                        findingHighlights={findingHighlights}
                        onSelectLesson={onSelectLesson}
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
// Rarer here (single-entity view is already filtered to one teacher/room/
// roll class) but still possible for a busy composite/registration slot.
const MAX_VISIBLE_PER_CELL = 4;

function Cell({
  view,
  entries,
  compact,
  pendingEntryIds,
  findingHighlights,
  onSelectLesson,
}: {
  view: ViewType;
  entries: TimetableEntry[];
  compact: boolean;
  pendingEntryIds?: Set<number>;
  findingHighlights?: Map<string, CellHighlight>;
  onSelectLesson?: (entry: TimetableEntry) => void;
}) {
  if (entries.length === 0) {
    if (compact) return <div className="rounded border border-dashed border-slate-100" />;
    return <div className="rounded border border-dashed border-slate-200 p-2 text-xs text-slate-300">Free</div>;
  }

  const visible = entries.slice(0, MAX_VISIBLE_PER_CELL);
  const overflow = entries.slice(MAX_VISIBLE_PER_CELL);

  return (
    <div className={entries.length > 1 ? `flex flex-col ${compact ? "gap-0.5" : "gap-1"}` : undefined}>
      {visible.map((e, i) => {
        const editable = e.entry_type === "LESSON" && !!onSelectLesson;
        const pending = pendingEntryIds?.has(e.entry_id);
        const highlight = findingHighlights ? highlightForEntry(findingHighlights, e) : null;
        const isLesson = e.entry_type === "LESSON";
        const color = isLesson ? facultyColor(e.faculty_code) : null;
        // Pending takes the ring when both apply - the user is actively
        // working this lesson, so that's the more relevant signal in the
        // moment, but the finding is still named in the title either way.
        const ringClass = pending ? "ring-2 ring-amber-400" : highlight ? HIGHLIGHT_RING[highlight.severity] : "";
        const className = `relative w-full rounded border text-left text-xs leading-tight transition-all duration-150 ${compact ? "p-1" : "p-1.5"} ${
          isLesson ? "border-transparent text-slate-900" : (ENTRY_STYLES[e.entry_type] ?? ENTRY_STYLES.OTHER)
        } ${editable ? "cursor-pointer hover:shadow-md hover:ring-2 hover:ring-sky-400" : ""} ${ringClass}`;
        const style = color ? { backgroundColor: `${color}1f`, borderLeft: `3px solid ${color}` } : undefined;
        const title = highlight ? highlight.titles.join("; ") : undefined;

        const content = (
          <>
            {pending && (
              <span className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-amber-500" title="Pending edit" />
            )}
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
      {overflow.length > 0 && (
        <div
          className="truncate rounded bg-slate-200 px-1.5 py-1 text-center text-[11px] font-semibold text-slate-500"
          title={`Also here: ${overflow.map((e) => e.class_code ?? entryTypeLabel(e.entry_type)).join(", ")}`}
        >
          +{overflow.length} more
        </div>
      )}
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
