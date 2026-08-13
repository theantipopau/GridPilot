"""Synthetic-fixture tests for room_feature_mismatch
(app/analysis/room_feature_rules.py) - the roadmap rule unblocked by the
class_room_type_constraint review queue. No real school data - see
tests/synthetic.py."""

from app.analysis.clash_rules import lesson_entries
from app.analysis.room_feature_rules import room_feature_mismatch
from tests.synthetic import add_lesson, build_richer_synthetic_db


def _set_room_type(conn, room_id, room_type):
    conn.execute("UPDATE room SET room_type = ? WHERE id = ?", (room_type, room_id))
    conn.commit()


def _insert_constraint(conn, *, class_name_id, room_type, review_status="APPROVED"):
    conn.execute(
        "INSERT INTO class_room_type_constraint (class_name_id, room_type, review_status, "
        "matching_lesson_count, total_lesson_count, detected_at) VALUES (?, ?, ?, 2, 2, 'test')",
        (class_name_id, room_type, review_status),
    )
    conn.commit()


def test_no_findings_without_any_approved_constraint():
    conn = build_richer_synthetic_db()
    _set_room_type(conn, 1, "Science")
    _set_room_type(conn, 2, "Classroom")
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=2)

    assert room_feature_mismatch(conn, lesson_entries(conn)) == []


def test_mismatch_flagged_when_constraint_is_approved():
    conn = build_richer_synthetic_db()
    _set_room_type(conn, 1, "Science")
    _set_room_type(conn, 2, "Classroom")
    _insert_constraint(conn, class_name_id=1, room_type="Science", review_status="APPROVED")
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=2)

    findings = room_feature_mismatch(conn, lesson_entries(conn))
    assert len(findings) == 1
    f = findings[0]
    assert f.rule_id == "room_feature_mismatch"
    assert f.severity == "warning"
    assert f.evidence["required_room_type"] == "Science"
    assert f.evidence["actual_room_type"] == "Classroom"
    assert f.evidence["room_code"] == "R2"
    assert ("class", "CLASSA") in {(r.type, r.code) for r in f.entity_refs}
    assert f.slot_refs == (f.slot_refs[0],)  # exactly one slot


def test_no_finding_when_room_matches_the_required_type():
    conn = build_richer_synthetic_db()
    _set_room_type(conn, 1, "Science")
    _insert_constraint(conn, class_name_id=1, room_type="Science", review_status="APPROVED")
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)

    assert room_feature_mismatch(conn, lesson_entries(conn)) == []


def test_no_finding_while_constraint_is_only_pending():
    conn = build_richer_synthetic_db()
    _set_room_type(conn, 1, "Science")
    _set_room_type(conn, 2, "Classroom")
    _insert_constraint(conn, class_name_id=1, room_type="Science", review_status="PENDING")
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=2)

    assert room_feature_mismatch(conn, lesson_entries(conn)) == []


def test_no_finding_when_constraint_was_rejected():
    conn = build_richer_synthetic_db()
    _set_room_type(conn, 1, "Science")
    _set_room_type(conn, 2, "Classroom")
    _insert_constraint(conn, class_name_id=1, room_type="Science", review_status="REJECTED")
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=2)

    assert room_feature_mismatch(conn, lesson_entries(conn)) == []


def test_untyped_room_still_flags_as_a_mismatch():
    """A NULL room_type (no Notes data at all) still fails an APPROVED
    requirement - "we don't know what this room is" is not the same as
    "it's the right type." """
    conn = build_richer_synthetic_db()
    _set_room_type(conn, 1, "Science")
    _insert_constraint(conn, class_name_id=1, room_type="Science", review_status="APPROVED")
    # room 2 stays untyped (NULL) by default
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=2)

    findings = room_feature_mismatch(conn, lesson_entries(conn))
    assert len(findings) == 1
    assert findings[0].evidence["actual_room_type"] is None
