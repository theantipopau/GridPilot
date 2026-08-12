"""Synthetic-fixture tests for the constraint-based suggestion engine
(PROJECT_ROADMAP.md Milestone 4). No real school data - see
tests/synthetic.py."""

from app.analysis.clash_rules import run_clash_rules
from app.analysis.consistency_rules import run_consistency_rules
from app.analysis.run import _persist
from app.analysis.suggestions import suggest_fixes
from tests.synthetic import add_enrolment, add_lesson, build_richer_synthetic_db


def _persist_current_findings(conn):
    """Runs the same upsert path app.analysis.run.run_analysis() uses, so
    finding evidence carries entry_id exactly like it would in production."""
    _persist(conn, run_clash_rules(conn))


def _persist_consistency_findings(conn):
    _persist(conn, run_consistency_rules(conn))


def test_unsupported_rule_type_is_explicit_not_silent():
    conn = build_richer_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=2, teacher_id=2, room_id=2)
    add_enrolment(conn, student_id=1, class_name_id=1)
    add_enrolment(conn, student_id=1, class_name_id=2)
    _persist_current_findings(conn)

    finding_id = conn.execute("SELECT id FROM finding WHERE rule_id = 'student_double_booking'").fetchone()["id"]
    result = suggest_fixes(conn, finding_id)

    assert result["supported"] is False
    assert result["candidates"] == []
    assert result["note"] is not None


def test_missing_finding_returns_unsupported_not_error():
    conn = build_richer_synthetic_db()
    result = suggest_fixes(conn, 999)
    assert result["supported"] is False


def test_room_double_booking_finds_same_slot_different_room():
    conn = build_richer_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=2, room_id=1)
    _persist_current_findings(conn)

    finding_id = conn.execute("SELECT id FROM finding WHERE rule_id = 'room_double_booking'").fetchone()["id"]
    result = suggest_fixes(conn, finding_id)

    assert result["supported"] is True
    assert len(result["candidates"]) > 0
    room_only = [c for c in result["candidates"] if c["movement_cost"] == 0]
    assert len(room_only) > 0
    for c in room_only:
        assert c["before"]["day_code"] == c["after"]["day_code"]
        assert c["before"]["period_code"] == c["after"]["period_code"]
        assert c["before"]["room_code"] != c["after"]["room_code"]


def test_candidates_never_move_into_an_already_busy_slot():
    conn = build_richer_synthetic_db()
    # T1 double-booked at day1/period1 (rooms 1 and 2). T1 is also already
    # teaching at day1/period4 (P2) in room 2 - a valid candidate for the
    # conflicting entry must never propose that slot for T1.
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=1, room_id=2)
    add_lesson(conn, day_id=1, period_id=4, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=2)
    _persist_current_findings(conn)

    finding_id = conn.execute("SELECT id FROM finding WHERE rule_id = 'teacher_double_booking'").fetchone()["id"]
    result = suggest_fixes(conn, finding_id)

    for c in result["candidates"]:
        moved_to_other_slot = (c["after"]["day_code"], c["after"]["period_code"]) != (c["before"]["day_code"], c["before"]["period_code"])
        if moved_to_other_slot:
            assert (c["after"]["day_code"], c["after"]["period_code"]) != ("Day 1 A", "P2")


def test_candidate_rejects_room_with_insufficient_capacity():
    conn = build_richer_synthetic_db()
    # Room 3 has seats=1. CLASSA has 2 enrolled students (must never be
    # offered room 3); CLASSB has none (room 3 is fine for it) - this
    # distinguishes a real per-candidate capacity check from one that
    # accidentally rejects/accepts every candidate regardless of which
    # entry it's actually for.
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=2, room_id=1)
    conn.execute("INSERT INTO student (id, code, roll_class_id) VALUES (2, '100002', 1)")
    add_enrolment(conn, student_id=1, class_name_id=1)
    add_enrolment(conn, student_id=2, class_name_id=1)
    _persist_current_findings(conn)

    finding_id = conn.execute("SELECT id FROM finding WHERE rule_id = 'room_double_booking'").fetchone()["id"]
    result = suggest_fixes(conn, finding_id)

    classa_candidates = [c for c in result["candidates"] if c["class_code"] == "CLASSA"]
    classb_candidates = [c for c in result["candidates"] if c["class_code"] == "CLASSB"]
    assert len(classa_candidates) > 0 and len(classb_candidates) > 0
    assert all(c["after"]["room_code"] != "R3" for c in classa_candidates)
    assert any(c["after"]["room_code"] == "R3" for c in classb_candidates)


def test_candidates_sorted_by_movement_cost_ascending():
    conn = build_richer_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=2, room_id=1)
    _persist_current_findings(conn)

    finding_id = conn.execute("SELECT id FROM finding WHERE rule_id = 'room_double_booking'").fetchone()["id"]
    result = suggest_fixes(conn, finding_id)

    costs = [c["movement_cost"] for c in result["candidates"]]
    assert costs == sorted(costs)


def test_candidate_explains_why_it_works():
    conn = build_richer_synthetic_db()
    conn.execute("UPDATE room SET seats = 5 WHERE id = 1")
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=2, room_id=1)
    add_enrolment(conn, student_id=1, class_name_id=1)
    _persist_current_findings(conn)

    finding_id = conn.execute("SELECT id FROM finding WHERE rule_id = 'room_double_booking'").fetchone()["id"]
    result = suggest_fixes(conn, finding_id)
    assert len(result["candidates"]) > 0

    # Only R1 (seats=5, set above) and R3 (seats=1, the fixture default)
    # have a confirmed capacity in build_richer_synthetic_db(); R2 doesn't.
    confirmed_seats = {"R1": 5, "R3": 1}
    for c in result["candidates"]:
        assert c["why"]["no_new_clash"] is True
        room_code = c["after"]["room_code"]
        if room_code in confirmed_seats:
            assert c["why"]["room_capacity"]["confirmed"] is True
            assert c["why"]["room_capacity"]["seats"] == confirmed_seats[room_code]
        else:
            assert c["why"]["room_capacity"]["confirmed"] is False


def test_class_room_familiarity_reflects_the_classs_own_room_history():
    conn = build_richer_synthetic_db()
    # CLASSA already runs in R2 twice (day1/p2/p1 pattern below) and R1
    # once (the conflicting slot) - a candidate moving it to R2 should
    # report 2 other lessons already there; a candidate moving it
    # somewhere it's never been should report 0.
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=2, room_id=1)
    add_lesson(conn, day_id=1, period_id=4, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=2)
    add_lesson(conn, day_id=3, period_id=6, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=2)
    _persist_current_findings(conn)

    finding_id = conn.execute("SELECT id FROM finding WHERE rule_id = 'room_double_booking'").fetchone()["id"]
    result = suggest_fixes(conn, finding_id)
    classa_candidates = [c for c in result["candidates"] if c["class_code"] == "CLASSA"]
    assert len(classa_candidates) > 0

    to_r2 = [c for c in classa_candidates if c["after"]["room_code"] == "R2"]
    assert to_r2, "expected at least one candidate offering R2, which CLASSA already uses twice"
    for c in to_r2:
        assert c["class_room_familiarity"]["same_room_elsewhere_count"] == 2
        assert c["class_room_familiarity"]["total_other_lessons"] == 2  # CLASSA's other 2 lessons, excluding this one

    to_new_room = [c for c in classa_candidates if c["after"]["room_code"] not in ("R1", "R2")]
    for c in to_new_room:
        assert c["class_room_familiarity"]["same_room_elsewhere_count"] == 0


def test_no_candidate_ever_introduces_a_regression():
    """Every returned candidate must itself be clash-free - re-verify by
    re-running the clash rules with the candidate applied."""
    from app.analysis.composite_review import load_approved_composites
    from app.analysis.whatif import apply_overrides, load_code_lookups, run_clash_findings
    from app.analysis.clash_rules import lesson_entries

    conn = build_richer_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=2, room_id=1)
    _persist_current_findings(conn)

    finding_id = conn.execute("SELECT id FROM finding WHERE rule_id = 'room_double_booking'").fetchone()["id"]
    result = suggest_fixes(conn, finding_id)
    assert len(result["candidates"]) > 0

    code_lookups = load_code_lookups(conn)
    composites = load_approved_composites(conn)
    before_entries = lesson_entries(conn)
    before_keys = {f.dedupe_key() for f in run_clash_findings(conn, before_entries, composites)}

    room_code_to_id = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM room")}
    day_code_to_id = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM day")}
    period_lookup = {
        (r["day_code"], r["code"]): r["id"]
        for r in conn.execute("SELECT p.id, p.code, d.code as day_code FROM period p JOIN day d ON d.id = p.day_id")
    }
    entries_by_id = {e["entry_id"]: e for e in before_entries}

    for c in result["candidates"]:
        overrides = {
            c["entry_id"]: {
                "after_day_id": day_code_to_id[c["after"]["day_code"]],
                "after_period_id": period_lookup[(c["after"]["day_code"], c["after"]["period_code"])],
                "after_room_id": room_code_to_id[c["after"]["room_code"]] if c["after"]["room_code"] else None,
                "after_teacher_id": entries_by_id[c["entry_id"]]["teacher_id"],  # unchanged - suggestions never reassign teacher
            }
        }
        after_entries = apply_overrides(before_entries, overrides, code_lookups)
        after_keys = {f.dedupe_key() for f in run_clash_findings(conn, after_entries, composites)}
        assert after_keys - before_keys == set(), f"candidate introduced a regression: {c}"


def test_class_room_instability_offers_moves_into_majority_room():
    conn = build_richer_synthetic_db()
    # CLASSA runs twice in R1 (its "home" room) and once in R2 - the
    # engine should propose moving the R2 lesson into R1, at its existing
    # slot, not searching for a different time too.
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=4, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=2)
    _persist_consistency_findings(conn)

    finding_id = conn.execute(
        "SELECT id FROM finding WHERE rule_id = 'class_room_instability'"
    ).fetchone()["id"]
    result = suggest_fixes(conn, finding_id)

    assert result["supported"] is True
    assert len(result["candidates"]) == 1
    c = result["candidates"][0]
    assert c["before"]["room_code"] == "R2"
    assert c["after"]["room_code"] == "R1"
    assert c["before"]["day_code"] == c["after"]["day_code"]
    assert c["before"]["period_code"] == c["after"]["period_code"]
    assert c["movement_cost"] == 0
    assert c["class_room_familiarity"]["same_room_elsewhere_count"] == 2
    assert c["class_room_familiarity"]["total_other_lessons"] == 2


def test_class_room_instability_skips_lesson_when_majority_room_already_busy():
    conn = build_richer_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=4, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=2)
    # A different class already occupies R1 (the majority room) at the
    # minority lesson's slot - there's no valid "just swap the room" fix
    # for that lesson, so it must not appear as a candidate at all.
    add_lesson(conn, day_id=1, period_id=4, roll_class_id=2, class_name_id=2, teacher_id=2, room_id=1)
    _persist_consistency_findings(conn)

    finding_id = conn.execute(
        "SELECT id FROM finding WHERE rule_id = 'class_room_instability'"
    ).fetchone()["id"]
    result = suggest_fixes(conn, finding_id)

    assert result["supported"] is True
    assert result["candidates"] == []


def test_class_teacher_inconsistency_has_no_suggestion_support():
    """Deliberate scope boundary (docs/suggestions.md) - reassigning a
    lesson to a different teacher would be an invented suggestion with no
    subject-qualification data behind it, unlike a same-class room swap."""
    conn = build_richer_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=1, class_name_id=1, teacher_id=2, room_id=1)
    _persist_consistency_findings(conn)

    finding_id = conn.execute(
        "SELECT id FROM finding WHERE rule_id = 'class_teacher_inconsistency'"
    ).fetchone()["id"]
    result = suggest_fixes(conn, finding_id)

    assert result["supported"] is False
    assert result["candidates"] == []
