import { useState } from "react";
import { findTimetableEntries } from "../api";
import type { ReferenceData, TimetableEntryLookup } from "../types";

interface Prefill {
  day_code?: string;
  period_code?: string;
  teacher_code?: string;
  room_code?: string;
  class_code?: string;
  finding_id?: number;
}

interface Props {
  reference: ReferenceData;
  prefill?: Prefill;
  onSubmit: (params: {
    timetable_entry_id: number;
    after_day_code?: string;
    after_period_code?: string;
    after_room_code?: string;
    after_teacher_code?: string;
    reason?: string;
    finding_ids?: number[];
  }) => Promise<void>;
}

const uniquePeriodCodes = (reference: ReferenceData) => {
  const seen = new Map<string, number>();
  for (const p of reference.periods) {
    if (!seen.has(p.code)) seen.set(p.code, p.period_no);
  }
  return [...seen.entries()].sort((a, b) => a[1] - b[1]).map(([code]) => code);
};

export default function AddChangeForm({ reference, prefill, onSubmit }: Props) {
  const [dayCode, setDayCode] = useState(prefill?.day_code ?? "");
  const [periodCode, setPeriodCode] = useState(prefill?.period_code ?? "");
  const [teacherCode, setTeacherCode] = useState(prefill?.teacher_code ?? "");
  const [roomCode, setRoomCode] = useState(prefill?.room_code ?? "");
  const [classCode, setClassCode] = useState(prefill?.class_code ?? "");

  const [matches, setMatches] = useState<TimetableEntryLookup[] | null>(null);
  const [selectedEntryId, setSelectedEntryId] = useState<number | null>(null);
  const [searching, setSearching] = useState(false);

  const [afterDay, setAfterDay] = useState("");
  const [afterPeriod, setAfterPeriod] = useState("");
  const [afterRoom, setAfterRoom] = useState("");
  const [afterTeacher, setAfterTeacher] = useState("");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const periodCodes = uniquePeriodCodes(reference);

  const search = async () => {
    setSearching(true);
    try {
      const res = await findTimetableEntries({
        day_code: dayCode || undefined,
        period_code: periodCode || undefined,
        teacher_code: teacherCode || undefined,
        room_code: roomCode || undefined,
        class_code: classCode || undefined,
      });
      setMatches(res.entries);
      setSelectedEntryId(null);
    } finally {
      setSearching(false);
    }
  };

  const submit = async () => {
    if (!selectedEntryId) return;
    setSubmitting(true);
    try {
      await onSubmit({
        timetable_entry_id: selectedEntryId,
        after_day_code: afterDay || undefined,
        after_period_code: afterPeriod || undefined,
        after_room_code: afterRoom || undefined,
        after_teacher_code: afterTeacher || undefined,
        reason: reason || undefined,
        finding_ids: prefill?.finding_id ? [prefill.finding_id] : undefined,
      });
      setMatches(null);
      setSelectedEntryId(null);
      setAfterDay("");
      setAfterPeriod("");
      setAfterRoom("");
      setAfterTeacher("");
      setReason("");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <h3 className="mb-3 text-sm font-semibold text-slate-700">Propose a change</h3>

      <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-5">
        <input placeholder="Day code" value={dayCode} onChange={(e) => setDayCode(e.target.value)} className="rounded border border-slate-300 px-2 py-1 text-sm" />
        <input placeholder="Period code" value={periodCode} onChange={(e) => setPeriodCode(e.target.value)} className="rounded border border-slate-300 px-2 py-1 text-sm" />
        <input placeholder="Teacher code" value={teacherCode} onChange={(e) => setTeacherCode(e.target.value)} className="rounded border border-slate-300 px-2 py-1 text-sm" />
        <input placeholder="Room code" value={roomCode} onChange={(e) => setRoomCode(e.target.value)} className="rounded border border-slate-300 px-2 py-1 text-sm" />
        <input placeholder="Class code" value={classCode} onChange={(e) => setClassCode(e.target.value)} className="rounded border border-slate-300 px-2 py-1 text-sm" />
      </div>
      <button type="button" onClick={search} disabled={searching} className="rounded-md bg-slate-700 px-3 py-1 text-xs font-medium text-white disabled:opacity-50">
        {searching ? "Searching…" : "Find lesson"}
      </button>

      {matches && (
        <div className="mt-3">
          {matches.length === 0 ? (
            <p className="text-xs text-slate-400">No matching lessons.</p>
          ) : (
            <div className="flex flex-col gap-1">
              {matches.map((m) => (
                <label key={m.entry_id} className="flex items-center gap-2 rounded border border-slate-200 bg-white p-2 text-xs">
                  <input type="radio" name="entry" checked={selectedEntryId === m.entry_id} onChange={() => setSelectedEntryId(m.entry_id)} />
                  <span>
                    {m.day_code} {m.period_code} - {m.class_code ?? "(no class)"} - {m.teacher_code ?? "no teacher"} - {m.room_code ?? "no room"} - roll {m.roll_class_code}
                  </span>
                </label>
              ))}
            </div>
          )}
        </div>
      )}

      {selectedEntryId && (
        <div className="mt-4 border-t border-slate-200 pt-3">
          <p className="mb-2 text-xs font-medium text-slate-600">Move to (leave blank to keep unchanged):</p>
          <div className="mb-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <select value={afterDay} onChange={(e) => setAfterDay(e.target.value)} className="rounded border border-slate-300 px-2 py-1 text-xs">
              <option value="">Day (unchanged)</option>
              {reference.days.map((d) => <option key={d.code} value={d.code}>{d.code}</option>)}
            </select>
            <select value={afterPeriod} onChange={(e) => setAfterPeriod(e.target.value)} className="rounded border border-slate-300 px-2 py-1 text-xs">
              <option value="">Period (unchanged)</option>
              {periodCodes.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <select value={afterRoom} onChange={(e) => setAfterRoom(e.target.value)} className="rounded border border-slate-300 px-2 py-1 text-xs">
              <option value="">Room (unchanged)</option>
              {reference.rooms.map((r) => <option key={r.code} value={r.code}>{r.code}</option>)}
            </select>
            <select value={afterTeacher} onChange={(e) => setAfterTeacher(e.target.value)} className="rounded border border-slate-300 px-2 py-1 text-xs">
              <option value="">Teacher (unchanged)</option>
              {reference.teachers.map((t) => <option key={t.code} value={t.code}>{t.code}</option>)}
            </select>
          </div>
          <input placeholder="Reason (optional)" value={reason} onChange={(e) => setReason(e.target.value)} className="mb-2 w-full rounded border border-slate-300 px-2 py-1 text-xs" />
          <button type="button" onClick={submit} disabled={submitting} className="rounded-md bg-sky-600 px-3 py-1 text-xs font-medium text-white disabled:opacity-50">
            {submitting ? "Adding…" : "Add proposed change"}
          </button>
        </div>
      )}
    </div>
  );
}
