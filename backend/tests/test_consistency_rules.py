"""Synthetic-fixture tests for the structural consistency rules
(app.analysis.consistency_rules). No real school data - see
tests/synthetic.py."""

from app.analysis.consistency_rules import class_room_instability, class_teacher_inconsistency
from app.analysis.models import EntityRef
from tests.synthetic import add_lesson, build_synthetic_db


def test_class_room_instability_not_flagged_when_room_stays_the_same():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)

    assert class_room_instability(conn) == []


def test_class_room_instability_flags_a_genuine_case():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=2)

    findings = class_room_instability(conn)
    assert len(findings) == 1
    f = findings[0]
    assert f.rule_id == "class_room_instability"
    assert f.severity == "info"
    assert f.entity_refs == (EntityRef("class", "CLASSA"),)
    assert f.evidence["room_count"] == 2
    assert f.evidence["room_codes"] == ["R1", "R2"]
    assert f.evidence["lesson_count"] == 2


def test_class_room_instability_ignores_different_classes_in_different_rooms():
    """Two different class codes each in their own single room must not
    be conflated into one "unstable" class - this is per class_name, not
    a school-wide room-variety count."""
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=2, class_name_id=2, teacher_id=2, room_id=2)

    assert class_room_instability(conn) == []


def test_class_teacher_inconsistency_not_flagged_when_teacher_stays_the_same():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)

    assert class_teacher_inconsistency(conn) == []


def test_class_teacher_inconsistency_flags_a_genuine_case():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=1, class_name_id=1, teacher_id=2, room_id=1)

    findings = class_teacher_inconsistency(conn)
    assert len(findings) == 1
    f = findings[0]
    assert f.rule_id == "class_teacher_inconsistency"
    assert f.severity == "info"
    assert f.evidence["teacher_count"] == 2
    assert f.evidence["teacher_codes"] == ["T1", "T2"]


def test_non_lesson_entries_never_count_towards_either_rule():
    """A BREAK/REGISTRATION entry has no class_name_id and must never be
    mistaken for a lesson in a different room/with a different teacher."""
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    conn.execute(
        "INSERT INTO timetable_entry (source_ref, day_id, period_id, roll_class_id, entry_type) "
        "VALUES ('test', 2, 2, 1, 'BREAK')"
    )
    conn.commit()

    assert class_room_instability(conn) == []
    assert class_teacher_inconsistency(conn) == []
