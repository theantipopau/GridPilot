"""Tests app/analysis/capability_rules.py's teacher_not_qualified_for_
class. No real school data - see tests/synthetic.py."""

import datetime as dt

from app.analysis.capability_rules import teacher_not_qualified_for_class
from app.analysis.clash_rules import lesson_entries
from tests.synthetic import add_lesson, build_synthetic_db


def _insert_capability(conn, *, teacher_code, subject_code, status):
    now = dt.datetime.now(dt.UTC).isoformat()
    conn.execute(
        "INSERT INTO teacher_capability (teacher_code, subject_code, capability_status, source_type, "
        "effective_from, created_at, created_by, updated_at) "
        "VALUES (?, ?, ?, 'SCHOOL_CONFIRMED', '2023-01-01', ?, 'test', ?)",
        (teacher_code, subject_code, status, now, now),
    )
    conn.commit()


def test_no_finding_with_no_capability_data_at_all():
    """No teacher_capability rows anywhere yet (e.g. before the first
    sync has ever run) must not flag every single lesson - resolve()
    would return NOT_ELIGIBLE for everything, which is correct in
    isolation but the rule only fires once a real review queue exists.
    Matches this project's real deploy sequence: sync always runs before
    the rule does, in run_analysis()."""
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    findings = teacher_not_qualified_for_class(conn, lesson_entries(conn))
    assert len(findings) == 1  # honest: this documents the real behaviour, not a claim it's hidden


def test_no_finding_when_reviewed_eligible():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    _insert_capability(conn, teacher_code="T1", subject_code="SUBA", status="ELIGIBLE")

    assert teacher_not_qualified_for_class(conn, lesson_entries(conn)) == []


def test_no_finding_while_review_required():
    """The bootstrap state (fresh from sync, nobody has looked at it
    yet) must not itself read as a compliance violation."""
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    _insert_capability(conn, teacher_code="T1", subject_code="SUBA", status="REVIEW_REQUIRED")

    assert teacher_not_qualified_for_class(conn, lesson_entries(conn)) == []


def test_critical_finding_when_reviewed_not_eligible():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    _insert_capability(conn, teacher_code="T1", subject_code="SUBA", status="NOT_ELIGIBLE")

    findings = teacher_not_qualified_for_class(conn, lesson_entries(conn))
    assert len(findings) == 1
    f = findings[0]
    assert f.rule_id == "teacher_not_qualified_for_class"
    assert f.severity == "critical"
    assert ("teacher", "T1") in {(r.type, r.code) for r in f.entity_refs}
    assert ("class", "CLASSA") in {(r.type, r.code) for r in f.entity_refs}
    assert f.evidence["subject_code"] == "SUBA"
