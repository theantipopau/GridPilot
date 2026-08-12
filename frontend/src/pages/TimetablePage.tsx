import { useEffect, useState } from "react";
import {
  addProposedChange,
  createChangeSet,
  fetchAllTimetableEntries,
  fetchChangeSet,
  fetchTimetable,
  validateChangeSet,
} from "../api";
import FilterBar from "../components/FilterBar";
import LessonInspector, { type MoveParams } from "../components/LessonInspector";
import LoadingState from "../components/LoadingState";
import MasterTimetableGrid from "../components/MasterTimetableGrid";
import TimetableGrid from "../components/TimetableGrid";
import { applyPendingMoves, buildPendingMoveMap } from "../lib/pendingMoves";
import type { ChangeEndpoint, ReferenceData, TimetableEntry, TimetableResponse, ValidationResult, ViewType } from "../types";

interface Props {
  reference: ReferenceData;
  gridChangeSetId: number | null;
  onGridChangeSetCreated: (id: number) => void;
  onOpenChangeSet: (id: number) => void;
}

type Mode = "master" | "single";

const AXIS_OPTIONS: { value: ViewType; label: string }[] = [
  { value: "room", label: "Room" },
  { value: "teacher", label: "Teacher" },
  { value: "roll_class", label: "Roll class" },
];

export default function TimetablePage({ reference, gridChangeSetId, onGridChangeSetCreated, onOpenChangeSet }: Props) {
  const [mode, setMode] = useState<Mode>("master");
  const [axis, setAxis] = useState<ViewType>("room");
  const [masterEntries, setMasterEntries] = useState<TimetableEntry[] | null>(null);

  const [view, setView] = useState<ViewType>("teacher");
  const [code, setCode] = useState<string>(reference.teachers[0]?.code ?? "");
  const [timetable, setTimetable] = useState<TimetableResponse | null>(null);

  const [error, setError] = useState<string | null>(null);
  const [selectedEntry, setSelectedEntry] = useState<TimetableEntry | null>(null);
  const [pendingEntryIds, setPendingEntryIds] = useState<Set<number>>(new Set());
  const [pendingMoves, setPendingMoves] = useState<Map<number, ChangeEndpoint>>(new Map());
  const [changeSetName, setChangeSetName] = useState<string | null>(null);

  useEffect(() => {
    if (mode !== "master" || masterEntries) return;
    fetchAllTimetableEntries()
      .then((r) => setMasterEntries(r.entries))
      .catch((e) => setError(String(e)));
  }, [mode, masterEntries]);

  useEffect(() => {
    if (mode !== "single" || !code) return;
    fetchTimetable(view, code)
      .then(setTimetable)
      .catch((e) => setError(String(e)));
  }, [mode, view, code]);

  const loadPending = async (changeSetId: number) => {
    const detail = await fetchChangeSet(changeSetId);
    setChangeSetName(detail.name);
    setPendingEntryIds(new Set(detail.changes.map((c) => c.timetable_entry_id)));
    setPendingMoves(buildPendingMoveMap(detail.changes));
  };

  useEffect(() => {
    if (gridChangeSetId != null) loadPending(gridChangeSetId);
  }, [gridChangeSetId]);

  const handlePropose = async (params: MoveParams): Promise<ValidationResult> => {
    if (!selectedEntry) throw new Error("No lesson selected");
    let changeSetId = gridChangeSetId;
    if (changeSetId == null) {
      const created = await createChangeSet(`Timetable edits - ${new Date().toLocaleDateString()}`, undefined, "you");
      changeSetId = created.id;
      onGridChangeSetCreated(changeSetId);
    }
    await addProposedChange(changeSetId, { timetable_entry_id: selectedEntry.entry_id, ...params });
    const validation = await validateChangeSet(changeSetId);
    await loadPending(changeSetId);
    return validation;
  };

  if (error) {
    return <div className="p-6 text-red-600">Failed to load timetable: {error}</div>;
  }

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex gap-1 rounded-md bg-slate-100 p-1">
          <button
            type="button"
            onClick={() => setMode("master")}
            className={`rounded px-3 py-1.5 text-sm font-medium transition-colors duration-150 ${
              mode === "master" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            Master grid
          </button>
          <button
            type="button"
            onClick={() => setMode("single")}
            className={`rounded px-3 py-1.5 text-sm font-medium transition-colors duration-150 ${
              mode === "single" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            Single entity
          </button>
        </div>

        {mode === "master" && (
          <div>
            <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">Rows by</label>
            <select
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-900"
              value={axis}
              onChange={(e) => setAxis(e.target.value as ViewType)}
            >
              {AXIS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {mode === "single" && (
        <FilterBar
          reference={reference}
          view={view}
          code={code}
          onChange={(v, c) => {
            setView(v);
            setCode(c);
          }}
        />
      )}

      {mode === "master" &&
        (masterEntries ? (
          <MasterTimetableGrid
            axis={axis}
            reference={reference}
            entries={applyPendingMoves(masterEntries, pendingMoves, reference)}
            pendingEntryIds={pendingEntryIds}
            onSelectLesson={setSelectedEntry}
          />
        ) : (
          <LoadingState label="Loading the master timetable…" />
        ))}

      {mode === "single" && timetable && (
        <TimetableGrid
          view={view}
          days={reference.days}
          periods={reference.periods}
          entries={applyPendingMoves(timetable.entries, pendingMoves, reference)}
          pendingEntryIds={pendingEntryIds}
          onSelectLesson={setSelectedEntry}
        />
      )}

      {selectedEntry && (
        <LessonInspector
          entry={selectedEntry}
          reference={reference}
          changeSetName={changeSetName}
          onClose={() => setSelectedEntry(null)}
          onPropose={handlePropose}
          onOpenChangeSet={() => gridChangeSetId != null && onOpenChangeSet(gridChangeSetId)}
        />
      )}
    </div>
  );
}
