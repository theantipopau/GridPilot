"""Tests app/analysis/teacher_capability.py - detecting which (teacher,
subject) pairs are currently observed in the timetable. No real school
data - see tests/synthetic.py."""

from app.analysis.teacher_capability import observed_teacher_subject_pairings
from tests.synthetic import add_lesson, build_synthetic_db


def test_no_lessons_no_pairings():
    conn = build_synthetic_db()
    assert observed_teacher_subject_pairings(conn) == []


def test_observed_pairing_reflects_teacher_and_subject():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)

    pairings = observed_teacher_subject_pairings(conn)
    assert len(pairings) == 1
    p = pairings[0]
    assert p.teacher_code == "T1"
    assert p.subject_code == "SUBA"  # CLASSA -> SUBA in the synthetic fixture
    assert p.lesson_count == 1


def test_same_teacher_subject_pair_counted_once_across_multiple_lessons():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)

    pairings = observed_teacher_subject_pairings(conn)
    assert len(pairings) == 1
    assert pairings[0].lesson_count == 2


def test_different_subjects_produce_separate_pairings():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=2, class_name_id=2, teacher_id=1, room_id=2)

    pairings = {(p.teacher_code, p.subject_code) for p in observed_teacher_subject_pairings(conn)}
    assert pairings == {("T1", "SUBA"), ("T1", "SUBB")}


def test_teacherless_entries_are_ignored():
    conn = build_synthetic_db()
    conn.execute(
        "INSERT INTO timetable_entry (source_ref, day_id, period_id, roll_class_id, class_name_id, "
        "entry_type) VALUES ('test', 1, 1, 1, 1, 'LESSON')"
    )
    conn.commit()
    assert observed_teacher_subject_pairings(conn) == []
