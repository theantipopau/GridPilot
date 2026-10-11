"""AI room-allocation advice - the "which room should this lesson use?"
question, answered within this project's advisor boundary
(app/advisor/explain.py): the deterministic layer computes the facts
(which rooms are legal at each candidate slot, what type/capacity
constraints apply, what the class's room history looks like) and the
local Ollama model only *explains* the trade-off in plain English. The
model never picks a room, never invents availability, and every
statement it makes is traceable to the facts block below - the same
explain-never-decide discipline as explain_finding/explain_portfolio.

This is deliberately not a solver: app/analysis/repair_solver.py already
makes optimal room choices under constraints, and suggest_fixes() already
produces ranked, pre-validated candidates. This endpoint is the "why is
RIE01 the sensible target for 10SCI2's Tuesday P3 lesson, and what
happens to 9MAT1 if I take it?" narrative layer between those.
"""

import json
import sqlite3
from collections import defaultdict

from app.advisor.explain import AdvisorError, OLLAMA_MODEL, _generate
from app.analysis.suggestions import legal_slots_for_entry


def _room_facts(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT code, name, seats, room_type FROM room ORDER BY code").fetchall()
    lesson_slots_total = conn.execute(
        "SELECT COUNT(*) FROM period WHERE entry_kind = 'LESSON_SLOT'"
    ).fetchone()[0]
    used_by_room: dict[str, int] = defaultdict(int)
    for r in conn.execute(
        """
        SELECT rm.code, COUNT(DISTINCT te.day_id || '-' || te.period_id) AS n
        FROM timetable_entry te JOIN room rm ON rm.id = te.room_id
        WHERE te.entry_type = 'LESSON' AND te.room_id IS NOT NULL
        GROUP BY rm.code
        """
    ):
        used_by_room[r["code"]] = r["n"]
    return [
        {
            "code": row["code"],
            "room_type": row["room_type"],
            "seats": row["seats"],
            "used_lesson_slots": used_by_room.get(row["code"], 0),
            "total_lesson_slots": lesson_slots_total,
        }
        for row in rows
    ]


def room_advice(conn: sqlite3.Connection, entry_id: int, preferred_day_code: str | None = None) -> dict | None:
    """Gathers the deterministic facts for one lesson's room decision and
    returns them with the AI's narrative. Returns None if entry_id
    doesn't resolve to a LESSON entry (same contract as
    legal_slots_for_entry)."""
    legal = legal_slots_for_entry(conn, entry_id)
    if legal is None:
        return None

    entry_rows = conn.execute(
        """
        SELECT te.id, cn.code AS class_code, s.source_code AS subject_code,
               rm.code AS current_room_code, rm.room_type AS current_room_type
        FROM timetable_entry te
        JOIN roll_class rc ON rc.id = te.roll_class_id
        LEFT JOIN class_name cn ON cn.id = te.class_name_id
        LEFT JOIN subject s ON s.id = cn.subject_id
        LEFT JOIN room rm ON rm.id = te.room_id
        WHERE te.id = ?
        """,
        (entry_id,),
    ).fetchone()

    enrolled = 0
    if entry_rows is not None and entry_rows["class_code"] is not None:
        row = conn.execute(
            """
            SELECT COUNT(DISTINCT e.student_id) AS n
            FROM enrolment e JOIN class_name cn ON cn.id = e.class_name_id
            WHERE cn.code = ?
            """,
            (entry_rows["class_code"],),
        ).fetchone()
        enrolled = row["n"] if row else 0

    # Legal slots only (per legal_slots_for_entry), each carrying the
    # rooms that can actually host the class there. Deliberately excludes
    # the full slot list - an AI prompt with 50 mostly-illegal rows drowns
    # the signal.
    open_slots = [s for s in legal["slots"] if s["legal"]]
    if preferred_day_code:
        open_slots = [s for s in open_slots if s["day_code"] == preferred_day_code] or open_slots

    legal_by_slot = [
        {"day_code": s["day_code"], "period_code": s["period_code"], "rooms": s["legal_room_codes"]}
        for s in open_slots[:20]
    ]

    # Class's own room usage across the cycle - consistency is a real
    # trade-off a room decision makes (taking today's free lab might mean
    # a third room for the same class this week).
    class_entries = conn.execute(
        """
        SELECT rm.code, COUNT(*) AS n
        FROM timetable_entry te
        LEFT JOIN room rm ON rm.id = te.room_id
        WHERE te.class_name_id = (SELECT id FROM class_name WHERE code = ?) AND te.entry_type = 'LESSON'
        GROUP BY rm.code
        """,
        (legal["class_code"],),
    ).fetchall()
    room_usage = [{"room_code": r["code"] or "(none)", "lessons": r["n"]} for r in class_entries]

    facts = {
        "entry_id": entry_id,
        "class_code": legal["class_code"],
        "subject_code": entry_rows["subject_code"] if entry_rows else None,
        "current_room_code": legal["current_room_code"],
        "enrolled_students": enrolled,
        "legal_slots_with_rooms": legal_by_slot,
        "class_room_usage_this_cycle": room_usage,
        "rooms": _room_facts(conn),
    }

    return {"facts": facts}


def _build_room_prompt(facts: dict) -> str:
    slots = "\n".join(
        f"- {s['day_code']} {s['period_code']}: rooms available: {', '.join(s['rooms']) if s['rooms'] else '(none)'}"
        for s in facts["legal_slots_with_rooms"]
    ) or "(no legal slot anywhere - the class cannot be placed right now)"
    usage = "\n".join(f"- {u['room_code']}: {u['lessons']} lesson(s)" for u in facts["class_room_usage_this_cycle"]) or "(none)"
    rooms = "\n".join(
        f"- {r['code']}: type={r['room_type'] or 'unspecified'}, seats={r['seats'] if r['seats'] is not None else 'no fixed capacity'}, "
        f"{r['used_lesson_slots']}/{r['total_lesson_slots']} lesson slots used"
        for r in facts["rooms"]
    )

    return (
        "You are helping a school timetabler choose a room for one lesson. Below are facts computed directly "
        "from the real timetable by a deterministic checker - teacher/student availability, room type and "
        "capacity constraints, and the class's own room history. Write 2-5 sentences of plain English about "
        "HOW TO THINK about this choice: which slots are genuinely open, which rooms fit the class size and "
        "any type requirement, and what the trade-off is (e.g. keeping the class in its usual room versus "
        "spreading across another). If a fact isn't given, say you don't know rather than guessing. "
        "Do NOT invent availability, do NOT invent room types, do NOT claim a room is free when the facts "
        "don't list it as available - and never suggest changing teachers, times beyond the listed slots, "
        "or anything the facts don't show. End by pointing back to the Suggest-a-fix and solver features for "
        "actually applying a change.\n\n"
        f"Class: {facts['class_code']} (subject {facts['subject_code'] or 'unknown'}), "
        f"{facts['enrolled_students']} enrolled student(s), currently in room "
        f"{facts['current_room_code'] or '(no room)'}.\n\n"
        f"Slots where this lesson can legally go, with the rooms free in each:\n{slots}\n\n"
        f"This class's room usage across the whole cycle:\n{usage}\n\n"
        f"All rooms:\n{rooms}"
    )


async def explain_room_choice(facts: dict) -> str:
    return await _generate(_build_room_prompt(facts))


__all__ = ["AdvisorError", "OLLAMA_MODEL", "room_advice", "explain_room_choice"]
