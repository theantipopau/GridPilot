"""Synthetic-fixture tests for the capacity/load/utilisation rules. No
real school data - see tests/synthetic.py."""

from app.analysis.clash_rules import lesson_entries
from app.analysis.load_rules import (
    room_capacity_exceeded,
    room_underutilization,
    teacher_over_contracted_load,
)
from tests.synthetic import add_enrolment, add_lesson, build_synthetic_db


def test_room_capacity_not_exceeded_when_under_seats():
    conn = build_synthetic_db()
    conn.execute("UPDATE room SET seats = 2 WHERE id = 1")
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_enrolment(conn, student_id=1, class_name_id=1)

    assert room_capacity_exceeded(conn, lesson_entries(conn)) == []


def test_room_capacity_exceeded_genuine_issue():
    conn = build_synthetic_db()
    conn.execute("UPDATE room SET seats = 1 WHERE id = 1")
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    conn.execute("INSERT INTO student (id, code, roll_class_id) VALUES (2, '100002', 1)")
    add_enrolment(conn, student_id=1, class_name_id=1)
    add_enrolment(conn, student_id=2, class_name_id=1)

    findings = room_capacity_exceeded(conn, lesson_entries(conn))
    assert len(findings) == 1
    assert findings[0].evidence["enrolled_count"] == 2
    assert findings[0].evidence["seats"] == 1


def test_room_capacity_sums_composite_classes_sharing_one_room():
    """Two composite class codes in the same room/slot must have their
    enrolments summed, not checked independently - they're physically
    the same room full of students at once."""
    conn = build_synthetic_db()
    conn.execute("UPDATE room SET seats = 1 WHERE id = 1")
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=1, room_id=1)
    add_enrolment(conn, student_id=1, class_name_id=1)
    conn.execute("INSERT INTO student (id, code, roll_class_id) VALUES (2, '100002', 2)")
    add_enrolment(conn, student_id=2, class_name_id=2)

    findings = room_capacity_exceeded(conn, lesson_entries(conn))
    assert len(findings) == 1
    assert findings[0].evidence["enrolled_count"] == 2


def test_room_with_unconfirmed_capacity_is_skipped():
    """seats IS NULL means 'no fixed capacity' per docs/data-formats.md -
    must never be treated as capacity zero."""
    conn = build_synthetic_db()
    conn.execute("UPDATE room SET seats = NULL WHERE id = 1")
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_enrolment(conn, student_id=1, class_name_id=1)

    assert room_capacity_exceeded(conn, lesson_entries(conn)) == []


def test_teacher_within_contracted_load_no_finding():
    conn = build_synthetic_db()
    conn.execute("UPDATE teacher SET contracted_load_minutes = 120 WHERE id = 1")
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)

    assert teacher_over_contracted_load(conn) == []


def test_teacher_over_contracted_load_genuine_issue():
    conn = build_synthetic_db()
    conn.execute("UPDATE teacher SET contracted_load_minutes = 60 WHERE id = 1")
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)

    findings = teacher_over_contracted_load(conn)
    assert len(findings) == 1
    assert findings[0].evidence["scheduled_minutes"] == 120
    assert findings[0].evidence["contracted_load_minutes"] == 60


def test_teacher_load_does_not_double_count_composite_lesson():
    """A teacher co-teaching one physical composite lesson under two class
    codes at the same period must be charged that period's load once, not
    twice."""
    conn = build_synthetic_db()
    conn.execute("UPDATE teacher SET contracted_load_minutes = 90 WHERE id = 1")
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=1, room_id=1)

    # Both entries are the same 60-minute period; scheduled load should be
    # 60, not 120, and 60 <= 90 so no finding.
    assert teacher_over_contracted_load(conn) == []


def test_teacher_with_no_contracted_load_is_skipped():
    conn = build_synthetic_db()
    conn.execute("UPDATE teacher SET contracted_load_minutes = NULL WHERE id = 1")
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)


def test_registration_is_excluded_from_load_by_default():
    """docs/roadmap-v2.md 0.2: the LESSON-only default is unchanged unless
    a school has confirmed a wider EA definition - see test_contact_time.py."""
    conn = build_synthetic_db()
    conn.execute("UPDATE teacher SET contracted_load_minutes = 60 WHERE id = 1")
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    conn.execute(
        "INSERT INTO timetable_entry (source_ref, day_id, period_id, roll_class_id, teacher_id, entry_type) "
        "VALUES ('test-reg', 2, 3, 1, 1, 'REGISTRATION')"
    )
    conn.commit()

    assert teacher_over_contracted_load(conn) == []


def test_confirmed_agreement_widens_load_to_include_registration():
    conn = build_synthetic_db()
    conn.execute("UPDATE teacher SET contracted_load_minutes = 60 WHERE id = 1")
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    conn.execute(
        "INSERT INTO timetable_entry (source_ref, day_id, period_id, roll_class_id, teacher_id, entry_type) "
        "VALUES ('test-reg', 2, 3, 1, 1, 'REGISTRATION')"
    )
    conn.execute(
        "INSERT INTO industrial_agreement (id, name, effective_from, confirmed_by, confirmed_at, created_at) "
        "VALUES (1, 'Test EA', '2023-01-01', 'hr-rep', '2026-01-01T00:00:00', 'test')"
    )
    conn.execute(
        "INSERT INTO agreement_load_rule (agreement_id, sector, ordinary_hours_per_week, "
        "max_contact_hours_per_week, contact_entry_types) VALUES (1, 'SECONDARY', 30.5, 21.5, 'LESSON,REGISTRATION')"
    )
    conn.commit()

    findings = teacher_over_contracted_load(conn)
    assert len(findings) == 1
    assert findings[0].evidence["scheduled_minutes"] == 120  # 60 (lesson) + 60 (registration period's load_minutes)
    assert findings[0].evidence["contact_entry_types"] == ["LESSON", "REGISTRATION"]


def test_room_underutilization_flags_unused_room():
    conn = build_synthetic_db()
    # Room 1 used once, Room 2 never used - only Room 2 should be flagged
    # (Room 1's 50% utilisation, out of 2 lesson slots in this synthetic
    # cycle, is above the default threshold). Both need a confirmed
    # capacity - seats IS NULL means "skip", not "0% used".
    conn.execute("UPDATE room SET seats = 20 WHERE id IN (1, 2)")
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)

    findings = room_underutilization(conn)
    flagged_rooms = {r.code for f in findings for r in f.entity_refs}
    assert "R2" in flagged_rooms
    assert "R1" not in flagged_rooms
    assert all(f.severity == "info" for f in findings)
