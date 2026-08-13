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

from app.analysis.models import EntityRef, Finding, SlotRef


def room_feature_mismatch(conn: sqlite3.Connection) -> list[Finding]:
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

    placeholders = ",".join("?" for _ in required_by_class_id)
    rows = conn.execute(
        f"""
        SELECT te.class_name_id, rm.code AS room_code, rm.room_type AS room_type,
               d.code AS day_code, p.code AS period_code
        FROM timetable_entry te
        JOIN room rm ON rm.id = te.room_id
        JOIN day d ON d.id = te.day_id
        JOIN period p ON p.id = te.period_id
        WHERE te.entry_type = 'LESSON' AND te.class_name_id IN ({placeholders})
        """,
        tuple(required_by_class_id),
    ).fetchall()

    findings = []
    for r in rows:
        required_type, class_code = required_by_class_id[r["class_name_id"]]
        if r["room_type"] == required_type:
            continue
        actual = r["room_type"] or "an untyped room"
        findings.append(Finding(
            rule_id="room_feature_mismatch",
            severity="warning",
            title=f"Class {class_code} scheduled in {r['room_code']} ({actual}), not a {required_type} room, "
                  f"at {r['day_code']} {r['period_code']}",
            entity_refs=(EntityRef("class", class_code), EntityRef("room", r["room_code"])),
            slot_refs=(SlotRef(r["day_code"], r["period_code"]),),
            evidence={
                "required_room_type": required_type,
                "actual_room_type": r["room_type"],
                "room_code": r["room_code"],
            },
        ))
    return findings


def run_room_feature_rules(conn: sqlite3.Connection) -> list[Finding]:
    return [*room_feature_mismatch(conn)]
