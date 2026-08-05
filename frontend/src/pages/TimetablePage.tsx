import { useEffect, useState } from "react";
import { addProposedChange, createChangeSet, fetchChangeSet, fetchTimetable, validateChangeSet } from "../api";
import FilterBar from "../components/FilterBar";
import LessonInspector, { type MoveParams } from "../components/LessonInspector";
import TimetableGrid from "../components/TimetableGrid";
import type { ReferenceData, TimetableEntry, TimetableResponse, ValidationResult, ViewType } from "../types";

interface Props {
  reference: ReferenceData;
  gridChangeSetId: number | null;
  onGridChangeSetCreated: (id: number) => void;
  onOpenChangeSet: (id: number) => void;
}

export default function TimetablePage({ reference, gridChangeSetId, onGridChangeSetCreated, onOpenChangeSet }: Props) {
  const [view, setView] = useState<ViewType>("teacher");
  const [code, setCode] = useState<string>(reference.teachers[0]?.code ?? "");
  const [timetable, setTimetable] = useState<TimetableResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedEntry, setSelectedEntry] = useState<TimetableEntry | null>(null);
  const [pendingEntryIds, setPendingEntryIds] = useState<Set<number>>(new Set());
  const [changeSetName, setChangeSetName] = useState<string | null>(null);

  useEffect(() => {
    if (!code) return;
    fetchTimetable(view, code)
      .then(setTimetable)
      .catch((e) => setError(String(e)));
  }, [view, code]);

  const loadPending = async (changeSetId: number) => {
    const detail = await fetchChangeSet(changeSetId);
    setChangeSetName(detail.name);
    setPendingEntryIds(new Set(detail.changes.map((c) => c.timetable_entry_id)));
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
        <TimetableGrid
          view={view}
          days={reference.days}
          periods={reference.periods}
          entries={timetable.entries}
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
