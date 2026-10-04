"""Synthetic-fixture tests for teaching_requirement bootstrap detection
(app/analysis/teaching_requirement.py) - docs/roadmap-v3.md section 3.1.
No real school data - see tests/synthetic.py."""

from app.analysis.teaching_requirement import detect_teaching_requirement_candidates
from tests.synthetic import add_lesson, build_richer_synthetic_db


def _insert_composite_group(conn, *, teacher_id, room_id, member_class_name_ids, review_status="APPROVED"):
    cur = conn.execute(
        "INSERT INTO composite_group (teacher_id, room_id, review_status, slot_count, detected_at) "
        "VALUES (?, ?, ?, 1, 'test')",
        (teacher_id, room_id, review_status),
    )
    group_id = cur.lastrowid
    conn.executemany(
        "INSERT INTO composite_group_member (composite_group_id, class_name_id) VALUES (?, ?)",
        [(group_id, cid) for cid in member_class_name_ids],
    )
    conn.commit()
    return group_id


def test_a_plain_scheduled_class_produces_one_candidate():
    conn = build_richer_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)

    candidates = detect_teaching_requirement_candidates(conn)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.requirement_key == "CLASSA"
    assert c.class_name_id == 1
    assert c.composite_group_id is None
    assert c.roll_class_id == 1
    assert c.subject_id == 1
    assert c.periods_per_cycle == 2
    assert c.assigned_teacher_id == 1
    assert c.assigned_room_id == 1
    assert (c.matching_lesson_count, c.total_lesson_count) == (2, 2)


def test_a_class_with_no_lessons_produces_no_candidate():
    conn = build_richer_synthetic_db()
    assert detect_teaching_requirement_candidates(conn) == []


def test_a_double_period_on_the_same_day_counts_as_one_distinct_slot_pair_but_two_lessons():
    """periods_per_cycle counts distinct (day, period) slots, not lesson
    rows - two different periods on the same day are two slots."""
    conn = build_richer_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=4, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)

    candidates = detect_teaching_requirement_candidates(conn)
    assert len(candidates) == 1
    assert candidates[0].periods_per_cycle == 2
    assert candidates[0].total_lesson_count == 2


def test_majority_teacher_and_room_win_with_a_lower_matching_count():
    conn = build_richer_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    # A cover lesson in a different room - still counted in total, but not
    # matching the majority (teacher 1, room 1) pairing.
    add_lesson(conn, day_id=1, period_id=4, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=2)

    candidates = detect_teaching_requirement_candidates(conn)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.assigned_teacher_id == 1
    assert c.assigned_room_id == 1
    assert (c.matching_lesson_count, c.total_lesson_count) == (2, 3)


def test_an_approved_composite_group_collapses_its_members_into_one_candidate():
    conn = build_richer_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=1, room_id=1)
    _insert_composite_group(conn, teacher_id=1, room_id=1, member_class_name_ids=[1, 2], review_status="APPROVED")

    candidates = detect_teaching_requirement_candidates(conn)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.requirement_key == "COMPOSITE:CLASSA|CLASSB"
    assert c.class_name_id is None
    assert c.composite_group_id is not None
    assert c.roll_class_id is None  # spans two roll classes, no single value
    assert c.subject_id is None  # spans two subjects, no single value
    assert c.periods_per_cycle == 1
    assert (c.matching_lesson_count, c.total_lesson_count) == (2, 2)


def test_a_pending_composite_group_does_not_collapse_its_members():
    conn = build_richer_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=1, room_id=1)
    _insert_composite_group(conn, teacher_id=1, room_id=1, member_class_name_ids=[1, 2], review_status="PENDING")

    candidates = detect_teaching_requirement_candidates(conn)
    keys = {c.requirement_key for c in candidates}
    assert keys == {"CLASSA", "CLASSB"}
