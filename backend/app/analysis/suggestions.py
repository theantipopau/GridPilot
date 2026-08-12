"""Constraint-based candidate moves, per PROJECT_ROADMAP.md Milestone 4:

    1. Find alternate rooms or periods satisfying hard constraints.
    2. Reject candidates that create teacher, room or student clashes.
    3. Reject room-capacity and room-feature failures.
    4. Score remaining options using soft constraints such as movement.
    5. Give the ranked candidates and evidence to the local AI only for
       explanation.

This is deliberately algorithmic, not AI - nothing here calls a model.
The (not yet built) AI advisor layer's job is to explain *these* ranked,
pre-validated candidates in plain language, never to invent its own.

Scope: teacher_double_booking and room_double_booking only. Room-feature
matching and student_double_booking suggestions are out of scope - see
docs/suggestions.md for why. Teacher reassignment (moving a lesson to a
*different teacher*) is deliberately never suggested - there's no
authoritative subject-qualification data yet (see docs/staff-capability-
model.md), and guessing would be exactly the kind of invented suggestion
the roadmap warns against."""

import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass

from app.analysis.clash_rules import lesson_entries
from app.analysis.composite_review import load_approved_composites
from app.analysis.whatif import apply_overrides, load_code_lookups, run_clash_findings

MAX_ENTRIES_CONSIDERED = 3  # cap on how many conflicting entries per finding get candidates generated
MAX_CANDIDATES_RETURNED = 15


@dataclass(frozen=True)
class Slot:
    day_id: int
    period_id: int
    day_code: str
    period_code: str


def _all_lesson_slots(conn: sqlite3.Connection) -> list[Slot]:
    rows = conn.execute(
        "SELECT p.id AS period_id, p.day_id, d.code AS day_code, p.code AS period_code "
        "FROM period p JOIN day d ON d.id = p.day_id WHERE p.entry_kind = 'LESSON_SLOT'"
    ).fetchall()
    return [Slot(r["day_id"], r["period_id"], r["day_code"], r["period_code"]) for r in rows]


def _busy_sets(entries: list[dict]) -> tuple[dict[int, set], dict[int, set]]:
    teacher_busy: dict[int, set] = defaultdict(set)
    room_busy: dict[int, set] = defaultdict(set)
    for e in entries:
        if e["teacher_id"] is not None:
            teacher_busy[e["teacher_id"]].add((e["day_id"], e["period_id"]))
        if e["room_id"] is not None:
            room_busy[e["room_id"]].add((e["day_id"], e["period_id"]))
    return teacher_busy, room_busy


def _enrolled_count(conn: sqlite3.Connection, class_name_ids: set[int]) -> int:
    if not class_name_ids:
        return 0
    placeholders = ",".join("?" for _ in class_name_ids)
    return conn.execute(
        f"SELECT COUNT(DISTINCT student_id) FROM enrolment WHERE class_name_id IN ({placeholders})",
        tuple(class_name_ids),
    ).fetchone()[0]


def _movement_cost(entry: dict, slot_day_id: int, slot_period_id: int, room_id: int) -> int:
    """Lower is less disruptive. 0 = room-only change, 1 = same day
    different period, 2 = different day. A documented default heuristic
    (see docs/suggestions.md), not a confirmed school weighting."""
    if slot_day_id == entry["day_id"] and slot_period_id == entry["period_id"]:
        return 0  # room-only change
    if slot_day_id == entry["day_id"]:
        return 1
    return 2


def _class_room_familiarity(entries_by_class: dict[int, list[dict]], entry: dict, after_room_id: int | None) -> dict | None:
    """How "at home" the class already is in the candidate's target room -
    the same signal class_room_instability (app/analysis/consistency_
    rules.py) computes, surfaced here so a suggestion can say whether it
    moves the class *towards* or *away from* a consistent room, not just
    "5 · P3 -> RIE01"."""
    if after_room_id is None:
        return None
    others = [e for e in entries_by_class.get(entry["class_name_id"], []) if e["entry_id"] != entry["entry_id"]]
    if not others:
        return None
    same_room_elsewhere = sum(1 for e in others if e["room_id"] == after_room_id)
    return {"same_room_elsewhere_count": same_room_elsewhere, "total_other_lessons": len(others)}


def _try_candidate(
    conn: sqlite3.Connection,
    before_entries: list[dict],
    before_findings: dict,
    composites,
    code_lookups: dict,
    entry: dict,
    after_day_id: int,
    after_period_id: int,
    after_room_id: int | None,
    class_name_ids: set[int],
    entries_by_class: dict[int, list[dict]],
) -> dict | None:
    room_capacity: dict = {"confirmed": False}
    if after_room_id is not None:
        room = conn.execute("SELECT seats FROM room WHERE id = ?", (after_room_id,)).fetchone()
        if room is not None and room["seats"] is not None:
            enrolled = _enrolled_count(conn, class_name_ids)
            if enrolled > room["seats"]:
                return None  # hard constraint: room capacity
            room_capacity = {"confirmed": True, "seats": room["seats"], "enrolled": enrolled}

    overrides = {
        entry["entry_id"]: {
            "after_day_id": after_day_id, "after_period_id": after_period_id,
            "after_room_id": after_room_id, "after_teacher_id": entry["teacher_id"],
        }
    }
    after_entries = apply_overrides(before_entries, overrides, code_lookups)
    after_findings = {f.dedupe_key(): f for f in run_clash_findings(conn, after_entries, composites)}

    introduced = [f for k, f in after_findings.items() if k not in before_findings]
    if introduced:
        return None  # hard constraint: would create a new clash

    return {
        "entry_id": entry["entry_id"],
        "class_code": entry["class_code"],
        "before": {"day_code": entry["day_code"], "period_code": entry["period_code"], "room_code": entry["room_code"]},
        "after": {
            "day_code": code_lookups["day"][after_day_id],
            "period_code": code_lookups["period"][after_period_id],
            "room_code": code_lookups["room"].get(after_room_id),
        },
        "movement_cost": _movement_cost(entry, after_day_id, after_period_id, after_room_id),
        "resolves_finding_count": sum(1 for k in before_findings if k not in after_findings),
        "why": {"no_new_clash": True, "room_capacity": room_capacity},
        "class_room_familiarity": _class_room_familiarity(entries_by_class, entry, after_room_id),
    }


def suggest_fixes(conn: sqlite3.Connection, finding_id: int) -> dict:
    finding_row = conn.execute(
        "SELECT rule_id, evidence_json FROM finding WHERE id = ?", (finding_id,)
    ).fetchone()
    if finding_row is None:
        return {"finding_id": finding_id, "supported": False, "note": "No such finding.", "candidates": []}

    if finding_row["rule_id"] not in ("teacher_double_booking", "room_double_booking"):
        return {
            "finding_id": finding_id, "supported": False,
            "note": f"Suggestion generation isn't implemented for {finding_row['rule_id']} yet - see docs/suggestions.md.",
            "candidates": [],
        }

    evidence = json.loads(finding_row["evidence_json"])
    conflicting = evidence.get("entries", [])[:MAX_ENTRIES_CONSIDERED]
    if not conflicting or "entry_id" not in conflicting[0]:
        return {
            "finding_id": finding_id, "supported": False,
            "note": "Finding evidence predates entry_id tracking - re-run the rules engine.",
            "candidates": [],
        }

    code_lookups = load_code_lookups(conn)
    composites = load_approved_composites(conn)
    before_entries = lesson_entries(conn)
    entries_by_id = {e["entry_id"]: e for e in before_entries}
    before_findings = {f.dedupe_key(): f for f in run_clash_findings(conn, before_entries, composites)}
    teacher_busy, room_busy = _busy_sets(before_entries)
    all_slots = _all_lesson_slots(conn)

    entries_by_class: dict[int, list[dict]] = defaultdict(list)
    for e in before_entries:
        if e["class_name_id"] is not None:
            entries_by_class[e["class_name_id"]].append(e)

    all_candidates = []
    for conflict in conflicting:
        entry = entries_by_id.get(conflict["entry_id"])
        if entry is None:
            continue

        class_name_ids = {entry["class_name_id"]} if entry["class_name_id"] else set()

        # Type A: same room, different slot.
        if entry["teacher_id"] is not None and entry["room_id"] is not None:
            for slot in all_slots:
                if (slot.day_id, slot.period_id) == (entry["day_id"], entry["period_id"]):
                    continue
                if (slot.day_id, slot.period_id) in teacher_busy.get(entry["teacher_id"], set()):
                    continue
                if (slot.day_id, slot.period_id) in room_busy.get(entry["room_id"], set()):
                    continue
                candidate = _try_candidate(
                    conn, before_entries, before_findings, composites, code_lookups,
                    entry, slot.day_id, slot.period_id, entry["room_id"], class_name_ids,
                    entries_by_class,
                )
                if candidate:
                    all_candidates.append(candidate)

        # Type B: same slot, different room.
        if entry["room_id"] is not None:
            for room_row in conn.execute("SELECT id, code FROM room WHERE id != ?", (entry["room_id"],)):
                if (entry["day_id"], entry["period_id"]) in room_busy.get(room_row["id"], set()):
                    continue
                candidate = _try_candidate(
                    conn, before_entries, before_findings, composites, code_lookups,
                    entry, entry["day_id"], entry["period_id"], room_row["id"], class_name_ids,
                    entries_by_class,
                )
                if candidate:
                    all_candidates.append(candidate)

    def familiarity_tiebreak(c: dict) -> int:
        fam = c["class_room_familiarity"]
        return -fam["same_room_elsewhere_count"] if fam else 0

    # Least disruptive first, then most findings resolved, then prefer a
    # room the class already uses elsewhere (ties back to
    # class_room_instability - a suggestion that happens to make the class
    # *more* consistent, not just conflict-free, ranks ahead of one that
    # doesn't).
    all_candidates.sort(key=lambda c: (c["movement_cost"], -c["resolves_finding_count"], familiarity_tiebreak(c)))
    return {
        "finding_id": finding_id, "supported": True, "note": None,
        "candidates": all_candidates[:MAX_CANDIDATES_RETURNED],
    }
