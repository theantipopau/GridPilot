"""Synthetic-fixture tests for app.analysis.teaching_requirement_review -
the upsert step that turns detected teaching_requirement candidates into
reviewable rows without clobbering a human decision. No real school
data - see tests/synthetic.py."""

from app.analysis.teaching_requirement_review import sync_teaching_requirement_candidates
from tests.synthetic import add_lesson, build_richer_synthetic_db


def _seed_two_lessons(conn):
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)


def test_first_sync_creates_a_pending_row_matching_detection():
    conn = build_richer_synthetic_db()
    _seed_two_lessons(conn)

    result = sync_teaching_requirement_candidates(conn)
    assert result == {"detected": 1, "created": 1, "updated": 0}

    row = conn.execute("SELECT * FROM teaching_requirement").fetchone()
    assert row["requirement_key"] == "CLASSA"
    assert row["review_status"] == "PENDING"
    assert row["periods_per_cycle"] == 2
    assert row["planning_year"]  # falls back to today's year with no ingest_run present


def test_resync_refreshes_a_pending_rows_facts_to_the_new_schedule():
    conn = build_richer_synthetic_db()
    _seed_two_lessons(conn)
    sync_teaching_requirement_candidates(conn)

    add_lesson(conn, day_id=1, period_id=4, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)

    result = sync_teaching_requirement_candidates(conn)
    assert result == {"detected": 1, "created": 0, "updated": 1}

    row = conn.execute("SELECT * FROM teaching_requirement").fetchone()
    assert row["periods_per_cycle"] == 3
    assert row["total_lesson_count"] == 3


def test_resync_never_touches_an_approved_row_even_when_the_schedule_drifts():
    conn = build_richer_synthetic_db()
    _seed_two_lessons(conn)
    sync_teaching_requirement_candidates(conn)

    row_id = conn.execute("SELECT id FROM teaching_requirement").fetchone()["id"]
    conn.execute(
        "UPDATE teaching_requirement SET review_status = 'APPROVED', reviewed_at = 'test', "
        "reviewed_by = 'tester', review_note = 'confirmed' WHERE id = ?", (row_id,),
    )
    conn.commit()

    # The schedule genuinely changes (a new teacher, more lessons) after approval.
    add_lesson(conn, day_id=1, period_id=4, roll_class_id=1, class_name_id=1, teacher_id=2, room_id=2)

    result = sync_teaching_requirement_candidates(conn)
    assert result["updated"] == 0

    row = conn.execute("SELECT * FROM teaching_requirement WHERE id = ?", (row_id,)).fetchone()
    assert row["review_status"] == "APPROVED"
    assert row["reviewed_by"] == "tester"
    assert row["periods_per_cycle"] == 2  # untouched, even though 3 slots are now scheduled
    assert row["assigned_teacher_id"] == 1  # untouched


def test_resync_never_touches_a_rejected_row():
    conn = build_richer_synthetic_db()
    _seed_two_lessons(conn)
    sync_teaching_requirement_candidates(conn)

    row_id = conn.execute("SELECT id FROM teaching_requirement").fetchone()["id"]
    conn.execute(
        "UPDATE teaching_requirement SET review_status = 'REJECTED', reviewed_at = 'test', "
        "reviewed_by = 'tester' WHERE id = ?", (row_id,),
    )
    conn.commit()

    sync_teaching_requirement_candidates(conn)

    row = conn.execute("SELECT * FROM teaching_requirement WHERE id = ?", (row_id,)).fetchone()
    assert row["review_status"] == "REJECTED"
    assert row["periods_per_cycle"] == 2


def test_planning_year_is_derived_from_the_most_recent_ingest_run():
    conn = build_richer_synthetic_db()
    _seed_two_lessons(conn)
    conn.execute("INSERT INTO ingest_run (started_at) VALUES ('2026-09-14T10:00:00+00:00')")
    conn.commit()

    sync_teaching_requirement_candidates(conn)

    row = conn.execute("SELECT * FROM teaching_requirement").fetchone()
    assert row["planning_year"] == "2026"
