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
conflicting lessons) and an obvious search space (alternate rooms/times).

**Not supported, and says so rather than silently returning nothing
useful**: every other rule type, most notably `student_double_booking`
(there's no single lesson whose room/time you'd move - the fix usually
means restructuring an option line, out of scope here) and the
capacity/utilisation rules (not really "move this lesson" problems).
`GET /api/findings/{id}/suggestions` on an unsupported finding returns
`supported: false` with an explanatory `note`, never an empty result that
could be mistaken for "no fix exists."

**Never suggested**: moving a lesson to a *different teacher*. There's no
authoritative subject-qualification data yet (`docs/staff-capability-
model.md` covers what that would take) - guessing would be exactly the
"invented suggestion" the roadmap warns against.

## How a candidate is generated and validated

For each of up to the first 3 conflicting entries in a finding
(`MAX_ENTRIES_CONSIDERED` - a finding like a 6-class composite-candidate
clash won't generate 6x the search space):

- **Type A - same room, different slot**: every `LESSON_SLOT` period in
  the cycle where both the entry's teacher and room are free (a fast
  set-membership pre-filter before anything expensive runs).
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
least disruptive.

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

Each finding in the **Findings** tab has a **"Suggest fixes"** button
that fetches and displays ranked candidates inline, each with a **"Use
this"** button that creates a change set, adds the proposed change (with
`finding_ids` linking back to the originating finding), and jumps
straight to Change Sets for review/validate/approve - the suggestion
still has to pass through the same human-approval gate as a manually
proposed change; nothing here applies itself.
