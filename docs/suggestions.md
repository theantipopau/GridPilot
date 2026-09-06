# Constraint-Based Suggestions

Implements PROJECT_ROADMAP.md's Milestone 4:

> Before Ollama, generate candidate moves algorithmically:
> 1. Find alternate rooms or periods satisfying hard constraints.
> 2. Reject candidates that create teacher, room or student clashes.
> 3. Reject room-capacity and room-feature failures.
> 4. Score remaining options using soft constraints such as movement,
>    timetable spread, room utilization and staff load.
> 5. Give the ranked candidates and evidence to the local AI only for
>    explanation.
>
> This prevents the language model from inventing timetable changes.

See `backend/app/analysis/suggestions.py`. Nothing in this module calls a
model - it's pure search + validation, same as the rest of the rules
engine. The (not yet built) AI advisor's job, per the roadmap, is to
explain *these* candidates in plain language - never to invent its own.

## Scope

**Supported**: `teacher_double_booking`, `room_double_booking` - the two
rule types where there's an obvious "thing to move" (one of the
conflicting lessons) and an obvious search space (alternate rooms/times) -
`class_room_instability` (added 2026-08-13), where the "thing to move"
is instead every lesson of the class sitting in a room other than the one
it already mostly uses, and the search space is exactly one room: the
class's own majority room, at each minority lesson's existing slot (see
"Room consolidation" below); and, since 2026-08-17,
`class_teacher_inconsistency`, its teacher-facing sibling - see "Teacher
consolidation" below.

**Not supported, and says so rather than silently returning nothing
useful**: every other rule type, most notably `student_double_booking`
(there's no single lesson whose room/time you'd move - the fix usually
means restructuring an option line, out of scope here) and the
capacity/utilisation rules (not really "move this lesson" problems).
`GET /api/findings/{id}/suggestions` on an unsupported finding returns
`supported: false` with an explanatory `note`, never an empty result that
could be mistaken for "no fix exists."

**Never suggested without confirmed data behind it**: moving a lesson to
a *different teacher* used to be entirely out of scope - there was no
authoritative subject-qualification data, and guessing would have been
exactly the "invented suggestion" the roadmap warns against.
`teacher_capability` (`docs/roadmap-v2.md` 2.2) removed that blocker, but
the same discipline still applies at the per-candidate level: a
teacher-consolidation candidate is only ever offered when
`CapabilityService.resolve()` (`app/analysis/capability.py`) confirms the
target teacher isn't `NOT_ELIGIBLE` for the class's subject - the same
check `teacher_not_qualified_for_class` uses to raise a finding, applied
here as a hard constraint *before* a move is proposed. A class with no
`teacher_capability` data at all for its majority teacher still gets zero
candidates, exactly like before - "no suggestion" remains the answer
whenever there's nothing to confirm the move against.

## How a candidate is generated and validated

For each of up to the first 3 conflicting entries in a finding
(`MAX_ENTRIES_CONSIDERED` - a finding like a 6-class composite-candidate
clash won't generate 6x the search space):

- **Type A - same room, different slot**: every `LESSON_SLOT` period in
  the cycle where both the entry's teacher and room are free (a fast
  set-membership pre-filter before anything expensive runs) - "free" now
  includes a teacher's standing `teacher_commitment` rows, since
  2026-09-07 (`docs/roadmap-v3.md` 1.1), the same shared `teacher_
  commitment_busy()` the repair solver uses, so a slot with nothing in
  `timetable_entry` can still be excluded.
- **Type B - same slot, different room**: every other room free at that
  exact period.

Every slot/room that survives the cheap pre-filter is then genuinely
validated, reusing the *exact same* machinery as change-set validation
(`app/analysis/whatif.py`, factored out so there's one implementation,
not two that could drift):

1. **Room capacity** (a hard constraint): distinct enrolled students
   across the target room/slot against `room.seats`, skipped for rooms
   with no confirmed capacity. Room-feature matching isn't included -
   see `docs/rules.md`'s note on why `room_feature_mismatch` isn't
   implemented (no controlled room-feature data yet).
2. **No new clash** (a hard constraint): the candidate is applied to an
   in-memory copy of the timetable and every clash rule re-run; any
   finding present after that wasn't present before is a rejection.
   `test_no_candidate_ever_introduces_a_regression` in
   `backend/tests/test_suggestions.py` independently re-verifies this for
   every candidate the engine returns, not just trusts the internal check.

Candidates that survive both checks are scored by **movement cost** (a
documented default heuristic, not a confirmed school weighting - see the
docstring in `suggestions.py`): `0` = room-only change, `1` = same-day
different period, `2` = different day. Room-only fixes rank first as the
least disruptive; ties break on `resolves_finding_count`, then on
**room familiarity** (below) - a candidate that happens to put the class
in a room it already uses elsewhere ranks ahead of an equally-cheap move
to a room it's never been in.

## Room consolidation for class_room_instability (2026-08-13)

Real feedback after the user hit the finding's "Suggestion generation
isn't implemented ... yet" note during their own testing and asked what's
next. Unlike the clash rules, a `class_room_instability` finding has no
"conflicting entry" to move - every one of the class's lessons is
individually valid, the issue is only that they don't agree on a room.
So the search here is deliberately narrower than Type A/B above:

1. Find the class's **majority room** - whichever room the most of its
   lessons already use (ties break on room code, so re-runs are stable).
2. For each of the class's lessons in a different room (capped at
   `MAX_ENTRIES_CONSIDERED`, same as the clash rules), offer exactly one
   candidate: that lesson, moved into the majority room, **at its
   existing slot**. No alternate times are searched - the point is
   consistency, not finding it a new time too, and combining both would
   turn one clear suggestion into a much larger, harder-to-explain
   search.
3. The candidate still goes through the same hard-constraint checks as
   every other candidate (room capacity, no new clash) via `_try_
   candidate()` - if the majority room is already taken by another class
   at that particular slot, no candidate is offered for that lesson at
   all, rather than silently proposing an invalid move.

`resolves_finding_count` is always `0` here (there's no clash finding to
resolve), so ranking falls to `class_room_familiarity` - and because the
target room is by definition the class's majority room, familiarity is
always high, which is exactly the point.

Verified against the real finding that prompted this ("Class 12RAE1 used
3 different rooms across the cycle" - `ANG1`, `LEO2`, `LEO4`). 12RAE1's
8 lessons run in `LEO2` six times, so that's the majority room; of its
two minority lessons, only the `LEO4` one got a candidate (move to `LEO2`
Fri B P2, capacity confirmed 20/30 seats, familiarity 6/7) - the `ANG1`
lesson (Fri A P4) was correctly skipped because a different class already
holds `LEO2` at that exact slot, which is the "no valid fix, so don't
show one" case rather than a bug.

## Teacher consolidation for class_teacher_inconsistency (2026-08-17)

`class_teacher_inconsistency`'s sibling treatment to room consolidation
above, unblocked by `teacher_capability` (`docs/roadmap-v2.md` 2.2, item
9) - see "Never suggested without confirmed data behind it" above for why
this was out of scope until that table existed. The search mirrors room
consolidation almost exactly, with one addition:

1. Find the class's **majority teacher** - whichever teacher already
   covers the most of its lessons (ties break on teacher code).
2. Resolve the class's subject (and faculty) once, then call
   `CapabilityService.resolve()` for the majority teacher against that
   subject. If the result is `NOT_ELIGIBLE`, the search stops there - no
   candidates at all, for any of the class's minority-teacher lessons.
   This check runs *before* the per-lesson search, not per-candidate,
   since the answer is the same teacher for every lesson being
   consolidated.
3. For each of the class's lessons taught by a different teacher (capped
   at `MAX_ENTRIES_CONSIDERED`), offer exactly one candidate: that
   lesson, reassigned to the majority teacher, **at its existing slot and
   room**. Like room consolidation, no alternate times are searched.
4. The candidate still goes through the same no-new-clash check as every
   other candidate (via `run_clash_findings`) - if the majority teacher
   is already teaching something else at that particular slot, no
   candidate is offered for that lesson, the same "no valid fix, so don't
   show one" behaviour as the room-busy case above.

Unlike room consolidation, room capacity is irrelevant here (the room
never changes), so `why.room_capacity` is always `{confirmed: false}` for
these candidates and `why.capability_status` carries the real signal
instead - `"ELIGIBLE"` or `"REVIEW_REQUIRED"` (both allowed; the same
distinction `teacher_not_qualified_for_class` draws). Ranking falls to
`class_teacher_familiarity`, the teacher-facing counterpart to
`class_room_familiarity` below.

A class whose majority teacher has no `teacher_capability` row at all -
the common case for a school that hasn't reviewed the bootstrap queue yet
- still gets zero candidates, exactly like before this shipped. This is
deliberate, not a gap: `resolve()`'s no-match fallback is `NOT_ELIGIBLE`
(detect-never-assert, `app/analysis/capability.py`), so an unreviewed
school gets no algorithmic teacher-reassignment suggestions until it
reviews its capability queue - the same trade `teacher_not_qualified_for_
class` makes for findings.

## Why it works, and what else it affects (2026-08-12)

Real feedback after shipping the first version: *"propose fixes needs to
be more detailed."* Each candidate now carries two extra fields, both
computed from data the engine already touches - no new queries beyond
what capacity-checking and clash-checking were already doing:

- **`why`**: `no_new_clash` (always `true` for a returned candidate - the
  hard constraint check above already guarantees it, this just makes it
  visible), `room_capacity` (`{confirmed: false}` if the target room
  has no confirmed seat count, or `{confirmed: true, seats, enrolled}` if
  it does - the same numbers the capacity check itself used), and (since
  2026-08-17) `capability_status` - `null` for room/slot candidates (the
  teacher never changes), or the resolved `CapabilityStatus` (`"ELIGIBLE"`
  or `"REVIEW_REQUIRED"` - never `"NOT_ELIGIBLE"`, since that's a hard
  constraint the candidate wouldn't have survived) for a teacher-
  consolidation candidate.
- **`class_room_familiarity`**: `{same_room_elsewhere_count,
  total_other_lessons}` - how many of the class's *other* lessons already
  run in the candidate's target room. Directly reuses the same signal
  `class_room_instability` (`docs/rules.md`) computes, surfaced here as a
  forward-looking "does this move make the class more or less
  consistent" rather than only a backward-looking finding. `null` when
  the candidate has no room, or is a teacher-consolidation candidate
  (room never changes there - see `class_teacher_familiarity` instead).
- **`class_teacher_familiarity`** (since 2026-08-17): the teacher-facing
  counterpart - `{same_teacher_elsewhere_count, total_other_lessons}`,
  `null` for every candidate type except teacher consolidation.

`MAX_CANDIDATES_RETURNED` raised from 8 to 15 - the extra candidates were
already being computed and discarded, so returning more doesn't add
meaningful cost.

## Performance

On-demand only, never precomputed for all findings (250+ findings x a
couple of seconds each would be far too slow to run eagerly on every
rules-engine pass). A single finding's suggestions take roughly 2-4
seconds against the real ~2,200-entry dataset - acceptable for a button
click, not for a page load. `GET /api/findings/{id}/suggestions`.

## What this looked like against the real data

Requested suggestions for finding "Room RIE02 double-booked at Mon A P2"
(one half of the `11SIP1`/`12SIP1` composite candidate, unreviewed at the
time). The engine correctly proposed several room-only fixes (`AC1`,
`ANG8`, `BON08`, ...) ranked first - much cheaper than the earlier manual
test in `docs/change-sets.md`, which tried moving the same lesson to a
different *time* and got rejected for cascading student clashes. This is
exactly the roadmap's point: search the full space and let hard
constraints do the filtering, rather than a human guessing one option and
finding out it fails after the fact.

## UI

Two entry points, sharing one presentation component
(`SuggestionCandidateCard.tsx`) so they can't drift apart:

- Each finding in the **Findings** tab has a **"Suggest fixes"** button
  that fetches and displays ranked candidates inline, each with a **"Use
  this"** button that creates a *new* change set, adds the proposed
  change (with `finding_ids` linking back to the originating finding),
  and jumps straight to Change Sets for review/validate/approve.
- Clicking a lesson on the **Timetable** grid opens the inspector panel
  with a **"Suggested fixes"** tab alongside "Move manually" (added
  2026-08-12, real feedback: *"maybe extra tabs"*). This finds every
  *open* finding relevant to the clicked lesson: for
  `teacher_double_booking`/`room_double_booking`, matched by slot +
  teacher/room code; for `class_room_instability` (added 2026-08-13) and
  `class_teacher_inconsistency` (added 2026-08-17), matched by class code
  instead, since neither finding has `slot_refs` - they're about the
  whole class, not one lesson. Either way it fetches suggestions for each
  match and keeps only the candidates that would move *this specific*
  lesson - deduplicated by target slot *and* teacher, since a teacher-
  consolidation candidate leaves the slot untouched.
  "Use this" here reuses the grid's own in-progress change set
  (`onPropose`, the same path "Move manually" uses) rather than creating
  a separate one, since the panel is already scoped to one change set.
  Lazy-loaded on tab click, not prefetched on every lesson click -
  `suggest_fixes()` is a real computation (~2-4s against the real
  dataset), not something to run on every single grid click.

Either way, the suggestion still has to pass through the same
human-approval gate as a manually proposed change; nothing here applies
itself.
