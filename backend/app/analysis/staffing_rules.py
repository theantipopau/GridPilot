"""teaching_requirement_blocking - docs/staffing-priority-policy.md: "no
eligible+available teacher... doesn't need a solver, it's a
straightforward query, and is one of the first useful things to build
once the capability tables land." Scoped to eligibility only for now, not
the fuller BLOCKING/HIGH/MEDIUM/HEALTHY risk banding that doc describes
(remaining capacity minutes need real load accounting a solver would
provide) - an APPROVED teaching_requirement with zero teachers resolving
ELIGIBLE for its subject/faculty is a genuine, provable staffing gap on
its own, critical severity.

A composite requirement (subject_id NULL - it spans multiple subjects by
definition, see app/analysis/teaching_requirement.py) has nothing to
resolve capability against yet and is skipped, not silently treated as
blocked."""

import sqlite3

from app.analysis.capability import resolve
from app.analysis.models import EntityRef, Finding


def teaching_requirement_blocking(conn: sqlite3.Connection) -> list[Finding]:
    teacher_codes = [r["code"] for r in conn.execute("SELECT code FROM teacher")]

    rows = conn.execute(
        """
        SELECT tr.id, tr.requirement_key, tr.composite_group_id, s.source_code AS subject_code,
               f.code AS faculty_code
        FROM teaching_requirement tr
        LEFT JOIN subject s ON s.id = tr.subject_id
        LEFT JOIN faculty f ON f.id = s.faculty_id
        WHERE tr.review_status = 'APPROVED'
        """
    ).fetchall()

    findings = []
    for r in rows:
        subject_code, faculty_code = r["subject_code"], r["faculty_code"]
        if subject_code is None and faculty_code is None:
            continue

        has_eligible = any(resolve(conn, code, subject_code, faculty_code) == "ELIGIBLE" for code in teacher_codes)
        if has_eligible:
            continue

        # requirement_key doubles as a stable, human-readable identity for
        # the entity_ref - a class code for the simple case, or the same
        # "COMPOSITE:<sorted member codes>" key detection itself uses,
        # which dedupe_key() needs to tell two different composites apart
        # (evidence is deliberately excluded from dedupe_key()).
        entity_type = "composite_group" if r["composite_group_id"] is not None else "class"
        findings.append(Finding(
            rule_id="teaching_requirement_blocking",
            severity="critical",
            title=f"No teacher is marked eligible to teach {r['requirement_key']} ({subject_code or faculty_code})",
            entity_refs=(EntityRef(entity_type, r["requirement_key"]),),
            slot_refs=(),
            evidence={"subject_code": subject_code, "faculty_code": faculty_code, "teaching_requirement_id": r["id"]},
        ))
    return findings


def run_staffing_rules(conn: sqlite3.Connection) -> list[Finding]:
    return [*teaching_requirement_blocking(conn)]
