import type { ChangeEndpoint, ProposedChange, ReferenceData, TimetableEntry } from "../types";

export function buildPendingMoveMap(changes: ProposedChange[]): Map<number, ChangeEndpoint> {
  const map = new Map<number, ChangeEndpoint>();
  for (const c of changes) map.set(c.timetable_entry_id, c.after);
  return map;
}

/** An entry as it still exists in the imported source, alongside where a
 *  draft change set proposes it should go. The grid renders these as a ghost
 *  in the ORIGINAL slot: applyPendingMoves makes the destination show the
 *  proposal, and the ghost is what stops the origin from looking like the
 *  lesson simply vanished (docs/ui-ux-audit.md §3.2 - "the source slot looks
 *  empty"). Never shown as an applied fact: everything about a ghost is
 *  worded as "proposed". */
export interface GhostEntry {
  entry: TimetableEntry;
  after: ChangeEndpoint;
  /** Finding ids this change addresses (used for "resolves" copy). */
  findingIds: number[];
}

/** Pairs each pending change with its pre-move entry, straight from the
 *  source list - no guessing: the API's `before` endpoint always equals the
 *  imported entry, and this keeps the ghost byte-for-byte identical to what
 *  the live grid shows. */
export function buildGhosts(sourceEntries: TimetableEntry[], changes: ProposedChange[]): GhostEntry[] {
  const byId = new Map(sourceEntries.map((e) => [e.entry_id, e]));
  // One ghost per ENTRY, last change wins - exactly the semantics of
  // buildPendingMoveMap, so the destination the grid renders and the origin
  // the ghost points at can never name different target slots (a change set
  // can legitimately hold several changes for one entry). Map iteration
  // order is insertion order, and re-assignment doesn't move the key, so the
  // ghost stays in the entry's original chronological slot.
  const ghosts = new Map<number, GhostEntry>();
  for (const c of changes) {
    const entry = byId.get(c.timetable_entry_id);
    if (!entry) continue;
    ghosts.set(c.timetable_entry_id, { entry, after: c.after, findingIds: c.finding_ids });
  }
  return [...ghosts.values()];
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
