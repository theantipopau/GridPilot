"""Upserts detected composite groups (app/analysis/composite.py) into the
reviewable composite_group/composite_group_member tables, without ever
clobbering an existing human review decision. See PROJECT_ROADMAP.md's
'Milestone 2: Human-reviewed composite classes' - detection produces
candidates; a person approves or rejects; only APPROVED groups suppress
clash findings."""

import datetime as dt
import sqlite3
from dataclasses import dataclass

from app.analysis.composite import detect_composite_groups


def _code_to_id_maps(conn: sqlite3.Connection) -> tuple[dict, dict, dict]:
    teacher_id_by_code = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM teacher")}
    room_id_by_code = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM room")}
    class_name_id_by_code = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM class_name")}
    return teacher_id_by_code, room_id_by_code, class_name_id_by_code


def _existing_groups(conn: sqlite3.Connection) -> dict[tuple, dict]:
    """(teacher_id, room_id, frozenset(class_name_id)) -> {id, review_status, ...}"""
    groups = {r["id"]: dict(r) for r in conn.execute(
        "SELECT id, teacher_id, room_id, review_status FROM composite_group"
    )}
    members: dict[int, set[int]] = {}
    for r in conn.execute("SELECT composite_group_id, class_name_id FROM composite_group_member"):
        members.setdefault(r["composite_group_id"], set()).add(r["class_name_id"])

    by_key = {}
    for group_id, group in groups.items():
        key = (group["teacher_id"], group["room_id"], frozenset(members.get(group_id, set())))
        by_key[key] = group
    return by_key


def sync_composite_candidates(conn: sqlite3.Connection, min_slots: int = 2) -> dict[str, int]:
    detected = detect_composite_groups(conn, min_slots=min_slots)
    teacher_id_by_code, room_id_by_code, class_name_id_by_code = _code_to_id_maps(conn)
    existing_by_key = _existing_groups(conn)

    now = dt.datetime.now(dt.UTC).isoformat()
    created = 0
    updated = 0
    seen_keys = set()

    for g in detected:
        teacher_id = teacher_id_by_code[g.teacher_code]
        room_id = room_id_by_code[g.room_code]
        member_ids = frozenset(class_name_id_by_code[c] for c in g.class_codes)
        key = (teacher_id, room_id, member_ids)
        seen_keys.add(key)

        existing = existing_by_key.get(key)
        if existing is not None:
            conn.execute(
                "UPDATE composite_group SET slot_count = ?, detected_at = ? WHERE id = ?",
                (g.slot_count, now, existing["id"]),
            )
            updated += 1
            continue

        cur = conn.execute(
            "INSERT INTO composite_group (teacher_id, room_id, review_status, slot_count, detected_at) "
            "VALUES (?, ?, 'PENDING', ?, ?)",
            (teacher_id, room_id, g.slot_count, now),
        )
        group_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO composite_group_member (composite_group_id, class_name_id) VALUES (?, ?)",
            [(group_id, cid) for cid in member_ids],
        )
        created += 1

    conn.commit()
    return {"detected": len(detected), "created": created, "updated": updated}


@dataclass(frozen=True)
class ApprovedGroup:
    id: int
    teacher_id: int
    room_id: int
    member_class_name_ids: frozenset[int]


class ApprovedComposites:
    """Kept as distinct per-group member sets, not merged by (teacher, room)
    - a teacher+room pair can host several genuinely different composite
    groupings at different periods (seen in the real data: one room shared
    by rotating supervisors across several distinct study-block groupings),
    and merging them would risk suppressing a clash between two classes
    that were never actually approved to run together."""

    def __init__(self, groups: list[ApprovedGroup]):
        self._groups = groups

    def slot_is_suppressed(self, teacher_id: int, room_id: int, class_name_ids: set[int]) -> bool:
        return any(
            g.teacher_id == teacher_id and g.room_id == room_id and class_name_ids <= g.member_class_name_ids
            for g in self._groups
        )

    def classes_are_composite(self, class_a_id: int, class_b_id: int) -> bool:
        return any({class_a_id, class_b_id} <= g.member_class_name_ids for g in self._groups)


def load_approved_composites(conn: sqlite3.Connection) -> ApprovedComposites:
    group_rows = conn.execute(
        "SELECT id, teacher_id, room_id FROM composite_group WHERE review_status = 'APPROVED'"
    ).fetchall()
    members: dict[int, set[int]] = {}
    for r in conn.execute("SELECT composite_group_id, class_name_id FROM composite_group_member"):
        members.setdefault(r["composite_group_id"], set()).add(r["class_name_id"])

    groups = [
        ApprovedGroup(r["id"], r["teacher_id"], r["room_id"], frozenset(members.get(r["id"], set())))
        for r in group_rows
    ]
    return ApprovedComposites(groups)
