"""Phase B of docs/full-timetabler-plan.md - structural consistency
signals a timetabler cares about but Timetabling Solutions never
surfaces on its own: does a class keep the same room/teacher across the
cycle, or does it bounce around?

Deliberately threshold-free, unlike some of load_rules.py's rules: "this
class used more than one room/teacher across the cycle" is itself the
finding, not a magnitude crossing an invented cutoff - no
LOW_UTILISATION_THRESHOLD-style heuristic needed here. That's also why
this file exists separately from load_rules.py rather than folding in:
these two rules needed real-data investigation to confirm they produce a
genuine, non-trivial signal (see docs/rules.md's "Consistency rules"
section for what else was investigated and deliberately not built -
day/subject spread and free-period fragmentation both turned out to
need a school-confirmed threshold this project doesn't have, the same
trap PROJECT_ROADMAP.md already flagged for teacher_free_period_
fragmentation and uneven_subject_spread)."""

import sqlite3
from collections import defaultdict

from app.analysis.models import EntityRef, Finding


def class_room_instability(conn: sqlite3.Connection) -> list[Finding]:
    rows = conn.execute(
        """
        SELECT cn.code AS class_code, rm.code AS room_code
        FROM timetable_entry te
        JOIN class_name cn ON cn.id = te.class_name_id
        JOIN room rm ON rm.id = te.room_id
        WHERE te.entry_type = 'LESSON'
        """
    ).fetchall()

    rooms_by_class: dict[str, set[str]] = defaultdict(set)
    lesson_count_by_class: dict[str, int] = defaultdict(int)
    for r in rows:
        rooms_by_class[r["class_code"]].add(r["room_code"])
        lesson_count_by_class[r["class_code"]] += 1

    findings = []
    for class_code, rooms in rooms_by_class.items():
        if len(rooms) <= 1:
            continue
        findings.append(Finding(
            rule_id="class_room_instability",
            severity="info",
            title=f"Class {class_code} used {len(rooms)} different rooms across the cycle",
            entity_refs=(EntityRef("class", class_code),),
            slot_refs=(),
            evidence={
                "room_codes": sorted(rooms),
                "room_count": len(rooms),
                "lesson_count": lesson_count_by_class[class_code],
            },
        ))
    return findings


def class_teacher_inconsistency(conn: sqlite3.Connection) -> list[Finding]:
    rows = conn.execute(
        """
        SELECT cn.code AS class_code, t.code AS teacher_code
        FROM timetable_entry te
        JOIN class_name cn ON cn.id = te.class_name_id
        JOIN teacher t ON t.id = te.teacher_id
        WHERE te.entry_type = 'LESSON'
        """
    ).fetchall()

    teachers_by_class: dict[str, set[str]] = defaultdict(set)
    lesson_count_by_class: dict[str, int] = defaultdict(int)
    for r in rows:
        teachers_by_class[r["class_code"]].add(r["teacher_code"])
        lesson_count_by_class[r["class_code"]] += 1

    findings = []
    for class_code, teachers in teachers_by_class.items():
        if len(teachers) <= 1:
            continue
        findings.append(Finding(
            rule_id="class_teacher_inconsistency",
            severity="info",
            title=f"Class {class_code} taught by {len(teachers)} different teachers across the cycle",
            entity_refs=(EntityRef("class", class_code),),
            slot_refs=(),
            evidence={
                "teacher_codes": sorted(teachers),
                "teacher_count": len(teachers),
                "lesson_count": lesson_count_by_class[class_code],
            },
        ))
    return findings


def run_consistency_rules(conn: sqlite3.Connection) -> list[Finding]:
    return [
        *class_room_instability(conn),
        *class_teacher_inconsistency(conn),
    ]
