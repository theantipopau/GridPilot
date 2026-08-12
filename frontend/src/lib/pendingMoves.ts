import type { ChangeEndpoint, ProposedChange, ReferenceData, TimetableEntry } from "../types";

export function buildPendingMoveMap(changes: ProposedChange[]): Map<number, ChangeEndpoint> {
  const map = new Map<number, ChangeEndpoint>();
  for (const c of changes) map.set(c.timetable_entry_id, c.after);
  return map;
}

/** Relocates each entry with a pending move to its proposed slot, so the
 * grid renders the move live instead of just ringing the old cell -
 * `after` from the API is always a fully-resolved endpoint (the backend
 * fills in unchanged fields from the current entry, see
 * app/changes/service.py's add_proposed_change), so every field here can
 * be taken from it directly, no merging with the entry's old values. Only
 * day_code + period_no actually drive grid grouping (TimetableGrid.tsx/
 * MasterTimetableGrid.tsx key cells by those two fields) - the rest
 * (names, period_name, week_label) are recomputed too so the moved
 * entry's own display text and re-selecting it for a second edit stay
 * consistent, not just its position. */
export function applyPendingMoves(
  entries: TimetableEntry[],
  moves: Map<number, ChangeEndpoint>,
  reference: ReferenceData,
): TimetableEntry[] {
  if (moves.size === 0) return entries;

  return entries.map((e) => {
    const after = moves.get(e.entry_id);
    if (!after) return e;

    const day = after.day_code ? reference.days.find((d) => d.code === after.day_code) : undefined;
    const period = after.day_code && after.period_code
      ? reference.periods.find((p) => p.day_code === after.day_code && p.code === after.period_code)
      : undefined;
    const room = after.room_code ? reference.rooms.find((r) => r.code === after.room_code) : undefined;
    const teacher = after.teacher_code ? reference.teachers.find((t) => t.code === after.teacher_code) : undefined;

    return {
      ...e,
      day_code: after.day_code ?? e.day_code,
      day_no: day?.day_no ?? e.day_no,
      week_label: day?.week_label ?? e.week_label,
      period_code: after.period_code ?? e.period_code,
      period_no: period?.period_no ?? e.period_no,
      period_name: period?.name ?? e.period_name,
      entry_kind: period?.entry_kind ?? e.entry_kind,
      room_code: after.room_code,
      room_name: room?.name ?? null,
      teacher_code: after.teacher_code,
      teacher_first_name: teacher?.first_name ?? null,
      teacher_last_name: teacher?.last_name ?? null,
    };
  });
}
