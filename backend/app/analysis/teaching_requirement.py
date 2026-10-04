"""Bootstraps candidate teaching_requirement rows describing what the
school currently intends to run, inferred from the resolved timetable -
docs/roadmap-v3.md section 3.1, docs/staff-capability-model.md. Everything
built so far describes an already-resolved timetable; nothing describes
intent. One candidate per class_name not already covered by an APPROVED
composite group, one per APPROVED composite_group (collapsing its
members, per staff-capability-model.md's explicit recommendation - a
composite class must not double-count as several separate requirements).

Every fact here (periods_per_cycle, assigned teacher/room, roll class) is
read directly off timetable_entry and is a majority-vote proposal for
human review, never asserted - same discipline as
room_type_constraints.py, but with no ratio threshold to tune: unlike
room-type (a genuinely ambiguous free-text field), a class either has a
resolved schedule or it doesn't, so every scheduled class produces a
candidate."""

import sqlite3
from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class TeachingRequirementCandidate:
    requirement_key: str
    class_name_id: int | None
    composite_group_id: int | None
    roll_class_id: int | None
    subject_id: int | None
    periods_per_cycle: int
    assigned_teacher_id: int | None
    assigned_room_id: int | None
    matching_lesson_count: int
    total_lesson_count: int


def _approved_composite_membership(conn: sqlite3.Connection) -> tuple[dict[int, int], dict[int, list[int]]]:
    """class_name_id -> composite_group_id, and composite_group_id ->
    [class_name_id, ...], restricted to APPROVED groups - a PENDING or
    REJECTED composite must not suppress its members' own requirements."""
    group_of_class: dict[int, int] = {}
    members_by_group: dict[int, list[int]] = {}
    for r in conn.execute(
        """
        SELECT cgm.composite_group_id, cgm.class_name_id
        FROM composite_group_member cgm
        JOIN composite_group cg ON cg.id = cgm.composite_group_id
        WHERE cg.review_status = 'APPROVED'
        """
    ):
        group_of_class[r["class_name_id"]] = r["composite_group_id"]
        members_by_group.setdefault(r["composite_group_id"], []).append(r["class_name_id"])
    return group_of_class, members_by_group


def _majority(counter: Counter):
    if not counter:
        return None
    return counter.most_common(1)[0][0]


def _lessons_for(conn: sqlite3.Connection, class_name_ids: list[int]) -> list[sqlite3.Row]:
    placeholders = ",".join("?" for _ in class_name_ids)
    return conn.execute(
        f"""
        SELECT day_id, period_id, roll_class_id, teacher_id, room_id
        FROM timetable_entry
        WHERE entry_type = 'LESSON' AND class_name_id IN ({placeholders})
        """,
        class_name_ids,
    ).fetchall()


def _build_candidate(
    requirement_key: str,
    class_name_id: int | None,
    composite_group_id: int | None,
    subject_id: int | None,
    lessons: list[sqlite3.Row],
) -> TeachingRequirementCandidate:
    period_slots = {(r["day_id"], r["period_id"]) for r in lessons}
    teacher_id = _majority(Counter(r["teacher_id"] for r in lessons))
    room_id = _majority(Counter(r["room_id"] for r in lessons))
    # A composite spans multiple roll classes by definition - no single
    # roll_class_id applies, same reasoning schema.sql documents for
    # subject_id staying NULL on the composite path.
    roll_class_id = None if composite_group_id is not None else _majority(Counter(r["roll_class_id"] for r in lessons))
    matching = sum(1 for r in lessons if r["teacher_id"] == teacher_id and r["room_id"] == room_id)

    return TeachingRequirementCandidate(
        requirement_key=requirement_key,
        class_name_id=class_name_id,
        composite_group_id=composite_group_id,
        roll_class_id=roll_class_id,
        subject_id=subject_id,
        periods_per_cycle=len(period_slots),
        assigned_teacher_id=teacher_id,
        assigned_room_id=room_id,
        matching_lesson_count=matching,
        total_lesson_count=len(lessons),
    )


def detect_teaching_requirement_candidates(conn: sqlite3.Connection) -> list[TeachingRequirementCandidate]:
    class_code_by_id = {r["id"]: r["code"] for r in conn.execute("SELECT id, code FROM class_name")}
    subject_by_class = {r["id"]: r["subject_id"] for r in conn.execute("SELECT id, subject_id FROM class_name")}
    group_of_class, members_by_group = _approved_composite_membership(conn)

    candidates: list[TeachingRequirementCandidate] = []

    for group_id, member_ids in members_by_group.items():
        lessons = _lessons_for(conn, member_ids)
        if not lessons:
            continue
        key = "COMPOSITE:" + "|".join(sorted(class_code_by_id[m] for m in member_ids))
        candidates.append(_build_candidate(key, None, group_id, None, lessons))

    scheduled_class_ids = {
        r["class_name_id"]
        for r in conn.execute(
            "SELECT DISTINCT class_name_id FROM timetable_entry "
            "WHERE entry_type = 'LESSON' AND class_name_id IS NOT NULL"
        )
    }
    for class_id in scheduled_class_ids:
        if class_id in group_of_class:
            continue  # covered by its approved composite's own requirement above
        lessons = _lessons_for(conn, [class_id])
        candidates.append(
            _build_candidate(class_code_by_id[class_id], class_id, None, subject_by_class.get(class_id), lessons)
        )

    return sorted(candidates, key=lambda c: c.requirement_key)
