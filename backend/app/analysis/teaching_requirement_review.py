"""Upserts detected teaching_requirement candidates
(app/analysis/teaching_requirement.py) into the reviewable
teaching_requirement table, without clobbering an existing human review
decision - same pattern as room_type_review.py and
teacher_capability_review.py.

Deliberately simpler than room_type_review.py's per-field evidence
refresh: once a requirement has been APPROVED or REJECTED, this sync
leaves the row entirely untouched, including its supporting lesson
counts. A teaching_requirement candidate is a bundle of several facts at
once (periods_per_cycle, assigned teacher, assigned room, roll class) -
unlike room_type's single reviewed field, there is no one "stored fact"
to refresh evidence against without inventing a drift policy for a
multi-field bundle. If a school's resolved schedule diverges from an
already-approved requirement, that is a real question for a human to
re-review, not something to fold quietly into a background count -
revisit only once real drift is observed against real data."""

import datetime as dt
import sqlite3

from app.analysis.teaching_requirement import detect_teaching_requirement_candidates


def sync_teaching_requirement_candidates(conn: sqlite3.Connection) -> dict[str, int]:
    detected = {c.requirement_key: c for c in detect_teaching_requirement_candidates(conn)}
    existing = {
        r["requirement_key"]: dict(r)
        for r in conn.execute("SELECT id, requirement_key, review_status FROM teaching_requirement")
    }

    # Models "what's currently running," not a future planning year (that
    # is the AUTHORED path - not built yet, see schema.sql).
    ingest_row = conn.execute("SELECT started_at FROM ingest_run ORDER BY id DESC LIMIT 1").fetchone()
    planning_year = ingest_row["started_at"][:4] if ingest_row and ingest_row["started_at"] else str(dt.date.today().year)

    now = dt.datetime.now(dt.UTC).isoformat()
    created = 0
    updated = 0

    for key, c in detected.items():
        row = existing.get(key)
        if row is None:
            conn.execute(
                "INSERT INTO teaching_requirement (requirement_key, class_name_id, composite_group_id, "
                "roll_class_id, subject_id, periods_per_cycle, assigned_teacher_id, assigned_room_id, "
                "matching_lesson_count, total_lesson_count, planning_year, review_status, detected_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)",
                (key, c.class_name_id, c.composite_group_id, c.roll_class_id, c.subject_id,
                 c.periods_per_cycle, c.assigned_teacher_id, c.assigned_room_id,
                 c.matching_lesson_count, c.total_lesson_count, planning_year, now),
            )
            created += 1
        elif row["review_status"] == "PENDING":
            conn.execute(
                "UPDATE teaching_requirement SET class_name_id = ?, composite_group_id = ?, roll_class_id = ?, "
                "subject_id = ?, periods_per_cycle = ?, assigned_teacher_id = ?, assigned_room_id = ?, "
                "matching_lesson_count = ?, total_lesson_count = ?, planning_year = ?, detected_at = ? "
                "WHERE id = ?",
                (c.class_name_id, c.composite_group_id, c.roll_class_id, c.subject_id, c.periods_per_cycle,
                 c.assigned_teacher_id, c.assigned_room_id, c.matching_lesson_count, c.total_lesson_count,
                 planning_year, now, row["id"]),
            )
            updated += 1
        # else: APPROVED/REJECTED - left entirely untouched, see module docstring.

    conn.commit()
    return {"detected": len(detected), "created": created, "updated": updated}
