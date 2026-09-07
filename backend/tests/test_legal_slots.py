"""Tests for app/analysis/suggestions.py's legal_slots_for_entry() -
roadmap-v3 4.4 / full-timetabler-plan.md §12.6's per-entry candidate
endpoint, used for live legal-slot feedback in LessonInspector's
move-manually dropdowns."""

from app.analysis.suggestions import legal_slots_for_entry
from tests.synthetic import add_enrolment, add_lesson, build_richer_synthetic_db


def test_unknown_entry_returns_none():
    conn = build_richer_synthetic_db()
    assert legal_slots_for_entry(conn, 999) is None


def test_home_slot_is_legal_by_default():
    conn = build_richer_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    entry_id = conn.execute("SELECT id FROM timetable_entry WHERE entry_type = 'LESSON'").fetchone()["id"]

    result = legal_slots_for_entry(conn, entry_id)
    assert result["entry_id"] == entry_id
    assert result["class_code"] == "CLASSA"
    home = next(s for s in result["slots"] if s["day_code"] == "Day 1 A" and s["period_code"] == "P1")
    assert home["legal"] is True
    assert "R1" in home["legal_room_codes"]


def test_slot_where_teacher_has_another_fixed_lesson_is_illegal():
    conn = build_richer_synthetic_db()
    # Entry under test: T1 teaches CLASSA at day1/P1.
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    # T1 is also fixed at day2/P1 teaching something else - that slot must
    # read illegal for CLASSA even though nothing about CLASSA itself sits there.
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=2, class_name_id=2, teacher_id=1, room_id=2)
    entry_id = conn.execute("SELECT id FROM timetable_entry WHERE class_name_id = 1").fetchone()["id"]

    result = legal_slots_for_entry(conn, entry_id)
    blocked = next(s for s in result["slots"] if s["day_code"] == "Day 2 A" and s["period_code"] == "P1")
    assert blocked["legal"] is False
    assert blocked["legal_room_codes"] == []


def test_slot_where_a_shared_student_already_has_another_lesson_is_illegal():
    conn = build_richer_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=2, class_name_id=2, teacher_id=2, room_id=2)
    add_enrolment(conn, student_id=1, class_name_id=1)
    add_enrolment(conn, student_id=1, class_name_id=2)
    entry_id = conn.execute("SELECT id FROM timetable_entry WHERE class_name_id = 1").fetchone()["id"]

    result = legal_slots_for_entry(conn, entry_id)
    blocked = next(s for s in result["slots"] if s["day_code"] == "Day 2 A" and s["period_code"] == "P1")
    assert blocked["legal"] is False


def test_a_slot_free_of_teacher_and_student_conflicts_lists_every_other_free_room():
    conn = build_richer_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    entry_id = conn.execute("SELECT id FROM timetable_entry WHERE class_name_id = 1").fetchone()["id"]

    result = legal_slots_for_entry(conn, entry_id)
    free_elsewhere = next(s for s in result["slots"] if s["day_code"] == "Day 2 A" and s["period_code"] == "P1")
    assert free_elsewhere["legal"] is True
    assert set(free_elsewhere["legal_room_codes"]) == {"R1", "R2", "R3"}


def test_a_standing_teacher_commitment_blocks_a_slot_too():
    conn = build_richer_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    conn.execute("INSERT INTO teacher_commitment (teacher_id, period_id) VALUES (1, 3)")  # day2/P1
    entry_id = conn.execute("SELECT id FROM timetable_entry WHERE class_name_id = 1").fetchone()["id"]

    result = legal_slots_for_entry(conn, entry_id)
    blocked = next(s for s in result["slots"] if s["day_code"] == "Day 2 A" and s["period_code"] == "P1")
    assert blocked["legal"] is False
