"""Rooms page (docs/roadmap-v2.md 3.3a) - there was no room-centric view
anywhere in the app despite room being the default axis of the master
grid. Read-only: authoring a room is Tier 2 (docs/full-timetabler-plan.md
§5) and gated on the still-open GUID minting experiment, same as every
other entity-authoring item in that plan."""

import json
import sqlite3
from collections import defaultdict

from fastapi import APIRouter, Depends

from app.api.deps import get_db

router = APIRouter()


def _used_slots_by_room(conn: sqlite3.Connection) -> dict[int, int]:
    used: dict[int, set[tuple]] = defaultdict(set)
    for r in conn.execute(
        "SELECT room_id, day_id, period_id FROM timetable_entry WHERE entry_type = 'LESSON' AND room_id IS NOT NULL"
    ):
        used[r["room_id"]].add((r["day_id"], r["period_id"]))
    return {rid: len(slots) for rid, slots in used.items()}


def _open_finding_counts_by_room_code(conn: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for r in conn.execute("SELECT entity_refs_json FROM finding WHERE status = 'OPEN'"):
        for ref in json.loads(r["entity_refs_json"]):
            if ref["type"] == "room":
                counts[ref["code"]] += 1
    return counts


def _pool_by_room_id(conn: sqlite3.Connection) -> dict[int, dict]:
    pool_rooms: dict[int, list[str]] = defaultdict(list)
    for r in conn.execute(
        "SELECT rpr.room_pool_id, rm.code FROM room_pool_room rpr JOIN room rm ON rm.id = rpr.room_id"
    ):
        pool_rooms[r["room_pool_id"]].append(r["code"])

    by_room: dict[int, dict] = {}
    for r in conn.execute("SELECT rpr.room_id, rp.id AS pool_id, rp.code AS pool_code FROM room_pool_room rpr JOIN room_pool rp ON rp.id = rpr.room_pool_id"):
        by_room[r["room_id"]] = {"pool_code": r["pool_code"], "room_codes": sorted(pool_rooms[r["pool_id"]])}
    return by_room


def _approved_classes_by_room_type(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """For a room of a given type, which classes have an APPROVED
    class_room_type_constraint requiring that type - i.e. classes
    expected to use rooms like this one."""
    by_type: dict[str, list[str]] = defaultdict(list)
    for r in conn.execute(
        """
        SELECT crtc.room_type, cn.code
        FROM class_room_type_constraint crtc
        JOIN class_name cn ON cn.id = crtc.class_name_id
        WHERE crtc.review_status = 'APPROVED'
        ORDER BY cn.code
        """
    ):
        by_type[r["room_type"]].append(r["code"])
    return by_type


@router.get("/rooms")
def list_rooms(conn: sqlite3.Connection = Depends(get_db)) -> dict:
    total_lesson_slots = conn.execute("SELECT COUNT(*) FROM period WHERE entry_kind = 'LESSON_SLOT'").fetchone()[0]
    used_by_room = _used_slots_by_room(conn)
    findings_by_code = _open_finding_counts_by_room_code(conn)
    pool_by_room = _pool_by_room_id(conn)
    classes_by_type = _approved_classes_by_room_type(conn)

    rooms = conn.execute("SELECT id, code, name, seats, room_type FROM room ORDER BY code").fetchall()
    return {
        "rooms": [
            {
                "code": r["code"],
                "name": r["name"],
                "seats": r["seats"],
                "room_type": r["room_type"],
                "used_slots": used_by_room.get(r["id"], 0),
                "total_lesson_slots": total_lesson_slots,
                "utilisation_pct": round(100 * used_by_room.get(r["id"], 0) / total_lesson_slots, 1)
                if total_lesson_slots else None,
                "pool": pool_by_room.get(r["id"]),
                "expected_class_codes": classes_by_type.get(r["room_type"], []) if r["room_type"] else [],
                "open_finding_count": findings_by_code.get(r["code"], 0),
            }
            for r in rooms
        ]
    }
