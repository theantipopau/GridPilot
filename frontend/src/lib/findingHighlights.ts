import type { Finding, Severity } from "../types";

export interface CellHighlight {
  severity: Severity;
  titles: string[];
}

interface HighlightableEntry {
  day_code: string;
  period_code: string;
  teacher_code?: string | null;
  room_code?: string | null;
  class_code?: string | null;
}

const SEVERITY_RANK: Record<Severity, number> = { info: 0, warning: 1, critical: 2 };

/** Index open findings by slot + entity so a grid can look up "does this
 * exact lesson have a live problem" in O(1) per cell, instead of the grid
 * re-deriving its own notion of a clash from raw entries (which can't tell
 * an approved composite from a real double-booking, and can't see
 * student_double_booking or room_capacity_exceeded at all - those only
 * exist as findings, not as "two entries landed in one cell"). Findings
 * with no slot_refs (class_room_instability, teacher load, ...) describe a
 * whole class/teacher rather than one lesson, so they're deliberately
 * excluded - a grid cell can't usefully show "this class is inconsistent
 * across the whole cycle." */
export function buildFindingHighlightIndex(findings: Finding[]): Map<string, CellHighlight> {
  const index = new Map<string, CellHighlight>();

  for (const f of findings) {
    if (f.status !== "OPEN" || f.slot_refs.length === 0) continue;
    for (const slot of f.slot_refs) {
      for (const ref of f.entity_refs) {
        if (ref.type !== "teacher" && ref.type !== "room" && ref.type !== "class") continue;
        const key = `${slot.day_code}|${slot.period_code}|${ref.type}:${ref.code}`;
        const existing = index.get(key);
        if (existing) {
          existing.titles.push(f.title);
          if (SEVERITY_RANK[f.severity] > SEVERITY_RANK[existing.severity]) existing.severity = f.severity;
        } else {
          index.set(key, { severity: f.severity, titles: [f.title] });
        }
      }
    }
  }
  return index;
}

/** A lesson can match on teacher, room, and class independently (e.g. a
 * teacher double-booking and a room-capacity issue on the very same
 * lesson) - merge to the worst severity and the union of titles rather
 * than only reporting whichever key happened to be checked first. */
export function highlightForEntry(index: Map<string, CellHighlight>, entry: HighlightableEntry): CellHighlight | null {
  const keys = [
    entry.teacher_code && `${entry.day_code}|${entry.period_code}|teacher:${entry.teacher_code}`,
    entry.room_code && `${entry.day_code}|${entry.period_code}|room:${entry.room_code}`,
    entry.class_code && `${entry.day_code}|${entry.period_code}|class:${entry.class_code}`,
  ].filter((k): k is string => !!k);

  const titles = new Set<string>();
  let severity: Severity | null = null;
  for (const key of keys) {
    const hit = index.get(key);
    if (!hit) continue;
    hit.titles.forEach((t) => titles.add(t));
    if (!severity || SEVERITY_RANK[hit.severity] > SEVERITY_RANK[severity]) severity = hit.severity;
  }
  return severity ? { severity, titles: [...titles] } : null;
}

export const HIGHLIGHT_RING: Record<Severity, string> = {
  critical: "ring-2 ring-red-500",
  warning: "ring-2 ring-orange-500",
  info: "ring-2 ring-slate-400",
};
