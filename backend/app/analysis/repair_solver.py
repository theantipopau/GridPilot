"""Mode A ("mass repair") from docs/solver.md: given a set of findings,
find a minimal-movement set of moves that resolves as many as possible
without introducing anything new - using a real constraint solver
(OR-Tools CP-SAT), not a language model. See docs/solver.md section 1 for
why an LLM cannot do this job, and docs/mass-repair.md for the full
design writeup.

Two-layer correctness, deliberately:

1. **Native hard constraints** (teacher/room/student double-booking, room
   capacity, approved room-type) are encoded directly in the CP-SAT
   model. Student clashes are modelled the same way as room/teacher ones
   - AtMostOne per (slot, student) - even though suggest_fixes() and
   REPAIR_ELIGIBLE_RULES both correctly refuse to treat
   student_double_booking as something with a single "the" entry to move
   (see docs/suggestions.md's Scope section): that restriction is about
   which *findings* are worth asking the solver to fix, not about
   whether the solver needs to know students exist. It does - real data
   showed almost every candidate move landing on some student's other
   class (see docs/mass-repair.md's "what real data taught us" section),
   so this constraint is load-bearing, not a nice-to-have.
2. **Everything else is caught by re-validation, not re-implementation.**
   Composite-suppression nuances and anything else not natively modelled
   are still independently re-checked with the exact same validator
   change-set validation and suggest_fixes() already use
   (app/analysis/whatif.py, plus the capacity/room-feature rules refactored
   to accept an entries list for exactly this reason). Anything the
   validator flags as newly introduced gets its implicated lessons frozen
   at their original placement, and the model is re-solved without them -
   a "solve, validate, freeze offenders, retry" loop that is guaranteed to
   terminate (the movable set only ever shrinks) and can never return a
   result with a regression, because the same independent check that
   would catch one is what accepts the result in the first place. With
   students modelled natively, this loop now only has to handle the rare
   remainder, not the majority case."""

import json
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from app.analysis.clash_rules import lesson_entries
from app.analysis.composite_review import load_approved_composites
from app.analysis.load_rules import room_capacity_exceeded
from app.analysis.room_feature_rules import room_feature_mismatch
from app.analysis.whatif import apply_overrides, load_code_lookups, run_clash_findings

# Rule types with an obvious single lesson to move and an obvious search
# space - same restriction suggest_fixes() already applies (docs/
# suggestions.md's Scope section) and for the same reason:
# student_double_booking has no single "the" entry, and consistency/load
# rules aren't slot-scoped at all.
REPAIR_ELIGIBLE_RULES = {"teacher_double_booking", "room_double_booking", "room_capacity_exceeded", "room_feature_mismatch"}

MAX_MOVABLE_ENTRIES = 60  # keeps CP-SAT model size and CEGAR-loop iteration count bounded - a v1 default, not a hard architectural limit
DEFAULT_TIME_BUDGET_SECONDS = 20.0
MOVE_PENALTY = 10_000  # dominates the finer movement_cost tiebreak (0-2) for any realistic movable-set size


@dataclass(frozen=True)
class Slot:
    day_id: int
    period_id: int


@dataclass
class RepairMove:
    entry_id: int
    class_code: str | None
    before: dict
    after: dict


@dataclass
class NotEligible:
    finding_id: int
    rule_id: str
    reason: str


@dataclass
class RepairResult:
    status: str  # "SOLVED" | "PARTIAL" | "NO_MOVABLE_ENTRIES" | "INFEASIBLE"
    moves: list[RepairMove] = field(default_factory=list)
    not_eligible: list[NotEligible] = field(default_factory=list)
    findings_resolved: list[int] = field(default_factory=list)
    findings_unresolved: list[int] = field(default_factory=list)
    frozen_entry_ids: list[int] = field(default_factory=list)
    movable_entry_count: int = 0
    moved_count: int = 0
    solve_time_seconds: float = 0.0


def _all_lesson_slots(conn: sqlite3.Connection) -> list[Slot]:
    rows = conn.execute("SELECT id AS period_id, day_id FROM period WHERE entry_kind = 'LESSON_SLOT'")
    return [Slot(r["day_id"], r["period_id"]) for r in rows]


def _movement_cost(entry: dict, day_id: int, period_id: int) -> int:
    if day_id == entry["day_id"] and period_id == entry["period_id"]:
        return 0
    if day_id == entry["day_id"]:
        return 1
    return 2


def _code_maps(conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
    return {
        "teacher": {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM teacher")},
        "room": {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM room")},
        "class": {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM class_name")},
        "day": {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM day")},
    }


def _period_id_by_day_and_code(conn: sqlite3.Connection) -> dict[tuple, int]:
    return {(r["day_id"], r["code"]): r["id"] for r in conn.execute("SELECT id, day_id, code FROM period")}


def _students_by_class(conn: sqlite3.Connection) -> dict[int, frozenset[int]]:
    by_class: dict[int, set[int]] = defaultdict(set)
    for r in conn.execute("SELECT class_name_id, student_id FROM enrolment"):
        by_class[r["class_name_id"]].add(r["student_id"])
    return {cid: frozenset(sids) for cid, sids in by_class.items()}


def _entries_by_slot_entity(entries: list[dict]) -> dict[tuple, set[int]]:
    """(day_id, period_id, entity_type, entity_id) -> set of entry_ids
    occupying that slot for that teacher/room/class - the same
    slot+entity matching technique frontend/src/lib/findingHighlights.ts
    uses to connect a finding back to the lesson(s) it's about, done here
    in Python so the solver can resolve which timetable_entry rows a
    selected finding actually means."""
    index: dict[tuple, set[int]] = defaultdict(set)
    for e in entries:
        key_base = (e["day_id"], e["period_id"])
        if e["teacher_id"] is not None:
            index[(*key_base, "teacher", e["teacher_id"])].add(e["entry_id"])
        if e["room_id"] is not None:
            index[(*key_base, "room", e["room_id"])].add(e["entry_id"])
        if e["class_name_id"] is not None:
            index[(*key_base, "class", e["class_name_id"])].add(e["entry_id"])
    return index


def _resolve_finding_entries(
    finding_row, codes: dict, period_lookup: dict, slot_index: dict[tuple, set[int]]
) -> set[int] | None:
    """None means the finding's slot couldn't be resolved (predates
    entry-level tracking or references a code that no longer exists) -
    distinct from an empty set, which just means no entries matched."""
    slot_refs = json.loads(finding_row["slot_refs_json"])
    if len(slot_refs) != 1:
        return None
    day_id = codes["day"].get(slot_refs[0]["day_code"])
    if day_id is None:
        return None
    period_id = period_lookup.get((day_id, slot_refs[0]["period_code"]))
    if period_id is None:
        return None

    entity_refs = json.loads(finding_row["entity_refs_json"])
    matched: set[int] = set()
    for ref in entity_refs:
        if ref["type"] not in ("teacher", "room", "class"):
            continue
        entity_id = codes[ref["type"]].get(ref["code"])
        if entity_id is None:
            continue
        matched |= slot_index.get((day_id, period_id, ref["type"], entity_id), set())
    return matched


def _feasible_candidates(
    entry: dict,
    all_slots: list[Slot],
    rooms: dict[int, dict],
    teacher_busy: dict[int, set],
    room_busy: dict[int, set],
    student_busy: dict[int, set],
    students: frozenset[int],
    required_room_type: str | None,
    enrolled: int,
) -> tuple[list[tuple[int, int, int | None]], bool]:
    """Every (day_id, period_id, room_id) this entry could occupy without
    clashing with the FIXED background (everything not in this repair
    run's movable set), found via the exact same busy-check applied to
    every candidate including the entry's own current placement - not a
    special-cased freebie. That matters across CEGAR-loop iterations: once
    a previously-movable neighbour gets frozen back onto this entry's home
    slot, home is no longer actually free, and must not keep pricing at 0
    or the solver will happily "resolve" nothing by sitting in a clash it
    thinks is costless (a real bug caught by test_repair_solver.py before
    this shipped). Returns (candidates, home_is_valid) - home is always
    included, appended as a last resort even when invalid, purely so
    AddExactlyOne always has something to choose from; home_is_valid tells
    the caller whether that inclusion should actually be priced as free."""
    home = (entry["day_id"], entry["period_id"], entry["room_id"])
    seen: set[tuple] = set()
    candidates: list[tuple] = []
    teacher_id = entry["teacher_id"]

    for slot in all_slots:
        if teacher_id is not None and (slot.day_id, slot.period_id) in teacher_busy.get(teacher_id, ()):
            continue
        # A student clash doesn't depend on which room either lesson is
        # in - if any of this class's students already has a fixed lesson
        # at this slot, the whole slot is out, not just a subset of rooms.
        if any((slot.day_id, slot.period_id) in student_busy.get(s, ()) for s in students):
            continue
        for room_id, room in rooms.items():
            if (slot.day_id, slot.period_id) in room_busy.get(room_id, ()):
                continue
            if room["seats"] is not None and enrolled > room["seats"]:
                continue
            if required_room_type is not None and room["room_type"] != required_room_type:
                continue
            cand = (slot.day_id, slot.period_id, room_id)
            if cand in seen:
                continue
            seen.add(cand)
            candidates.append(cand)

    home_is_valid = home in seen
    if home_is_valid:
        candidates.remove(home)
    candidates.insert(0, home)  # keep index 0 == home for the warm-start hint either way
    return candidates, home_is_valid


def _solve_cp_model(
    movable: list[dict],
    all_slots: list[Slot],
    rooms: dict[int, dict],
    teacher_busy: dict[int, set],
    room_busy: dict[int, set],
    student_busy: dict[int, set],
    students_by_class: dict[int, frozenset[int]],
    required_room_type_by_class: dict[int, str],
    enrolled_by_class: dict[int, int],
    time_budget_seconds: float,
) -> dict[int, tuple[int, int, int | None]] | None:
    """One solve attempt over exactly `movable`. Returns entry_id ->
    chosen (day_id, period_id, room_id), or None if no feasible/optimal
    solution was found within the time budget."""
    model = cp_model.CpModel()
    by_teacher_slot: dict[tuple, list] = defaultdict(list)
    by_room_slot: dict[tuple, list] = defaultdict(list)
    by_student_slot: dict[tuple, list] = defaultdict(list)
    per_entry: dict[int, tuple[list[tuple], list]] = {}
    objective_terms = []

    for entry in movable:
        required_type = required_room_type_by_class.get(entry["class_name_id"])
        enrolled = enrolled_by_class.get(entry["class_name_id"], 0)
        students = students_by_class.get(entry["class_name_id"], frozenset())
        candidates, home_is_valid = _feasible_candidates(
            entry, all_slots, rooms, teacher_busy, room_busy, student_busy, students, required_type, enrolled
        )
        bool_vars = []
        for idx, (day_id, period_id, room_id) in enumerate(candidates):
            v = model.NewBoolVar(f"e{entry['entry_id']}_c{idx}")
            bool_vars.append(v)
            if entry["teacher_id"] is not None:
                by_teacher_slot[(day_id, period_id, entry["teacher_id"])].append(v)
            if room_id is not None:
                by_room_slot[(day_id, period_id, room_id)].append(v)
            for student_id in students:
                by_student_slot[(day_id, period_id, student_id)].append(v)
            # idx 0 is always home. Three cost tiers, strictly ordered:
            # 0 (genuinely stay, nothing wrong) < a real move
            # (MOVE_PENALTY + 0..2) < the forced-fallback "stay in a
            # clash we can't avoid" case (2*MOVE_PENALTY) - that last one
            # must never be allowed to look cheap just because
            # _movement_cost is 0 for "same day/period as itself", or the
            # solver "resolves" nothing while believing it found the
            # optimum. See _feasible_candidates.
            if idx == 0 and home_is_valid:
                cost = 0
            elif idx == 0:
                cost = 2 * MOVE_PENALTY
            else:
                cost = MOVE_PENALTY + _movement_cost(entry, day_id, period_id)
            objective_terms.append(cost * v)
        model.AddExactlyOne(bool_vars)
        model.AddHint(bool_vars[0], 1)
        per_entry[entry["entry_id"]] = (candidates, bool_vars)

    for var_list in by_teacher_slot.values():
        if len(var_list) > 1:
            model.AddAtMostOne(var_list)
    for var_list in by_room_slot.values():
        if len(var_list) > 1:
            model.AddAtMostOne(var_list)
    for var_list in by_student_slot.values():
        if len(var_list) > 1:
            model.AddAtMostOne(var_list)

    model.Minimize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_budget_seconds
    solver.parameters.num_search_workers = 1  # deterministic/reproducible - docs/solver.md section 6
    solver.parameters.random_seed = 42
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    chosen = {}
    for entry_id, (candidates, bool_vars) in per_entry.items():
        for idx, v in enumerate(bool_vars):
            if solver.Value(v) == 1:
                chosen[entry_id] = candidates[idx]
                break
    return chosen


def solve_repair(
    conn: sqlite3.Connection,
    finding_ids: list[int],
    time_budget_seconds: float = DEFAULT_TIME_BUDGET_SECONDS,
) -> RepairResult:
    started = time.monotonic()
    codes = _code_maps(conn)
    period_lookup = _period_id_by_day_and_code(conn)

    placeholders = ",".join("?" for _ in finding_ids)
    finding_rows = conn.execute(
        f"SELECT id, rule_id, dedupe_key, slot_refs_json, entity_refs_json, status FROM finding WHERE id IN ({placeholders})",
        tuple(finding_ids),
    ).fetchall() if finding_ids else []
    found_ids = {r["id"] for r in finding_rows}

    before_entries = lesson_entries(conn)
    entries_by_id = {e["entry_id"]: e for e in before_entries}
    slot_index = _entries_by_slot_entity(before_entries)

    not_eligible: list[NotEligible] = []
    eligible_findings = []
    for fid in finding_ids:
        if fid not in found_ids:
            not_eligible.append(NotEligible(fid, "unknown", "No such finding."))
            continue
    for row in finding_rows:
        if row["status"] != "OPEN":
            not_eligible.append(NotEligible(row["id"], row["rule_id"], f"Finding is {row['status']}, not OPEN."))
            continue
        if row["rule_id"] not in REPAIR_ELIGIBLE_RULES:
            not_eligible.append(NotEligible(
                row["id"], row["rule_id"],
                f"{row['rule_id']} has no single lesson to move - see docs/suggestions.md's Scope section.",
            ))
            continue
        eligible_findings.append(row)

    movable_ids: set[int] = set()
    finding_dedupe_key: dict[int, str] = {}
    for row in eligible_findings:
        finding_dedupe_key[row["id"]] = row["dedupe_key"]
        matched = _resolve_finding_entries(row, codes, period_lookup, slot_index)
        if not matched:
            not_eligible.append(NotEligible(row["id"], row["rule_id"], "Could not resolve to any timetable entry."))
            continue
        movable_ids |= matched

    if len(movable_ids) > MAX_MOVABLE_ENTRIES:
        capped = set(sorted(movable_ids)[:MAX_MOVABLE_ENTRIES])
        movable_ids = capped

    if not movable_ids:
        return RepairResult(status="NO_MOVABLE_ENTRIES", not_eligible=not_eligible)

    composites = load_approved_composites(conn)
    before_clash = {f.dedupe_key(): f for f in run_clash_findings(conn, before_entries, composites)}
    before_capacity = {f.dedupe_key(): f for f in room_capacity_exceeded(conn, before_entries)}
    before_feature = {f.dedupe_key(): f for f in room_feature_mismatch(conn, before_entries)}
    before_all = {**before_clash, **before_capacity, **before_feature}

    code_lookups = load_code_lookups(conn)
    rooms = {r["id"]: dict(r) for r in conn.execute("SELECT id, code, seats, room_type FROM room")}
    enrolled_by_class = {
        r["class_name_id"]: r["n"]
        for r in conn.execute("SELECT class_name_id, COUNT(DISTINCT student_id) AS n FROM enrolment GROUP BY class_name_id")
    }
    required_room_type_by_class = {
        r["class_name_id"]: r["room_type"]
        for r in conn.execute("SELECT class_name_id, room_type FROM class_room_type_constraint WHERE review_status = 'APPROVED'")
    }
    students_by_class = _students_by_class(conn)
    all_slots = _all_lesson_slots(conn)

    current_movable: dict[int, dict] = {eid: entries_by_id[eid] for eid in movable_ids}
    frozen_ids: list[int] = []
    accepted_chosen: dict[int, tuple] | None = None
    # Defaults to "nothing changed" - if no clean solution is ever
    # accepted below, every original finding must still read as
    # unresolved, not as resolved-by-omission from an empty dict.
    accepted_after_all: dict = before_all

    # Bounded by construction, not by a fixed iteration count: every branch
    # below either accepts a solution (break) or removes at least one entry
    # from current_movable, so this can run at most len(movable_ids) times
    # regardless of which branch fires.
    while current_movable:
        fixed_entries = [e for e in before_entries if e["entry_id"] not in current_movable]
        teacher_busy: dict[int, set] = defaultdict(set)
        room_busy: dict[int, set] = defaultdict(set)
        student_busy: dict[int, set] = defaultdict(set)
        for e in fixed_entries:
            if e["teacher_id"] is not None:
                teacher_busy[e["teacher_id"]].add((e["day_id"], e["period_id"]))
            if e["room_id"] is not None:
                room_busy[e["room_id"]].add((e["day_id"], e["period_id"]))
            for student_id in students_by_class.get(e["class_name_id"], ()):
                student_busy[student_id].add((e["day_id"], e["period_id"]))

        remaining_budget = max(1.0, time_budget_seconds - (time.monotonic() - started))
        chosen = _solve_cp_model(
            list(current_movable.values()), all_slots, rooms, teacher_busy, room_busy, student_busy,
            students_by_class, required_room_type_by_class, enrolled_by_class, remaining_budget,
        )
        if chosen is None:
            # No feasible joint assignment exists for the whole current
            # batch - real dense data showed this happening even when
            # large subsets of the same batch solve fine (see docs/
            # mass-repair.md). Shrink by one (deterministically, so re-runs
            # are reproducible) and retry, rather than giving up on
            # everyone still in the batch.
            worst_id = min(current_movable)
            frozen_ids.append(worst_id)
            current_movable.pop(worst_id)
            continue

        overrides = {}
        for entry_id, (day_id, period_id, room_id) in chosen.items():
            entry = entries_by_id[entry_id]
            if (day_id, period_id, room_id) == (entry["day_id"], entry["period_id"], entry["room_id"]):
                continue
            overrides[entry_id] = {"after_day_id": day_id, "after_period_id": period_id, "after_room_id": room_id}

        after_entries = apply_overrides(before_entries, overrides, code_lookups)
        after_clash = {f.dedupe_key(): f for f in run_clash_findings(conn, after_entries, composites)}
        after_capacity = {f.dedupe_key(): f for f in room_capacity_exceeded(conn, after_entries)}
        after_feature = {f.dedupe_key(): f for f in room_feature_mismatch(conn, after_entries)}
        after_all = {**after_clash, **after_capacity, **after_feature}

        introduced = [f for k, f in after_all.items() if k not in before_all]
        if not introduced:
            accepted_chosen = chosen
            accepted_after_all = after_all
            break

        implicated: set[int] = set()
        after_by_entry = {eid: chosen[eid] for eid in current_movable}
        after_index: dict[tuple, set[int]] = defaultdict(set)
        for eid, (day_id, period_id, room_id) in after_by_entry.items():
            entry = entries_by_id[eid]
            after_index[(day_id, period_id, "teacher", entry["teacher_id"])].add(eid)
            if room_id is not None:
                after_index[(day_id, period_id, "room", room_id)].add(eid)
            after_index[(day_id, period_id, "class", entry["class_name_id"])].add(eid)

        for f in introduced:
            for ref in f.entity_refs:
                if ref.type not in ("teacher", "room", "class"):
                    continue
                entity_id = codes[ref.type].get(ref.code)
                if entity_id is None:
                    continue
                for slot_ref in f.slot_refs:
                    day_id = codes["day"].get(slot_ref.day_code)
                    period_id = period_lookup.get((day_id, slot_ref.period_code)) if day_id else None
                    if period_id is None:
                        continue
                    implicated |= after_index.get((day_id, period_id, ref.type, entity_id), set())

        if not implicated:
            # Couldn't pin down which movable entry caused it - safest
            # option is to give up on the whole remaining batch rather
            # than guess, since we can't safely narrow the search further.
            frozen_ids.extend(current_movable.keys())
            current_movable = {}
            break

        for eid in implicated:
            frozen_ids.append(eid)
            current_movable.pop(eid, None)

    moves = []
    if accepted_chosen:
        for entry_id, (day_id, period_id, room_id) in accepted_chosen.items():
            entry = entries_by_id[entry_id]
            if (day_id, period_id, room_id) == (entry["day_id"], entry["period_id"], entry["room_id"]):
                continue
            moves.append(RepairMove(
                entry_id=entry_id,
                class_code=entry["class_code"],
                before={"day_code": entry["day_code"], "period_code": entry["period_code"], "room_code": entry["room_code"]},
                after={
                    "day_code": code_lookups["day"][day_id],
                    "period_code": code_lookups["period"][period_id],
                    "room_code": code_lookups["room"].get(room_id),
                },
            ))

    findings_resolved = []
    findings_unresolved = []
    for row in eligible_findings:
        key = finding_dedupe_key[row["id"]]
        if key not in accepted_after_all:
            findings_resolved.append(row["id"])
        else:
            findings_unresolved.append(row["id"])

    # Status reflects the outcome for the findings actually asked about,
    # not the solver's internal path to get there - a finding that took a
    # rejected attempt and a CEGAR retry to resolve is still "resolved",
    # same as one solved on the first try. frozen_entry_ids is reported
    # separately for transparency, it just isn't what the headline means.
    if findings_resolved and not findings_unresolved:
        status = "SOLVED"
    elif findings_resolved:
        status = "PARTIAL"
    else:
        status = "INFEASIBLE"

    return RepairResult(
        status=status,
        moves=moves,
        not_eligible=not_eligible,
        findings_resolved=findings_resolved,
        findings_unresolved=findings_unresolved,
        frozen_entry_ids=frozen_ids,
        movable_entry_count=len(movable_ids),
        moved_count=len(moves),
        solve_time_seconds=time.monotonic() - started,
    )
