"""Tests app/analysis/teacher_capability_review.py - the sync that
upserts observed pairings into teacher_capability without clobbering a
human review decision. No real school data - see tests/synthetic.py."""

from app.analysis.teacher_capability_review import sync_teacher_capability_candidates
from tests.synthetic import add_lesson, build_synthetic_db


def test_new_pairing_creates_a_review_required_row():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)

    result = sync_teacher_capability_candidates(conn)
    assert result == {"detected": 1, "created": 1, "updated": 0}

    row = conn.execute("SELECT * FROM teacher_capability WHERE teacher_code = 'T1'").fetchone()
    assert row["subject_code"] == "SUBA"
    assert row["capability_status"] == "REVIEW_REQUIRED"
    assert row["source_type"] == "CURRENT_TIMETABLE_INFERRED"
    assert "1 lesson(s)" in row["notes"]


def test_resync_never_overwrites_a_reviewed_decision():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    sync_teacher_capability_candidates(conn)

    conn.execute("UPDATE teacher_capability SET capability_status = 'ELIGIBLE' WHERE teacher_code = 'T1'")
    conn.commit()

    add_lesson(conn, day_id=2, period_id=3, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    result = sync_teacher_capability_candidates(conn)
    assert result == {"detected": 1, "created": 0, "updated": 1}

    row = conn.execute("SELECT * FROM teacher_capability WHERE teacher_code = 'T1'").fetchone()
    assert row["capability_status"] == "ELIGIBLE"  # untouched
    assert "2 lesson(s)" in row["notes"]  # evidence still refreshes


def test_resync_is_idempotent():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    sync_teacher_capability_candidates(conn)
    sync_teacher_capability_candidates(conn)

    rows = conn.execute("SELECT COUNT(*) AS n FROM teacher_capability").fetchone()
    assert rows["n"] == 1
