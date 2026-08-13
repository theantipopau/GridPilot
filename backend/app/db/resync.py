"""Re-ingest that preserves human-made review decisions (composite group
reviews, room-type constraint reviews, change sets, audit trail) across a
refreshed .tfx/.sfx export, instead of wiping the whole working database
on every ingest.

Previously every ingest called app.db.connection.fresh_database(), which
deletes the entire SQLite file - meaning approved/rejected composite
reviews, in-progress change sets, and the audit trail were silently lost
every time a new export replaced the old one. This was flagged as the
top-priority known weakness in docs/project-status.md. fresh_database()
is still used for a brand-new database with nothing to preserve, and is
untouched here - many tests depend on its "always a truly empty db"
behaviour.

Design: tables that describe the source export (day, period, room,
teacher, timetable_entry, ...) are rebuilt from scratch every ingest, as
before - there's no meaningful way to "diff" a resolved timetable against
a new term's export. Tables that hold a human decision are snapshotted by
*code* (teacher code, room code, class code, day code, period code)
rather than internal integer id before the rebuild, then re-linked
against the freshly-ingested rows afterwards - internal ids are only
stable within one ingest, never across two.

finding and audit_event need no snapshot/remap at all: findings are
already keyed by dedupe_key() (code-based, see app.analysis.models) and
simply left in the table across the rebuild (nothing here deletes from
finding); audit events carry no FK into any source table. change_set
rows likewise carry no source FK and are left alone; only its child
proposed_change rows need remapping.

A link that can't be re-resolved (e.g. a composite review's teacher code
no longer exists in the new export, or a proposed change's lesson slot no
longer exists) is dropped, never guessed at - and always logged via
audit_event, per the project's established 'fail loudly, never silently
drop' rule (see docs/rules.md, docs/tfx-compatibility.md)."""

import sqlite3
from typing import Callable

from app.audit import log_event

# Tables that are entirely rebuilt from the source export every ingest,
# deleted in an order that respects every foreign key among them (a child
# table - the one holding the FK column - always comes before the parent
# table it references). Anything NOT in this list (finding, audit_event,
# change_set, ingest_run, ingest_discrepancy, and the composite_group*/
# class_room_type_constraint/proposed_change* tables, handled separately
# below) is left untouched by this delete pass.
SOURCE_TABLES_IN_DELETE_ORDER = [
    "class_group_course_room_override",
    "enrolment",
    "sfx_constraint_option",
    "sfx_student_preference",
    "sfx_constraint",
    "sfx_class",
    "sfx_option",
    "sfx_subject",
    "sfx_line",
    "sfx_file",
    "timetable_entry",
    "class_group_course",
    "blocking_line_class_group",
    "blocking_line",
    "class_group",
    "room_pool_class_name",
    "class_name",
    "subject",
    "yard_duty_allocation",
    "yard_duty_session",
    "yard_duty_area",
    "student",
    "roll_class",
    "teacher_faculty",
    "teacher",
    "faculty",
    "room_pool_room",
    "room_pool",
    "room",
    "period",
    "year_level",
    "day",
    "school_setting",
]


def _snapshot_composite_groups(conn: sqlite3.Connection) -> list[dict]:
    groups = conn.execute(
        "SELECT cg.id, cg.review_status, cg.slot_count, cg.detected_at, cg.reviewed_at, "
        "cg.reviewed_by, cg.review_note, t.code AS teacher_code, r.code AS room_code "
        "FROM composite_group cg "
        "JOIN teacher t ON t.id = cg.teacher_id "
        "JOIN room r ON r.id = cg.room_id"
    ).fetchall()
    members_by_group: dict[int, list[str]] = {}
    for row in conn.execute(
        "SELECT cgm.composite_group_id, cn.code AS class_code "
        "FROM composite_group_member cgm JOIN class_name cn ON cn.id = cgm.class_name_id"
    ):
        members_by_group.setdefault(row["composite_group_id"], []).append(row["class_code"])

    return [
        {
            "review_status": g["review_status"],
            "slot_count": g["slot_count"],
            "detected_at": g["detected_at"],
            "reviewed_at": g["reviewed_at"],
            "reviewed_by": g["reviewed_by"],
            "review_note": g["review_note"],
            "teacher_code": g["teacher_code"],
            "room_code": g["room_code"],
            "member_class_codes": members_by_group.get(g["id"], []),
        }
        for g in groups
    ]


def _snapshot_room_type_constraints(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT crtc.room_type, crtc.review_status, crtc.matching_lesson_count, crtc.total_lesson_count, "
        "crtc.detected_at, crtc.reviewed_at, crtc.reviewed_by, crtc.review_note, cn.code AS class_code "
        "FROM class_room_type_constraint crtc "
        "JOIN class_name cn ON cn.id = crtc.class_name_id"
    ).fetchall()
    return [dict(r) for r in rows]


def _snapshot_proposed_changes(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT pc.id, pc.change_set_id, pc.reason, rc.code AS roll_class_code, "
        "bd.code AS before_day_code, bp.code AS before_period_code, "
        "br.code AS before_room_code, bt.code AS before_teacher_code, "
        "ad.code AS after_day_code, ap.code AS after_period_code, "
        "ar.code AS after_room_code, at.code AS after_teacher_code "
        "FROM proposed_change pc "
        "JOIN timetable_entry te ON te.id = pc.timetable_entry_id "
        "JOIN roll_class rc ON rc.id = te.roll_class_id "
        "JOIN day bd ON bd.id = pc.before_day_id "
        "JOIN period bp ON bp.id = pc.before_period_id "
        "LEFT JOIN room br ON br.id = pc.before_room_id "
        "LEFT JOIN teacher bt ON bt.id = pc.before_teacher_id "
        "JOIN day ad ON ad.id = pc.after_day_id "
        "JOIN period ap ON ap.id = pc.after_period_id "
        "LEFT JOIN room ar ON ar.id = pc.after_room_id "
        "LEFT JOIN teacher at ON at.id = pc.after_teacher_id"
    ).fetchall()
    finding_ids_by_change: dict[int, list[int]] = {}
    for r in conn.execute("SELECT proposed_change_id, finding_id FROM proposed_change_finding"):
        finding_ids_by_change.setdefault(r["proposed_change_id"], []).append(r["finding_id"])

    return [{**dict(row), "finding_ids": finding_ids_by_change.get(row["id"], [])} for row in rows]


def _detach_app_owned_links(conn: sqlite3.Connection) -> None:
    """Removes the rows that hold a *live* FK into source tables, now that
    they've been snapshotted by code above. composite_group/proposed_change/
    class_room_type_constraint are re-created after the rebuild from their
    snapshots; their parent change_set row (proposed_change's case) is
    untouched throughout."""
    conn.execute("DELETE FROM composite_group_member")
    conn.execute("DELETE FROM composite_group")
    conn.execute("DELETE FROM class_room_type_constraint")
    conn.execute("DELETE FROM proposed_change_finding")
    conn.execute("DELETE FROM proposed_change")


def _rebuild_source_tables(conn: sqlite3.Connection) -> None:
    for table in SOURCE_TABLES_IN_DELETE_ORDER:
        conn.execute(f"DELETE FROM {table}")


def _restore_composite_groups(conn: sqlite3.Connection, snapshot: list[dict]) -> dict[str, int]:
    teacher_id_by_code = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM teacher")}
    room_id_by_code = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM room")}
    class_name_id_by_code = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM class_name")}

    restored = 0
    dropped = 0
    for g in snapshot:
        teacher_id = teacher_id_by_code.get(g["teacher_code"])
        room_id = room_id_by_code.get(g["room_code"])
        member_ids = [class_name_id_by_code.get(c) for c in g["member_class_codes"]]
        if teacher_id is None or room_id is None or not member_ids or any(m is None for m in member_ids):
            dropped += 1
            log_event(
                conn, "composite_review_dropped_on_reingest",
                f"A {g['review_status']} composite group review could not be carried forward into the "
                "new export - its teacher, room, or a member class code no longer exists.",
                entity_type="composite_group",
                detail={"teacher_code": g["teacher_code"], "room_code": g["room_code"],
                        "member_class_codes": g["member_class_codes"], "review_status": g["review_status"]},
            )
            continue
        cur = conn.execute(
            "INSERT INTO composite_group (teacher_id, room_id, review_status, slot_count, detected_at, "
            "reviewed_at, reviewed_by, review_note) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (teacher_id, room_id, g["review_status"], g["slot_count"], g["detected_at"],
             g["reviewed_at"], g["reviewed_by"], g["review_note"]),
        )
        group_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO composite_group_member (composite_group_id, class_name_id) VALUES (?, ?)",
            [(group_id, mid) for mid in member_ids],
        )
        restored += 1
    return {"restored": restored, "dropped": dropped}


def _restore_room_type_constraints(conn: sqlite3.Connection, snapshot: list[dict]) -> dict[str, int]:
    class_name_id_by_code = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM class_name")}

    restored = 0
    dropped = 0
    for c in snapshot:
        class_name_id = class_name_id_by_code.get(c["class_code"])
        if class_name_id is None:
            dropped += 1
            log_event(
                conn, "room_type_constraint_dropped_on_reingest",
                f"A {c['review_status']} room-type constraint could not be carried forward into the "
                "new export - its class code no longer exists.",
                entity_type="class_room_type_constraint",
                detail={"class_code": c["class_code"], "room_type": c["room_type"], "review_status": c["review_status"]},
            )
            continue
        conn.execute(
            "INSERT INTO class_room_type_constraint (class_name_id, room_type, review_status, "
            "matching_lesson_count, total_lesson_count, detected_at, reviewed_at, reviewed_by, review_note) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (class_name_id, c["room_type"], c["review_status"], c["matching_lesson_count"], c["total_lesson_count"],
             c["detected_at"], c["reviewed_at"], c["reviewed_by"], c["review_note"]),
        )
        restored += 1
    return {"restored": restored, "dropped": dropped}


def _restore_proposed_changes(conn: sqlite3.Connection, snapshot: list[dict]) -> dict[str, int]:
    roll_class_id_by_code = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM roll_class")}
    day_id_by_code = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM day")}
    # Period codes (P1, P5, FB, ...) repeat once per day of the cycle - NOT
    # globally unique (see schema.sql's UNIQUE (day_id, period_no)) - so a
    # period must be resolved as "this code, on that specific day", never by
    # code alone, or this would silently resolve to a different day's period.
    period_id_by_day_and_code = {(r["day_id"], r["code"]): r["id"] for r in conn.execute("SELECT id, day_id, code FROM period")}
    room_id_by_code = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM room")}
    teacher_id_by_code = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM teacher")}

    affected_change_sets: set[int] = set()
    restored = 0
    dropped = 0
    for pc in snapshot:
        roll_class_id = roll_class_id_by_code.get(pc["roll_class_code"])
        before_day_id = day_id_by_code.get(pc["before_day_code"])
        after_day_id = day_id_by_code.get(pc["after_day_code"])
        before_period_id = period_id_by_day_and_code.get((before_day_id, pc["before_period_code"])) if before_day_id else None
        after_period_id = period_id_by_day_and_code.get((after_day_id, pc["after_period_code"])) if after_day_id else None

        timetable_entry_id = None
        if roll_class_id and before_day_id and before_period_id:
            row = conn.execute(
                "SELECT id FROM timetable_entry WHERE roll_class_id = ? AND day_id = ? AND period_id = ?",
                (roll_class_id, before_day_id, before_period_id),
            ).fetchone()
            timetable_entry_id = row["id"] if row else None

        before_room_id = room_id_by_code.get(pc["before_room_code"]) if pc["before_room_code"] else None
        before_teacher_id = teacher_id_by_code.get(pc["before_teacher_code"]) if pc["before_teacher_code"] else None
        after_room_id = room_id_by_code.get(pc["after_room_code"]) if pc["after_room_code"] else None
        after_teacher_id = teacher_id_by_code.get(pc["after_teacher_code"]) if pc["after_teacher_code"] else None

        unresolved = (
            timetable_entry_id is None or after_day_id is None or after_period_id is None
            or (pc["before_room_code"] and before_room_id is None)
            or (pc["before_teacher_code"] and before_teacher_id is None)
            or (pc["after_room_code"] and after_room_id is None)
            or (pc["after_teacher_code"] and after_teacher_id is None)
        )
        if unresolved:
            dropped += 1
            affected_change_sets.add(pc["change_set_id"])
            log_event(
                conn, "proposed_change_dropped_on_reingest",
                "A proposed change could not be carried forward into the new export - the lesson "
                "slot, room, or teacher it referenced no longer exists.",
                entity_type="change_set", entity_id=pc["change_set_id"],
                detail={"roll_class_code": pc["roll_class_code"], "before_day_code": pc["before_day_code"],
                        "before_period_code": pc["before_period_code"]},
            )
            continue

        cur = conn.execute(
            "INSERT INTO proposed_change (change_set_id, timetable_entry_id, before_day_id, before_period_id, "
            "before_room_id, before_teacher_id, after_day_id, after_period_id, after_room_id, after_teacher_id, "
            "reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (pc["change_set_id"], timetable_entry_id, before_day_id, before_period_id, before_room_id,
             before_teacher_id, after_day_id, after_period_id, after_room_id, after_teacher_id, pc["reason"]),
        )
        new_id = cur.lastrowid
        for finding_id in pc["finding_ids"]:
            conn.execute(
                "INSERT OR IGNORE INTO proposed_change_finding (proposed_change_id, finding_id) VALUES (?, ?)",
                (new_id, finding_id),
            )
        restored += 1

    if affected_change_sets:
        conn.executemany(
            "UPDATE change_set SET validation_status = 'NOT_VALIDATED', validation_result_json = NULL "
            "WHERE id = ? AND approval_status = 'DRAFT'",
            [(cs_id,) for cs_id in affected_change_sets],
        )
    return {"restored": restored, "dropped": dropped}


def resync_source_tables(conn: sqlite3.Connection, ingest_fn: Callable[[], None]) -> dict:
    """Rebuilds every source-derived table (via ingest_fn, which does the
    actual .tfx/CSV/eMinerva/.sfx parsing against `conn`) while carrying
    forward composite group reviews and proposed changes by code, and
    leaving findings, the audit trail, and change_set rows untouched.

    Use this instead of app.db.connection.fresh_database() whenever the
    working database might already hold human-made decisions worth
    keeping - i.e. every ingest after the first."""
    composite_snapshot = _snapshot_composite_groups(conn)
    room_type_snapshot = _snapshot_room_type_constraints(conn)
    proposed_change_snapshot = _snapshot_proposed_changes(conn)

    _detach_app_owned_links(conn)
    _rebuild_source_tables(conn)
    conn.commit()

    ingest_fn()

    composite_result = _restore_composite_groups(conn, composite_snapshot)
    room_type_result = _restore_room_type_constraints(conn, room_type_snapshot)
    proposed_result = _restore_proposed_changes(conn, proposed_change_snapshot)
    conn.commit()

    log_event(
        conn, "reingest_state_carried_forward",
        f"Re-ingest carried forward {composite_result['restored']} composite review(s) "
        f"({composite_result['dropped']} dropped), {room_type_result['restored']} room-type "
        f"constraint(s) ({room_type_result['dropped']} dropped), and {proposed_result['restored']} "
        f"proposed change(s) ({proposed_result['dropped']} dropped).",
        detail={"composite_groups": composite_result, "room_type_constraints": room_type_result,
                "proposed_changes": proposed_result},
    )
    conn.commit()

    return {"composite_groups": composite_result, "room_type_constraints": room_type_result,
            "proposed_changes": proposed_result}
