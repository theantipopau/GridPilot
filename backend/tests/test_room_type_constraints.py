"""Synthetic-fixture tests for room-type constraint detection
(app/analysis/room_type_constraints.py) - the inference step behind
docs/solver.md section 4.2. No real school data - see tests/synthetic.py."""

from app.analysis.room_type_constraints import detect_room_type_candidates
from tests.synthetic import add_lesson, build_richer_synthetic_db


def _set_room_type(conn, room_id, room_type):
    conn.execute("UPDATE room SET room_type = ? WHERE id = ?", (room_type, room_id))
    conn.commit()


def test_class_using_one_room_type_for_every_lesson_is_a_candidate():
    conn = build_richer_synthetic_db()
    _set_room_type(conn, 1, "Science")
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)

    candidates = detect_room_type_candidates(conn)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.class_code == "CLASSA"
    assert c.room_type == "Science"
    assert (c.matching_lesson_count, c.total_lesson_count) == (2, 2)


def test_class_below_the_ratio_threshold_is_not_a_candidate():
    conn = build_richer_synthetic_db()
    _set_room_type(conn, 1, "Science")
    _set_room_type(conn, 2, "Classroom")
    _set_room_type(conn, 3, "Classroom")
    # 2/5 Science, 3/5 Classroom - majority (Classroom, 60%) is still below
    # MIN_RATIO=0.7, so this must not be proposed as a candidate at all.
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=4, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=2)
    add_lesson(conn, day_id=2, period_id=5, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=2)
    add_lesson(conn, day_id=3, period_id=6, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=3)

    assert detect_room_type_candidates(conn) == []


def test_class_at_the_ratio_threshold_is_a_candidate_with_the_majority_type():
    conn = build_richer_synthetic_db()
    _set_room_type(conn, 1, "Science")
    _set_room_type(conn, 2, "Classroom")
    # 4/5 Science (80%, above MIN_RATIO=0.7) - majority type wins even
    # though one lesson used a different room.
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=4, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=2, period_id=5, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=3, period_id=6, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=2)

    candidates = detect_room_type_candidates(conn)
    assert len(candidates) == 1
    assert candidates[0].room_type == "Science"
    assert (candidates[0].matching_lesson_count, candidates[0].total_lesson_count) == (4, 5)


def test_a_single_typed_lesson_is_never_enough_signal_on_its_own():
    """MIN_LESSONS guards against a class with only one typed lesson
    producing a spurious 100%-confidence candidate."""
    conn = build_richer_synthetic_db()
    _set_room_type(conn, 1, "Science")
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)

    assert detect_room_type_candidates(conn) == []


def test_lessons_in_untyped_rooms_are_excluded_from_the_ratio():
    """A room with no room_type (NULL, e.g. a room whose Notes column was
    blank in the source export) contributes no evidence either way - it
    must not be silently treated as a mismatch against the class's other,
    typed lessons."""
    conn = build_richer_synthetic_db()
    _set_room_type(conn, 1, "Science")
    # room 2 keeps room_type = NULL (build_richer_synthetic_db's default)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=4, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=2)

    candidates = detect_room_type_candidates(conn)
    assert len(candidates) == 1
    assert candidates[0].room_type == "Science"
    assert (candidates[0].matching_lesson_count, candidates[0].total_lesson_count) == (2, 2)
