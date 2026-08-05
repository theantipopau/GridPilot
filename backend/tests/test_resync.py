"""Tests for app.db.resync - re-ingest that carries forward human-made
decisions (composite group reviews, proposed changes, the audit trail)
instead of wiping them, per docs/reingest-persistence.md.

Deliberately reseeds source tables in a different insertion order than
tests/synthetic.build_synthetic_db() uses (a decoy row inserted first
shifts every autoincrement id) - this proves restoration is genuinely
code-based, not an accidental id coincidence that would happen to work
just because SQLite reused the same row ids."""

import sqlite3

from app.changes.service import add_proposed_change, create_change_set
from app.db.resync import resync_source_tables
from tests.synthetic import add_lesson, build_synthetic_db


def _reseed_shifted(conn: sqlite3.Connection, *, include_room2: bool = True, include_class_b: bool = True) -> None:
    conn.execute("INSERT INTO day (code, day_no, week_label) VALUES ('Day 1 A', 1, 'A')")
    conn.execute("INSERT INTO day (code, day_no, week_label) VALUES ('Day 2 A', 2, 'A')")
    day1 = conn.execute("SELECT id FROM day WHERE code = 'Day 1 A'").fetchone()["id"]

    day2 = conn.execute("SELECT id FROM day WHERE code = 'Day 2 A'").fetchone()["id"]
    conn.execute(
        "INSERT INTO period (code, name, day_id, period_no, load_minutes, entry_kind) "
        "VALUES ('P1', 'Period 1', ?, 1, 60, 'LESSON_SLOT')", (day1,),
    )
    # Same code ('P1') on a different day, exactly as the real 10-day cycle
    # repeats period codes daily (schema.sql: UNIQUE is (day_id, period_no),
    # never on code alone) - this is what exposed the original bug, where a
    # plain {code: id} lookup silently resolved to whichever day happened to
    # be inserted last.
    conn.execute(
        "INSERT INTO period (code, name, day_id, period_no, load_minutes, entry_kind) "
        "VALUES ('P1', 'Period 1', ?, 1, 60, 'LESSON_SLOT')", (day2,),
    )
    p1_day1 = conn.execute("SELECT id FROM period WHERE code = 'P1' AND day_id = ?", (day1,)).fetchone()["id"]

    # Decoy rows inserted first so T1/R1 land on different ids than they had
    # before the rebuild - a real re-ingest of a new export wouldn't
    # necessarily preserve array order either.
    conn.execute("INSERT INTO room (code, name) VALUES ('R0', 'Decoy Room')")
    conn.execute("INSERT INTO room (code, name) VALUES ('R1', 'Room 1')")
    room1 = conn.execute("SELECT id FROM room WHERE code = 'R1'").fetchone()["id"]
    if include_room2:
        conn.execute("INSERT INTO room (code, name) VALUES ('R2', 'Room 2')")

    conn.execute("INSERT INTO teacher (code, first_name, last_name) VALUES ('T0', 'Decoy', 'Teacher')")
    conn.execute("INSERT INTO teacher (code, first_name, last_name) VALUES ('T1', 'Test', 'One')")
    teacher1 = conn.execute("SELECT id FROM teacher WHERE code = 'T1'").fetchone()["id"]
    conn.execute("INSERT INTO teacher (code, first_name, last_name) VALUES ('T2', 'Test', 'Two')")

    conn.execute("INSERT INTO year_level (code) VALUES ('07')")
    year_level = conn.execute("SELECT id FROM year_level WHERE code = '07'").fetchone()["id"]
    conn.execute("INSERT INTO roll_class (code, year_level_id) VALUES ('7A', ?)", (year_level,))
    roll_class1 = conn.execute("SELECT id FROM roll_class WHERE code = '7A'").fetchone()["id"]
    conn.execute("INSERT INTO roll_class (code, year_level_id) VALUES ('7B', ?)", (year_level,))

    conn.execute("INSERT INTO subject (source_code, name) VALUES ('SUBA', 'Subject A')")
    subject_a = conn.execute("SELECT id FROM subject WHERE source_code = 'SUBA'").fetchone()["id"]
    conn.execute("INSERT INTO class_name (code, name, subject_id) VALUES ('CLASSA', 'Class A', ?)", (subject_a,))
    class_a = conn.execute("SELECT id FROM class_name WHERE code = 'CLASSA'").fetchone()["id"]
    if include_class_b:
        conn.execute("INSERT INTO subject (source_code, name) VALUES ('SUBB', 'Subject B')")
        subject_b = conn.execute("SELECT id FROM subject WHERE source_code = 'SUBB'").fetchone()["id"]
        conn.execute("INSERT INTO class_name (code, name, subject_id) VALUES ('CLASSB', 'Class B', ?)", (subject_b,))

    conn.execute(
        "INSERT INTO timetable_entry (source_ref, day_id, period_id, roll_class_id, class_name_id, "
        "room_id, teacher_id, entry_type) VALUES ('test', ?, ?, ?, ?, ?, ?, 'LESSON')",
        (day1, p1_day1, roll_class1, class_a, room1, teacher1),
    )
    conn.commit()


def _insert_composite_group(conn: sqlite3.Connection, *, teacher_id: int, room_id: int,
                             member_class_name_ids: list[int], review_status: str = "APPROVED") -> int:
    cur = conn.execute(
        "INSERT INTO composite_group (teacher_id, room_id, review_status, slot_count, detected_at, "
        "reviewed_at, reviewed_by, review_note) VALUES (?, ?, ?, 1, 'test', 'test', 'reviewer', 'confirmed real')",
        (teacher_id, room_id, review_status),
    )
    group_id = cur.lastrowid
    conn.executemany(
        "INSERT INTO composite_group_member (composite_group_id, class_name_id) VALUES (?, ?)",
        [(group_id, cid) for cid in member_class_name_ids],
    )
    conn.commit()
    return group_id


def test_approved_composite_review_survives_reingest_by_code():
    conn = build_synthetic_db()
    _insert_composite_group(conn, teacher_id=1, room_id=1, member_class_name_ids=[1, 2])

    resync_source_tables(conn, lambda: _reseed_shifted(conn))

    groups = conn.execute("SELECT * FROM composite_group").fetchall()
    assert len(groups) == 1
    new_group = groups[0]
    assert new_group["review_status"] == "APPROVED"
    assert new_group["reviewed_by"] == "reviewer"
    assert new_group["review_note"] == "confirmed real"

    new_teacher_id = conn.execute("SELECT id FROM teacher WHERE code = 'T1'").fetchone()["id"]
    new_room_id = conn.execute("SELECT id FROM room WHERE code = 'R1'").fetchone()["id"]
    assert new_group["teacher_id"] == new_teacher_id
    assert new_group["room_id"] == new_room_id

    member_codes = {
        r["code"] for r in conn.execute(
            "SELECT cn.code FROM composite_group_member cgm JOIN class_name cn ON cn.id = cgm.class_name_id "
            "WHERE cgm.composite_group_id = ?", (new_group["id"],)
        )
    }
    assert member_codes == {"CLASSA", "CLASSB"}


def test_composite_review_dropped_when_member_class_disappears():
    conn = build_synthetic_db()
    _insert_composite_group(conn, teacher_id=1, room_id=1, member_class_name_ids=[1, 2])

    result = resync_source_tables(conn, lambda: _reseed_shifted(conn, include_class_b=False))

    assert result["composite_groups"] == {"restored": 0, "dropped": 1}
    assert conn.execute("SELECT COUNT(*) FROM composite_group").fetchone()[0] == 0

    audit = conn.execute(
        "SELECT * FROM audit_event WHERE event_type = 'composite_review_dropped_on_reingest'"
    ).fetchone()
    assert audit is not None
    assert "CLASSB" not in (audit["detail_json"] or "") or "CLASSA" in audit["detail_json"]


def test_proposed_change_moved_to_a_different_day_with_the_same_period_code_resolves_correctly():
    """Regression test for a real bug found against production data: period
    codes repeat once per day (P1 on day 1, P1 on day 2, ...), so a lookup
    keyed only by period code silently resolved to the wrong day's period.
    Moving a lesson to day 2's P1 (same code as day 1's P1) must land on
    day 2's period, not get confused with day 1's."""
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    entry_id = conn.execute(
        "SELECT id FROM timetable_entry WHERE day_id=1 AND period_id=1 AND roll_class_id=1"
    ).fetchone()["id"]

    cs_id = create_change_set(conn, "Move to day 2's P1", None, "tester")
    add_proposed_change(conn, cs_id, entry_id, after_day_id=2, after_period_id=3, reason="move a day")

    resync_source_tables(conn, lambda: _reseed_shifted(conn))

    pc = conn.execute("SELECT * FROM proposed_change WHERE change_set_id = ?", (cs_id,)).fetchone()
    assert pc is not None

    new_day2_p1_id = conn.execute(
        "SELECT p.id FROM period p JOIN day d ON d.id = p.day_id WHERE d.code = 'Day 2 A' AND p.code = 'P1'"
    ).fetchone()["id"]
    new_day1_p1_id = conn.execute(
        "SELECT p.id FROM period p JOIN day d ON d.id = p.day_id WHERE d.code = 'Day 1 A' AND p.code = 'P1'"
    ).fetchone()["id"]
    assert new_day1_p1_id != new_day2_p1_id  # sanity: genuinely two distinct periods sharing a code
    assert pc["after_period_id"] == new_day2_p1_id
    assert pc["before_period_id"] == new_day1_p1_id


def test_proposed_change_survives_reingest_by_code():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    entry_id = conn.execute(
        "SELECT id FROM timetable_entry WHERE day_id=1 AND period_id=1 AND roll_class_id=1"
    ).fetchone()["id"]

    cs_id = create_change_set(conn, "Move to R2", None, "tester")
    add_proposed_change(conn, cs_id, entry_id, after_room_id=2, reason="free up R1")

    resync_source_tables(conn, lambda: _reseed_shifted(conn))

    changes = conn.execute("SELECT * FROM proposed_change WHERE change_set_id = ?", (cs_id,)).fetchall()
    assert len(changes) == 1
    pc = changes[0]

    new_entry_id = conn.execute(
        "SELECT te.id FROM timetable_entry te JOIN roll_class rc ON rc.id = te.roll_class_id "
        "JOIN day d ON d.id = te.day_id JOIN period p ON p.id = te.period_id "
        "WHERE rc.code = '7A' AND d.code = 'Day 1 A' AND p.code = 'P1'"
    ).fetchone()["id"]
    assert pc["timetable_entry_id"] == new_entry_id

    new_room2_id = conn.execute("SELECT id FROM room WHERE code = 'R2'").fetchone()["id"]
    assert pc["after_room_id"] == new_room2_id
    assert pc["reason"] == "free up R1"

    # change_set itself was never touched (no source FK) - id is stable.
    row = conn.execute("SELECT * FROM change_set WHERE id = ?", (cs_id,)).fetchone()
    assert row["approval_status"] == "DRAFT"


def test_proposed_change_dropped_and_change_set_flagged_when_target_room_disappears():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    entry_id = conn.execute(
        "SELECT id FROM timetable_entry WHERE day_id=1 AND period_id=1 AND roll_class_id=1"
    ).fetchone()["id"]

    cs_id = create_change_set(conn, "Move to R2", None, "tester")
    add_proposed_change(conn, cs_id, entry_id, after_room_id=2)
    conn.execute("UPDATE change_set SET validation_status = 'VALID' WHERE id = ?", (cs_id,))
    conn.commit()

    result = resync_source_tables(conn, lambda: _reseed_shifted(conn, include_room2=False))

    assert result["proposed_changes"] == {"restored": 0, "dropped": 1}
    assert conn.execute(
        "SELECT COUNT(*) FROM proposed_change WHERE change_set_id = ?", (cs_id,)
    ).fetchone()[0] == 0

    row = conn.execute("SELECT validation_status FROM change_set WHERE id = ?", (cs_id,)).fetchone()
    assert row["validation_status"] == "NOT_VALIDATED"

    audit = conn.execute(
        "SELECT * FROM audit_event WHERE event_type = 'proposed_change_dropped_on_reingest'"
    ).fetchone()
    assert audit is not None


def test_findings_and_audit_trail_are_left_alone_by_resync():
    conn = build_synthetic_db()
    conn.execute(
        "INSERT INTO finding (dedupe_key, rule_id, severity, title, entity_refs_json, slot_refs_json, "
        "evidence_json, status, first_seen_at, computed_at) VALUES ('k1', 'rule', 'info', 'Old finding', "
        "'[]', '[]', '{}', 'ACKNOWLEDGED', 'test', 'test')"
    )
    conn.commit()
    finding_id = conn.execute("SELECT id FROM finding WHERE dedupe_key = 'k1'").fetchone()["id"]

    resync_source_tables(conn, lambda: _reseed_shifted(conn))

    row = conn.execute("SELECT * FROM finding WHERE id = ?", (finding_id,)).fetchone()
    assert row is not None
    assert row["status"] == "ACKNOWLEDGED"  # untouched - resync never writes to finding

    # A summary event for this resync itself should now exist too.
    summary = conn.execute(
        "SELECT * FROM audit_event WHERE event_type = 'reingest_state_carried_forward'"
    ).fetchone()
    assert summary is not None
