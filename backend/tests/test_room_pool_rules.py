"""Synthetic-fixture tests for room_pool_violation
(app/analysis/room_pool_rules.py). No real school data - see
tests/synthetic.py."""

from app.analysis.clash_rules import lesson_entries
from app.analysis.room_pool_rules import room_pool_violation
from tests.synthetic import add_lesson, build_richer_synthetic_db


def _make_pool(conn, *, pool_id=1, code="RUR 1", room_ids, class_name_ids):
    conn.execute(
        "INSERT INTO room_pool (id, source_guid, code, name, type_is_class) VALUES (?, ?, ?, ?, 1)",
        (pool_id, f"guid-{pool_id}", code, code),
    )
    for room_id in room_ids:
        conn.execute(
            "INSERT INTO room_pool_room (room_pool_id, room_id) VALUES (?, ?)", (pool_id, room_id)
        )
    for class_name_id in class_name_ids:
        conn.execute(
            "INSERT INTO room_pool_class_name (room_pool_id, class_name_id) VALUES (?, ?)",
            (pool_id, class_name_id),
        )
    conn.commit()


def test_no_findings_without_any_room_pool():
    conn = build_richer_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=2)

    assert room_pool_violation(conn, lesson_entries(conn)) == []


def test_violation_flagged_when_class_scheduled_outside_its_pool():
    conn = build_richer_synthetic_db()
    _make_pool(conn, room_ids=[1], class_name_ids=[1])
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=2)

    findings = room_pool_violation(conn, lesson_entries(conn))
    assert len(findings) == 1
    f = findings[0]
    assert f.rule_id == "room_pool_violation"
    assert f.severity == "warning"
    assert f.evidence["pool_code"] == "RUR 1"
    assert f.evidence["allowed_room_codes"] == ["R1"]
    assert f.evidence["actual_room_code"] == "R2"
    assert ("class", "CLASSA") in {(r.type, r.code) for r in f.entity_refs}
    assert ("room", "R2") in {(r.type, r.code) for r in f.entity_refs}


def test_no_finding_when_class_stays_inside_its_pool():
    conn = build_richer_synthetic_db()
    _make_pool(conn, room_ids=[1, 2], class_name_ids=[1])
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=2)

    assert room_pool_violation(conn, lesson_entries(conn)) == []


def test_class_not_in_any_pool_is_never_flagged():
    """A pool is a positive restriction on the classes it names - a class
    outside every pool has no room requirement at all, same as
    room_feature_mismatch treating "no constraint" as "no finding," not
    as "must be in room 1."""
    conn = build_richer_synthetic_db()
    _make_pool(conn, room_ids=[1], class_name_ids=[2])  # constrains class 2, not class 1
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=2)

    assert room_pool_violation(conn, lesson_entries(conn)) == []
