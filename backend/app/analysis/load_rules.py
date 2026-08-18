"""Capacity, load, and utilisation rules - the remaining Milestone 1
"first rules" that can be checked against data we actually have,
without guessing an unconfirmed school policy value (see docs/rules.md
for which rules were deliberately skipped and why).

Composite-awareness matters here in a different way than for the clash
rules: a composite lesson (two class codes, one physical room/teacher at
one period) must be counted as ONE occupied slot, not two - otherwise a
teacher's load or a room's utilisation would be inflated by however many
class codes happen to be attached to the same physical lesson. This
applies regardless of whether the composite has been reviewed/approved -
it's a fact about physical time, not an administrative judgement."""

import sqlite3
from collections import defaultdict

from app.analysis.clash_rules import lesson_entries
from app.analysis.contact_time import resolve_contact_entry_types
from app.analysis.models import EntityRef, Finding, SlotRef

# Rooms below this utilisation are flagged as `info`. This is a default
# heuristic for surfacing candidates worth a human look, not a confirmed
# Sophia College policy value - see docs/rules.md.
LOW_UTILISATION_THRESHOLD = 0.20

# early_career_teacher_overloaded (docs/roadmap-v2.md 2.4) - both default
# heuristics, not confirmed school policy, same caveat as
# LOW_UTILISATION_THRESHOLD above. EARLY_CAREER_LOAD_THRESHOLD_PCT mirrors
# the 90-100%-of-cap band already used in docs/roadmap-v2.md 0.2's
# real-data investigation. EARLY_CAREER_SUBJECT_PREP_THRESHOLD was picked
# after checking the real distribution of distinct-subject counts per
# teacher (1-11, median 5, see docs/rules.md) - anything above it sits in
# the top tail, not a made-up round number.
EARLY_CAREER_LOAD_THRESHOLD_PCT = 0.90
EARLY_CAREER_SUBJECT_PREP_THRESHOLD = 7


def room_capacity_exceeded(conn: sqlite3.Connection, entries: list[dict]) -> list[Finding]:
    """entries: LESSON rows shaped like app.analysis.clash_rules.lesson_
    entries() output (room_id, class_name_id, day_code, period_code) - an
    explicit parameter, not an internal query, so a what-if caller (the
    solver's validation loop, app/analysis/repair_solver.py) can check a
    hypothetical timetable without writing to the database. Every other
    caller just passes lesson_entries(conn)."""
    rooms = {r["id"]: r for r in conn.execute("SELECT id, code, seats FROM room WHERE seats IS NOT NULL")}
    if not rooms:
        return []

    slot_classes: dict[tuple, set[int]] = defaultdict(set)
    slot_meta: dict[tuple, tuple[str, str]] = {}
    for e in entries:
        if e["room_id"] not in rooms or e["class_name_id"] is None:
            continue
        key = (e["room_id"], e["day_code"], e["period_code"])
        slot_classes[key].add(e["class_name_id"])
        slot_meta[key] = (e["day_code"], e["period_code"])

    class_codes_by_id = {r["id"]: r["code"] for r in conn.execute("SELECT id, code FROM class_name")}

    findings = []
    for (room_id, day_code, period_code), class_ids in slot_classes.items():
        placeholders = ",".join("?" for _ in class_ids)
        enrolled_count = conn.execute(
            f"SELECT COUNT(DISTINCT student_id) FROM enrolment WHERE class_name_id IN ({placeholders})",
            tuple(class_ids),
        ).fetchone()[0]

        room = rooms[room_id]
        if enrolled_count <= room["seats"]:
            continue

        findings.append(Finding(
            rule_id="room_capacity_exceeded",
            severity="warning",
            title=f"Room {room['code']} over capacity at {day_code} {period_code} "
                  f"({enrolled_count} enrolled, {room['seats']} seats)",
            entity_refs=(
                (EntityRef("room", room["code"]),)
                + tuple(EntityRef("class", class_codes_by_id[cid]) for cid in class_ids)
            ),
            slot_refs=(SlotRef(day_code, period_code),),
            evidence={
                "seats": room["seats"],
                "enrolled_count": enrolled_count,
                "class_codes": [class_codes_by_id[cid] for cid in class_ids],
            },
        ))
    return findings


def teacher_over_contracted_load(conn: sqlite3.Connection) -> list[Finding]:
    teachers = conn.execute(
        "SELECT id, code, contracted_load_minutes FROM teacher WHERE contracted_load_minutes IS NOT NULL"
    ).fetchall()
    if not teachers:
        return []

    # LESSON-only unless a confirmed agreement states otherwise - see
    # app/analysis/contact_time.py and docs/roadmap-v2.md 0.2. Changing
    # what counts as "contact time" changes what every load number in
    # this app means, so it never happens silently.
    contact_entry_types = resolve_contact_entry_types(conn)
    placeholders = ",".join("?" for _ in contact_entry_types)
    entries = conn.execute(
        f"""
        SELECT te.teacher_id, te.period_id, p.load_minutes
        FROM timetable_entry te
        JOIN period p ON p.id = te.period_id
        WHERE te.entry_type IN ({placeholders}) AND te.teacher_id IS NOT NULL
        """,
        contact_entry_types,
    ).fetchall()

    # Distinct (teacher, period) - a composite lesson must not be counted
    # once per class code sharing that slot.
    slots_by_teacher: dict[int, dict[int, float]] = defaultdict(dict)
    for e in entries:
        slots_by_teacher[e["teacher_id"]][e["period_id"]] = e["load_minutes"]

    findings = []
    for t in teachers:
        scheduled_minutes = sum(slots_by_teacher.get(t["id"], {}).values())
        if scheduled_minutes <= t["contracted_load_minutes"]:
            continue

        findings.append(Finding(
            rule_id="teacher_over_contracted_load",
            severity="warning",
            title=f"Teacher {t['code']} scheduled {scheduled_minutes:.0f} min/cycle, "
                  f"over their {t['contracted_load_minutes']:.0f} min contracted load",
            entity_refs=(EntityRef("teacher", t["code"]),),
            slot_refs=(),
            evidence={
                "scheduled_minutes": scheduled_minutes,
                "contracted_load_minutes": t["contracted_load_minutes"],
                "over_by_minutes": scheduled_minutes - t["contracted_load_minutes"],
                "contact_entry_types": list(contact_entry_types),
            },
        ))
    return findings


def room_underutilization(conn: sqlite3.Connection) -> list[Finding]:
    total_lesson_slots = conn.execute(
        "SELECT COUNT(*) FROM period WHERE entry_kind = 'LESSON_SLOT'"
    ).fetchone()[0]
    if total_lesson_slots == 0:
        return []

    rooms = conn.execute("SELECT id, code FROM room WHERE seats IS NOT NULL").fetchall()

    used_slots_by_room: dict[int, set[tuple]] = defaultdict(set)
    entries = conn.execute(
        """
        SELECT te.room_id, te.day_id, te.period_id
        FROM timetable_entry te
        WHERE te.entry_type = 'LESSON' AND te.room_id IS NOT NULL
        """
    ).fetchall()
    for e in entries:
        used_slots_by_room[e["room_id"]].add((e["day_id"], e["period_id"]))

    findings = []
    for room in rooms:
        used = len(used_slots_by_room.get(room["id"], set()))
        utilisation = used / total_lesson_slots
        if utilisation >= LOW_UTILISATION_THRESHOLD:
            continue

        findings.append(Finding(
            rule_id="room_underutilization",
            severity="info",
            title=f"Room {room['code']} used {utilisation:.0%} of available lesson slots",
            entity_refs=(EntityRef("room", room["code"]),),
            slot_refs=(),
            evidence={
                "used_slots": used,
                "total_lesson_slots": total_lesson_slots,
                "utilisation": round(utilisation, 4),
                "threshold": LOW_UTILISATION_THRESHOLD,
                "threshold_note": "Default heuristic for surfacing candidates - not a confirmed school policy value.",
            },
        ))
    return findings


def early_career_teacher_overloaded(conn: sqlite3.Connection) -> list[Finding]:
    """docs/roadmap-v2.md 2.4: 'flag, don't enforce' - no specific ECT
    release entitlement is encoded here (that needs the confirmed
    agreement plus school policy, see app/analysis/release.py's
    leadership pool for the pattern this would follow once one exists).
    Two independent signals, either sufficient to flag: at/near the
    contact cap (the same cap teacher_over_contracted_load checks), or
    an unusual number of distinct subject preparations - a real workload
    driver the raw minute count misses (a teacher covering 8 different
    subjects at 80% load is a different risk than one covering 2)."""
    ects = conn.execute(
        "SELECT t.id, t.code, t.contracted_load_minutes FROM teacher t "
        "JOIN teacher_profile tp ON tp.teacher_code = t.code WHERE tp.career_stage = 'EARLY_CAREER'"
    ).fetchall()
    if not ects:
        return []

    contact_entry_types = resolve_contact_entry_types(conn)
    placeholders = ",".join("?" for _ in contact_entry_types)
    load_rows = conn.execute(
        f"""
        SELECT te.teacher_id, te.period_id, p.load_minutes
        FROM timetable_entry te JOIN period p ON p.id = te.period_id
        WHERE te.entry_type IN ({placeholders}) AND te.teacher_id IS NOT NULL
        """,
        contact_entry_types,
    ).fetchall()
    slots_by_teacher: dict[int, dict[int, float]] = defaultdict(dict)
    for r in load_rows:
        slots_by_teacher[r["teacher_id"]][r["period_id"]] = r["load_minutes"]

    subject_rows = conn.execute(
        """
        SELECT te.teacher_id, COUNT(DISTINCT cn.subject_id) AS distinct_subjects
        FROM timetable_entry te JOIN class_name cn ON cn.id = te.class_name_id
        WHERE te.entry_type = 'LESSON' AND te.teacher_id IS NOT NULL
        GROUP BY te.teacher_id
        """
    ).fetchall()
    distinct_subjects_by_teacher = {r["teacher_id"]: r["distinct_subjects"] for r in subject_rows}

    findings = []
    for t in ects:
        scheduled_minutes = sum(slots_by_teacher.get(t["id"], {}).values())
        distinct_subjects = distinct_subjects_by_teacher.get(t["id"], 0)

        near_cap = (
            t["contracted_load_minutes"] is not None
            and scheduled_minutes >= EARLY_CAREER_LOAD_THRESHOLD_PCT * t["contracted_load_minutes"]
        )
        many_preparations = distinct_subjects > EARLY_CAREER_SUBJECT_PREP_THRESHOLD
        if not near_cap and not many_preparations:
            continue

        reasons = []
        if near_cap:
            reasons.append(f"scheduled {scheduled_minutes:.0f}/{t['contracted_load_minutes']:.0f} min/cycle")
        if many_preparations:
            reasons.append(f"{distinct_subjects} distinct subject preparations")

        findings.append(Finding(
            rule_id="early_career_teacher_overloaded",
            severity="warning",
            title=f"Early-career teacher {t['code']} - {'; '.join(reasons)}",
            entity_refs=(EntityRef("teacher", t["code"]),),
            slot_refs=(),
            evidence={
                "scheduled_minutes": scheduled_minutes,
                "contracted_load_minutes": t["contracted_load_minutes"],
                "distinct_subjects": distinct_subjects,
                "near_cap": near_cap,
                "many_preparations": many_preparations,
                "load_threshold_pct": EARLY_CAREER_LOAD_THRESHOLD_PCT,
                "subject_prep_threshold": EARLY_CAREER_SUBJECT_PREP_THRESHOLD,
                "contact_entry_types": list(contact_entry_types),
                "threshold_note": "Default heuristics for surfacing candidates - not confirmed school policy values.",
            },
        ))
    return findings


def run_load_rules(conn: sqlite3.Connection) -> list[Finding]:
    return [
        *room_capacity_exceeded(conn, lesson_entries(conn)),
        *teacher_over_contracted_load(conn),
        *room_underutilization(conn),
        *early_career_teacher_overloaded(conn),
    ]
