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
import MasterTimetableGrid from "../components/MasterTimetableGrid";
import TimetableGrid from "../components/TimetableGrid";
import { Button, Select, Tabs, Tooltip } from "../ui";
import { IconPrinter } from "../components/icons";
import { useDensity } from "../lib/density";
import { buildFindingHighlightIndex } from "../lib/findingHighlights";
import { applyPendingMoves, buildGhosts, buildPendingMoveMap, type GhostEntry } from "../lib/pendingMoves";
import type {
  ChangeEndpoint,
  ChangeSetSummary,
  Finding,
  ProposedChange,
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
  const [density, setDensity] = useDensity();
  const [masterEntries, setMasterEntries] = useState<TimetableEntry[] | null>(null);
  const [onlyRowsWithFindings, setOnlyRowsWithFindings] = useState(false);
  const [focusMode, setFocusMode] = useState(false);

  const [view, setView] = useState<ViewType>("teacher");
  const [code, setCode] = useState<string>(reference.teachers[0]?.code ?? "");
  const [timetable, setTimetable] = useState<TimetableResponse | null>(null);

  const [error, setError] = useState<string | null>(null);
  const [selectedEntry, setSelectedEntry] = useState<TimetableEntry | null>(null);
  const [pendingEntryIds, setPendingEntryIds] = useState<Set<number>>(new Set());
  const [pendingMoves, setPendingMoves] = useState<Map<number, ChangeEndpoint>>(new Map());
  const [pendingChanges, setPendingChanges] = useState<ProposedChange[]>([]);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
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
      setPendingChanges([]);
      setValidation(null);
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
    setPendingChanges(detail.changes);
    setValidation(detail.validation_result);
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
    const result = await validateChangeSet(changeSetId);
    await loadPending(changeSetId);
    return result;
  };

  // Ghosts (the origin slot of every proposed move) come straight from the
  // pre-move source list, so the live grid and the ghost can never disagree.
  const sourceEntries = mode === "master" ? masterEntries : timetable?.entries;
  const ghosts: GhostEntry[] = useMemo(
    () => (sourceEntries ? buildGhosts(sourceEntries, pendingChanges) : []),
    [sourceEntries, pendingChanges],
  );

  // How many originating findings each pending move clears, once validated.
  // From the API's own unresolved list - never inferred client-side.
  const resolvingCounts = useMemo(() => {
    const map = new Map<number, number>();
    const unresolved = new Set(validation?.unresolved_originating_findings ?? []);
    for (const c of pendingChanges) {
      const resolved = c.finding_ids.filter((id) => !unresolved.has(id)).length;
      if (resolved > 0) map.set(c.timetable_entry_id, resolved);
    }
    return map;
  }, [pendingChanges, validation]);

  const proposedCount = pendingEntryIds.size;

  if (error) {
    return (
      <div className="flex h-full flex-col p-6">
        <div className="rounded-lg border border-critical-border bg-critical-surface px-4 py-3 text-sm text-critical">
          Failed to load timetable: {error}
        </div>
      </div>
    );
  }

  // One toolbar row, not a stack of separately-bordered bars - the mode
  // toggle and whichever controls the current mode needs (axis+scenario,
  // or the entity picker) live together.
  return (
    <div className="flex h-full flex-col print:block print:h-auto">
      <div className="flex shrink-0 flex-wrap items-end justify-between gap-4 border-b border-border bg-surface px-5 py-3 print:hidden">
        <div className="flex flex-wrap items-end gap-4">
          <Tabs
            label="Timetable mode"
            variant="segmented"
            size="sm"
            value={mode}
            onChange={setMode}
            tabs={[
              { id: "master", label: "Master grid" },
              { id: "single", label: "Single entity" },
            ]}
          />

          {/* Applies to both modes - a timetabler scanning the whole school
              wants compact, someone reviewing one teacher wants comfortable.
              Persisted per-browser via useDensity, not reset on mode changes. */}
          <Tabs
            label="Density"
            variant="segmented"
            size="sm"
            value={density}
            onChange={setDensity}
            tabs={[
              { id: "comfortable", label: "Comfortable" },
              { id: "compact", label: "Compact" },
            ]}
          />

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

          {mode === "master" && onlyRowsWithFindings && (
            <Button size="sm" variant="ghost" onClick={() => setOnlyRowsWithFindings(false)}>
              Show all rows
            </Button>
          )}
        </div>

        <div className="flex flex-wrap items-end gap-3">
          {mode === "master" && (
            <>
              <Select
                containerClassName="w-32"
                label="Rows by"
                size="sm"
                options={AXIS_OPTIONS}
                value={axis}
                onChange={(v) => setAxis(v as ViewType)}
              />
              <Select
                containerClassName="w-56"
                label="Viewing"
                size="sm"
                options={[
                  { value: "", label: "Live timetable" },
                  ...draftChangeSets.map((cs) => ({ value: String(cs.id), label: `Scenario: ${cs.name}` })),
                ]}
                value={gridChangeSetId != null ? String(gridChangeSetId) : ""}
                onChange={(v) => onGridChangeSetCreated(v ? Number(v) : null)}
                className={gridChangeSetId != null ? "border-accent-border bg-accent-surface text-accent" : ""}
              />
              <Button
                size="sm"
                variant={onlyRowsWithFindings ? "primary" : "secondary"}
                aria-pressed={onlyRowsWithFindings}
                onClick={() => setOnlyRowsWithFindings((v) => !v)}
                title="Hide rows with no open finding - the fastest way through 51 rows"
              >
                Only rows with findings
              </Button>
            </>
          )}
          <Button
            size="sm"
            iconLeft={<IconPrinter className="h-4 w-4" />}
            onClick={() => window.print()}
            title="Print this timetable, or save it as a PDF, via your browser's print dialog"
          >
            Print
          </Button>
          <Tooltip
            content={focusMode ? "Leave focus mode" : "Hide the legend and give the grid the whole workspace"}
            placement="bottom"
          >
            <Button size="sm" variant={focusMode ? "primary" : "secondary"} aria-pressed={focusMode} onClick={() => setFocusMode((v) => !v)}>
              {focusMode ? "Exit focus" : "Focus"}
            </Button>
          </Tooltip>
        </div>
      </div>

      {/* Scenario banner: when the grid is showing a draft, say so in words
          above the grid - the dashed cells and ghosts explain each lesson,
          this explains the whole view. */}
      {gridChangeSetId != null && (
        <div className="flex shrink-0 flex-wrap items-center gap-x-3 gap-y-1 border-b border-accent-border bg-accent-surface px-5 py-2 text-xs text-accent print:hidden">
          <span className="font-semibold">
            Showing draft scenario: {changeSetName ?? `change set #${gridChangeSetId}`}
          </span>
          <span>
            {proposedCount} proposed move{proposedCount === 1 ? "" : "s"} rendered in place. The imported timetable is
            unchanged until this change set is approved.
          </span>
          <button
            type="button"
            className="ml-auto rounded underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
            onClick={() => onOpenChangeSet(gridChangeSetId)}
          >
            Review in Change Sets
          </button>
        </div>
      )}

      {!focusMode && <FacultyLegend className="shrink-0 print:hidden" />}

      {/* The one scroll region for the whole page - the grid used to sit
          inside a page that also scrolled AND each week table had its own
          independent max-h box. min-h-0 is required here: without it a flex
          child refuses to shrink below its content size. On print, the
          opposite is wanted - the full timetable, not a viewport-clipped
          scroll window, so print:h-auto/overflow-visible let it grow. */}
      <div className="min-h-0 flex-1 overflow-hidden print:h-auto print:overflow-visible">
        {mode === "master" &&
          (masterEntries ? (
            <MasterTimetableGrid
              axis={axis}
              reference={reference}
              entries={applyPendingMoves(masterEntries, pendingMoves, reference)}
              density={density}
              pendingEntryIds={pendingEntryIds}
              findingHighlights={findingHighlights}
              ghostEntries={ghosts}
              resolvingCounts={resolvingCounts}
              selectedEntryId={selectedEntry?.entry_id ?? null}
              onlyRowsWithFindings={onlyRowsWithFindings}
              onSelectLesson={setSelectedEntry}
            />
          ) : (
            <div className="p-6" role="status" aria-live="polite">
              <span className="sr-only">Loading the master timetable…</span>
              <div className="mb-3 h-5 w-40 skeleton" />
              <div className="h-96 w-full skeleton" />
            </div>
          ))}

        {mode === "single" &&
          (timetable ? (
            <TimetableGrid
              view={view}
              days={reference.days}
              periods={reference.periods}
              entries={applyPendingMoves(timetable.entries, pendingMoves, reference)}
              density={density}
              pendingEntryIds={pendingEntryIds}
              findingHighlights={findingHighlights}
              ghostEntries={ghosts}
              resolvingCounts={resolvingCounts}
              selectedEntryId={selectedEntry?.entry_id ?? null}
              onSelectLesson={setSelectedEntry}
            />
          ) : (
            <div className="p-6" role="status" aria-live="polite">
              <span className="sr-only">Loading this timetable…</span>
              <div className="h-96 w-full skeleton" />
            </div>
          ))}
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
