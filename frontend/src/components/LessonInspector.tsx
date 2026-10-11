import { useEffect, useState } from "react";
import { fetchFindings, fetchLegalSlots, fetchRoomAdvice, fetchSuggestions, findTimetableEntries } from "../api";
import SuggestionCandidateCard from "./SuggestionCandidateCard";
import { Alert, Badge, Button, Drawer, Tabs } from "../ui";
import type {
  LegalSlot,
  ReferenceData,
  RoomAdviceResponse,
  SuggestionCandidate,
  TimetableEntry,
  TimetableEntryLookup,
  ValidationResult,
} from "../types";

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

const SUGGESTABLE_RULES = new Set([
  "teacher_double_booking", "room_double_booking", "class_room_instability", "class_teacher_inconsistency",
]);
const WHOLE_CLASS_RULES = new Set(["class_room_instability", "class_teacher_inconsistency"]);

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
  const [tab, setTab] = useState<"move" | "suggestions" | "ai">("move");
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
  const [legalSlots, setLegalSlots] = useState<Map<string, LegalSlot> | null>(null);
  const [aiAdvice, setAiAdvice] = useState<RoomAdviceResponse | null>(null);
  const [aiError, setAiError] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);

  useEffect(() => {
    setOccurrences(null);
    if (!entry.class_code) return;
    findTimetableEntries({ class_code: entry.class_code })
      .then((r) => setOccurrences(r.entries))
      .catch(() => setOccurrences([]));
  }, [entry.class_code]);

  // docs/roadmap-v3.md 4.4: live legal-slot feedback for the move-manually
  // dropdowns below - fetched once per selected lesson, not per keystroke.
  // A fetch failure just means no shading, not a blocking error - the
  // dropdowns still work exactly as before, "Propose this move" is still
  // the real check.
  useEffect(() => {
    setLegalSlots(null);
    fetchLegalSlots(entry.entry_id)
      .then((r) => setLegalSlots(new Map(r.slots.map((s) => [`${s.day_code}|${s.period_code}`, s]))))
      .catch(() => setLegalSlots(null));
  }, [entry.entry_id]);

  // A different lesson was clicked without closing the panel first - reset
  // the tab-scoped state rather than carrying it over from the old entry.
  useEffect(() => {
    setTab("move");
    setSuggestions({ status: "idle" });
    setAiAdvice(null);
    setAiError(null);
  }, [entry.entry_id]);

  const loadAiAdvice = async () => {
    setAiLoading(true);
    setAiError(null);
    try {
      setAiAdvice(await fetchRoomAdvice(entry.entry_id));
    } catch (e) {
      setAiError(String(e));
    } finally {
      setAiLoading(false);
    }
  };

  const loadSuggestions = async () => {
    setSuggestions({ status: "loading" });
    try {
      const { findings } = await fetchFindings();
      const matches = findings.filter((f) => {
        if (!SUGGESTABLE_RULES.has(f.rule_id)) return false;
        // class_room_instability / class_teacher_inconsistency findings cover
        // the whole class, not one slot - they carry no slot_refs at all, so
        // match by class code instead of the slot+teacher/room match the
        // double-booking rules use.
        if (WHOLE_CLASS_RULES.has(f.rule_id)) {
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
          const key = `${c.after.day_code}|${c.after.period_code}|${c.after.room_code}|${c.after.teacher_code}`;
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

  // docs/roadmap-v3.md 4.4: cheap, live feedback on the currently-selected
  // day/period/room, computed from legalSlots (or null before it loads /
  // if the fetch failed - in which case every dropdown just behaves as it
  // always did, no shading). Room legality is only meaningful once the
  // slot itself is free; an illegal slot makes every room moot.
  const currentSlot = legalSlots?.get(`${afterDay}|${afterPeriod}`) ?? null;
  const roomIsLegal = !currentSlot || !currentSlot.legal || afterRoom === "" || currentSlot.legal_room_codes.includes(afterRoom);
  const isDayLegalFor = (dayCode: string) => legalSlots?.get(`${dayCode}|${afterPeriod}`)?.legal !== false;
  const isPeriodLegalFor = (periodCode: string) => legalSlots?.get(`${afterDay}|${periodCode}`)?.legal !== false;

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
        after_teacher_code: c.after.teacher_code !== c.before.teacher_code ? c.after.teacher_code ?? undefined : undefined,
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
    <Drawer
      open
      onClose={onClose}
      title={entry.class_code ?? entry.subject_name ?? "Lesson"}
      subtitle={entry.roll_class_code}
      scrim="none"
      meta={
        <>
          <Badge size="sm" tone="neutral" variant="outline">
            {entry.day_code} · {entry.period_code}
          </Badge>
          <Badge size="sm" tone="neutral" variant="outline">
            {entry.room_code ?? "no room"}
          </Badge>
          <Badge size="sm" tone="neutral" variant="outline">
            {entry.teacher_code ?? "no teacher"}
          </Badge>
          {changeSetName && (
            <Badge size="sm" tone="accent">
              draft: {changeSetName}
            </Badge>
          )}
        </>
      }
    >
      <dl className="mb-5 grid grid-cols-2 gap-y-2 text-xs">
        <dt className="text-ink-muted">Current slot</dt>
        <dd className="text-slate-700">
          {entry.day_code} · {entry.period_code}
        </dd>
        <dt className="text-ink-muted">Room</dt>
        <dd className="text-slate-700">{entry.room_code ?? "—"}</dd>
        <dt className="text-ink-muted">Teacher</dt>
        <dd className="text-slate-700">{teacherName ?? "—"}</dd>
      </dl>

      {entry.class_code && <OtherOccurrences classCode={entry.class_code} currentEntryId={entry.entry_id} occurrences={occurrences} />}

      {!result && (
        <>
          <Tabs
            label="Lesson actions"
            variant="segmented"
            size="sm"
            className="mb-3 w-full [&>div]:w-full"
            value={tab}
            onChange={(next) => {
              setTab(next);
              if (next === "suggestions" && suggestions.status === "idle") void loadSuggestions();
              if (next === "ai" && !aiAdvice && !aiLoading) void loadAiAdvice();
            }}
            tabs={[
              { id: "move", label: "Move manually" },
              { id: "suggestions", label: "Suggested fixes" },
              { id: "ai", label: "AI advice" },
            ]}
          />

          {tab === "move" && (
            <>
              <h3 className="mb-2 text-label">Move to</h3>
              <div className="mb-2 grid grid-cols-2 gap-2">
                <select
                  value={afterDay}
                  onChange={(e) => setAfterDay(e.target.value)}
                  className="rounded border border-slate-300 px-2 py-1 text-sm"
                >
                  {reference.days.map((d) => (
                    <option key={d.code} value={d.code}>
                      {d.code}
                      {!isDayLegalFor(d.code) ? " ⚠" : ""}
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
                      {!isPeriodLegalFor(c) ? " ⚠" : ""}
                    </option>
                  ))}
                </select>
                <select
                  value={afterRoom}
                  onChange={(e) => setAfterRoom(e.target.value)}
                  className="rounded border border-slate-300 px-2 py-1 text-sm"
                >
                  <option value="">(no room)</option>
                  {reference.rooms.map((r) => {
                    const roomLegal = !currentSlot || !currentSlot.legal || currentSlot.legal_room_codes.includes(r.code);
                    return (
                      <option key={r.code} value={r.code}>
                        {r.code}
                        {!roomLegal ? " ⚠" : ""}
                      </option>
                    );
                  })}
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
              {legalSlots && (
                <p
                  className={`mb-3 text-xs ${
                    currentSlot && (!currentSlot.legal || !roomIsLegal) ? "text-warning" : "text-success"
                  }`}
                  title="Cheap check: teacher/student availability and room type/pool/capacity - Propose this move still runs the real, authoritative check"
                >
                  {currentSlot && !currentSlot.legal
                    ? "⚠ Not free - the teacher or a shared student already has something else then."
                    : currentSlot && !roomIsLegal
                      ? `⚠ ${afterRoom || "This room"} isn't free at this slot${currentSlot.legal_room_codes.length ? ` - try: ${currentSlot.legal_room_codes.slice(0, 5).join(", ")}` : ""}.`
                      : "✓ This slot and room look free."}
                </p>
              )}
              <input
                aria-label="Reason (optional)"
                placeholder="Reason (optional)"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="mb-3 h-8.5 w-full rounded-md border border-border-strong bg-surface px-2.5 text-sm text-text-primary placeholder:text-text-muted focus:border-focus focus:shadow-[0_0_0_3px_color-mix(in_oklab,var(--color-focus)_22%,transparent)] focus:outline-none"
              />
              {error && (
                <Alert tone="critical" className="mb-3">
                  {error}
                </Alert>
              )}
              <Button
                variant="primary"
                block
                onClick={submit}
                disabled={!hasChange}
                loading={submitting}
              >
                {submitting ? "Checking…" : "Propose this move"}
              </Button>
              {!hasChange && <p className="mt-2 text-center text-meta">Change something to propose a move.</p>}
            </>
          )}

          {tab === "ai" && (
            <>
              <h3 className="mb-2 text-label">AI room advice</h3>
              {aiLoading && <p className="text-xs text-ink-muted">Asking the local advisor…</p>}
              {aiError && (
                <Alert tone="warning" className="mb-2">
                  {aiError}
                </Alert>
              )}
              {aiAdvice && (
                <div className="flex flex-col gap-3">
                  <div className="rounded-lg border border-border bg-surface-sunken p-3 text-sm">
                    <p className="text-text-secondary">{aiAdvice.explanation}</p>
                  </div>
                  <details className="rounded-lg border border-border bg-surface p-3">
                    <summary className="cursor-pointer text-label">Facts behind this (computed, not generated)</summary>
                    <ul className="mt-2 flex flex-col gap-1 text-xs text-text-secondary">
                      <li>
                        {aiAdvice.facts.legal_slots_with_rooms.length} legal slot(s) where this lesson could go, with the
                        rooms free in each.
                      </li>
                      {aiAdvice.facts.class_room_usage_this_cycle.length > 1 && (
                        <li>
                          This class already use(s) {aiAdvice.facts.class_room_usage_this_cycle.length} different room(s)
                          across the cycle.
                        </li>
                      )}
                      <li>Advice is explanation only - applying a move always goes through the normal propose/validate flow.</li>
                    </ul>
                  </details>
                  <p className="text-meta text-text-muted">Model: {aiAdvice.model}</p>
                </div>
              )}
            </>
          )}

          {tab === "suggestions" && (
            <>
              <h3 className="mb-2 text-label">Suggested fixes</h3>
              {suggestions.status === "loading" && <p className="text-xs text-ink-muted">Searching for valid alternatives…</p>}
              {suggestions.status === "not_applicable" && (
                <p className="text-xs text-ink-muted">
                  This lesson isn't part of an open teacher/room double-booking or room-instability finding - suggestions don't
                  cover other finding types yet.
                </p>
              )}
              {suggestions.status === "ready" && suggestions.candidates.length === 0 && (
                <p className="text-xs text-ink-muted">No valid alternative found for this lesson that doesn't create a new clash.</p>
              )}
              {suggestions.status === "ready" && suggestions.candidates.length > 0 && (
                <div className="flex max-h-96 flex-col gap-1.5 overflow-y-auto pr-1">
                  {suggestions.candidates.map((c, i) => (
                    <SuggestionCandidateCard key={i} candidate={c} onApply={() => applySuggestion(c)} applying={submitting} />
                  ))}
                </div>
              )}
              {error && (
                <Alert tone="critical" className="mt-3">
                  {error}
                </Alert>
              )}
            </>
          )}
        </>
      )}

      {result && (
        <div className="rounded-lg border border-border bg-surface p-3 text-sm">
          <p className={`mb-2 font-medium ${result.valid ? "text-success" : "text-warning"}`}>
            {result.valid ? "No new clashes introduced." : result.reason}
          </p>
          {result.introduced_findings.length > 0 && (
            <>
              <p className="text-xs font-medium text-critical">Introduces:</p>
              <ul className="mb-2 list-disc pl-4 text-xs text-critical">
                {result.introduced_findings.map((f, i) => (
                  <li key={i}>{f.title}</li>
                ))}
              </ul>
            </>
          )}
          {result.resolved_findings.length > 0 && (
            <>
              <p className="text-xs font-medium text-success">Resolves:</p>
              <ul className="mb-2 list-disc pl-4 text-xs text-success">
                {result.resolved_findings.map((f, i) => (
                  <li key={i}>{f.title}</li>
                ))}
              </ul>
            </>
          )}
          <p className="mb-3 text-meta">
            Added to change set "{changeSetName}" - not written to the timetable until approved.
          </p>
          <div className="flex gap-2">
            <Button size="sm" variant="primary" className="flex-1" onClick={onOpenChangeSet}>
              Review in Change Sets
            </Button>
            <Button size="sm" onClick={onClose}>
              Close
            </Button>
          </div>
        </div>
      )}
    </Drawer>
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
    return <p className="mb-4 text-xs text-ink-muted">Loading other occurrences of {classCode}…</p>;
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
