import { useEffect, useState } from "react";
import { fetchFindings, fetchSuggestions, findTimetableEntries } from "../api";
import SuggestionCandidateCard from "./SuggestionCandidateCard";
import type { ReferenceData, SuggestionCandidate, TimetableEntry, TimetableEntryLookup, ValidationResult } from "../types";

export interface MoveParams {
  after_day_code?: string;
  after_period_code?: string;
  after_room_code?: string;
  after_teacher_code?: string;
  reason?: string;
}

interface Props {
  entry: TimetableEntry;
  reference: ReferenceData;
  changeSetName: string | null;
  onClose: () => void;
  onPropose: (params: MoveParams) => Promise<ValidationResult>;
  onOpenChangeSet: () => void;
}

const SUGGESTABLE_RULES = new Set(["teacher_double_booking", "room_double_booking", "class_room_instability"]);

type SuggestionsState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "not_applicable" }
  | { status: "ready"; candidates: SuggestionCandidate[] };

function uniquePeriodCodes(reference: ReferenceData): string[] {
  const seen = new Map<string, number>();
  for (const p of reference.periods) {
    if (!seen.has(p.code)) seen.set(p.code, p.period_no);
  }
  return [...seen.entries()].sort((a, b) => a[1] - b[1]).map(([code]) => code);
}

export default function LessonInspector({ entry, reference, changeSetName, onClose, onPropose, onOpenChangeSet }: Props) {
  const [tab, setTab] = useState<"move" | "suggestions">("move");
  const [afterDay, setAfterDay] = useState(entry.day_code);
  const [afterPeriod, setAfterPeriod] = useState(entry.period_code);
  const [afterRoom, setAfterRoom] = useState(entry.room_code ?? "");
  const [afterTeacher, setAfterTeacher] = useState(entry.teacher_code ?? "");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<ValidationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [occurrences, setOccurrences] = useState<TimetableEntryLookup[] | null>(null);
  const [suggestions, setSuggestions] = useState<SuggestionsState>({ status: "idle" });

  useEffect(() => {
    setOccurrences(null);
    if (!entry.class_code) return;
    findTimetableEntries({ class_code: entry.class_code })
      .then((r) => setOccurrences(r.entries))
      .catch(() => setOccurrences([]));
  }, [entry.class_code]);

  // A different lesson was clicked without closing the panel first - reset
  // the tab-scoped state rather than carrying it over from the old entry.
  useEffect(() => {
    setTab("move");
    setSuggestions({ status: "idle" });
  }, [entry.entry_id]);

  const loadSuggestions = async () => {
    setSuggestions({ status: "loading" });
    try {
      const { findings } = await fetchFindings();
      const matches = findings.filter((f) => {
        if (!SUGGESTABLE_RULES.has(f.rule_id)) return false;
        // class_room_instability findings cover the whole class, not one
        // slot - they carry no slot_refs at all, so match by class code
        // instead of the slot+teacher/room match the double-booking rules use.
        if (f.rule_id === "class_room_instability") {
          return f.entity_refs.some((e) => e.type === "class" && e.code === entry.class_code);
        }
        return (
          f.slot_refs.some((s) => s.day_code === entry.day_code && s.period_code === entry.period_code) &&
          f.entity_refs.some(
            (e) => (e.type === "teacher" && e.code === entry.teacher_code) || (e.type === "room" && e.code === entry.room_code),
          )
        );
      });
      if (matches.length === 0) {
        setSuggestions({ status: "not_applicable" });
        return;
      }
      const results = await Promise.all(matches.map((f) => fetchSuggestions(f.id)));
      const seen = new Set<string>();
      const candidates: SuggestionCandidate[] = [];
      for (const r of results) {
        for (const c of r.candidates) {
          if (c.entry_id !== entry.entry_id) continue; // only suggestions that move *this* lesson
          const key = `${c.after.day_code}|${c.after.period_code}|${c.after.room_code}`;
          if (seen.has(key)) continue;
          seen.add(key);
          candidates.push(c);
        }
      }
      setSuggestions({ status: "ready", candidates });
    } catch {
      setSuggestions({ status: "not_applicable" });
    }
  };

  const periodCodes = uniquePeriodCodes(reference);
  const teacherName = entry.teacher_last_name
    ? `${entry.teacher_last_name}, ${entry.teacher_first_name ?? ""}`.trim()
    : null;

  const hasChange =
    afterDay !== entry.day_code ||
    afterPeriod !== entry.period_code ||
    afterRoom !== (entry.room_code ?? "") ||
    afterTeacher !== (entry.teacher_code ?? "");

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      // Day and period must travel together - the API rejects one without
      // the other (a period code alone, e.g. "P2", repeats on every day,
      // see app/api/change_sets.py) - so always send both together rather
      // than diffing them independently, even if only one actually moved.
      const slotChanged = afterDay !== entry.day_code || afterPeriod !== entry.period_code;
      const validation = await onPropose({
        after_day_code: slotChanged ? afterDay : undefined,
        after_period_code: slotChanged ? afterPeriod : undefined,
        after_room_code: afterRoom !== (entry.room_code ?? "") ? afterRoom || undefined : undefined,
        after_teacher_code: afterTeacher !== (entry.teacher_code ?? "") ? afterTeacher || undefined : undefined,
        reason: reason || undefined,
      });
      setResult(validation);
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  };

  const applySuggestion = async (c: SuggestionCandidate) => {
    setSubmitting(true);
    setError(null);
    try {
      const validation = await onPropose({
        after_day_code: c.after.day_code,
        after_period_code: c.after.period_code,
        after_room_code: c.after.room_code ?? undefined,
        reason: "Applied from a suggested fix",
      });
      setResult(validation);
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-y-0 right-0 z-40 flex w-96 flex-col overflow-y-auto border-l border-slate-200 bg-white p-5 shadow-xl">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h2 className="text-base font-semibold text-slate-900">
            {entry.class_code ?? entry.subject_name ?? "Lesson"}
          </h2>
          <p className="text-xs text-slate-500">{entry.roll_class_code}</p>
        </div>
        <button type="button" onClick={onClose} className="text-sm text-slate-400 hover:text-slate-700">
          ✕
        </button>
      </div>

      <dl className="mb-5 grid grid-cols-2 gap-y-2 text-xs">
        <dt className="text-slate-400">Current slot</dt>
        <dd className="text-slate-700">
          {entry.day_code} · {entry.period_code}
        </dd>
        <dt className="text-slate-400">Room</dt>
        <dd className="text-slate-700">{entry.room_code ?? "—"}</dd>
        <dt className="text-slate-400">Teacher</dt>
        <dd className="text-slate-700">{teacherName ?? "—"}</dd>
      </dl>

      {entry.class_code && <OtherOccurrences classCode={entry.class_code} currentEntryId={entry.entry_id} occurrences={occurrences} />}

      {!result && (
        <>
          <div className="mb-3 flex gap-1 rounded-md bg-slate-100 p-1">
            <button
              type="button"
              onClick={() => setTab("move")}
              className={`flex-1 rounded px-2 py-1.5 text-xs font-medium transition-colors duration-150 ${
                tab === "move" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
              }`}
            >
              Move manually
            </button>
            <button
              type="button"
              onClick={() => {
                setTab("suggestions");
                if (suggestions.status === "idle") loadSuggestions();
              }}
              className={`flex-1 rounded px-2 py-1.5 text-xs font-medium transition-colors duration-150 ${
                tab === "suggestions" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
              }`}
            >
              Suggested fixes
            </button>
          </div>

          {tab === "move" && (
            <>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Move to</h3>
              <div className="mb-3 grid grid-cols-2 gap-2">
                <select
                  value={afterDay}
                  onChange={(e) => setAfterDay(e.target.value)}
                  className="rounded border border-slate-300 px-2 py-1 text-sm"
                >
                  {reference.days.map((d) => (
                    <option key={d.code} value={d.code}>
                      {d.code}
                    </option>
                  ))}
                </select>
                <select
                  value={afterPeriod}
                  onChange={(e) => setAfterPeriod(e.target.value)}
                  className="rounded border border-slate-300 px-2 py-1 text-sm"
                >
                  {periodCodes.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
                <select
                  value={afterRoom}
                  onChange={(e) => setAfterRoom(e.target.value)}
                  className="rounded border border-slate-300 px-2 py-1 text-sm"
                >
                  <option value="">(no room)</option>
                  {reference.rooms.map((r) => (
                    <option key={r.code} value={r.code}>
                      {r.code}
                    </option>
                  ))}
                </select>
                <select
                  value={afterTeacher}
                  onChange={(e) => setAfterTeacher(e.target.value)}
                  className="rounded border border-slate-300 px-2 py-1 text-sm"
                >
                  <option value="">(no teacher)</option>
                  {reference.teachers.map((t) => (
                    <option key={t.code} value={t.code}>
                      {t.code}
                    </option>
                  ))}
                </select>
              </div>
              <input
                placeholder="Reason (optional)"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="mb-3 w-full rounded border border-slate-300 px-2 py-1 text-sm"
              />
              {error && <p className="mb-3 rounded bg-red-50 p-2 text-xs text-red-700">{error}</p>}
              <button
                type="button"
                onClick={submit}
                disabled={!hasChange || submitting}
                className="w-full rounded-md bg-sky-600 px-3 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-300"
              >
                {submitting ? "Checking…" : "Propose this move"}
              </button>
              {!hasChange && <p className="mt-2 text-center text-xs text-slate-400">Change something to propose a move.</p>}
            </>
          )}

          {tab === "suggestions" && (
            <>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Suggested fixes</h3>
              {suggestions.status === "loading" && <p className="text-xs text-slate-400">Searching for valid alternatives…</p>}
              {suggestions.status === "not_applicable" && (
                <p className="text-xs text-slate-400">
                  This lesson isn't part of an open teacher/room double-booking or room-instability finding - suggestions don't
                  cover other finding types yet.
                </p>
              )}
              {suggestions.status === "ready" && suggestions.candidates.length === 0 && (
                <p className="text-xs text-slate-400">No valid alternative found for this lesson that doesn't create a new clash.</p>
              )}
              {suggestions.status === "ready" && suggestions.candidates.length > 0 && (
                <div className="flex max-h-96 flex-col gap-1.5 overflow-y-auto pr-1">
                  {suggestions.candidates.map((c, i) => (
                    <SuggestionCandidateCard key={i} candidate={c} onApply={() => applySuggestion(c)} applying={submitting} />
                  ))}
                </div>
              )}
              {error && <p className="mt-3 rounded bg-red-50 p-2 text-xs text-red-700">{error}</p>}
            </>
          )}
        </>
      )}

      {result && (
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
          <p className={`mb-2 font-medium ${result.valid ? "text-emerald-700" : "text-amber-700"}`}>
            {result.valid ? "No new clashes introduced." : result.reason}
          </p>
          {result.introduced_findings.length > 0 && (
            <>
              <p className="text-xs font-medium text-red-700">Introduces:</p>
              <ul className="mb-2 list-disc pl-4 text-xs text-red-700">
                {result.introduced_findings.map((f, i) => (
                  <li key={i}>{f.title}</li>
                ))}
              </ul>
            </>
          )}
          {result.resolved_findings.length > 0 && (
            <>
              <p className="text-xs font-medium text-emerald-700">Resolves:</p>
              <ul className="mb-2 list-disc pl-4 text-xs text-emerald-700">
                {result.resolved_findings.map((f, i) => (
                  <li key={i}>{f.title}</li>
                ))}
              </ul>
            </>
          )}
          <p className="mb-3 text-xs text-slate-500">
            Added to change set "{changeSetName}" - not written to the timetable until approved.
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onOpenChangeSet}
              className="flex-1 rounded-md bg-slate-700 px-3 py-2 text-xs font-medium text-white hover:bg-slate-800"
            >
              Review in Change Sets
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-slate-300 px-3 py-2 text-xs text-slate-600 hover:bg-slate-100"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function OtherOccurrences({
  classCode,
  currentEntryId,
  occurrences,
}: {
  classCode: string;
  currentEntryId: number;
  occurrences: TimetableEntryLookup[] | null;
}) {
  if (occurrences === null) {
    return <p className="mb-4 text-xs text-slate-400">Loading other occurrences of {classCode}…</p>;
  }

  const others = occurrences.filter((o) => o.entry_id !== currentEntryId);
  if (others.length === 0) return null;

  const roomCount = new Set(others.map((o) => o.room_code).filter(Boolean)).size;
  const teacherCount = new Set(others.map((o) => o.teacher_code).filter(Boolean)).size;

  return (
    <div className="mb-5">
      <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
        Also on the timetable ({others.length})
      </h3>
      {(roomCount > 1 || teacherCount > 1) && (
        <p className="mb-2 text-xs text-amber-700">
          {roomCount > 1 && `${roomCount} different rooms`}
          {roomCount > 1 && teacherCount > 1 && " · "}
          {teacherCount > 1 && `${teacherCount} different teachers`}
          {" across the cycle"}
        </p>
      )}
      <ul className="max-h-40 overflow-y-auto rounded border border-slate-200 text-xs">
        {others.map((o) => (
          <li key={o.entry_id} className="flex items-center justify-between gap-2 border-b border-slate-100 px-2 py-1 last:border-b-0">
            <span className="text-slate-500">
              {o.day_code} · {o.period_code}
            </span>
            <span className="text-slate-700">
              {o.room_code ?? "no room"} · {o.teacher_code ?? "no teacher"}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
