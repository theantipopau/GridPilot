import { useEffect, useMemo, useState } from "react";
import {
  addProposedChange,
  createChangeSet,
  fetchAllTimetableEntries,
  fetchChangeSet,
  fetchChangeSets,
  fetchFindings,
  fetchTimetable,
  validateChangeSet,
} from "../api";
import EntityPicker from "../components/EntityPicker";
import FacultyLegend from "../components/FacultyLegend";
import LessonInspector, { type MoveParams } from "../components/LessonInspector";
import LoadingState from "../components/LoadingState";
import MasterTimetableGrid from "../components/MasterTimetableGrid";
import TimetableGrid from "../components/TimetableGrid";
import { buildFindingHighlightIndex } from "../lib/findingHighlights";
import { applyPendingMoves, buildPendingMoveMap } from "../lib/pendingMoves";
import type {
  ChangeEndpoint,
  ChangeSetSummary,
  Finding,
  ReferenceData,
  TimetableEntry,
  TimetableResponse,
  ValidationResult,
  ViewType,
} from "../types";

interface Props {
  reference: ReferenceData;
  gridChangeSetId: number | null;
  onGridChangeSetCreated: (id: number | null) => void;
  onOpenChangeSet: (id: number) => void;
  jumpTarget: { view: ViewType; code: string } | null;
  onJumpConsumed: () => void;
}

type Mode = "master" | "single";

const AXIS_OPTIONS: { value: ViewType; label: string }[] = [
  { value: "room", label: "Room" },
  { value: "teacher", label: "Teacher" },
  { value: "roll_class", label: "Roll class" },
];

export default function TimetablePage({
  reference,
  gridChangeSetId,
  onGridChangeSetCreated,
  onOpenChangeSet,
  jumpTarget,
  onJumpConsumed,
}: Props) {
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
  const [openFindings, setOpenFindings] = useState<Finding[]>([]);
  const [draftChangeSets, setDraftChangeSets] = useState<ChangeSetSummary[]>([]);

  useEffect(() => {
    if (!jumpTarget) return;
    setMode("single");
    setView(jumpTarget.view);
    setCode(jumpTarget.code);
    onJumpConsumed();
  }, [jumpTarget, onJumpConsumed]);

  // A "scenario" is just an existing draft change set viewed through the
  // grid instead of edited via a finding/repair flow - refresh the list
  // whenever master mode is opened so a scenario made elsewhere shows up.
  useEffect(() => {
    if (mode !== "master") return;
    fetchChangeSets()
      .then((r) => setDraftChangeSets(r.change_sets.filter((c) => c.approval_status === "DRAFT")))
      .catch(() => setDraftChangeSets([]));
  }, [mode]);

  useEffect(() => {
    if (gridChangeSetId == null) {
      setPendingEntryIds(new Set());
      setPendingMoves(new Map());
      setChangeSetName(null);
    }
  }, [gridChangeSetId]);

  useEffect(() => {
    fetchFindings("OPEN")
      .then((r) => setOpenFindings(r.findings))
      .catch(() => setOpenFindings([]));
  }, []);

  // Findings only reflect the last rules-engine run, not any change still
  // sitting in a pending change set (nothing is written to the timetable
  // until a change set is approved) - so this index doesn't need to
  // refresh as the user proposes moves, only once per page visit.
  const findingHighlights = useMemo(() => buildFindingHighlightIndex(openFindings), [openFindings]);

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

  // One toolbar row, not a stack of separately-bordered bars - the mode
  // toggle and whichever controls the current mode needs (axis+scenario,
  // or the entity picker) live together, docs/roadmap-v2.md 4.3.
  return (
    <div className="flex h-full flex-col">
      <div className="flex shrink-0 flex-wrap items-end justify-between gap-4 border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex items-end gap-4">
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

          {mode === "single" && (
            <EntityPicker
              reference={reference}
              view={view}
              code={code}
              onChange={(v, c) => {
                setView(v);
                setCode(c);
              }}
            />
          )}
        </div>

        {mode === "master" && (
          <div className="flex items-end gap-4">
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
            <div>
              <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">Viewing</label>
              <select
                className={`rounded-md border px-3 py-1.5 text-sm ${
                  gridChangeSetId != null
                    ? "border-violet-300 bg-violet-50 text-violet-800"
                    : "border-slate-300 text-slate-900"
                }`}
                value={gridChangeSetId ?? ""}
                onChange={(e) => onGridChangeSetCreated(e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">Live timetable</option>
                {draftChangeSets.map((cs) => (
                  <option key={cs.id} value={cs.id}>
                    Scenario: {cs.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}
      </div>

      <div className="shrink-0">
        <FacultyLegend />
      </div>

      {/* The one scroll region for the whole page - the grid used to sit
          inside a page that also scrolled (main's overflow-y-auto) AND
          each week table had its own independent max-h box, so getting
          anywhere meant tracking two or three separate scrollbars at
          once. min-h-0 is required here: without it a flex child refuses
          to shrink below its content size and this box would just grow
          past the viewport instead of clipping and scrolling. */}
      <div className="min-h-0 flex-1 overflow-hidden">
        {mode === "master" &&
          (masterEntries ? (
            <MasterTimetableGrid
              axis={axis}
              reference={reference}
              entries={applyPendingMoves(masterEntries, pendingMoves, reference)}
              pendingEntryIds={pendingEntryIds}
              findingHighlights={findingHighlights}
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
            findingHighlights={findingHighlights}
            onSelectLesson={setSelectedEntry}
          />
        )}
      </div>

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
