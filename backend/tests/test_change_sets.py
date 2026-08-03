"""Synthetic-fixture tests for the change-set service (Milestone 3).
No real school data - see tests/synthetic.py."""

import json

import pytest

from app.analysis.clash_rules import run_clash_rules
from app.changes.service import (
    ChangeSetError,
    add_proposed_change,
    approve_change_set,
    create_change_set,
    reject_change_set,
    validate_change_set,
)
from tests.synthetic import add_lesson, build_synthetic_db


def _entry_id(conn, *, day_id, period_id, roll_class_id):
    row = conn.execute(
        "SELECT id FROM timetable_entry WHERE day_id = ? AND period_id = ? AND roll_class_id = ?",
        (day_id, period_id, roll_class_id),
    ).fetchone()
    return row["id"]


def test_move_that_resolves_a_clash_is_valid():
    conn = build_synthetic_db()
    # Teacher 1 double-booked at day 1 period 1, two different rooms.
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=1, room_id=2)

    cs_id = create_change_set(conn, "Fix T1 clash", None, "tester")
    moved_entry_id = _entry_id(conn, day_id=1, period_id=1, roll_class_id=2)
    # Move the second lesson to day 2 period 3, where nothing else is scheduled.
    add_proposed_change(conn, cs_id, moved_entry_id, after_day_id=2, after_period_id=3)

    result = validate_change_set(conn, cs_id)
    assert result["valid"] is True
    assert result["introduced_findings"] == []
    # Different rooms in the "before" state, so only teacher_double_booking
    # fired (never room_double_booking) - one finding clears.
    assert len(result["resolved_findings"]) == 1
    assert result["resolved_findings"][0]["rule_id"] == "teacher_double_booking"

    row = conn.execute("SELECT validation_status FROM change_set WHERE id = ?", (cs_id,)).fetchone()
    assert row["validation_status"] == "VALID"


def test_move_that_introduces_a_new_clash_is_invalid():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    # Teacher 2 already has a lesson at day 2 period 3.
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=1, class_name_id=1, teacher_id=2, room_id=1)

    cs_id = create_change_set(conn, "Bad move", None, "tester")
    entry_id = _entry_id(conn, day_id=1, period_id=1, roll_class_id=1)
    # Reassigning this lesson's teacher to teacher 2 at the same slot teacher 2
    # already teaches elsewhere doesn't clash here directly - instead move it
    # into teacher 2's existing slot with a teacher reassignment to collide.
    add_proposed_change(conn, cs_id, entry_id, after_day_id=2, after_period_id=3, after_teacher_id=2)

    result = validate_change_set(conn, cs_id)
    assert result["valid"] is False
    assert len(result["introduced_findings"]) > 0


def test_approve_blocked_until_validated():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=1, room_id=2)

    cs_id = create_change_set(conn, "Fix T1 clash", None, "tester")
    entry_id = _entry_id(conn, day_id=1, period_id=1, roll_class_id=2)
    add_proposed_change(conn, cs_id, entry_id, after_day_id=2, after_period_id=3)

    with pytest.raises(ChangeSetError):
        approve_change_set(conn, cs_id, "reviewer")


def test_approve_succeeds_after_valid_and_never_mutates_source():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=1, room_id=2)

    cs_id = create_change_set(conn, "Fix T1 clash", None, "tester")
    entry_id = _entry_id(conn, day_id=1, period_id=1, roll_class_id=2)
    before = dict(conn.execute("SELECT * FROM timetable_entry WHERE id = ?", (entry_id,)).fetchone())

    add_proposed_change(conn, cs_id, entry_id, after_day_id=2, after_period_id=3)
    validate_change_set(conn, cs_id)
    approve_change_set(conn, cs_id, "reviewer")

    row = conn.execute("SELECT approval_status FROM change_set WHERE id = ?", (cs_id,)).fetchone()
    assert row["approval_status"] == "APPROVED"

    # The source timetable_entry row must be completely untouched by approval.
    after = dict(conn.execute("SELECT * FROM timetable_entry WHERE id = ?", (entry_id,)).fetchone())
    assert after == before


def test_reject_change_set():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    cs_id = create_change_set(conn, "Some change", None, "tester")

    reject_change_set(conn, cs_id, "reviewer")
    row = conn.execute("SELECT approval_status FROM change_set WHERE id = ?", (cs_id,)).fetchone()
    assert row["approval_status"] == "REJECTED"


def test_editing_a_non_draft_change_set_is_blocked():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    entry_id = _entry_id(conn, day_id=1, period_id=1, roll_class_id=1)

    cs_id = create_change_set(conn, "Some change", None, "tester")
    reject_change_set(conn, cs_id, "reviewer")

    with pytest.raises(ChangeSetError):
        add_proposed_change(conn, cs_id, entry_id, after_day_id=2, after_period_id=3)


def test_originating_finding_left_unresolved_makes_change_set_invalid():
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=1, room_id=2)

    # A finding referencing this clash, as if the rules engine had already
    # run - using the rule's real dedupe_key, since validate_change_set
    # matches on it to decide whether the originating issue actually cleared.
    [real_finding] = [f for f in run_clash_rules(conn) if f.rule_id == "teacher_double_booking"]
    conn.execute(
        "INSERT INTO finding (dedupe_key, rule_id, severity, title, entity_refs_json, slot_refs_json, "
        "evidence_json, status, first_seen_at, computed_at) VALUES (?, 'teacher_double_booking', 'critical', "
        "'Teacher T1 double-booked', '[]', '[]', '{}', 'OPEN', 'test', 'test')",
        (real_finding.dedupe_key(),),
    )
    finding_id = conn.execute(
        "SELECT id FROM finding WHERE dedupe_key = ?", (real_finding.dedupe_key(),)
    ).fetchone()["id"]
    conn.commit()

    cs_id = create_change_set(conn, "Unrelated change", None, "tester")
    entry_id = _entry_id(conn, day_id=1, period_id=1, roll_class_id=1)
    # A change that doesn't actually move anything meaningful (no-op-ish reason field
    # only) still claims to address the finding - should stay unresolved.
    add_proposed_change(conn, cs_id, entry_id, reason="doesn't actually fix it", finding_ids=[finding_id])

    result = validate_change_set(conn, cs_id)
    assert result["valid"] is False
    assert finding_id in result["unresolved_originating_findings"]
