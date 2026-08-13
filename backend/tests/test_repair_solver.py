"""Synthetic-fixture tests for the Mode A repair solver
(app/analysis/repair_solver.py) - see docs/mass-repair.md and
docs/solver.md section 1 for why this is a CP-SAT model, not a language
model. No real school data - see tests/synthetic.py."""

from app.analysis.clash_rules import run_clash_rules
from app.analysis.repair_solver import solve_repair
from app.analysis.run import _persist
from tests.synthetic import add_enrolment, add_lesson, build_richer_synthetic_db, build_synthetic_db


def _persist_current_findings(conn):
    _persist(conn, run_clash_rules(conn))


def test_simple_room_double_booking_resolved_with_a_room_only_move():
    conn = build_richer_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=2, room_id=1)
    _persist_current_findings(conn)

    finding_id = conn.execute("SELECT id FROM finding WHERE rule_id = 'room_double_booking'").fetchone()["id"]
    result = solve_repair(conn, [finding_id])

    assert result.status == "SOLVED"
    assert result.findings_resolved == [finding_id]
    assert len(result.moves) == 1
    move = result.moves[0]
    assert move.before["day_code"] == move.after["day_code"]
    assert move.before["period_code"] == move.after["period_code"]
    assert move.before["room_code"] != move.after["room_code"]


def test_deterministic_across_repeated_runs():
    conn = build_richer_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=2, room_id=1)
    _persist_current_findings(conn)

    finding_id = conn.execute("SELECT id FROM finding WHERE rule_id = 'room_double_booking'").fetchone()["id"]
    r1 = solve_repair(conn, [finding_id])
    r2 = solve_repair(conn, [finding_id])

    assert r1.status == r2.status
    assert [(m.entry_id, m.after) for m in r1.moves] == [(m.entry_id, m.after) for m in r2.moves]


def test_respects_room_capacity():
    conn = build_richer_synthetic_db()
    # R3 has seats=1 (build_richer_synthetic_db's default). CLASSA has 2
    # enrolled students, so the solver must never offer it R3 even though
    # R3 is otherwise free at the clash slot.
    conn.execute("UPDATE room SET seats = NULL WHERE id = 2")  # remove the other escape so R3 would be tempting
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=2, room_id=1)
    conn.execute("INSERT INTO student (id, code, roll_class_id) VALUES (2, '100002', 1)")
    add_enrolment(conn, student_id=1, class_name_id=1)
    add_enrolment(conn, student_id=2, class_name_id=1)
    _persist_current_findings(conn)

    finding_id = conn.execute("SELECT id FROM finding WHERE rule_id = 'room_double_booking'").fetchone()["id"]
    result = solve_repair(conn, [finding_id])

    classa_moves = [m for m in result.moves if m.class_code == "CLASSA"]
    assert all(m.after["room_code"] != "R3" for m in classa_moves)


def test_repairs_a_room_feature_mismatch_into_a_correctly_typed_room():
    """Deterministic by construction: a single movable entry, no
    competing class - the only question is whether the room-type domain
    filter actually excludes wrongly-typed rooms, including the entry's
    *own current room* (home isn't exempt from the room-type check just
    because it isn't "busy" - see _feasible_candidates)."""
    from app.analysis.room_feature_rules import run_room_feature_rules

    conn = build_richer_synthetic_db()
    conn.execute("UPDATE room SET room_type = 'Science' WHERE id = 1")
    conn.execute("UPDATE room SET room_type = 'Classroom' WHERE id = 2")
    conn.execute("UPDATE room SET room_type = 'Classroom' WHERE id = 3")
    conn.execute(
        "INSERT INTO class_room_type_constraint (class_name_id, room_type, review_status, "
        "matching_lesson_count, total_lesson_count, detected_at) VALUES (1, 'Science', 'APPROVED', 4, 4, 'test')"
    )
    # CLASSA scheduled in R2 (Classroom) - a mismatch against its own
    # approved Science requirement.
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=2)
    conn.commit()
    _persist(conn, run_room_feature_rules(conn))

    finding_id = conn.execute("SELECT id FROM finding WHERE rule_id = 'room_feature_mismatch'").fetchone()["id"]
    result = solve_repair(conn, [finding_id])

    assert result.status == "SOLVED"
    assert result.findings_resolved == [finding_id]
    assert len(result.moves) == 1
    move = result.moves[0]
    assert move.after["room_code"] == "R1"  # the only Science room
    assert move.before["day_code"] == move.after["day_code"]
    assert move.before["period_code"] == move.after["period_code"]  # room-only, cheapest possible fix


def test_never_touches_an_approved_composite():
    conn = build_richer_synthetic_db()
    # CLASSA and CLASSB share T1+R1 at the clash slot as an *approved*
    # composite - not a real clash, so it must produce no repair-eligible
    # finding at all, and the solver must never move either of them.
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=1, room_id=1)
    conn.execute(
        "INSERT INTO composite_group (teacher_id, room_id, review_status, slot_count, detected_at) "
        "VALUES (1, 1, 'APPROVED', 2, 'test')"
    )
    cur = conn.execute("SELECT id FROM composite_group").fetchone()
    conn.executemany(
        "INSERT INTO composite_group_member (composite_group_id, class_name_id) VALUES (?, ?)",
        [(cur["id"], 1), (cur["id"], 2)],
    )
    conn.commit()
    _persist_current_findings(conn)

    assert conn.execute(
        "SELECT COUNT(*) FROM finding WHERE rule_id = 'room_double_booking' AND status = 'OPEN'"
    ).fetchone()[0] == 0
    # Nothing to repair - confirms the composite is genuinely suppressed
    # upstream, before the solver is ever involved.


def test_unsupported_rule_type_is_reported_not_eligible_not_silently_skipped():
    conn = build_richer_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=2, teacher_id=2, room_id=2)
    add_enrolment(conn, student_id=1, class_name_id=1)
    add_enrolment(conn, student_id=1, class_name_id=2)
    _persist_current_findings(conn)

    finding_id = conn.execute("SELECT id FROM finding WHERE rule_id = 'student_double_booking'").fetchone()["id"]
    result = solve_repair(conn, [finding_id])

    assert result.status == "NO_MOVABLE_ENTRIES"
    assert len(result.not_eligible) == 1
    assert result.not_eligible[0].finding_id == finding_id
    assert result.not_eligible[0].rule_id == "student_double_booking"


def test_unknown_finding_id_reported_not_eligible():
    conn = build_richer_synthetic_db()
    result = solve_repair(conn, [999])
    assert result.status == "NO_MOVABLE_ENTRIES"
    assert len(result.not_eligible) == 1
    assert result.not_eligible[0].finding_id == 999
    assert "No such finding" in result.not_eligible[0].reason


def test_student_clash_is_avoided_natively_not_just_caught_after_the_fact():
    """Student double-booking is modelled as a real CP-SAT constraint
    (AtMostOne per slot+student), not left entirely to the CEGAR
    re-validation loop - so the solver should avoid this trap on its
    first attempt, with nothing needing to be frozen and retried."""
    conn = build_synthetic_db()
    conn.execute("INSERT INTO teacher (id, code, first_name, last_name) VALUES (3, 'T3', 'Test', 'Three')")
    conn.execute("INSERT INTO subject (id, source_code, name) VALUES (3, 'SUBC', 'Subject C')")
    conn.execute("INSERT INTO class_name (id, code, name, subject_id) VALUES (3, 'CLASSC', 'Class C', 3)")
    conn.commit()

    # Clash: CLASSA(T1) + CLASSB(T2) both in R1 at day1/p1. R2 is occupied
    # at both lesson slots by CLASSC(T3), so neither side has a same-slot
    # or same-day escape - the only formally-cheap move is day2/p1/R1.
    # Student 1 is enrolled in both CLASSA and CLASSC, so moving CLASSA
    # there collides on students with CLASSC's day2 occurrence; CLASSB has
    # no such overlap and is the only side that can actually go there.
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=2, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=3, teacher_id=3, room_id=2)
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=1, class_name_id=3, teacher_id=3, room_id=2)
    add_enrolment(conn, student_id=1, class_name_id=1)
    add_enrolment(conn, student_id=1, class_name_id=3)
    _persist_current_findings(conn)

    finding_id = conn.execute("SELECT id FROM finding WHERE rule_id = 'room_double_booking'").fetchone()["id"]
    result = solve_repair(conn, [finding_id])

    assert result.status == "SOLVED"
    assert result.findings_resolved == [finding_id]
    assert len(result.moves) == 1
    assert result.moves[0].class_code == "CLASSB"  # CLASSA's only escape clashes on students; CLASSB's doesn't
    assert result.frozen_entry_ids == []  # solved on the first attempt - no CEGAR retry needed


def test_never_returns_a_solution_with_a_new_regression():
    """Independent re-check, mirroring test_suggestions.py's
    test_no_candidate_ever_introduces_a_regression: re-run the clash rules
    against the solver's own output and confirm no finding exists that
    wasn't already present beforehand."""
    from app.analysis.clash_rules import lesson_entries
    from app.analysis.composite_review import load_approved_composites
    from app.analysis.whatif import apply_overrides, load_code_lookups, run_clash_findings

    conn = build_richer_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=2, room_id=1)
    _persist_current_findings(conn)

    finding_id = conn.execute("SELECT id FROM finding WHERE rule_id = 'room_double_booking'").fetchone()["id"]

    code_lookups = load_code_lookups(conn)
    composites = load_approved_composites(conn)
    before_entries = lesson_entries(conn)
    before_keys = {f.dedupe_key() for f in run_clash_findings(conn, before_entries, composites)}

    result = solve_repair(conn, [finding_id])
    assert result.moves

    room_by_code = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM room")}
    day_by_code = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM day")}
    period_lookup = {
        (r["day_code"], r["code"]): r["id"]
        for r in conn.execute("SELECT p.id, p.code, d.code AS day_code FROM period p JOIN day d ON d.id = p.day_id")
    }
    overrides = {}
    for m in result.moves:
        day_id = day_by_code[m.after["day_code"]]
        overrides[m.entry_id] = {
            "after_day_id": day_id,
            "after_period_id": period_lookup[(m.after["day_code"], m.after["period_code"])],
            "after_room_id": room_by_code.get(m.after["room_code"]) if m.after["room_code"] else None,
        }
    after_entries = apply_overrides(before_entries, overrides, code_lookups)
    after_keys = {f.dedupe_key() for f in run_clash_findings(conn, after_entries, composites)}
    assert after_keys - before_keys == set(), "solver produced a regression"
