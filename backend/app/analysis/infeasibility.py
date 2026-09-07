"""Infeasibility diagnosis - docs/solver.md §7.2, docs/roadmap-v3.md 4.3:
"CP-SAT can produce a minimal infeasible subset... translating that into
[a plain-English structural explanation] is a genuine language task on
top of a genuine computation. TTS tells you the clash. Nothing tells you
the structure is impossible."

Deliberately scoped down from a full minimal-unsatisfiable-core
extraction (which would mean reformulating repair_solver.py's CP-SAT
model with assumption literals - a real rewrite of a tested, load-
bearing module). Instead: for each timetable entry behind a finding the
mass-repair solver left unresolved, ask the one question that's cheap
and honest to answer exactly - "if this lesson were the only thing
allowed to move, is there ANY legal slot for it at all, right now?" -
using the same three-layer check (teacher, then student, then room)
repair_solver.py's own `_feasible_candidates` uses, so the answer is
guaranteed consistent with what actually makes the solver fail.

When the answer is no, the layer that ran out (teacher availability vs
student clash vs no matching room) is a real, provable bottleneck -
exactly the "Year 10 Science needs 5 periods across 4 lab-capable rooms,
but three are already committed to Year 11" shape. When the answer is
yes - the lesson has options alone but the joint problem still failed -
that's a genuine multi-lesson interaction a single-entry check cannot
diagnose; this deliberately reports that honestly (has_legal_slot: true,
no bucketed reason) rather than fabricating a specific cause. This is
the same "detect, never assert" discipline as everywhere else in this
project.

A small amount of finding-to-entry resolution logic here duplicates what
repair_solver.py's private `_resolve_finding_entries` does, rather than
importing a `_`-prefixed name across modules - that solver is a tested,
production-critical 550+ line file and this stays entirely read-only
against it."""

import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass

from app.analysis.availability_rules import teacher_commitment_busy
from app.analysis.clash_rules import lesson_entries
from app.analysis.room_pool_rules import pool_room_ids_by_class
from app.analysis.room_type_constraints import required_room_type_by_class


@dataclass(frozen=True)
class _Slot:
    day_id: int
    period_id: int


def _code_maps(conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
    return {
        "teacher": {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM teacher")},
        "room": {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM room")},
        "class": {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM class_name")},
        "day": {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM day")},
    }


def _entries_by_slot_entity(entries: list[dict]) -> dict[tuple, set[int]]:
    index: dict[tuple, set[int]] = defaultdict(set)
    for e in entries:
        key = (e["day_id"], e["period_id"])
        if e["teacher_id"] is not None:
            index[(*key, "teacher", e["teacher_id"])].add(e["entry_id"])
        if e["room_id"] is not None:
            index[(*key, "room", e["room_id"])].add(e["entry_id"])
        if e["class_name_id"] is not None:
            index[(*key, "class", e["class_name_id"])].add(e["entry_id"])
    return index


def _resolve_finding_to_entries(
    finding_row: sqlite3.Row, codes: dict, period_lookup: dict, slot_index: dict[tuple, set[int]]
) -> set[int]:
    slot_refs = json.loads(finding_row["slot_refs_json"])
    if len(slot_refs) != 1:
        return set()
    day_id = codes["day"].get(slot_refs[0]["day_code"])
    if day_id is None:
        return set()
    period_id = period_lookup.get((day_id, slot_refs[0]["period_code"]))
    if period_id is None:
        return set()

    entity_refs = json.loads(finding_row["entity_refs_json"])
    matched: set[int] = set()
    for ref in entity_refs:
        if ref["type"] not in ("teacher", "room", "class"):
            continue
        entity_id = codes[ref["type"]].get(ref["code"])
        if entity_id is None:
            continue
        matched |= slot_index.get((day_id, period_id, ref["type"], entity_id), set())
    return matched


def _diagnose_entry(
    entry: dict,
    all_slots: list[_Slot],
    rooms: dict[int, dict],
    teacher_busy: dict[int, set],
    room_busy: dict[int, set],
    student_busy: dict[int, set],
    students: frozenset,
    required_room_type: str | None,
    required_room_ids: frozenset | None,
    enrolled: int,
) -> dict:
    """The same three-layer check as repair_solver.py's
    `_feasible_candidates` (teacher, then student, then room), but
    counting eliminations at each layer instead of just listing
    survivors - the bucketed counts are the "why"."""
    total = len(all_slots)
    teacher_id = entry["teacher_id"]

    teacher_free = [
        s for s in all_slots
        if teacher_id is None or (s.day_id, s.period_id) not in teacher_busy.get(teacher_id, ())
    ]
    student_free = [
        s for s in teacher_free
        if not any((s.day_id, s.period_id) in student_busy.get(sid, ()) for sid in students)
    ]

    def room_is_eligible(room: dict) -> bool:
        if room["seats"] is not None and enrolled > room["seats"]:
            return False
        if required_room_type is not None and room["room_type"] != required_room_type:
            return False
        if required_room_ids is not None and room["id"] not in required_room_ids:
            return False
        return True

    matching_rooms_total = sum(1 for r in rooms.values() if room_is_eligible(r))

    slots_with_legal_room = 0
    for s in student_free:
        for room_id, room in rooms.items():
            if not room_is_eligible(room):
                continue
            if (s.day_id, s.period_id) in room_busy.get(room_id, ()):
                continue
            slots_with_legal_room += 1
            break

    return {
        "entry_id": entry["entry_id"],
        "class_code": entry["class_code"],
        "teacher_code": entry["teacher_code"],
        "room_code": entry["room_code"],
        "day_code": entry["day_code"],
        "period_code": entry["period_code"],
        "has_legal_slot": slots_with_legal_room > 0,
        "total_slots": total,
        "slots_lost_to_teacher_availability": total - len(teacher_free),
        "slots_lost_to_student_clash": len(teacher_free) - len(student_free),
        "slots_checked_for_a_room": len(student_free),
        "slots_with_a_legal_room": slots_with_legal_room,
        "required_room_type": required_room_type,
        "matching_rooms_total": matching_rooms_total,
    }


def diagnose_unresolved_findings(conn: sqlite3.Connection, finding_ids: list[int]) -> list[dict]:
    """For every OPEN finding in `finding_ids`, resolve it to the
    timetable entry(ies) it's about and diagnose each one against the
    CURRENT live timetable (not a stale mid-solve snapshot). Returns one
    diagnosis per distinct entry, sorted by entry_id."""
    if not finding_ids:
        return []

    placeholders = ",".join("?" for _ in finding_ids)
    finding_rows = conn.execute(
        f"SELECT id, slot_refs_json, entity_refs_json FROM finding WHERE id IN ({placeholders})",
        tuple(finding_ids),
    ).fetchall()

    codes = _code_maps(conn)
    period_lookup = {(r["day_id"], r["code"]): r["id"] for r in conn.execute("SELECT id, day_id, code FROM period")}

    entries = lesson_entries(conn)
    entries_by_id = {e["entry_id"]: e for e in entries}
    slot_index = _entries_by_slot_entity(entries)

    entry_ids: set[int] = set()
    for row in finding_rows:
        entry_ids |= _resolve_finding_to_entries(row, codes, period_lookup, slot_index)
    if not entry_ids:
        return []

    all_slots = [
        _Slot(r["day_id"], r["id"])
        for r in conn.execute("SELECT id, day_id FROM period WHERE entry_kind = 'LESSON_SLOT'")
    ]
    rooms = {r["id"]: dict(r) for r in conn.execute("SELECT id, code, seats, room_type FROM room")}
    enrolled_by_class = {
        r["class_name_id"]: r["n"]
        for r in conn.execute("SELECT class_name_id, COUNT(DISTINCT student_id) AS n FROM enrolment GROUP BY class_name_id")
    }
    students_by_class: dict[int, set[int]] = defaultdict(set)
    for r in conn.execute("SELECT class_name_id, student_id FROM enrolment"):
        students_by_class[r["class_name_id"]].add(r["student_id"])
    room_type_by_class = required_room_type_by_class(conn)
    room_pool_by_class = pool_room_ids_by_class(conn)

    teacher_busy: dict[int, set] = defaultdict(set)
    for teacher_id, slots in teacher_commitment_busy(conn).items():
        teacher_busy[teacher_id] |= slots
    room_busy: dict[int, set] = defaultdict(set)
    student_busy: dict[int, set] = defaultdict(set)
    for e in entries:
        if e["entry_id"] in entry_ids:
            continue  # never treat one of the entries being diagnosed as part of the fixed background
        if e["teacher_id"] is not None:
            teacher_busy[e["teacher_id"]].add((e["day_id"], e["period_id"]))
        if e["room_id"] is not None:
            room_busy[e["room_id"]].add((e["day_id"], e["period_id"]))
        for student_id in students_by_class.get(e["class_name_id"], ()):
            student_busy[student_id].add((e["day_id"], e["period_id"]))

    diagnoses = []
    for entry_id in sorted(entry_ids):
        entry = entries_by_id.get(entry_id)
        if entry is None:
            continue
        diagnoses.append(_diagnose_entry(
            entry, all_slots, rooms, teacher_busy, room_busy, student_busy,
            frozenset(students_by_class.get(entry["class_name_id"], ())),
            room_type_by_class.get(entry["class_name_id"]),
            room_pool_by_class.get(entry["class_name_id"]),
            enrolled_by_class.get(entry["class_name_id"], 0),
        ))
    return diagnoses
