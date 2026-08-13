"""Upserts detected room-type candidates (app/analysis/room_type_
constraints.py) into the reviewable class_room_type_constraint table,
without clobbering an existing human review decision - same pattern as
composite_review.py, one row per class instead of one row per detected
group.

A PENDING row's evidence (room_type, counts) is refreshed to the latest
detection on every sync - a candidate nobody has looked at yet should
always show the freshest majority. Once a human has APPROVED or REJECTED
a class's constraint, its room_type is never silently rewritten
underneath them - only the supporting counts refresh, and they refresh
against the *stored* room_type (how many of the class's current lessons
actually match what was reviewed), never against whatever type happens
to be today's majority - otherwise the counts and the type they're
supposed to be evidence for could quietly go out of sync with each
other. This is a deliberate difference from composite_review.py, where
slot_count evidence refreshes unconditionally: there, the reviewed thing
is a (teacher, room, member-set) key that can't drift; here, the
reviewed thing - room_type itself - is exactly the field usage could
drift away from."""

import datetime as dt
import sqlite3

from app.analysis.room_type_constraints import class_room_type_usage, detect_room_type_candidates


def sync_room_type_candidates(conn: sqlite3.Connection) -> dict[str, int]:
    detected = {c.class_code: c for c in detect_room_type_candidates(conn)}
    usage = class_room_type_usage(conn)
    class_name_id_by_code = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM class_name")}
    class_code_by_id = {v: k for k, v in class_name_id_by_code.items()}
    existing = {
        r["class_name_id"]: dict(r)
        for r in conn.execute(
            "SELECT id, class_name_id, room_type, review_status FROM class_room_type_constraint"
        )
    }

    now = dt.datetime.now(dt.UTC).isoformat()
    created = 0
    updated = 0

    for class_name_id, existing_row in existing.items():
        class_code = class_code_by_id.get(class_name_id)
        if class_code is None or existing_row["review_status"] == "PENDING":
            continue
        # Reviewed already: refresh only the count of lessons matching the
        # room_type that was actually reviewed, not the current majority.
        class_usage = usage.get(class_code, {})
        matching = class_usage.get(existing_row["room_type"], 0)
        total = sum(class_usage.values())
        conn.execute(
            "UPDATE class_room_type_constraint SET matching_lesson_count = ?, total_lesson_count = ?, "
            "detected_at = ? WHERE id = ?",
            (matching, total, now, existing_row["id"]),
        )
        updated += 1

    for class_code, c in detected.items():
        class_name_id = class_name_id_by_code.get(class_code)
        if class_name_id is None:
            continue
        existing_row = existing.get(class_name_id)

        if existing_row is None:
            conn.execute(
                "INSERT INTO class_room_type_constraint (class_name_id, room_type, review_status, "
                "matching_lesson_count, total_lesson_count, detected_at) VALUES (?, ?, 'PENDING', ?, ?, ?)",
                (class_name_id, c.room_type, c.matching_lesson_count, c.total_lesson_count, now),
            )
            created += 1
        elif existing_row["review_status"] == "PENDING":
            conn.execute(
                "UPDATE class_room_type_constraint SET room_type = ?, matching_lesson_count = ?, "
                "total_lesson_count = ?, detected_at = ? WHERE id = ?",
                (c.room_type, c.matching_lesson_count, c.total_lesson_count, now, existing_row["id"]),
            )
            updated += 1
        # else: already handled in the refresh pass above.

    conn.commit()
    return {"detected": len(detected), "created": created, "updated": updated}
