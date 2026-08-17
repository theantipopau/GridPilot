"""Tests app/analysis/capability.py's resolve() precedence - exact
subject match, then faculty match, else NOT_ELIGIBLE. No real school
data - see tests/synthetic.py."""

import datetime as dt

from app.analysis.capability import resolve
from tests.synthetic import build_synthetic_db


def _insert_capability(conn, *, teacher_code, subject_code=None, faculty_code=None, status):
    now = dt.datetime.now(dt.UTC).isoformat()
    conn.execute(
        "INSERT INTO teacher_capability (teacher_code, faculty_code, subject_code, capability_status, "
        "source_type, effective_from, created_at, created_by, updated_at) "
        "VALUES (?, ?, ?, ?, 'SCHOOL_CONFIRMED', '2023-01-01', ?, 'test', ?)",
        (teacher_code, faculty_code, subject_code, status, now, now),
    )
    conn.commit()


def test_no_row_at_all_resolves_not_eligible():
    conn = build_synthetic_db()
    assert resolve(conn, "T1", "SUBA", "SCI") == "NOT_ELIGIBLE"


def test_exact_subject_match_wins():
    conn = build_synthetic_db()
    _insert_capability(conn, teacher_code="T1", subject_code="SUBA", status="ELIGIBLE")
    assert resolve(conn, "T1", "SUBA", "SCI") == "ELIGIBLE"


def test_faculty_match_used_when_no_exact_subject_row():
    conn = build_synthetic_db()
    _insert_capability(conn, teacher_code="T1", faculty_code="SCI", status="ELIGIBLE")
    assert resolve(conn, "T1", "SUBA", "SCI") == "ELIGIBLE"


def test_exact_subject_match_takes_priority_over_a_disagreeing_faculty_row():
    conn = build_synthetic_db()
    _insert_capability(conn, teacher_code="T1", faculty_code="SCI", status="NOT_ELIGIBLE")
    _insert_capability(conn, teacher_code="T1", subject_code="SUBA", status="ELIGIBLE")
    assert resolve(conn, "T1", "SUBA", "SCI") == "ELIGIBLE"


def test_review_required_is_returned_as_is_not_coerced():
    conn = build_synthetic_db()
    _insert_capability(conn, teacher_code="T1", subject_code="SUBA", status="REVIEW_REQUIRED")
    assert resolve(conn, "T1", "SUBA", "SCI") == "REVIEW_REQUIRED"


def test_a_different_teachers_row_does_not_leak_across():
    conn = build_synthetic_db()
    _insert_capability(conn, teacher_code="T2", subject_code="SUBA", status="ELIGIBLE")
    assert resolve(conn, "T1", "SUBA", "SCI") == "NOT_ELIGIBLE"


def test_expired_row_is_ignored():
    conn = build_synthetic_db()
    conn.execute(
        "INSERT INTO teacher_capability (teacher_code, subject_code, capability_status, source_type, "
        "effective_from, effective_to, created_at, created_by, updated_at) "
        "VALUES ('T1', 'SUBA', 'ELIGIBLE', 'SCHOOL_CONFIRMED', '2020-01-01', '2021-01-01', 'x', 'test', 'x')"
    )
    conn.commit()
    assert resolve(conn, "T1", "SUBA", "SCI") == "NOT_ELIGIBLE"
