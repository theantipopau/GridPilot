"""room_pool_violation - room_pool/room_pool_room/room_pool_class_name
have been parsed from the .tfx's RURs (Room Utilisation Requirements)
since Phase A of docs/full-timetabler-plan.md, but no rule ever read
them (docs/roadmap-v2.md 3.3b). A RUR is the school's own declared
constraint - "these classes must use one of these rooms" - so unlike
room_feature_mismatch, this needs no human review step first: the pool
membership itself already came from Timetabling Solutions.

Verified against the real database before writing this: RUR 1 restricts
28 science classes (07SCI-12PHY) to 5 rooms (RIE01/02/05/06/07). Two
real lessons currently sit outside it - 12PHY1 in ANG7, 11BIO1 in
SPO05 - a genuine signal, not a hypothetical."""

import sqlite3
from collections import defaultdict

from app.analysis.clash_rules import lesson_entries
from app.analysis.models import EntityRef, Finding, SlotRef


def pool_room_ids_by_class(conn: sqlite3.Connection) -> dict[int, frozenset[int]]:
    """class_name_id -> the set of room ids its room_pool restricts it to.
    Shared by the repair solver (repair_solver.py) and the suggestion
    engine (suggestions.py) - one implementation, not two that could
    drift (docs/roadmap-v3.md 1.2)."""
    rows = conn.execute(
        """
        SELECT rpc.class_name_id, rpr.room_id
        FROM room_pool_class_name rpc
        JOIN room_pool_room rpr ON rpr.room_pool_id = rpc.room_pool_id
        """
    ).fetchall()
    by_class: dict[int, set[int]] = defaultdict(set)
    for r in rows:
        by_class[r["class_name_id"]].add(r["room_id"])
    return {cid: frozenset(rids) for cid, rids in by_class.items()}


def room_pool_violation(conn: sqlite3.Connection, entries: list[dict]) -> list[Finding]:
    """entries: LESSON rows shaped like app.analysis.clash_rules.lesson_
    entries() output - an explicit parameter, not an internal query, so a
    what-if caller (the solver's validation loop, app/analysis/
    repair_solver.py) can check a hypothetical timetable without writing
    to the database. Every other caller just passes lesson_entries(conn)."""
    pool_rows = conn.execute(
        """
        SELECT rp.id AS pool_id, rp.code AS pool_code, rpc.class_name_id
        FROM room_pool_class_name rpc
        JOIN room_pool rp ON rp.id = rpc.room_pool_id
        """
    ).fetchall()
    if not pool_rows:
        return []

    pool_by_class_id: dict[int, tuple[int, str]] = {
        r["class_name_id"]: (r["pool_id"], r["pool_code"]) for r in pool_rows
    }

    allowed_rooms_by_pool: dict[int, set[int]] = {}
    for r in conn.execute("SELECT room_pool_id, room_id FROM room_pool_room"):
        allowed_rooms_by_pool.setdefault(r["room_pool_id"], set()).add(r["room_id"])

    pool_room_codes = {
        pool_id: sorted(
            code for (code,) in conn.execute(
                "SELECT rm.code FROM room_pool_room rpr JOIN room rm ON rm.id = rpr.room_id "
                "WHERE rpr.room_pool_id = ?",
                (pool_id,),
            )
        )
        for pool_id in allowed_rooms_by_pool
    }

    findings = []
    for e in entries:
        if e["class_name_id"] not in pool_by_class_id or e["room_id"] is None:
            continue
        pool_id, pool_code = pool_by_class_id[e["class_name_id"]]
        allowed = allowed_rooms_by_pool.get(pool_id, set())
        if e["room_id"] in allowed:
            continue

        findings.append(Finding(
            rule_id="room_pool_violation",
            severity="warning",
            title=f"Class {e['class_code']} scheduled in {e['room_code']}, outside its declared room pool "
                  f"{pool_code} ({e['day_code']} {e['period_code']})",
            entity_refs=(EntityRef("class", e["class_code"]), EntityRef("room", e["room_code"])),
            slot_refs=(SlotRef(e["day_code"], e["period_code"]),),
            evidence={
                "pool_code": pool_code,
                "allowed_room_codes": pool_room_codes.get(pool_id, []),
                "actual_room_code": e["room_code"],
            },
        ))
    return findings


def run_room_pool_rules(conn: sqlite3.Connection) -> list[Finding]:
    return [*room_pool_violation(conn, lesson_entries(conn))]
