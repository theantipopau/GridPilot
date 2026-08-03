import { useEffect, useState } from "react";
import { fetchReference, fetchTimetable } from "./api";
import gridPilotLogo from "./assets/gridpilot-logo.png";
import FilterBar from "./components/FilterBar";
import TimetableGrid from "./components/TimetableGrid";
import type { ReferenceData, TimetableResponse, ViewType } from "./types";

export default function App() {
  const [reference, setReference] = useState<ReferenceData | null>(null);
  const [view, setView] = useState<ViewType>("teacher");
  const [code, setCode] = useState<string>("");
  const [timetable, setTimetable] = useState<TimetableResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchReference()
      .then((data) => {
        setReference(data);
        if (data.teachers[0]) setCode(data.teachers[0].code);
      })
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!code) return;
    fetchTimetable(view, code)
      .then(setTimetable)
      .catch((e) => setError(String(e)));
  }, [view, code]);

  if (error) {
    return (
      <div className="p-6 text-red-600">
        Failed to load: {error}. Is the backend running (
        <code>python -m uvicorn app.api.main:app --port 8000</code> from <code>backend/</code>)?
      </div>
    );
  }

  if (!reference) {
    return <div className="p-6 text-slate-500">Loading…</div>;
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
        <img src={gridPilotLogo} alt="GridPilot" className="h-8 w-auto" />
        <div className="text-right">
          <p className="text-sm font-medium text-slate-700">Sophia College</p>
          <p className="text-sm text-slate-500">{timetable ? timetable.label : "Loading timetable…"}</p>
        </div>
      </header>
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
