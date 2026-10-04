"""Synthetic-fixture tests for the Loads view's per-teacher breakdown
(app/analysis/teacher_loads.py). No real school data - see
tests/synthetic.py."""

from app.analysis.teacher_loads import compute_teacher_loads
from tests.synthetic import add_lesson, build_richer_synthetic_db


def _by_code(result):
    return {t["code"]: t for t in result["teachers"]}


def test_scheduled_minutes_are_distinct_teacher_period_slots():
    conn = build_richer_synthetic_db()
    conn.execute("UPDATE teacher SET contracted_load_minutes = 600 WHERE id = 1")
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)

    t1 = _by_code(compute_teacher_loads(conn))["T1"]
    assert t1["scheduled_minutes"] == 120  # two 60-minute LESSON_SLOT periods
    assert t1["contracted_minutes"] == 600
    assert t1["remaining_minutes"] == 480
    assert t1["percent_of_contract"] == 20.0
    assert t1["teaching_periods"] == 2


def test_a_composite_slot_counts_once_not_once_per_class_code():
    conn = build_richer_synthetic_db()
    # Same teacher, same period, two class codes at once (a composite lesson).
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=1, room_id=1)

    t1 = _by_code(compute_teacher_loads(conn))["T1"]
    assert t1["scheduled_minutes"] == 60
    assert t1["teaching_periods"] == 1
    assert t1["class_count"] == 2  # but both classes are still taught


def test_remaining_minutes_go_negative_when_over_contract():
    conn = build_richer_synthetic_db()
    conn.execute("UPDATE teacher SET contracted_load_minutes = 60 WHERE id = 1")
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)

    t1 = _by_code(compute_teacher_loads(conn))["T1"]
    assert t1["remaining_minutes"] == -60
    assert t1["percent_of_contract"] == 200.0


def test_a_teacher_with_no_lessons_is_included_with_zero_load():
    conn = build_richer_synthetic_db()
    conn.execute("UPDATE teacher SET contracted_load_minutes = 600 WHERE id = 2")

    t2 = _by_code(compute_teacher_loads(conn))["T2"]
    assert t2["scheduled_minutes"] == 0
    assert t2["teaching_periods"] == 0
    assert t2["percent_of_contract"] == 0.0
    assert all(d["minutes"] == 0 for d in t2["by_day"])


def test_no_contracted_figure_means_no_percentage_not_a_crash():
    conn = build_richer_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)

    t1 = _by_code(compute_teacher_loads(conn))["T1"]  # synthetic teachers have no contracted_load_minutes
    assert t1["contracted_minutes"] is None
    assert t1["remaining_minutes"] is None
    assert t1["percent_of_contract"] is None
    assert t1["scheduled_minutes"] == 60


def test_by_day_spreads_minutes_across_the_cycle_in_day_order():
    conn = build_richer_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=4, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)

    result = compute_teacher_loads(conn)
    t1 = _by_code(result)["T1"]
    assert result["days"] == ["Day 1 A", "Day 2 A", "Day 3 A"]
    assert [(d["day_code"], d["minutes"], d["periods"]) for d in t1["by_day"]] == [
        ("Day 1 A", 120.0, 2), ("Day 2 A", 60.0, 1), ("Day 3 A", 0.0, 0),
    ]


def test_subject_and_year_level_breadth_are_reported():
    conn = build_richer_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)  # SUBA
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=2, class_name_id=2, teacher_id=1, room_id=1)  # SUBB

    t1 = _by_code(compute_teacher_loads(conn))["T1"]
    assert t1["subject_count"] == 2
    assert t1["year_levels"] == ["07"]


def test_non_contact_entry_types_are_excluded_from_scheduled_minutes():
    conn = build_richer_synthetic_db()
    conn.execute(
        "INSERT INTO timetable_entry (source_ref, day_id, period_id, roll_class_id, teacher_id, entry_type) "
        "VALUES ('test', 1, 1, 1, 1, 'ASSEMBLY')"
    )
    conn.commit()

    t1 = _by_code(compute_teacher_loads(conn))["T1"]
    assert t1["scheduled_minutes"] == 0  # LESSON-only until an agreement confirms a wider definition
