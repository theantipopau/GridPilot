"""Upserts observed (teacher, subject) pairings (app/analysis/teacher_
capability.py) into the reviewable teacher_capability table, without
clobbering an existing human review decision - same pattern as
room_type_review.py, one row per (teacher_code, subject_code) pair.

A REVIEW_REQUIRED row's supporting note (how many lessons currently
observed) refreshes on every sync - a candidate nobody has looked at yet
should always show the freshest count. Once a human has confirmed a
teacher ELIGIBLE or NOT_ELIGIBLE for a subject, that decision is never
silently overwritten - matching class_room_type_constraint's discipline
for exactly the same reason (a reviewed fact and a freshly-detected
majority must never quietly drift apart)."""

import datetime as dt
import sqlite3

from app.analysis.teacher_capability import observed_teacher_subject_pairings


def sync_teacher_capability_candidates(conn: sqlite3.Connection) -> dict[str, int]:
    detected = {(p.teacher_code, p.subject_code): p for p in observed_teacher_subject_pairings(conn)}
    existing = {
        (r["teacher_code"], r["subject_code"]): dict(r)
        for r in conn.execute(
            "SELECT id, teacher_code, subject_code, capability_status FROM teacher_capability "
            "WHERE subject_code IS NOT NULL"
        )
    }

    now = dt.datetime.now(dt.UTC).isoformat()
    today = dt.date.today().isoformat()
    created = 0
    updated = 0

    for key, pairing in detected.items():
        note = f"{pairing.lesson_count} lesson(s) observed in the current timetable"
        row = existing.get(key)
        if row is None:
            conn.execute(
                "INSERT INTO teacher_capability (teacher_code, faculty_code, subject_code, capability_status, "
                "source_type, effective_from, notes, created_at, created_by, updated_at) "
                "VALUES (?, ?, ?, 'REVIEW_REQUIRED', 'CURRENT_TIMETABLE_INFERRED', ?, ?, ?, 'system', ?)",
                (pairing.teacher_code, pairing.faculty_code, pairing.subject_code, today, note, now, now),
            )
            created += 1
        else:
            # Refresh the supporting note either way - it's evidence, not
            # the decision. The decision (capability_status) only ever
            # changes through explicit review (app/api/teacher_capability.py).
            conn.execute(
                "UPDATE teacher_capability SET notes = ?, updated_at = ? WHERE id = ?",
                (note, now, row["id"]),
            )
            updated += 1

    conn.commit()
    return {"detected": len(detected), "created": created, "updated": updated}
