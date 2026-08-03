"""The three clash rules required by PROJECT_ROADMAP.md's definition of
done: teacher_double_booking, room_double_booking, student_double_booking.

Deterministic, no AI involved. Every finding references entities by code
only (never a name/email - see docs/rules.md). A composite group only
suppresses a clash once a human has approved it (review_status =
'APPROVED') - a detected-but-unreviewed candidate still produces a clash
finding, per the roadmap's explicit 'do not suppress while pending'
instruction."""

import sqlite3
from collections import defaultdict

from app.analysis.composite_review import ApprovedComposites, load_approved_composites
from app.analysis.models import EntityRef, Finding, SlotRef


def lesson_entries(conn: sqlite3.Connection) -> list[dict]:
    """Every LESSON timetable_entry, joined with display codes. Returned as
    plain dicts (not sqlite3.Row) so callers - notably change-set what-if
    validation (app/changes/service.py) - can apply in-memory overrides
    without touching the database."""
    rows = conn.execute(
        """
        SELECT te.id AS entry_id,
               te.teacher_id, t.code AS teacher_code,
               te.room_id, rm.code AS room_code,
               te.day_id, d.code AS day_code,
               te.period_id, p.code AS period_code,
               te.class_name_id, cn.code AS class_code,
               te.roll_class_id, rc.code AS roll_class_code
        FROM timetable_entry te
        JOIN day d ON d.id = te.day_id
        JOIN period p ON p.id = te.period_id
        JOIN roll_class rc ON rc.id = te.roll_class_id
        LEFT JOIN teacher t ON t.id = te.teacher_id
        LEFT JOIN room rm ON rm.id = te.room_id
        LEFT JOIN class_name cn ON cn.id = te.class_name_id
        WHERE te.entry_type = 'LESSON'
        """
    ).fetchall()
    return [dict(r) for r in rows]


def teacher_double_booking(entries: list[dict], composites: ApprovedComposites) -> list[Finding]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for e in entries:
        if e["teacher_id"] is None:
            continue
        groups[(e["teacher_id"], e["day_id"], e["period_id"])].append(e)

    findings = []
    for (teacher_id, _day_id, _period_id), rows in groups.items():
        if len(rows) < 2:
            continue
        room_ids = {r["room_id"] for r in rows}
        class_name_ids = {r["class_name_id"] for r in rows}

        if len(room_ids) == 1:
            (room_id,) = room_ids
            if room_id is not None and composites.slot_is_suppressed(teacher_id, room_id, class_name_ids):
                continue

        sample = rows[0]
        findings.append(Finding(
            rule_id="teacher_double_booking",
            severity="critical",
            title=f"Teacher {sample['teacher_code']} double-booked at {sample['day_code']} {sample['period_code']}",
            entity_refs=(
                (EntityRef("teacher", sample["teacher_code"]),)
                + tuple(EntityRef("class", r["class_code"]) for r in rows if r["class_code"])
            ),
            slot_refs=(SlotRef(sample["day_code"], sample["period_code"]),),
            evidence={
                "entries": [
                    {"entry_id": r["entry_id"], "class_code": r["class_code"], "room_code": r["room_code"],
                     "roll_class_code": r["roll_class_code"]}
                    for r in rows
                ],
                "spans_multiple_rooms": len(room_ids) > 1,
            },
        ))
    return findings


def room_double_booking(entries: list[dict], composites: ApprovedComposites) -> list[Finding]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for e in entries:
        if e["room_id"] is None:
            continue
        groups[(e["room_id"], e["day_id"], e["period_id"])].append(e)

    findings = []
    for (room_id, _day_id, _period_id), rows in groups.items():
        if len(rows) < 2:
            continue
        teacher_ids = {r["teacher_id"] for r in rows}
        class_name_ids = {r["class_name_id"] for r in rows}

        if len(teacher_ids) == 1:
            (teacher_id,) = teacher_ids
            if teacher_id is not None and composites.slot_is_suppressed(teacher_id, room_id, class_name_ids):
                continue

        sample = rows[0]
        findings.append(Finding(
            rule_id="room_double_booking",
            severity="critical",
            title=f"Room {sample['room_code']} double-booked at {sample['day_code']} {sample['period_code']}",
            entity_refs=(
                (EntityRef("room", sample["room_code"]),)
                + tuple(EntityRef("class", r["class_code"]) for r in rows if r["class_code"])
            ),
            slot_refs=(SlotRef(sample["day_code"], sample["period_code"]),),
            evidence={
                "entries": [
                    {"entry_id": r["entry_id"], "class_code": r["class_code"], "teacher_code": r["teacher_code"],
                     "roll_class_code": r["roll_class_code"]}
                    for r in rows
                ],
                "spans_multiple_teachers": len(teacher_ids) > 1,
            },
        ))
    return findings


def student_double_booking(conn: sqlite3.Connection, entries: list[dict], composites: ApprovedComposites) -> list[Finding]:
    # class_name_id -> list of (day_id, period_id, day_code, period_code, class_code)
    slots_by_class: dict[int, list[tuple]] = defaultdict(list)
    for e in entries:
        if e["class_name_id"] is None:
            continue
        slots_by_class[e["class_name_id"]].append(
            (e["day_id"], e["period_id"], e["day_code"], e["period_code"], e["class_code"])
        )

    enrolment_rows = conn.execute(
        """
        SELECT s.id AS student_id, s.code AS student_code, e.class_name_id
        FROM enrolment e
        JOIN student s ON s.id = e.student_id
        WHERE e.class_name_id IN (SELECT DISTINCT class_name_id FROM timetable_entry WHERE class_name_id IS NOT NULL)
        ORDER BY s.id
        """
    ).fetchall()

    classes_by_student: dict[int, set[int]] = defaultdict(set)
    student_code_by_id: dict[int, str] = {}
    for r in enrolment_rows:
        classes_by_student[r["student_id"]].add(r["class_name_id"])
        student_code_by_id[r["student_id"]] = r["student_code"]

    findings = []
    for student_id, class_ids in classes_by_student.items():
        class_ids = list(class_ids)
        if len(class_ids) < 2:
            continue
        # Compare every pair of the student's classes for an overlapping slot.
        for i in range(len(class_ids)):
            for j in range(i + 1, len(class_ids)):
                a, b = class_ids[i], class_ids[j]
                if composites.classes_are_composite(a, b):
                    continue
                slots_a = {(d, p): (dc, pc, cc) for d, p, dc, pc, cc in slots_by_class.get(a, [])}
                slots_b = {(d, p): (dc, pc, cc) for d, p, dc, pc, cc in slots_by_class.get(b, [])}
                overlap = set(slots_a) & set(slots_b)
                for slot in overlap:
                    dc, pc, class_a_code = slots_a[slot]
                    _, _, class_b_code = slots_b[slot]
                    findings.append(Finding(
                        rule_id="student_double_booking",
                        severity="critical",
                        title=f"Student {student_code_by_id[student_id]} double-booked at {dc} {pc}",
                        entity_refs=(
                            EntityRef("student", student_code_by_id[student_id]),
                            EntityRef("class", class_a_code),
                            EntityRef("class", class_b_code),
                        ),
                        slot_refs=(SlotRef(dc, pc),),
                        evidence={"class_codes": [class_a_code, class_b_code]},
                    ))
    return findings


def run_clash_rules(conn: sqlite3.Connection) -> list[Finding]:
    entries = lesson_entries(conn)
    composites = load_approved_composites(conn)
    return [
        *teacher_double_booking(entries, composites),
        *room_double_booking(entries, composites),
        *student_double_booking(conn, entries, composites),
    ]
