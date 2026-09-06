"""Teacher availability, from Meetings[] (docs/roadmap-v3.md 1.1) - a
standing commitment Timetabling Solutions itself records against a
teacher's slot, parsed straight from the source file
(app/ingest/tfx_parser.py's _ingest_meetings()) into teacher_commitment.
Unlike every other clash rule, this checks a LESSON entry against data
that never comes from timetable_entry at all."""

import sqlite3
from collections import defaultdict

from app.analysis.models import EntityRef, Finding, SlotRef


def teacher_commitment_busy(conn: sqlite3.Connection) -> dict[int, set[tuple]]:
    """teacher_id -> {(day_id, period_id), ...} for every standing
    Meetings[] commitment (docs/roadmap-v3.md 1.1). One implementation,
    shared by the repair solver (app/analysis/repair_solver.py) and the
    suggestion engine (app/analysis/suggestions.py) - both need "is this
    teacher free at this slot" to include commitments the same way, and a
    second copy is exactly the kind of thing that quietly drifts."""
    by_teacher: dict[int, set[tuple]] = defaultdict(set)
    rows = conn.execute(
        "SELECT tc.teacher_id, tc.period_id, p.day_id FROM teacher_commitment tc JOIN period p ON p.id = tc.period_id"
    )
    for r in rows:
        by_teacher[r["teacher_id"]].add((r["day_id"], r["period_id"]))
    return by_teacher


def teacher_meeting_clash(conn: sqlite3.Connection, entries: list[dict]) -> list[Finding]:
    """entries: LESSON rows shaped like app.analysis.clash_rules.lesson_
    entries() output - an explicit parameter, matching every other rule
    that needs to run against a hypothetical (what-if) timetable, even
    though a teacher's meeting commitments themselves are never something
    a proposed change touches."""
    commitments = conn.execute(
        "SELECT tc.teacher_id, tc.period_id, tc.code AS meeting_code, tc.name AS meeting_name "
        "FROM teacher_commitment tc"
    ).fetchall()
    if not commitments:
        return []
    commitment_by_key = {(r["teacher_id"], r["period_id"]): r for r in commitments}

    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for e in entries:
        if e["teacher_id"] is None:
            continue
        key = (e["teacher_id"], e["period_id"])
        if key in commitment_by_key:
            grouped[key].append(e)

    findings = []
    for (teacher_id, period_id), rows in grouped.items():
        commitment = commitment_by_key[(teacher_id, period_id)]
        sample = rows[0]
        class_codes = sorted({r["class_code"] for r in rows if r["class_code"]})
        findings.append(Finding(
            rule_id="teacher_meeting_clash",
            severity="critical",
            title=f"Teacher {sample['teacher_code']} scheduled to teach during meeting "
                  f"{commitment['meeting_code']!r} at {sample['day_code']} {sample['period_code']}",
            entity_refs=(
                (EntityRef("teacher", sample["teacher_code"]),)
                + tuple(EntityRef("class", c) for c in class_codes)
            ),
            slot_refs=(SlotRef(sample["day_code"], sample["period_code"]),),
            evidence={
                "meeting_code": commitment["meeting_code"],
                "meeting_name": commitment["meeting_name"],
                "class_codes": class_codes,
                "entries": [
                    {"entry_id": r["entry_id"], "class_code": r["class_code"], "room_code": r["room_code"]}
                    for r in rows
                ],
            },
        ))
    return findings


def run_availability_rules(conn: sqlite3.Connection, entries: list[dict]) -> list[Finding]:
    return [*teacher_meeting_clash(conn, entries)]
