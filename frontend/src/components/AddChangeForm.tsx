import { useState } from "react";
import { findTimetableEntries } from "../api";
import type { ReferenceData, TimetableEntryLookup } from "../types";
import { Button, Input, RadioGroup, Select } from "../ui";

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
    <section className="rounded-lg border border-border bg-surface-sunken p-4">
      <h3 className="text-section-title">Propose a change</h3>
      <p className="mt-0.5 text-meta">Find the lesson to move, then set only the fields that should change.</p>

      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-5">
        <Input size="sm" aria-label="Day code" placeholder="Day code" value={dayCode} onChange={(e) => setDayCode(e.target.value)} />
        <Input size="sm" aria-label="Period code" placeholder="Period code" value={periodCode} onChange={(e) => setPeriodCode(e.target.value)} />
        <Input size="sm" aria-label="Teacher code" placeholder="Teacher code" value={teacherCode} onChange={(e) => setTeacherCode(e.target.value)} />
        <Input size="sm" aria-label="Room code" placeholder="Room code" value={roomCode} onChange={(e) => setRoomCode(e.target.value)} />
        <Input size="sm" aria-label="Class code" placeholder="Class code" value={classCode} onChange={(e) => setClassCode(e.target.value)} />
      </div>
      <Button size="sm" variant="secondary" loading={searching} className="mt-2" onClick={search}>
        {searching ? "Searching…" : "Find lesson"}
      </Button>

      {matches && (
        <div className="mt-3">
          {matches.length === 0 ? (
            <p className="text-meta">No matching lessons.</p>
          ) : (
            <RadioGroup
              legend="Matching lessons"
              name="entry"
              className="max-h-56 overflow-y-auto"
              value={selectedEntryId != null ? String(selectedEntryId) : ""}
              onChange={(v) => setSelectedEntryId(Number(v))}
              options={matches.map((m) => ({
                value: String(m.entry_id),
                label: (
                  <span className="nums text-code">
                    {m.day_code} {m.period_code} &middot; {m.class_code ?? "(no class)"} &middot;{" "}
                    {m.teacher_code ?? "no teacher"} &middot; {m.room_code ?? "no room"} &middot; roll{" "}
                    {m.roll_class_code}
                  </span>
                ),
              }))}
            />
          )}
        </div>
      )}

      {selectedEntryId && (
        <div className="mt-4 border-t border-border pt-3">
          <p className="text-label">Move to (leave blank to keep unchanged)</p>
          <div className="mt-1.5 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Select
              size="sm"
              label="Day"
              value={afterDay}
              onChange={setAfterDay}
              options={[{ value: "", label: "Day (unchanged)" }, ...reference.days.map((d) => ({ value: d.code, label: d.code }))]}
            />
            <Select
              size="sm"
              label="Period"
              value={afterPeriod}
              onChange={setAfterPeriod}
              options={[{ value: "", label: "Period (unchanged)" }, ...periodCodes.map((c) => ({ value: c, label: c }))]}
            />
            <Select
              size="sm"
              label="Room"
              value={afterRoom}
              onChange={setAfterRoom}
              options={[{ value: "", label: "Room (unchanged)" }, ...reference.rooms.map((r) => ({ value: r.code, label: r.code }))]}
            />
            <Select
              size="sm"
              label="Teacher"
              value={afterTeacher}
              onChange={setAfterTeacher}
              options={[{ value: "", label: "Teacher (unchanged)" }, ...reference.teachers.map((t) => ({ value: t.code, label: t.code }))]}
            />
          </div>
          <Input
            size="sm"
            containerClassName="mt-2"
            aria-label="Reason"
            placeholder="Reason (optional)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <Button
            size="sm"
            variant="accent"
            loading={submitting}
            className="mt-2"
            onClick={submit}
          >
            {submitting ? "Adding…" : "Add proposed change"}
          </Button>
        </div>
      )}
    </section>
  );
}
