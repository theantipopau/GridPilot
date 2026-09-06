"""Tests app/analysis/availability_rules.py's teacher_meeting_clash and
teacher_commitment_busy. No real school data - see tests/synthetic.py."""

from app.analysis.availability_rules import teacher_commitment_busy, teacher_meeting_clash
from app.analysis.clash_rules import lesson_entries
from tests.synthetic import add_lesson, build_synthetic_db


def _insert_commitment(conn, *, teacher_id, period_id, code="STAFF", name="Staff Meeting"):
    conn.execute(
        "INSERT INTO teacher_commitment (teacher_id, period_id, commitment_type, code, name) "
        "VALUES (?, ?, 'MEETING', ?, ?)",
        (teacher_id, period_id, code, name),
    )
    conn.commit()


def test_no_finding_with_no_commitments_at_all():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    assert teacher_meeting_clash(conn, lesson_entries(conn)) == []


def test_no_finding_when_teacher_free_during_the_meeting():
    """A commitment at a slot nobody is scheduled in must not fire -
    that's the whole point (an unused block, not a clash)."""
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    _insert_commitment(conn, teacher_id=2, period_id=1)  # T2, not T1, has the meeting

    assert teacher_meeting_clash(conn, lesson_entries(conn)) == []


def test_critical_finding_when_a_lesson_is_scheduled_during_a_meeting():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    _insert_commitment(conn, teacher_id=1, period_id=1, code="SSSMB", name="Senior Staff Meeting")

    findings = teacher_meeting_clash(conn, lesson_entries(conn))
    assert len(findings) == 1
    f = findings[0]
    assert f.rule_id == "teacher_meeting_clash"
    assert f.severity == "critical"
    assert ("teacher", "T1") in {(r.type, r.code) for r in f.entity_refs}
    assert ("class", "CLASSA") in {(r.type, r.code) for r in f.entity_refs}
    assert f.evidence["meeting_code"] == "SSSMB"


def test_composite_style_multiple_lessons_at_one_clash_produce_one_finding():
    """Same shape as teacher_double_booking's composite handling - several
    class codes at the same (teacher, slot) collapse into one finding
    listing all of them, not one finding per class code."""
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=1, room_id=1)
    _insert_commitment(conn, teacher_id=1, period_id=1)

    findings = teacher_meeting_clash(conn, lesson_entries(conn))
    assert len(findings) == 1
    assert findings[0].evidence["class_codes"] == ["CLASSA", "CLASSB"]


def test_commitment_at_a_different_slot_does_not_clash():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    _insert_commitment(conn, teacher_id=1, period_id=3)  # different day/period

    assert teacher_meeting_clash(conn, lesson_entries(conn)) == []


def test_teacher_commitment_busy_maps_by_day_and_period():
    conn = build_synthetic_db()
    _insert_commitment(conn, teacher_id=1, period_id=1)
    _insert_commitment(conn, teacher_id=1, period_id=3)
    _insert_commitment(conn, teacher_id=2, period_id=1)

    busy = teacher_commitment_busy(conn)
    assert busy[1] == {(1, 1), (2, 3)}  # (day_id, period_id) pairs - period 1 is day 1, period 3 is day 2
    assert busy[2] == {(1, 1)}
