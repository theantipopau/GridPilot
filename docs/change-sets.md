# Change Sets

Implements PROJECT_ROADMAP.md's Milestone 3: proposed timetable edits,
represented entirely separately from the imported data. See
`backend/app/changes/service.py`.

## Non-negotiable: source stays immutable

Approving a change set **never writes to `timetable_entry`**. The
`change_set`/`proposed_change` rows *are* the durable record of an
approved edit - a future export step (not built yet) would read an
approved change set and produce a new re-importable file, the same way
the rest of this tool never writes back into `Timetabler Export/`.
`test_approve_succeeds_after_valid_and_never_mutates_source` in
`backend/tests/test_change_sets.py` asserts this directly: the source row
is byte-identical before and after approval.

## Model

- **`change_set`**: a named batch of edits. Two independent status
  fields, matching the roadmap's explicit "validation state" and
  "approval state":
  - `validation_status`: `NOT_VALIDATED` → `VALID` / `INVALID`, set by
    re-running validation. Any edit to the change set (adding or removing
    a proposed change) resets this to `NOT_VALIDATED` - a stale
    validation result is never trusted.
  - `approval_status`: `DRAFT` → `APPROVED` / `REJECTED`. Only settable
    once (approve/reject on a non-`DRAFT` set is rejected), and
    **approval is blocked unless `validation_status = VALID`** - there is
    no path to approving something that hasn't been proven not to make
    things worse.
- **`proposed_change`**: one edit to one `timetable_entry` - before/after
  day, period, room, and teacher. Fields not being changed default to
  their current value (a "move room only" change leaves day/period/
  teacher untouched).
- **`proposed_change_finding`**: which findings this change claims to
  address - the roadmap's "originating finding IDs." Only reliable because
  findings are now upserted by a stable `dedupe_key` rather than wiped and
  recreated every rules-engine run (see `docs/rules.md` and
  `app/analysis/run.py`) - a finding's database id now survives as long as
  the underlying issue keeps reproducing, so a reference to it stays valid.

## Validation: what-if, never a real write

`validate_change_set()`:

1. Builds the current `LESSON` timetable entries (`lesson_entries()`,
   `app/analysis/clash_rules.py`).
2. Applies every proposed change's after-values to an **in-memory copy**
   of that list - the real `timetable_entry` table is never touched.
3. Re-runs the same three clash rules (teacher/room/student
   double-booking) against both the original and the modified list.
4. Diffs the two result sets by each finding's `dedupe_key`:
   - present before, gone after → **resolved**
   - absent before, present after → **introduced** (a regression)
5. Checks whether every finding referenced via `proposed_change_finding`
   actually cleared (its `dedupe_key` no longer appears in the "after"
   set) - a change set that claims to fix a finding but doesn't is
   invalid, not just "incomplete."

**`valid = (no introduced findings) AND (no unresolved originating findings)`.**

Room capacity isn't included in what-if validation yet - only the three
clash rules. A capacity-aware what-if check is a natural follow-up once
`load_rules.py`'s functions are refactored to accept an entries list the
same way the clash rules already do.

## What this looked like against the real data

Tested by proposing to move one half of a real composite-candidate clash
(`11SIP1`/`12SIP1`, room `RIE02`) to a slot that was free for both the
teacher and the room. The validator still correctly rejected it - moving
a small elective class to *any* mutually-free slot for teacher+room still
collided with 15 students' other classes, because the class's current
slot wasn't arbitrary: it was placed there specifically because that's
when those students were free. This is exactly the scenario Milestone 4
("constraint-based suggestions before any AI") exists for - a human
guessing a new slot is unlikely to satisfy every constraint at once,
which is why nothing gets approved without passing this check first.

## API

```
GET    /api/change-sets
GET    /api/change-sets/{id}
POST   /api/change-sets                                  {name, description, created_by}
POST   /api/change-sets/{id}/changes                     {timetable_entry_id, after_day_code?, after_period_code?, after_room_code?, after_teacher_code?, reason?, finding_ids?}
DELETE /api/change-sets/{id}/changes/{change_id}
POST   /api/change-sets/{id}/validate
POST   /api/change-sets/{id}/approve                     {reviewed_by}
POST   /api/change-sets/{id}/reject                      {reviewed_by}
GET    /api/timetable-entries?day_code=&period_code=&teacher_code=&room_code=&class_code=
```

The add-change endpoint takes **codes**, not internal database ids
(`after_day_code`/`after_period_code` together, since a period code like
`P2` repeats on every day) - matching every other public endpoint in this
API, and resolved to internal ids server-side.

## UI

A **Change Sets** tab: create a change set, search for the lesson to
move (by day/period/teacher/room/class code), pick its new slot, validate,
and approve/reject. A **"Propose a fix"** button on each finding in the
**Findings** tab jumps to Change Sets with a create form pre-filled from
that finding's entity/slot codes.

## A real bug this surfaced

Building this exposed a genuine issue in the API layer, unrelated to
change sets themselves: FastAPI runs a synchronous generator dependency's
setup and its `finally` teardown as separate thread-pool work items with
no guaranteed thread affinity between them, which trips SQLite's
same-thread check on `conn.close()`. Fixed by passing
`check_same_thread=False` in `app/api/deps.py` - safe here because each
request still gets its own connection, opened and closed within that
single request's lifecycle, never shared across concurrent requests.
