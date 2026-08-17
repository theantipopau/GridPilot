"""teacher_not_qualified_for_class - unblocked by teacher_capability
(docs/roadmap-v2.md 2.2). A scheduled lesson whose teacher resolves
NOT_ELIGIBLE for that class's subject (app/analysis/capability.py) is a
genuine compliance question, not a preference - critical severity.

capability_rule_conflict (two equally-specific active rules disagreeing,
per docs/staff-capability-model.md) is deliberately NOT built here: the
bootstrap-sync in teacher_capability_review.py upserts at most one row
per (teacher_code, subject_code), and there is no authoring UI yet for a
second, overlapping dated row - so there is currently no path that could
produce a genuine conflict. Building detection for a case that can't
occur yet would be untestable, unreachable code; add it when authoring
capability rows with overlapping effective_from/effective_to becomes
possible."""

import sqlite3

from app.analysis.capability import resolve
from app.analysis.models import EntityRef, Finding, SlotRef


def teacher_not_qualified_for_class(conn: sqlite3.Connection, entries: list[dict]) -> list[Finding]:
    """entries: LESSON rows shaped like app.analysis.clash_rules.lesson_
    entries() output - an explicit parameter, matching every other rule
    that needs to run against a hypothetical (what-if) timetable."""
    class_subject = {
        r["class_name_id"]: (r["subject_code"], r["faculty_code"])
        for r in conn.execute(
            """
            SELECT cn.id AS class_name_id, s.source_code AS subject_code, f.code AS faculty_code
            FROM class_name cn
            JOIN subject s ON s.id = cn.subject_id
            LEFT JOIN faculty f ON f.id = s.faculty_id
            """
        )
    }

    findings = []
    for e in entries:
        if e["teacher_id"] is None or e["class_name_id"] is None:
            continue
        subject_faculty = class_subject.get(e["class_name_id"])
        if subject_faculty is None:
            continue
        subject_code, faculty_code = subject_faculty

        status = resolve(conn, e["teacher_code"], subject_code, faculty_code)
        if status != "NOT_ELIGIBLE":
            continue

        findings.append(Finding(
            rule_id="teacher_not_qualified_for_class",
            severity="critical",
            title=f"Teacher {e['teacher_code']} is not marked qualified to teach {e['class_code']} "
                  f"({subject_code}) at {e['day_code']} {e['period_code']}",
            entity_refs=(EntityRef("teacher", e["teacher_code"]), EntityRef("class", e["class_code"])),
            slot_refs=(SlotRef(e["day_code"], e["period_code"]),),
            evidence={"subject_code": subject_code, "faculty_code": faculty_code},
        ))
    return findings


def run_capability_rules(conn: sqlite3.Connection, entries: list[dict]) -> list[Finding]:
    return [*teacher_not_qualified_for_class(conn, entries)]
