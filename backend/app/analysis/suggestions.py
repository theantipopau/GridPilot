"""Constraint-based candidate moves, per PROJECT_ROADMAP.md Milestone 4:

    1. Find alternate rooms or periods satisfying hard constraints.
    2. Reject candidates that create teacher, room or student clashes.
    3. Reject room-capacity and room-feature failures.
    4. Score remaining options using soft constraints such as movement.
    5. Give the ranked candidates and evidence to the local AI only for
       explanation.

This is deliberately algorithmic, not AI - nothing here calls a model.
The (not yet built) AI advisor layer's job is to explain *these* ranked,
pre-validated candidates in plain language, never to invent its own.

Scope: teacher_double_booking, room_double_booking, class_room_instability,
and (since 2026-08-17, roadmap 2.2 item 9) class_teacher_inconsistency.
Room-feature matching and student_double_booking suggestions are out of
scope - see docs/suggestions.md for why.

Teacher reassignment (moving a lesson to a *different teacher*) was
deliberately never suggested until now - there was no authoritative
subject-qualification data, and guessing would have been exactly the
kind of invented suggestion the roadmap warns against. teacher_capability
(app/analysis/capability.py) removed that blocker: a teacher-consolidation
candidate is only ever offered when CapabilityService.resolve() confirms
the target teacher is not NOT_ELIGIBLE for the class's subject - the same
check teacher_not_qualified_for_class (app/analysis/capability_rules.py)
uses to raise a finding, applied here as a hard constraint before a move
is ever proposed instead of after."""

import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass

from app.analysis.availability_rules import teacher_commitment_busy
from app.analysis.capability import resolve as resolve_capability
from app.analysis.clash_rules import lesson_entries
from app.analysis.composite_review import load_approved_composites
from app.analysis.room_pool_rules import pool_room_ids_by_class
from app.analysis.room_type_constraints import required_room_type_by_class
from app.analysis.whatif import apply_overrides, load_code_lookups, run_clash_findings

MAX_ENTRIES_CONSIDERED = 3  # cap on how many conflicting/minority-room entries per finding get candidates generated
MAX_CANDIDATES_RETURNED = 15
SUPPORTED_RULES = {
    "teacher_double_booking", "room_double_booking", "class_room_instability", "class_teacher_inconsistency",
}


@dataclass(frozen=True)
class Slot:
    day_id: int
    period_id: int
    day_code: str
    period_code: str


def _all_lesson_slots(conn: sqlite3.Connection) -> list[Slot]:
    rows = conn.execute(
        "SELECT p.id AS period_id, p.day_id, d.code AS day_code, p.code AS period_code "
        "FROM period p JOIN day d ON d.id = p.day_id WHERE p.entry_kind = 'LESSON_SLOT'"
    ).fetchall()
    return [Slot(r["day_id"], r["period_id"], r["day_code"], r["period_code"]) for r in rows]


def _busy_sets(entries: list[dict]) -> tuple[dict[int, set], dict[int, set]]:
    teacher_busy: dict[int, set] = defaultdict(set)
    room_busy: dict[int, set] = defaultdict(set)
    for e in entries:
        if e["teacher_id"] is not None:
            teacher_busy[e["teacher_id"]].add((e["day_id"], e["period_id"]))
        if e["room_id"] is not None:
            room_busy[e["room_id"]].add((e["day_id"], e["period_id"]))
    return teacher_busy, room_busy


def _enrolled_count(conn: sqlite3.Connection, class_name_ids: set[int]) -> int:
    if not class_name_ids:
        return 0
    placeholders = ",".join("?" for _ in class_name_ids)
    return conn.execute(
        f"SELECT COUNT(DISTINCT student_id) FROM enrolment WHERE class_name_id IN ({placeholders})",
        tuple(class_name_ids),
    ).fetchone()[0]


def _movement_cost(entry: dict, slot_day_id: int, slot_period_id: int, room_id: int) -> int:
    """Lower is less disruptive. 0 = room-only change, 1 = same day
    different period, 2 = different day. A documented default heuristic
    (see docs/suggestions.md), not a confirmed school weighting."""
    if slot_day_id == entry["day_id"] and slot_period_id == entry["period_id"]:
        return 0  # room-only change
    if slot_day_id == entry["day_id"]:
        return 1
    return 2


def _class_room_familiarity(entries_by_class: dict[int, list[dict]], entry: dict, after_room_id: int | None) -> dict | None:
    """How "at home" the class already is in the candidate's target room -
    the same signal class_room_instability (app/analysis/consistency_
    rules.py) computes, surfaced here so a suggestion can say whether it
    moves the class *towards* or *away from* a consistent room, not just
    "5 · P3 -> RIE01"."""
    if after_room_id is None:
        return None
    others = [e for e in entries_by_class.get(entry["class_name_id"], []) if e["entry_id"] != entry["entry_id"]]
    if not others:
        return None
    same_room_elsewhere = sum(1 for e in others if e["room_id"] == after_room_id)
    return {"same_room_elsewhere_count": same_room_elsewhere, "total_other_lessons": len(others)}


def _majority_room(entries: list[dict]) -> int | None:
    """The room_id most of a class's lessons already use - the "home" room
    a class_room_instability fix should consolidate the rest towards.
    Ties break on room_code alphabetically, so the choice is stable across
    runs rather than depending on query/dict iteration order."""
    counts: dict[int, int] = defaultdict(int)
    codes: dict[int, str] = {}
    for e in entries:
        if e["room_id"] is None:
            continue
        counts[e["room_id"]] += 1
        codes[e["room_id"]] = e["room_code"]
    if not counts:
        return None
    return min(counts, key=lambda room_id: (-counts[room_id], codes[room_id]))


def _majority_teacher(entries: list[dict]) -> int | None:
    """teacher_id equivalent of _majority_room - the teacher most of a
    class's lessons already use, for class_teacher_inconsistency's
    consolidation candidate. Same tie-break discipline (teacher_code
    alphabetically) for stable, re-run-independent results."""
    counts: dict[int, int] = defaultdict(int)
    codes: dict[int, str] = {}
    for e in entries:
        if e["teacher_id"] is None:
            continue
        counts[e["teacher_id"]] += 1
        codes[e["teacher_id"]] = e["teacher_code"]
    if not counts:
        return None
    return min(counts, key=lambda teacher_id: (-counts[teacher_id], codes[teacher_id]))


def _class_teacher_familiarity(entries_by_class: dict[int, list[dict]], entry: dict, after_teacher_id: int | None) -> dict | None:
    """teacher_id equivalent of _class_room_familiarity - how many of the
    class's *other* lessons already run with the candidate's target
    teacher."""
    if after_teacher_id is None:
        return None
    others = [e for e in entries_by_class.get(entry["class_name_id"], []) if e["entry_id"] != entry["entry_id"]]
    if not others:
        return None
    same_teacher_elsewhere = sum(1 for e in others if e["teacher_id"] == after_teacher_id)
    return {"same_teacher_elsewhere_count": same_teacher_elsewhere, "total_other_lessons": len(others)}


def _familiarity_count(c: dict) -> int:
    fam = c.get("class_room_familiarity")
    if fam:
        return fam["same_room_elsewhere_count"]
    fam = c.get("class_teacher_familiarity")
    if fam:
        return fam["same_teacher_elsewhere_count"]
    return 0


def _candidate_sort_key(c: dict) -> tuple:
    # Least disruptive first, then most findings resolved, then prefer a
    # room/teacher the class already uses elsewhere (ties back to the
    # class_room_instability / class_teacher_inconsistency findings these
    # candidates address - a suggestion that happens to make the class
    # *more* consistent, not just conflict-free, ranks ahead of one that
    # doesn't).
    return (c["movement_cost"], -c["resolves_finding_count"], -_familiarity_count(c))


def _try_candidate(
    conn: sqlite3.Connection,
    before_entries: list[dict],
    before_findings: dict,
    composites,
    code_lookups: dict,
    entry: dict,
    after_day_id: int,
    after_period_id: int,
    after_room_id: int | None,
    class_name_ids: set[int],
    entries_by_class: dict[int, list[dict]],
    room_type_by_class: dict[int, str],
    room_pool_by_class: dict[int, frozenset[int]],
) -> dict | None:
    # docs/roadmap-v3.md 1.2: the repair solver has restricted its
    # candidate room domain to a confirmed room-type/room-pool since
    # docs/roadmap-v2.md 3.3b - this search never did, so it could
    # propose a room the solver would refuse. Checked here as a hard
    # constraint, same tier as capacity, before anything expensive runs.
    if after_room_id is not None:
        required_type = room_type_by_class.get(entry["class_name_id"])
        required_room_ids = room_pool_by_class.get(entry["class_name_id"])
        if required_room_ids is not None and after_room_id not in required_room_ids:
            return None
    else:
        required_type = None

    room_capacity: dict = {"confirmed": False}
    if after_room_id is not None:
        room = conn.execute("SELECT seats, room_type FROM room WHERE id = ?", (after_room_id,)).fetchone()
        if room is not None and required_type is not None and room["room_type"] != required_type:
            return None  # hard constraint: approved room-type
        if room is not None and room["seats"] is not None:
            enrolled = _enrolled_count(conn, class_name_ids)
            if enrolled > room["seats"]:
                return None  # hard constraint: room capacity
            room_capacity = {"confirmed": True, "seats": room["seats"], "enrolled": enrolled}

    overrides = {
        entry["entry_id"]: {
            "after_day_id": after_day_id, "after_period_id": after_period_id,
            "after_room_id": after_room_id, "after_teacher_id": entry["teacher_id"],
        }
    }
    after_entries = apply_overrides(before_entries, overrides, code_lookups)
    after_findings = {f.dedupe_key(): f for f in run_clash_findings(conn, after_entries, composites)}

    introduced = [f for k, f in after_findings.items() if k not in before_findings]
    if introduced:
        return None  # hard constraint: would create a new clash

    return {
        "entry_id": entry["entry_id"],
        "class_code": entry["class_code"],
        "before": {
            "day_code": entry["day_code"], "period_code": entry["period_code"],
            "room_code": entry["room_code"], "teacher_code": entry["teacher_code"],
        },
        "after": {
            "day_code": code_lookups["day"][after_day_id],
            "period_code": code_lookups["period"][after_period_id],
            "room_code": code_lookups["room"].get(after_room_id),
            "teacher_code": entry["teacher_code"],  # unchanged - room/slot candidates never reassign teacher
        },
        "movement_cost": _movement_cost(entry, after_day_id, after_period_id, after_room_id),
        "resolves_finding_count": sum(1 for k in before_findings if k not in after_findings),
        "why": {"no_new_clash": True, "room_capacity": room_capacity, "capability_status": None},
        "class_room_familiarity": _class_room_familiarity(entries_by_class, entry, after_room_id),
        "class_teacher_familiarity": None,
    }


def _clash_candidates(
    conn: sqlite3.Connection,
    finding_row,
    before_entries: list[dict],
    entries_by_id: dict[int, dict],
    before_findings: dict,
    composites,
    code_lookups: dict,
    teacher_busy: dict,
    room_busy: dict,
    all_slots: list[Slot],
    entries_by_class: dict[int, list[dict]],
    room_type_by_class: dict[int, str],
    room_pool_by_class: dict[int, frozenset[int]],
) -> dict | None:
    """teacher_double_booking / room_double_booking: for each conflicting
    entry, search every alternate room-at-same-slot and same-room-at-
    another-slot. Returns None if the finding's evidence can't drive a
    search (predates entry_id tracking)."""
    evidence = json.loads(finding_row["evidence_json"])
    conflicting = evidence.get("entries", [])[:MAX_ENTRIES_CONSIDERED]
    if not conflicting or "entry_id" not in conflicting[0]:
        return None

    all_candidates = []
    for conflict in conflicting:
        entry = entries_by_id.get(conflict["entry_id"])
        if entry is None:
            continue

        class_name_ids = {entry["class_name_id"]} if entry["class_name_id"] else set()

        # Type A: same room, different slot.
        if entry["teacher_id"] is not None and entry["room_id"] is not None:
            for slot in all_slots:
                if (slot.day_id, slot.period_id) == (entry["day_id"], entry["period_id"]):
                    continue
                if (slot.day_id, slot.period_id) in teacher_busy.get(entry["teacher_id"], set()):
                    continue
                if (slot.day_id, slot.period_id) in room_busy.get(entry["room_id"], set()):
                    continue
                candidate = _try_candidate(
                    conn, before_entries, before_findings, composites, code_lookups,
                    entry, slot.day_id, slot.period_id, entry["room_id"], class_name_ids,
                    entries_by_class, room_type_by_class, room_pool_by_class,
                )
                if candidate:
                    all_candidates.append(candidate)

        # Type B: same slot, different room.
        if entry["room_id"] is not None:
            for room_row in conn.execute("SELECT id, code FROM room WHERE id != ?", (entry["room_id"],)):
                if (entry["day_id"], entry["period_id"]) in room_busy.get(room_row["id"], set()):
                    continue
                candidate = _try_candidate(
                    conn, before_entries, before_findings, composites, code_lookups,
                    entry, entry["day_id"], entry["period_id"], room_row["id"], class_name_ids,
                    entries_by_class, room_type_by_class, room_pool_by_class,
                )
                if candidate:
                    all_candidates.append(candidate)

    return all_candidates


def _room_instability_candidates(
    conn: sqlite3.Connection,
    finding_row,
    before_entries: list[dict],
    before_findings: dict,
    composites,
    code_lookups: dict,
    room_busy: dict,
    entries_by_class: dict[int, list[dict]],
    room_type_by_class: dict[int, str],
    room_pool_by_class: dict[int, frozenset[int]],
) -> list[dict] | None:
    """class_room_instability: unlike the clash rules, there's no
    conflicting entry to move - the "fix" is consolidating the class's
    lessons into whichever room it already favours. For each lesson
    currently in a minority room, the only candidate offered is that one
    room, at the lesson's existing slot (moving it *and* the time would
    also fix the room, but that's no longer "make this consistent", it's
    a different suggestion and out of scope - see docs/suggestions.md).
    Returns None if the finding's class can't be resolved from entity_refs
    (predates entity_refs tracking, or has no lessons left)."""
    entity_refs = json.loads(finding_row["entity_refs_json"])
    class_code = next((r["code"] for r in entity_refs if r["type"] == "class"), None)
    if class_code is None:
        return None

    class_entries = [e for e in before_entries if e["class_code"] == class_code]
    target_room_id = _majority_room(class_entries)
    if target_room_id is None:
        return None

    class_name_ids = {e["class_name_id"] for e in class_entries if e["class_name_id"] is not None}
    minority_entries = [e for e in class_entries if e["room_id"] != target_room_id][:MAX_ENTRIES_CONSIDERED]

    all_candidates = []
    for entry in minority_entries:
        if (entry["day_id"], entry["period_id"]) in room_busy.get(target_room_id, set()):
            continue  # the class's own room is already taken at this lesson's slot
        candidate = _try_candidate(
            conn, before_entries, before_findings, composites, code_lookups,
            entry, entry["day_id"], entry["period_id"], target_room_id, class_name_ids,
            entries_by_class, room_type_by_class, room_pool_by_class,
        )
        if candidate:
            all_candidates.append(candidate)
    return all_candidates


def _class_subject(conn: sqlite3.Connection, class_name_id: int) -> tuple[str, str | None] | None:
    row = conn.execute(
        "SELECT s.source_code AS subject_code, f.code AS faculty_code "
        "FROM class_name cn JOIN subject s ON s.id = cn.subject_id LEFT JOIN faculty f ON f.id = s.faculty_id "
        "WHERE cn.id = ?",
        (class_name_id,),
    ).fetchone()
    if row is None:
        return None
    return row["subject_code"], row["faculty_code"]


def _try_teacher_candidate(
    conn: sqlite3.Connection,
    before_entries: list[dict],
    before_findings: dict,
    composites,
    code_lookups: dict,
    entry: dict,
    after_teacher_id: int,
    subject_code: str,
    faculty_code: str | None,
    entries_by_class: dict[int, list[dict]],
) -> dict | None:
    after_teacher_code = code_lookups["teacher"].get(after_teacher_id)
    capability_status = resolve_capability(conn, after_teacher_code, subject_code, faculty_code)
    if capability_status == "NOT_ELIGIBLE":
        return None  # hard constraint: would create a teacher_not_qualified_for_class finding

    overrides = {entry["entry_id"]: {"after_teacher_id": after_teacher_id}}
    after_entries = apply_overrides(before_entries, overrides, code_lookups)
    after_findings = {f.dedupe_key(): f for f in run_clash_findings(conn, after_entries, composites)}

    introduced = [f for k, f in after_findings.items() if k not in before_findings]
    if introduced:
        return None  # hard constraint: would create a new clash (e.g. the target teacher is already double-booked)

    return {
        "entry_id": entry["entry_id"],
        "class_code": entry["class_code"],
        "before": {
            "day_code": entry["day_code"], "period_code": entry["period_code"],
            "room_code": entry["room_code"], "teacher_code": entry["teacher_code"],
        },
        "after": {
            "day_code": entry["day_code"], "period_code": entry["period_code"],
            "room_code": entry["room_code"], "teacher_code": after_teacher_code,
        },
        "movement_cost": 0,  # slot and room never change - only the teacher does
        "resolves_finding_count": sum(1 for k in before_findings if k not in after_findings),
        "why": {"no_new_clash": True, "room_capacity": {"confirmed": False}, "capability_status": capability_status},
        "class_room_familiarity": None,
        "class_teacher_familiarity": _class_teacher_familiarity(entries_by_class, entry, after_teacher_id),
    }


def _teacher_consolidation_candidates(
    conn: sqlite3.Connection,
    finding_row,
    before_entries: list[dict],
    before_findings: dict,
    composites,
    code_lookups: dict,
    teacher_busy: dict,
    entries_by_class: dict[int, list[dict]],
) -> list[dict] | None:
    """class_teacher_inconsistency's counterpart to _room_instability_
    candidates: consolidate the class's lessons onto whichever teacher
    already covers most of them. Unblocked by teacher_capability
    (docs/roadmap-v2.md 2.2, item 9) - the majority teacher is only ever
    offered as a candidate when CapabilityService.resolve() confirms
    they're not NOT_ELIGIBLE for the class's subject, so this never
    proposes the "invented suggestion" docs/suggestions.md used to warn
    against. Returns None if the finding's class, or its subject, can't be
    resolved (predates entity_refs tracking, or the class's subject_id is
    unset)."""
    entity_refs = json.loads(finding_row["entity_refs_json"])
    class_code = next((r["code"] for r in entity_refs if r["type"] == "class"), None)
    if class_code is None:
        return None

    class_entries = [e for e in before_entries if e["class_code"] == class_code]
    target_teacher_id = _majority_teacher(class_entries)
    if target_teacher_id is None:
        return None

    class_name_id = next((e["class_name_id"] for e in class_entries if e["class_name_id"] is not None), None)
    subject_faculty = _class_subject(conn, class_name_id) if class_name_id is not None else None
    if subject_faculty is None:
        return None
    subject_code, faculty_code = subject_faculty

    minority_entries = [e for e in class_entries if e["teacher_id"] != target_teacher_id][:MAX_ENTRIES_CONSIDERED]

    all_candidates = []
    for entry in minority_entries:
        if (entry["day_id"], entry["period_id"]) in teacher_busy.get(target_teacher_id, set()):
            continue  # the class's own majority teacher is already teaching elsewhere at this lesson's slot
        candidate = _try_teacher_candidate(
            conn, before_entries, before_findings, composites, code_lookups,
            entry, target_teacher_id, subject_code, faculty_code, entries_by_class,
        )
        if candidate:
            all_candidates.append(candidate)
    return all_candidates


def suggest_fixes(conn: sqlite3.Connection, finding_id: int) -> dict:
    finding_row = conn.execute(
        "SELECT rule_id, evidence_json, entity_refs_json FROM finding WHERE id = ?", (finding_id,)
    ).fetchone()
    if finding_row is None:
        return {"finding_id": finding_id, "supported": False, "note": "No such finding.", "candidates": []}

    if finding_row["rule_id"] not in SUPPORTED_RULES:
        return {
            "finding_id": finding_id, "supported": False,
            "note": f"Suggestion generation isn't implemented for {finding_row['rule_id']} yet - see docs/suggestions.md.",
            "candidates": [],
        }

    code_lookups = load_code_lookups(conn)
    composites = load_approved_composites(conn)
    before_entries = lesson_entries(conn)
    entries_by_id = {e["entry_id"]: e for e in before_entries}
    before_findings = {f.dedupe_key(): f for f in run_clash_findings(conn, before_entries, composites)}
    teacher_busy, room_busy = _busy_sets(before_entries)
    # docs/roadmap-v3.md 1.1: a standing meeting commitment blocks a slot
    # exactly like an existing lesson would - merged into the same
    # teacher_busy dict every candidate search below already consults, so
    # nothing here needs to know commitments exist as a separate concept.
    for teacher_id, slots in teacher_commitment_busy(conn).items():
        teacher_busy[teacher_id] |= slots
    all_slots = _all_lesson_slots(conn)
    # docs/roadmap-v3.md 1.2: the same confirmed room-type/room-pool
    # domain restriction the repair solver applies natively - loaded once
    # here rather than at every _try_candidate call.
    room_type_by_class = required_room_type_by_class(conn)
    room_pool_by_class = pool_room_ids_by_class(conn)

    entries_by_class: dict[int, list[dict]] = defaultdict(list)
    for e in before_entries:
        if e["class_name_id"] is not None:
            entries_by_class[e["class_name_id"]].append(e)

    if finding_row["rule_id"] == "class_room_instability":
        candidates = _room_instability_candidates(
            conn, finding_row, before_entries, before_findings, composites, code_lookups,
            room_busy, entries_by_class, room_type_by_class, room_pool_by_class,
        )
        not_found_note = "This class's lessons couldn't be matched to the current timetable - re-run the rules engine."
    elif finding_row["rule_id"] == "class_teacher_inconsistency":
        candidates = _teacher_consolidation_candidates(
            conn, finding_row, before_entries, before_findings, composites, code_lookups,
            teacher_busy, entries_by_class,
        )
        not_found_note = "This class's lessons or subject couldn't be matched to the current timetable - re-run the rules engine."
    else:
        candidates = _clash_candidates(
            conn, finding_row, before_entries, entries_by_id, before_findings, composites, code_lookups,
            teacher_busy, room_busy, all_slots, entries_by_class, room_type_by_class, room_pool_by_class,
        )
        not_found_note = "Finding evidence predates entry_id tracking - re-run the rules engine."

    if candidates is None:
        return {"finding_id": finding_id, "supported": False, "note": not_found_note, "candidates": []}

    candidates.sort(key=_candidate_sort_key)
    return {
        "finding_id": finding_id, "supported": True, "note": None,
        "candidates": candidates[:MAX_CANDIDATES_RETURNED],
    }


def legal_slots_for_entry(conn: sqlite3.Connection, entry_id: int) -> dict | None:
    """docs/full-timetabler-plan.md §12.6 / roadmap-v3.md 4.4: the
    per-entry candidate endpoint, generalised from "which finding is
    this" to "which lesson is this" - live legal-slot feedback in
    LessonInspector's move-manually dropdowns needs an answer for any
    selected lesson, most of which have no open finding at all.

    Deliberately the CHEAP check, not suggest_fixes()'s full
    re-validation: teacher/student availability plus room type/pool/
    capacity - the same three-layer check app/analysis/infeasibility.py
    and repair_solver.py's _feasible_candidates already use, not a second
    call to run_clash_findings() for every (slot, room) pair, which at
    ~50 slots x ~15+ rooms per lesson would be hundreds of full
    rules-engine passes for what is only ever a live UI hint. This is
    honest about that trade-off, not silently unsound: composite-
    suppression edge cases aren't re-checked here the way
    suggest_fixes()'s candidates are, exactly as "Propose this move"
    already does the real, authoritative check via validate_change_set
    before anything is ever written - this endpoint only ever shades a
    dropdown, never proposes a change on its own.

    Returns None if entry_id doesn't resolve to a LESSON entry."""
    before_entries = lesson_entries(conn)
    entry = next((e for e in before_entries if e["entry_id"] == entry_id), None)
    if entry is None:
        return None

    all_slots = _all_lesson_slots(conn)
    teacher_busy, room_busy = _busy_sets([e for e in before_entries if e["entry_id"] != entry_id])
    for teacher_id, slots in teacher_commitment_busy(conn).items():
        teacher_busy[teacher_id] |= slots

    students_by_class: dict[int, set[int]] = defaultdict(set)
    for r in conn.execute("SELECT class_name_id, student_id FROM enrolment"):
        students_by_class[r["class_name_id"]].add(r["student_id"])
    students = students_by_class.get(entry["class_name_id"], set())
    student_busy: dict[int, set] = defaultdict(set)
    for e in before_entries:
        if e["entry_id"] == entry_id:
            continue
        for sid in students_by_class.get(e["class_name_id"], ()):
            student_busy[sid].add((e["day_id"], e["period_id"]))

    rooms = {r["id"]: dict(r) for r in conn.execute("SELECT id, code, seats, room_type FROM room")}
    enrolled = len(students)
    required_room_type = required_room_type_by_class(conn).get(entry["class_name_id"])
    required_room_ids = pool_room_ids_by_class(conn).get(entry["class_name_id"])

    def room_is_eligible(room: dict) -> bool:
        if room["seats"] is not None and enrolled > room["seats"]:
            return False
        if required_room_type is not None and room["room_type"] != required_room_type:
            return False
        if required_room_ids is not None and room["id"] not in required_room_ids:
            return False
        return True

    eligible_rooms = [r for r in rooms.values() if room_is_eligible(r)]

    teacher_id = entry["teacher_id"]
    slots_out = []
    for slot in all_slots:
        if teacher_id is not None and (slot.day_id, slot.period_id) in teacher_busy.get(teacher_id, ()):
            slots_out.append({"day_code": slot.day_code, "period_code": slot.period_code, "legal": False, "legal_room_codes": []})
            continue
        if any((slot.day_id, slot.period_id) in student_busy.get(sid, ()) for sid in students):
            slots_out.append({"day_code": slot.day_code, "period_code": slot.period_code, "legal": False, "legal_room_codes": []})
            continue
        legal_rooms = [
            r["code"] for r in eligible_rooms if (slot.day_id, slot.period_id) not in room_busy.get(r["id"], ())
        ]
        slots_out.append({
            "day_code": slot.day_code, "period_code": slot.period_code,
            "legal": len(legal_rooms) > 0, "legal_room_codes": sorted(legal_rooms),
        })

    return {
        "entry_id": entry_id,
        "class_code": entry["class_code"],
        "current_room_code": entry["room_code"],
        "slots": slots_out,
    }
