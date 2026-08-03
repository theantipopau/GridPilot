# Staffing Priority Policy

Captures the addendum's allocation-priority and scarcity model (Sections
6-8) as a policy specification. **This entire document describes solver
behaviour and is not implemented yet** - it depends on `TeachingRequirement`
and `teacher_capability` existing first (see `docs/staff-capability-model.md`)
and, beyond that, on an actual constraint solver, which nothing in this
project uses today. Written now so the schema fields it needs
(`allocation_priority`, `lock_status` on `teaching_requirement`) are in
place from the start rather than retrofitted later - not as a signal that
solver work is starting next.

## Priority bands

```
CRITICAL, HIGH, STANDARD, FLEXIBLE
```

Stored per `teaching_requirement` as `allocation_priority`. The addendum's
suggested default ordering (locked/required first, then scarce senior
specialists, then other senior subjects, then room-constrained subjects,
then junior subjects by scarcity) is a **school-configurable profile**,
not hardcoded - matches the addendum's Section 6 instruction that this
must be editable and visible before solving, not buried in procedural
code.

## Staffing health

Per requirement, not just a raw eligible-teacher count (addendum Section
7 is explicit that eligible ≠ available ≠ has capacity):

```
eligible_teacher_count
available_teacher_count       (eligible AND not already fully loaded)
preferred_teacher_count
remaining_capacity_minutes
risk: BLOCKING | HIGH | MEDIUM | HEALTHY
```

`BLOCKING` (no eligible+available teacher) should be surfaced as a
findings-engine record the moment `teacher_capability` data exists and a
requirement resolves to zero valid candidates - this doesn't need a
solver, it's a straightforward query, and is one of the first useful
things to build once the capability tables land.

## Scarcity and opportunity cost

Only meaningful once a solver exists to act on it - documented here for
when that's built, not before:

```
opportunity_cost(teacher, requirement) = higher when:
  - teacher has few alternative eligible teachers for their scarce subject(s)
  - requirement is one many other teachers could also cover
```

Objective weights (`PREFERENCE_PENALTY` per `AllocationPreference` value
in the addendum) must live in a **versioned solver profile**, inspectable
by advanced users, never hardcoded constants buried in solver code -
directly per addendum Section 8's explicit instruction.

## Staged solving (addendum Section 6)

```
Stage 1: Lock approved staffing decisions
Stage 2: Protect scarce senior/specialist capability
Stage 3: Allocate remaining senior requirements
Stage 4: Allocate junior and flexible requirements
Stage 5: Improve load, spread, room stability and movement
```

With a whole-model feasibility check after every stage - never let an
early stage's allocation make a later stage infeasible. This is a UX/
explainability staging, not a hard requirement of the underlying CP-SAT
model itself (which the addendum correctly notes doesn't need to "go in
order" to protect scarce capacity - hard locks and penalty weights do
that work).

## When this becomes real work

Not until:
1. `teacher_capability` and `teaching_requirement` exist and have real
   data in them (bootstrapped from the current timetable, per
   `docs/staff-capability-model.md`).
2. The non-solver staffing views (Section 9-10 of the addendum - "who's
   eligible for this class," the staffing matrix) are built and useful
   on their own.
3. You confirm you want GridPilot to actually build/re-solve timetables,
   not just analyse and let a human edit the current one - this is a
   materially larger scope than anything built so far, closer to
   replacing Timetabling Solutions' core function than complementing it.
