"""room_feature_mismatch - the roadmap's Milestone 1 rule that was
blocked from day one on missing data (see docs/rules.md's "Not yet
implemented" section: "no authoritative subject-to-required-feature
mapping exists"). Unblocked by the class_room_type_constraint review
queue (docs/solver.md section 4.2): once a human has APPROVED a class's
required room_type, any lesson scheduled outside that type is a genuine,
reviewable mismatch. Reads only APPROVED constraints - a PENDING or
REJECTED one never produces a finding, same suppression discipline as
composite_group review status (app/analysis/composite_review.py)."""

import sqlite3

from app.analysis.clash_rules import lesson_entries
from app.analysis.models import EntityRef, Finding, SlotRef


def room_feature_mismatch(conn: sqlite3.Connection, entries: list[dict]) -> list[Finding]:
    """entries: LESSON rows shaped like app.analysis.clash_rules.lesson_
    entries() output - an explicit parameter, not an internal query, so a
    what-if caller (the solver's validation loop, app/analysis/
    repair_solver.py) can check a hypothetical timetable without writing
    to the database. Every other caller just passes lesson_entries(conn)."""
    constraints = conn.execute(
        """
        SELECT crtc.class_name_id, crtc.room_type AS required_type, cn.code AS class_code
        FROM class_room_type_constraint crtc
        JOIN class_name cn ON cn.id = crtc.class_name_id
        WHERE crtc.review_status = 'APPROVED'
        """
    ).fetchall()
    if not constraints:
        return []
    required_by_class_id = {r["class_name_id"]: (r["required_type"], r["class_code"]) for r in constraints}

    room_types_by_id = {r["id"]: r["room_type"] for r in conn.execute("SELECT id, room_type FROM room")}

    findings = []
    for e in entries:
        if e["class_name_id"] not in required_by_class_id or e["room_id"] is None:
            continue
        required_type, class_code = required_by_class_id[e["class_name_id"]]
        actual_type = room_types_by_id.get(e["room_id"])
        if actual_type == required_type:
            continue
        actual = actual_type or "an untyped room"
        findings.append(Finding(
            rule_id="room_feature_mismatch",
            severity="warning",
            title=f"Class {class_code} scheduled in {e['room_code']} ({actual}), not a {required_type} room, "
                  f"at {e['day_code']} {e['period_code']}",
            entity_refs=(EntityRef("class", class_code), EntityRef("room", e["room_code"])),
            slot_refs=(SlotRef(e["day_code"], e["period_code"]),),
            evidence={
                "required_room_type": required_type,
                "actual_room_type": actual_type,
                "room_code": e["room_code"],
            },
        ))
    return findings


def run_room_feature_rules(conn: sqlite3.Connection) -> list[Finding]:
    return [*room_feature_mismatch(conn, lesson_entries(conn))]
