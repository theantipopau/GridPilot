"""Tests for app/analysis/infeasibility.py - the "is there ANY legal
slot for this lesson alone, right now" diagnosis behind
POST /solver/runs/{id}/explain-infeasibility (roadmap-v3 4.3)."""

import sqlite3

from app.analysis.infeasibility import diagnose_unresolved_findings
from tests.synthetic import add_lesson, build_richer_synthetic_db


def _insert_finding(conn, *, dedupe_key, entity_type, entity_code, day_code, period_code):
    conn.execute(
        "INSERT INTO finding (dedupe_key, rule_id, severity, title, entity_refs_json, slot_refs_json, "
        "evidence_json, status, first_seen_at, computed_at) VALUES (?, 'teacher_double_booking', 'critical', "
        "'test', ?, ?, '{}', 'OPEN', 'test', 'test')",
        (
            dedupe_key,
            f'[{{"type": "{entity_type}", "code": "{entity_code}"}}]',
            f'[{{"day_code": "{day_code}", "period_code": "{period_code}"}}]',
        ),
    )
    return conn.execute("SELECT id FROM finding WHERE dedupe_key = ?", (dedupe_key,)).fetchone()["id"]


def _build_db():
    """5 LESSON_SLOT periods total (richer fixture): day1/P1 (id1),
    day2/P1 (id3), day1/P2 (id4), day2/P2 (id5), day3/P1 (id6).

    T1 teaches CLASSA at day1/P1 (the entry under test) and is also
    booked - via a standing commitment at that same home slot, plus real
    LESSON entries elsewhere - at every other LESSON_SLOT period, so T1
    has zero free slots anywhere: a provable, single-entry infeasibility.

    T3 teaches CLASSC at day1/P1 too (a different room) with no other
    commitments anywhere - plenty of free slots, so this one should
    report has_legal_slot: True (the honest "not a single-lesson cause"
    case)."""
    conn = build_richer_synthetic_db()
    conn.execute("INSERT INTO teacher (id, code, first_name, last_name) VALUES (3, 'T3', 'Test', 'Three')")
    conn.execute("INSERT INTO subject (id, source_code, name) VALUES (3, 'SUBC', 'Subject C')")
    conn.execute("INSERT INTO class_name (id, code, name, subject_id) VALUES (3, 'CLASSC', 'Class C', 3)")

    # T1 busy at home via a standing commitment (so excluding this entry
    # from the fixed background still leaves home blocked).
    conn.execute("INSERT INTO teacher_commitment (teacher_id, period_id) VALUES (1, 1)")
    # The entry under test.
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    # T1 booked solid at every other LESSON_SLOT period.
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=2, class_name_id=2, teacher_id=1, room_id=2)
    add_lesson(conn, day_id=1, period_id=4, roll_class_id=2, class_name_id=2, teacher_id=1, room_id=2)
    add_lesson(conn, day_id=2, period_id=5, roll_class_id=2, class_name_id=2, teacher_id=1, room_id=2)
    add_lesson(conn, day_id=3, period_id=6, roll_class_id=2, class_name_id=2, teacher_id=1, room_id=2)

    # T3's lesson, otherwise unconstrained.
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=3, teacher_id=3, room_id=2)

    conn.commit()
    return conn


def test_provably_infeasible_entry_reports_teacher_bottleneck():
    conn = _build_db()
    fid = _insert_finding(
        conn, dedupe_key="k1", entity_type="teacher", entity_code="T1", day_code="Day 1 A", period_code="P1"
    )

    diagnoses = diagnose_unresolved_findings(conn, [fid])
    assert len(diagnoses) == 1
    d = diagnoses[0]
    assert d["class_code"] == "CLASSA"
    assert d["teacher_code"] == "T1"
    assert d["has_legal_slot"] is False
    assert d["total_slots"] == 5
    assert d["slots_lost_to_teacher_availability"] == 5
    assert d["slots_checked_for_a_room"] == 0
    assert d["slots_with_a_legal_room"] == 0


def test_entry_with_options_elsewhere_reports_has_legal_slot_true():
    conn = _build_db()
    fid = _insert_finding(
        conn, dedupe_key="k2", entity_type="teacher", entity_code="T3", day_code="Day 1 A", period_code="P1"
    )

    diagnoses = diagnose_unresolved_findings(conn, [fid])
    assert len(diagnoses) == 1
    d = diagnoses[0]
    assert d["class_code"] == "CLASSC"
    assert d["has_legal_slot"] is True


def test_unresolvable_finding_yields_no_diagnosis():
    conn = _build_db()
    fid = _insert_finding(
        conn, dedupe_key="k3", entity_type="teacher", entity_code="NOBODY", day_code="Day 1 A", period_code="P1"
    )
    assert diagnose_unresolved_findings(conn, [fid]) == []


def test_no_finding_ids_returns_empty():
    conn = _build_db()
    assert diagnose_unresolved_findings(conn, []) == []
