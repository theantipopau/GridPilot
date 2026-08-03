import type { Day, Period, TimetableEntry, ViewType } from "../types";

interface Props {
  view: ViewType;
  days: Day[];
  periods: Period[];
  entries: TimetableEntry[];
}

const ENTRY_STYLES: Record<string, string> = {
  LESSON: "bg-sky-50 border-sky-200 text-sky-900",
  BREAK: "bg-slate-100 border-slate-200 text-slate-500",
  ASSEMBLY: "bg-purple-50 border-purple-200 text-purple-900",
  GENERAL_PURPOSE: "bg-amber-50 border-amber-200 text-amber-900",
  DETENTION: "bg-rose-50 border-rose-200 text-rose-900",
  REGISTRATION: "bg-slate-50 border-slate-200 text-slate-600",
  OTHER: "bg-slate-50 border-slate-200 text-slate-600",
};

export default function TimetableGrid({ view, days, periods, entries }: Props) {
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

  return (
    <div className="flex flex-col gap-8 p-6">
      <WeekTable
        label="Week A"
        weekDays={weekA}
        periods={canonicalPeriods}
        entriesByKey={entriesByKey}
        view={view}
      />
      <WeekTable
        label="Week B"
        weekDays={weekB}
        periods={canonicalPeriods}
        entriesByKey={entriesByKey}
        view={view}
      />
    </div>
  );
}

function WeekTable({
  label,
  weekDays,
  periods,
  entriesByKey,
  view,
}: {
  label: string;
  weekDays: Day[];
  periods: Period[];
  entriesByKey: Map<string, TimetableEntry[]>;
  view: ViewType;
}) {
  return (
    <div>
      <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">{label}</h2>
      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr>
              <th className="w-28 border-b border-r border-slate-200 bg-slate-50 p-2 text-left text-xs font-medium text-slate-500">
                Period
              </th>
              {weekDays.map((d) => (
                <th
                  key={d.code}
                  className="border-b border-slate-200 bg-slate-50 p-2 text-left text-xs font-medium text-slate-500"
                >
                  {d.code.replace(/ [AB]$/, "")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {periods.map((p) => (
              <tr key={p.period_no}>
                <td className="border-b border-r border-slate-200 p-2 align-top text-xs text-slate-500">
                  <div className="font-medium text-slate-700">{p.name}</div>
                  {p.start_time && (
                    <div className="text-[11px] text-slate-400">
                      {p.start_time}&ndash;{p.finish_time}
                    </div>
                  )}
                </td>
                {weekDays.map((d) => {
                  const key = `${d.code}|${p.period_no}`;
                  const cellEntries = entriesByKey.get(key) ?? [];
                  return (
                    <td key={d.code} className="border-b border-slate-200 p-1 align-top">
                      <Cell view={view} entries={cellEntries} />
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

function Cell({ view, entries }: { view: ViewType; entries: TimetableEntry[] }) {
  if (entries.length === 0) {
    return <div className="rounded border border-dashed border-slate-200 p-2 text-xs text-slate-300">Free</div>;
  }

  const clash = entries.length > 1;

  return (
    <div className={clash ? "flex flex-col gap-1 ring-2 ring-red-400 rounded" : undefined}>
      {entries.map((e, i) => (
        <div
          key={i}
          className={`rounded border p-1.5 text-xs leading-tight ${ENTRY_STYLES[e.entry_type] ?? ENTRY_STYLES.OTHER}`}
        >
          <EntryContent view={view} entry={e} />
        </div>
      ))}
      {clash && <div className="px-1 text-[10px] font-semibold text-red-600">CLASH</div>}
    </div>
  );
}

function EntryContent({ view, entry }: { view: ViewType; entry: TimetableEntry }) {
  if (entry.entry_type !== "LESSON") {
    return (
      <div>
        <div className="font-medium">{entryTypeLabel(entry.entry_type)}</div>
        {view !== "roll_class" && <div className="text-[11px] opacity-75">{entry.roll_class_code}</div>}
      </div>
    );
  }

  const primary = entry.class_code ?? entry.subject_name ?? "Class";
  const teacherName =
    entry.teacher_last_name ? `${entry.teacher_last_name}, ${entry.teacher_first_name ?? ""}`.trim() : null;

  return (
    <div>
      <div className="font-medium">{primary}</div>
      {view !== "roll_class" && <div className="text-[11px] opacity-75">{entry.roll_class_code}</div>}
      {view !== "room" && entry.room_code && <div className="text-[11px] opacity-75">{entry.room_code}</div>}
      {view !== "teacher" && teacherName && <div className="text-[11px] opacity-75">{teacherName}</div>}
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
