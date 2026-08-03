"""Synthetic-fixture tests for the three clash rules and composite-class
review gating. No real school data - see tests/synthetic.py."""

import json

from app.analysis.clash_rules import run_clash_rules
from app.analysis.composite_review import load_approved_composites
from app.analysis.models import Finding
from tests.synthetic import add_break, add_enrolment, add_lesson, build_synthetic_db


def rule_ids(findings: list[Finding]) -> set[str]:
    return {f.rule_id for f in findings}


def test_normal_case_no_clash():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)

    findings = run_clash_rules(conn)
    assert findings == []


def test_teacher_double_booking_genuine_issue():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=1, room_id=2)

    findings = run_clash_rules(conn)
    teacher_findings = [f for f in findings if f.rule_id == "teacher_double_booking"]
    assert len(teacher_findings) == 1
    assert teacher_findings[0].severity == "critical"
    assert teacher_findings[0].evidence["spans_multiple_rooms"] is True
    assert {r.code for r in teacher_findings[0].entity_refs if r.type == "teacher"} == {"T1"}


def test_room_double_booking_genuine_issue():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=2, room_id=1)

    findings = run_clash_rules(conn)
    room_findings = [f for f in findings if f.rule_id == "room_double_booking"]
    assert len(room_findings) == 1
    assert room_findings[0].evidence["spans_multiple_teachers"] is True


def test_composite_class_exemption_when_approved():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=1, room_id=1)

    conn.execute(
        "INSERT INTO composite_group (id, teacher_id, room_id, review_status, slot_count, detected_at) "
        "VALUES (1, 1, 1, 'APPROVED', 1, 'test')"
    )
    conn.execute("INSERT INTO composite_group_member (composite_group_id, class_name_id) VALUES (1, 1)")
    conn.execute("INSERT INTO composite_group_member (composite_group_id, class_name_id) VALUES (1, 2)")
    conn.commit()

    findings = run_clash_rules(conn)
    assert rule_ids(findings) == set()


def test_composite_candidate_pending_still_flags_clash():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=1, room_id=1)

    conn.execute(
        "INSERT INTO composite_group (id, teacher_id, room_id, review_status, slot_count, detected_at) "
        "VALUES (1, 1, 1, 'PENDING', 1, 'test')"
    )
    conn.execute("INSERT INTO composite_group_member (composite_group_id, class_name_id) VALUES (1, 1)")
    conn.execute("INSERT INTO composite_group_member (composite_group_id, class_name_id) VALUES (1, 2)")
    conn.commit()

    findings = run_clash_rules(conn)
    assert "teacher_double_booking" in rule_ids(findings)
    assert "room_double_booking" in rule_ids(findings)


def test_composite_candidate_rejected_still_flags_clash():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=1, room_id=1)

    conn.execute(
        "INSERT INTO composite_group (id, teacher_id, room_id, review_status, slot_count, detected_at) "
        "VALUES (1, 1, 1, 'REJECTED', 1, 'test')"
    )
    conn.execute("INSERT INTO composite_group_member (composite_group_id, class_name_id) VALUES (1, 1)")
    conn.execute("INSERT INTO composite_group_member (composite_group_id, class_name_id) VALUES (1, 2)")
    conn.commit()

    findings = run_clash_rules(conn)
    assert "teacher_double_booking" in rule_ids(findings)


def test_missing_teacher_or_room_does_not_crash_or_false_flag():
    conn = build_synthetic_db()
    # Two entries at the same slot with no teacher/room assigned at all -
    # nothing to double-book, must not be treated as a clash.
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=None, room_id=None)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=None, room_id=None)

    findings = run_clash_rules(conn)
    assert findings == []


def test_non_teaching_entry_not_flagged():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    # A break for a different roll class at a different period - entry_type
    # BREAK must never be considered by the LESSON-only clash rules.
    add_break(conn, day_id=1, period_id=2, roll_class_id=1)

    findings = run_clash_rules(conn)
    assert findings == []


def test_student_double_booking_genuine_issue():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=2, teacher_id=2, room_id=2)
    add_enrolment(conn, student_id=1, class_name_id=1)
    add_enrolment(conn, student_id=1, class_name_id=2)

    findings = run_clash_rules(conn)
    student_findings = [f for f in findings if f.rule_id == "student_double_booking"]
    assert len(student_findings) == 1
    assert {r.code for r in student_findings[0].entity_refs if r.type == "student"} == {"100001"}


def test_student_double_booking_composite_exemption():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=1, room_id=1)
    add_enrolment(conn, student_id=1, class_name_id=1)
    add_enrolment(conn, student_id=1, class_name_id=2)

    conn.execute(
        "INSERT INTO composite_group (id, teacher_id, room_id, review_status, slot_count, detected_at) "
        "VALUES (1, 1, 1, 'APPROVED', 1, 'test')"
    )
    conn.execute("INSERT INTO composite_group_member (composite_group_id, class_name_id) VALUES (1, 1)")
    conn.execute("INSERT INTO composite_group_member (composite_group_id, class_name_id) VALUES (1, 2)")
    conn.commit()

    findings = run_clash_rules(conn)
    assert "student_double_booking" not in rule_ids(findings)


def test_finding_entity_refs_never_contain_names():
    """Privacy check: entity_refs/evidence must be codes only. A regression
    here would mean a name leaked into a finding payload."""
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=1, room_id=2)

    findings = run_clash_rules(conn)
    for f in findings:
        payload = json.dumps({"title": f.title, "evidence": f.evidence, "refs": [r.code for r in f.entity_refs]})
        assert "Test" not in payload  # the synthetic teacher/student first name used above
        assert "One" not in payload  # the synthetic teacher last name used above


def test_approved_composites_loader_returns_correct_membership():
    conn = build_synthetic_db()
    conn.execute(
        "INSERT INTO composite_group (id, teacher_id, room_id, review_status, slot_count, detected_at) "
        "VALUES (1, 1, 1, 'APPROVED', 2, 'test')"
    )
    conn.execute("INSERT INTO composite_group_member (composite_group_id, class_name_id) VALUES (1, 1)")
    conn.execute("INSERT INTO composite_group_member (composite_group_id, class_name_id) VALUES (1, 2)")
    conn.commit()

    composites = load_approved_composites(conn)
    assert composites.slot_is_suppressed(1, 1, {1, 2})
    assert not composites.slot_is_suppressed(1, 1, {1, 2, 999})  # extra class not covered by the group
    assert not composites.slot_is_suppressed(2, 1, {1, 2})  # wrong teacher
