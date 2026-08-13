# Mass Repair (Solver Mode A)

Implements `docs/solver.md`'s Mode A: given a set of open findings, find a
minimal-movement set of moves that resolves as many as possible without
introducing anything new - using OR-Tools CP-SAT, a real constraint
solver, not a language model. See `docs/solver.md` section 1 for why an
LLM cannot do this job.

## What it is

`POST /api/solver/repair` takes a list of finding ids (or, by default,
every open finding of a repair-eligible type), runs the solver, and - if
it found any moves - lands them in a normal change set: the same
review → validate → approve → export pipeline every other edit in this
app goes through. Nothing auto-applies. A "Repair with solver" button on
the Findings page runs it against every open eligible finding and jumps
straight to the resulting change set.

## Scope: which findings the solver will touch

`REPAIR_ELIGIBLE_RULES = {teacher_double_booking, room_double_booking,
room_capacity_exceeded, room_feature_mismatch}` - the same "does this
finding have one obvious lesson to move" restriction `suggest_fixes()`
already applies (`docs/suggestions.md`'s Scope section), for the same
reason: `class_room_instability`/`class_teacher_inconsistency` aren't
slot-scoped at all, and `student_double_booking` involves two different
classes with no single "the" entry to reason about.

An unselected or ineligible finding is reported back explicitly
(`not_eligible: [{finding_id, rule_id, reason}]`), never silently
dropped - matching every other "explicit, not silent" decision in this
codebase (`suggest_fixes()`, `docs/rules.md`'s composite suppression).

## The model

For each selected finding, its slot + entity refs resolve to the actual
`timetable_entry` row(s) it's about (the same slot+entity matching
technique `frontend/src/lib/findingHighlights.ts` uses on the frontend,
implemented in Python as `_resolve_finding_entries`). The union of all
resolved entries is the **movable set**; everything else is the **fixed
background**.

For each movable entry, every `(day, period, room)` it could occupy
without clashing with the fixed background is precomputed
(`_feasible_candidates`) - filtered by teacher/room/student availability,
room capacity, and any *approved* `class_room_type_constraint`
(`docs/room-constraints.md`). Each candidate becomes a boolean variable;
`AddExactlyOne` per entry, `AddAtMostOne` per (slot, teacher) / (slot,
room) / (slot, student) group across the whole movable set. The
objective minimises, in strict priority order: **number of lessons
moved**, then a `movement_cost` tiebreak (0 = room-only, 1 = same day, 2
= different day) - same disruption ordering `suggest_fixes()` already
uses. Warm-started at every lesson's current placement, single worker,
fixed seed, so a re-run against unchanged data reproduces identically
(`docs/solver.md` section 6's reproducibility requirement).

## What real data taught us: students have to be a real constraint, not an afterthought

The first version deliberately left `student_double_booking` unmodelled
in CP-SAT - the scope restriction above says a *finding* about student
clashes has no single entry to move, which is true, but that's a
different question from whether the *solver* needs to know students
exist when moving something else. It doesn't have "the" entry to fix,
but any OTHER move it makes can still create one.

Against a small synthetic fixture this looked fine: a rejected move got
caught by re-validation, the offending lesson got frozen, and a retry
found a clean alternative. Against the real ~2,200-entry dataset it
did not scale - a first attempt at repairing the 20 open double-booking
findings (39 movable entries) produced **257 newly-introduced
`student_double_booking` findings from a single 23-move solve**. Real
classes overlap on students constantly; almost any teacher/room-legal
move landed on some student's other class. The "reject and freeze one
lesson, retry" loop, designed for an occasional edge case, had to freeze
almost the entire batch one lesson at a time to clear a wall of
regressions - technically still correct (nothing regressed), but useless
(nothing got fixed either).

Fix: student clashes are now a **native hard constraint**, modelled
exactly like teacher/room ones - `AddAtMostOne` per `(slot, student)`
group, with per-student busy-slots computed from the fixed background and
folded into candidate generation up front. The re-validation loop is
still there (composite-suppression nuances and anything not natively
modelled still get an independent check via the exact same
`app/analysis/whatif.py` validator `suggest_fixes()` and change-set
validation use), but it's now a safety net for the rare remainder, not
the mechanism carrying the majority case.

## What real data taught us, part two: the *joint* problem can be infeasible even when large parts of it aren't

With students modelled, the very first full-batch solve for those same
20 findings came back CP-SAT-infeasible for the *whole* 39-entry group -
not a slow search, an actual proof that no assignment satisfies every
constraint simultaneously. The original code treated "the whole batch is
infeasible" as "give up on everyone in it," which is far too blunt: nine
teachers and eleven rooms fighting over a handful of genuinely free slots
can make the full joint problem unsatisfiable while a smaller subset of
it solves cleanly.

Fix: on a fully-infeasible batch, shrink by exactly one entry
(deterministically - lowest `entry_id` first, so re-runs are
reproducible) and retry, rather than clearing the whole movable set. The
loop is bounded by construction rather than a fixed iteration count -
every branch either accepts a solution or removes at least one entry, so
it terminates in at most `len(movable_entries)` iterations regardless of
which branch fires.

## What this actually produces against the real data

Requesting a repair for the 20 open teacher/room double-booking findings:
**resolved 6 of 20 with 4 real moves, in ~4.4 seconds.** Requesting the
full default scope (49 open eligible findings, capped at
`MAX_MOVABLE_ENTRIES = 60`): **resolved 4 of 49 with 3 moves, in ~8
seconds.** Both are honest `PARTIAL` results, not failures - Sophia
College's real cycle is dense enough that a meaningful fraction of its
clashes genuinely cannot be resolved by moving *only* the directly
conflicting lessons without touching anything else, which is exactly the
boundary `docs/solver.md`'s "what this does not change" section already
drew: the solver proposes what it can find within scope and budget, a
human reviews it, and an unresolved remainder is reported, never hidden.

Verified end-to-end through the real UI: ran the default-scope repair,
confirmed the resulting change set's proposed changes and validation
result matched exactly what the standalone solver call produced, then
rejected the change set afterward so no test-authored artifact was left
in the school's real data - the same live-verification-then-cleanup
discipline applied throughout this project.

## What this does not change

Everything in `docs/solver.md` section 11 still holds: nothing
auto-applies, the LLM never decides, teacher reassignment stays off the
table, student identity is never authored. Two more, specific to this
feature:

- **A proposed change here is linked to every finding the whole run
  resolved, not just the one(s) its own move addresses.** Unlike
  `suggest_fixes()`, which produces one candidate per finding with a
  precise link, a repair run can resolve several findings through moves
  that interact (a chain), so there's no clean per-move attribution to
  preserve. The link is accurate at the change-set level - "this set of
  moves, taken together, resolved these findings" - just coarser than a
  single suggestion's link.
- **Approved composites are never offered as a shared slot for two
  movable entries**, even where the composite would genuinely allow it -
  the model's `AtMostOne` constraints don't currently carve out an
  exception for approved composite pairs. Conservative by construction
  (it can only make the solver *less* willing to co-locate lessons that
  are in fact fine together, never more willing to create a real clash),
  documented as a known v1 limitation rather than fixed, since it's
  strictly safer than the alternative.

## Not built yet

Per `docs/solver.md`'s phasing: no `solver_run` persistence/comparison
table (a run either becomes a change set or is gone - no "try again with
different weights and compare" UI yet), no Mode B (regional rebuild) or
Mode C (construction), no LLM explanation of a run or of infeasibility
(H3), no doubles/triples constraint (the other deferred half of Phase
G1), no per-user configurable weights (`MOVE_PENALTY` and the
movement-cost tiers are the same documented-default-heuristic status as
`suggest_fixes()`'s own weighting, not a confirmed school policy).
