"""Capacity, load, and utilisation rules - the remaining Milestone 1
"first rules" that can be checked against data we actually have,
without guessing an unconfirmed school policy value (see docs/rules.md
for which rules were deliberately skipped and why).

Composite-awareness matters here in a different way than for the clash
rules: a composite lesson (two class codes, one physical room/teacher at
one period) must be counted as ONE occupied slot, not two - otherwise a
teacher's load or a room's utilisation would be inflated by however many
class codes happen to be attached to the same physical lesson. This
applies regardless of whether the composite has been reviewed/approved -
it's a fact about physical time, not an administrative judgement."""

import sqlite3
from collections import defaultdict

from app.analysis.clash_rules import lesson_entries
from app.analysis.models import EntityRef, Finding, SlotRef

# Rooms below this utilisation are flagged as `info`. This is a default
# heuristic for surfacing candidates worth a human look, not a confirmed
# Sophia College policy value - see docs/rules.md.
LOW_UTILISATION_THRESHOLD = 0.20


def room_capacity_exceeded(conn: sqlite3.Connection, entries: list[dict]) -> list[Finding]:
    """entries: LESSON rows shaped like app.analysis.clash_rules.lesson_
    entries() output (room_id, class_name_id, day_code, period_code) - an
    explicit parameter, not an internal query, so a what-if caller (the
    solver's validation loop, app/analysis/repair_solver.py) can check a
    hypothetical timetable without writing to the database. Every other
    caller just passes lesson_entries(conn)."""
    rooms = {r["id"]: r for r in conn.execute("SELECT id, code, seats FROM room WHERE seats IS NOT NULL")}
    if not rooms:
        return []

    slot_classes: dict[tuple, set[int]] = defaultdict(set)
    slot_meta: dict[tuple, tuple[str, str]] = {}
    for e in entries:
        if e["room_id"] not in rooms or e["class_name_id"] is None:
            continue
        key = (e["room_id"], e["day_code"], e["period_code"])
        slot_classes[key].add(e["class_name_id"])
        slot_meta[key] = (e["day_code"], e["period_code"])

    class_codes_by_id = {r["id"]: r["code"] for r in conn.execute("SELECT id, code FROM class_name")}

    findings = []
    for (room_id, day_code, period_code), class_ids in slot_classes.items():
        placeholders = ",".join("?" for _ in class_ids)
        enrolled_count = conn.execute(
            f"SELECT COUNT(DISTINCT student_id) FROM enrolment WHERE class_name_id IN ({placeholders})",
            tuple(class_ids),
        ).fetchone()[0]

        room = rooms[room_id]
        if enrolled_count <= room["seats"]:
            continue

        findings.append(Finding(
            rule_id="room_capacity_exceeded",
            severity="warning",
            title=f"Room {room['code']} over capacity at {day_code} {period_code} "
                  f"({enrolled_count} enrolled, {room['seats']} seats)",
            entity_refs=(
                (EntityRef("room", room["code"]),)
                + tuple(EntityRef("class", class_codes_by_id[cid]) for cid in class_ids)
            ),
            slot_refs=(SlotRef(day_code, period_code),),
            evidence={
                "seats": room["seats"],
                "enrolled_count": enrolled_count,
                "class_codes": [class_codes_by_id[cid] for cid in class_ids],
            },
        ))
    return findings


def teacher_over_contracted_load(conn: sqlite3.Connection) -> list[Finding]:
    teachers = conn.execute(
        "SELECT id, code, contracted_load_minutes FROM teacher WHERE contracted_load_minutes IS NOT NULL"
    ).fetchall()
    if not teachers:
        return []

    entries = conn.execute(
        """
        SELECT te.teacher_id, te.period_id, p.load_minutes
        FROM timetable_entry te
        JOIN period p ON p.id = te.period_id
        WHERE te.entry_type = 'LESSON' AND te.teacher_id IS NOT NULL
        """
    ).fetchall()

    # Distinct (teacher, period) - a composite lesson must not be counted
    # once per class code sharing that slot.
    slots_by_teacher: dict[int, dict[int, float]] = defaultdict(dict)
    for e in entries:
        slots_by_teacher[e["teacher_id"]][e["period_id"]] = e["load_minutes"]

    findings = []
    for t in teachers:
        scheduled_minutes = sum(slots_by_teacher.get(t["id"], {}).values())
        if scheduled_minutes <= t["contracted_load_minutes"]:
            continue

        findings.append(Finding(
            rule_id="teacher_over_contracted_load",
            severity="warning",
            title=f"Teacher {t['code']} scheduled {scheduled_minutes:.0f} min/cycle, "
                  f"over their {t['contracted_load_minutes']:.0f} min contracted load",
            entity_refs=(EntityRef("teacher", t["code"]),),
            slot_refs=(),
            evidence={
                "scheduled_minutes": scheduled_minutes,
                "contracted_load_minutes": t["contracted_load_minutes"],
                "over_by_minutes": scheduled_minutes - t["contracted_load_minutes"],
            },
        ))
    return findings


def room_underutilization(conn: sqlite3.Connection) -> list[Finding]:
    total_lesson_slots = conn.execute(
        "SELECT COUNT(*) FROM period WHERE entry_kind = 'LESSON_SLOT'"
    ).fetchone()[0]
    if total_lesson_slots == 0:
        return []

    rooms = conn.execute("SELECT id, code FROM room WHERE seats IS NOT NULL").fetchall()

    used_slots_by_room: dict[int, set[tuple]] = defaultdict(set)
    entries = conn.execute(
        """
        SELECT te.room_id, te.day_id, te.period_id
        FROM timetable_entry te
        WHERE te.entry_type = 'LESSON' AND te.room_id IS NOT NULL
        """
    ).fetchall()
    for e in entries:
        used_slots_by_room[e["room_id"]].add((e["day_id"], e["period_id"]))

    findings = []
    for room in rooms:
        used = len(used_slots_by_room.get(room["id"], set()))
        utilisation = used / total_lesson_slots
        if utilisation >= LOW_UTILISATION_THRESHOLD:
            continue

        findings.append(Finding(
            rule_id="room_underutilization",
            severity="info",
            title=f"Room {room['code']} used {utilisation:.0%} of available lesson slots",
            entity_refs=(EntityRef("room", room["code"]),),
            slot_refs=(),
            evidence={
                "used_slots": used,
                "total_lesson_slots": total_lesson_slots,
                "utilisation": round(utilisation, 4),
                "threshold": LOW_UTILISATION_THRESHOLD,
                "threshold_note": "Default heuristic for surfacing candidates - not a confirmed school policy value.",
            },
        ))
    return findings


def run_load_rules(conn: sqlite3.Connection) -> list[Finding]:
    return [
        *room_capacity_exceeded(conn, lesson_entries(conn)),
        *teacher_over_contracted_load(conn),
        *room_underutilization(conn),
    ]
