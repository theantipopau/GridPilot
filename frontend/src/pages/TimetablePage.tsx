import { useEffect, useState } from "react";
import { fetchTimetable } from "../api";
import FilterBar from "../components/FilterBar";
import TimetableGrid from "../components/TimetableGrid";
import type { ReferenceData, TimetableResponse, ViewType } from "../types";

export default function TimetablePage({ reference }: { reference: ReferenceData }) {
  const [view, setView] = useState<ViewType>("teacher");
  const [code, setCode] = useState<string>(reference.teachers[0]?.code ?? "");
  const [timetable, setTimetable] = useState<TimetableResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!code) return;
    fetchTimetable(view, code)
      .then(setTimetable)
      .catch((e) => setError(String(e)));
  }, [view, code]);

  if (error) {
    return <div className="p-6 text-red-600">Failed to load timetable: {error}</div>;
  }

  return (
    <div>
      <FilterBar
        reference={reference}
        view={view}
        code={code}
        onChange={(v, c) => {
          setView(v);
          setCode(c);
        }}
      />
      {timetable && (
        <TimetableGrid view={view} days={reference.days} periods={reference.periods} entries={timetable.entries} />
      )}
    </div>
  );
}
