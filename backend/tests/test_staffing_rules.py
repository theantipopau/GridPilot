"""Synthetic-fixture tests for teaching_requirement_blocking
(app/analysis/staffing_rules.py) - docs/staffing-priority-policy.md.
No real school data - see tests/synthetic.py."""

from app.analysis.staffing_rules import teaching_requirement_blocking
from tests.synthetic import add_lesson, build_richer_synthetic_db


def _insert_approved_requirement(conn, *, class_name_id=1, subject_id=1, teacher_id=1, room_id=1):
    conn.execute(
        "INSERT INTO teaching_requirement (requirement_key, class_name_id, subject_id, periods_per_cycle, "
        "assigned_teacher_id, assigned_room_id, matching_lesson_count, total_lesson_count, planning_year, "
        "review_status, detected_at) VALUES ('CLASSA', ?, ?, 2, ?, ?, 2, 2, '2026', 'APPROVED', 'test')",
        (class_name_id, subject_id, teacher_id, room_id),
    )
    conn.commit()


def test_an_approved_requirement_with_no_eligible_teacher_is_blocking():
    conn = build_richer_synthetic_db()
    _insert_approved_requirement(conn)

    findings = teaching_requirement_blocking(conn)
    assert len(findings) == 1
    f = findings[0]
    assert f.severity == "critical"
    assert f.entity_refs[0].code == "CLASSA"


def test_a_requirement_with_an_eligible_teacher_is_not_blocking():
    conn = build_richer_synthetic_db()
    _insert_approved_requirement(conn)
    conn.execute(
        "INSERT INTO teacher_capability (teacher_code, subject_code, capability_status, source_type, "
        "effective_from, created_at, created_by, updated_at) "
        "VALUES ('T1', 'SUBA', 'ELIGIBLE', 'SCHOOL_CONFIRMED', 'test', 'test', 'tester', 'test')"
    )
    conn.commit()

    assert teaching_requirement_blocking(conn) == []


def test_a_pending_requirement_is_never_evaluated():
    conn = build_richer_synthetic_db()
    conn.execute(
        "INSERT INTO teaching_requirement (requirement_key, class_name_id, subject_id, periods_per_cycle, "
        "matching_lesson_count, total_lesson_count, planning_year, review_status, detected_at) "
        "VALUES ('CLASSA', 1, 1, 2, 2, 2, '2026', 'PENDING', 'test')"
    )
    conn.commit()

    assert teaching_requirement_blocking(conn) == []


def test_a_composite_requirement_with_no_subject_is_skipped_not_blocked():
    conn = build_richer_synthetic_db()
    conn.execute(
        "INSERT INTO composite_group (teacher_id, room_id, review_status, slot_count, detected_at) "
        "VALUES (1, 1, 'APPROVED', 1, 'test')"
    )
    group_id = conn.execute("SELECT id FROM composite_group").fetchone()["id"]
    conn.execute(
        "INSERT INTO teaching_requirement (requirement_key, composite_group_id, periods_per_cycle, "
        "matching_lesson_count, total_lesson_count, planning_year, review_status, detected_at) "
        "VALUES ('COMPOSITE:CLASSA|CLASSB', ?, 1, 2, 2, '2026', 'APPROVED', 'test')",
        (group_id,),
    )
    conn.commit()

    assert teaching_requirement_blocking(conn) == []
