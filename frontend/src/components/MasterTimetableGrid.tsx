import type { Day, Period, ReferenceData, TimetableEntry, ViewType } from "../types";

interface RowSpec {
  code: string;
  label: string;
}

interface Props {
  axis: ViewType;
  reference: ReferenceData;
  entries: TimetableEntry[];
  pendingEntryIds?: Set<number>;
  onSelectLesson?: (entry: TimetableEntry) => void;
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

export default function MasterTimetableGrid({ axis, reference, entries, pendingEntryIds, onSelectLesson }: Props) {
  const rows = rowsForAxis(reference, axis);
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

  return (
    <div className="flex flex-col gap-8 p-6">
      <MasterWeekTable
        label="Week A"
        weekDays={weekA}
        periods={canonicalPeriods}
        rows={rows}
        axis={axis}
        entriesByRowKey={entriesByRowKey}
        pendingEntryIds={pendingEntryIds}
        onSelectLesson={onSelectLesson}
      />
      <MasterWeekTable
        label="Week B"
        weekDays={weekB}
        periods={canonicalPeriods}
        rows={rows}
        axis={axis}
        entriesByRowKey={entriesByRowKey}
        pendingEntryIds={pendingEntryIds}
        onSelectLesson={onSelectLesson}
      />
    </div>
  );
}

function MasterWeekTable({
  label,
  weekDays,
  periods,
  rows,
  axis,
  entriesByRowKey,
  pendingEntryIds,
  onSelectLesson,
}: {
  label: string;
  weekDays: Day[];
  periods: Period[];
  rows: RowSpec[];
  axis: ViewType;
  entriesByRowKey: Map<string, TimetableEntry[]>;
  pendingEntryIds?: Set<number>;
  onSelectLesson?: (entry: TimetableEntry) => void;
}) {
  if (weekDays.length === 0) return null;

  return (
    <div>
      <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">{label}</h2>
      <div className="max-h-[70vh] overflow-auto rounded-lg border border-slate-200">
        <table className="w-full border-collapse text-xs">
          <thead className="sticky top-0 z-10">
            <tr>
              <th className="sticky left-0 z-20 w-40 border-b border-r border-slate-200 bg-slate-50 p-1.5 text-left font-medium text-slate-500">
                {axis === "teacher" ? "Teacher" : axis === "room" ? "Room" : "Roll class"}
              </th>
              {weekDays.map((d) => (
                <th
                  key={d.code}
                  colSpan={periods.length}
                  className="border-b border-l border-slate-200 bg-slate-50 p-1 text-center font-medium text-slate-500"
                >
                  {d.code.replace(/ [AB]$/, "")}
                </th>
              ))}
            </tr>
            <tr>
              <th className="sticky left-0 z-20 border-b border-r border-slate-200 bg-slate-50 p-1"></th>
              {weekDays.map((d) =>
                periods.map((p) => (
                  <th
                    key={`${d.code}-${p.period_no}`}
                    className="border-b border-l border-slate-200 bg-slate-50 p-1 text-center font-normal text-slate-400"
                    title={p.name}
                  >
                    {p.name.length > 4 ? p.period_no : p.name}
                  </th>
                )),
              )}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.code} className="even:bg-slate-50/50">
                <td
                  className="sticky left-0 z-10 max-w-[10rem] truncate border-b border-r border-slate-200 bg-white p-1.5 font-medium text-slate-700"
                  title={row.label}
                >
                  {row.label}
                </td>
                {weekDays.map((d) =>
                  periods.map((p) => {
                    const key = `${row.code}|${d.code}|${p.period_no}`;
                    const cellEntries = entriesByRowKey.get(key) ?? [];
                    return (
                      <MasterCell
                        key={`${d.code}-${p.period_no}`}
                        axis={axis}
                        entries={cellEntries}
                        pendingEntryIds={pendingEntryIds}
                        onSelectLesson={onSelectLesson}
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

function MasterCell({
  axis,
  entries,
  pendingEntryIds,
  onSelectLesson,
}: {
  axis: ViewType;
  entries: TimetableEntry[];
  pendingEntryIds?: Set<number>;
  onSelectLesson?: (entry: TimetableEntry) => void;
}) {
  if (entries.length === 0) {
    return <td className="border-b border-l border-slate-100 p-1 text-center text-slate-200">·</td>;
  }

  const clash = entries.length > 1;

  return (
    <td className={`border-b border-l border-slate-100 p-0.5 align-top ${clash ? "bg-red-50" : ""}`}>
      <div className="flex flex-col gap-0.5">
        {entries.map((e, i) => {
          const label = cellLabel(axis, e);
          const editable = e.entry_type === "LESSON" && !!onSelectLesson;
          const pending = pendingEntryIds?.has(e.entry_id);
          const className = `relative w-full truncate rounded px-1 py-0.5 text-left leading-tight ${
            e.entry_type === "LESSON" ? "bg-sky-50 text-sky-900" : "bg-slate-100 text-slate-500"
          } ${clash ? "ring-1 ring-red-400" : ""} ${editable ? "cursor-pointer hover:ring-1 hover:ring-sky-400" : ""} ${
            pending ? "ring-1 ring-amber-400" : ""
          }`;
          return editable ? (
            <button key={i} type="button" className={className} onClick={() => onSelectLesson!(e)} title={cellTitle(e)}>
              {label}
            </button>
          ) : (
            <div key={i} className={className} title={cellTitle(e)}>
              {label}
            </div>
          );
        })}
      </div>
    </td>
  );
}

function cellLabel(axis: ViewType, e: TimetableEntry): string {
  if (e.entry_type !== "LESSON") return e.entry_type.slice(0, 3);
  if (axis === "room") return e.teacher_code ?? e.class_code ?? "—";
  if (axis === "teacher") return e.room_code ?? e.class_code ?? "—";
  return e.class_code ?? "—";
}

function cellTitle(e: TimetableEntry): string {
  if (e.entry_type !== "LESSON") return e.entry_type;
  const teacherName = e.teacher_last_name ? `${e.teacher_last_name}, ${e.teacher_first_name ?? ""}`.trim() : null;
  return [e.class_code, e.roll_class_code, e.room_code, teacherName].filter(Boolean).join(" · ");
}
