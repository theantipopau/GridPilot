"""Synthetic-fixture tests for app.analysis.room_type_review - the
upsert step that turns detected room-type candidates into reviewable
class_room_type_constraint rows without clobbering a human decision.
No real school data - see tests/synthetic.py."""

from app.analysis.room_type_review import sync_room_type_candidates
from tests.synthetic import add_lesson, build_richer_synthetic_db


def _set_room_type(conn, room_id, room_type):
    conn.execute("UPDATE room SET room_type = ? WHERE id = ?", (room_type, room_id))
    conn.commit()


def _seed_two_science_lessons(conn):
    _set_room_type(conn, 1, "Science")
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)


def test_first_sync_creates_a_pending_row_matching_detection():
    conn = build_richer_synthetic_db()
    _seed_two_science_lessons(conn)

    result = sync_room_type_candidates(conn)
    assert result == {"detected": 1, "created": 1, "updated": 0}

    row = conn.execute("SELECT * FROM class_room_type_constraint").fetchone()
    assert row["room_type"] == "Science"
    assert row["review_status"] == "PENDING"
    assert (row["matching_lesson_count"], row["total_lesson_count"]) == (2, 2)


def test_resync_refreshes_a_pending_rows_evidence_to_the_new_majority():
    conn = build_richer_synthetic_db()
    _seed_two_science_lessons(conn)
    sync_room_type_candidates(conn)

    # Two more lessons land: one in a different typed room, one more in
    # Science - majority is still Science (3/4 = 75%, above MIN_RATIO),
    # but the evidence counts should move since nobody has reviewed this yet.
    _set_room_type(conn, 2, "Classroom")
    add_lesson(conn, day_id=1, period_id=4, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=2)
    add_lesson(conn, day_id=2, period_id=5, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)

    result = sync_room_type_candidates(conn)
    assert result == {"detected": 1, "created": 0, "updated": 1}

    row = conn.execute("SELECT * FROM class_room_type_constraint").fetchone()
    assert row["room_type"] == "Science"
    assert (row["matching_lesson_count"], row["total_lesson_count"]) == (3, 4)


def _add_extra_lesson_slots(conn):
    """A 4th day with 3 more LESSON_SLOT periods - build_richer_synthetic_db's
    5 slots aren't enough headroom to let a majority genuinely flip to a
    different type while staying above MIN_RATIO (0.7)."""
    conn.execute("INSERT INTO day (id, code, day_no, week_label) VALUES (4, 'Day 4 A', 4, 'A')")
    conn.execute(
        "INSERT INTO period (id, code, name, day_id, period_no, load_minutes, entry_kind) "
        "VALUES (7, 'P1', 'Period 1', 4, 1, 60, 'LESSON_SLOT')"
    )
    conn.execute(
        "INSERT INTO period (id, code, name, day_id, period_no, load_minutes, entry_kind) "
        "VALUES (8, 'P2', 'Period 2', 4, 2, 60, 'LESSON_SLOT')"
    )
    conn.execute(
        "INSERT INTO period (id, code, name, day_id, period_no, load_minutes, entry_kind) "
        "VALUES (9, 'P3', 'Period 3', 4, 3, 60, 'LESSON_SLOT')"
    )
    conn.commit()


def test_resync_never_rewrites_room_type_once_approved():
    conn = build_richer_synthetic_db()
    _add_extra_lesson_slots(conn)
    _seed_two_science_lessons(conn)
    sync_room_type_candidates(conn)

    row_id = conn.execute("SELECT id FROM class_room_type_constraint").fetchone()["id"]
    conn.execute(
        "UPDATE class_room_type_constraint SET review_status = 'APPROVED', reviewed_at = 'test', "
        "reviewed_by = 'tester', review_note = 'confirmed' WHERE id = ?", (row_id,),
    )
    conn.commit()

    # Usage drifts to a genuinely different majority type after approval -
    # 6 Music lessons added on top of the 2 existing Science ones, so
    # Music (6/8 = 75%) would win the majority if room_type were blindly
    # recomputed and rewritten. It must not be.
    _set_room_type(conn, 3, "Music")
    for day_id, period_id in [(1, 4), (2, 5), (3, 6), (4, 7), (4, 8), (4, 9)]:
        add_lesson(conn, day_id=day_id, period_id=period_id, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=3)

    result = sync_room_type_candidates(conn)
    assert result["updated"] == 1

    row = conn.execute("SELECT * FROM class_room_type_constraint WHERE id = ?", (row_id,)).fetchone()
    assert row["room_type"] == "Science"  # untouched, even though Music is now the detected majority
    assert row["review_status"] == "APPROVED"
    assert row["reviewed_by"] == "tester"
    assert row["review_note"] == "confirmed"
    # Evidence counts refresh against the *stored* type (Science: still 2
    # lessons), never against the new detected majority (Music: 6) - the
    # count and the type it's evidence for must never contradict each other.
    assert (row["matching_lesson_count"], row["total_lesson_count"]) == (2, 8)


def test_resync_never_rewrites_room_type_once_rejected():
    conn = build_richer_synthetic_db()
    _seed_two_science_lessons(conn)
    sync_room_type_candidates(conn)

    row_id = conn.execute("SELECT id FROM class_room_type_constraint").fetchone()["id"]
    conn.execute(
        "UPDATE class_room_type_constraint SET review_status = 'REJECTED', reviewed_at = 'test', "
        "reviewed_by = 'tester' WHERE id = ?", (row_id,),
    )
    conn.commit()

    sync_room_type_candidates(conn)

    row = conn.execute("SELECT * FROM class_room_type_constraint WHERE id = ?", (row_id,)).fetchone()
    assert row["review_status"] == "REJECTED"
    assert row["room_type"] == "Science"
