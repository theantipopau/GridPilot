# Rules Engine

Deterministic checks over the ingested timetable. Every rule returns
structured `Finding` records (`backend/app/analysis/models.py`) - never
prose. The (future) AI advisor layer explains findings; it doesn't invent
them. See `PROJECT_ROADMAP.md` for the milestone this implements.

## Privacy

`entity_refs` and `slot_refs` on every finding use **codes only** -
teacher code, room code, class code, student code (a 6-digit number, not
a name). Never a name or email. A UI that needs a display name joins it
from a code at render time; it is never stored on the finding itself.

## Implemented rules

### `teacher_double_booking` (critical)

A teacher has more than one lesson-type `TimetableEntry` at the same
`(day, period)`. Evidence includes every conflicting class code, room
code, and roll class code, plus whether the conflicting entries span more
than one room (`spans_multiple_rooms`) - a same-room conflict is the one
case that composite-class approval can explain; a multi-room conflict
never can (a teacher genuinely can't be in two rooms at once) and always
stays a real clash regardless of composite review status.

**Suppression**: only when every conflicting entry is in the same room
*and* that exact (teacher, room, class-code-set) combination is an
**approved** `composite_group` (see below). A detected-but-unreviewed
candidate still produces a finding - detection alone is never trusted.

### `room_double_booking` (critical)

Same as above, grouped by `(room, day, period)` instead. Evidence
includes `spans_multiple_teachers` - if two different teachers are both
booked into the same room at once, that's never a valid composite (a
composite is one teacher's combined lesson) and is always flagged.

**Suppression**: same rule as `teacher_double_booking`, checked from the
room's side.

### `student_double_booking` (critical)

A student is enrolled (`Enrolment`) in two different classes whose
`TimetableEntry` rows land on the same `(day, period)`. Computed by
intersecting each student's enrolled classes' scheduled slots, not from
`Class List Cycle.csv`'s per-occurrence rows (see `docs/data-formats.md`
- that file is structurally incapable of representing this, since
Timetabling Solutions has already resolved one class per period per
student by the time it's exported).

**Suppression**: if the two conflicting classes are both members of the
*same* approved composite group (the student would just be attending one
merged physical lesson under two of its class codes, not genuinely two
places at once).

### `room_capacity_exceeded` (warning)

Distinct enrolled students (via `Enrolment`) across every class sharing a
`(room, day, period)` slot, compared against `room.seats`. Rooms with
`seats IS NULL` are skipped entirely - that means "no fixed capacity
confirmed," not "capacity zero" (see `docs/data-formats.md` #5.3).

**Composite-aware by construction, not suppression**: a composite lesson's
two class codes share one room, so their enrolments are summed together
for this check (that's genuinely how many bodies are in the room) rather
than checked independently - this happens automatically from grouping by
room+slot and needs no approved-composite lookup, unlike the clash rules.

### `teacher_over_contracted_load` (warning)

Total scheduled minutes (summed from **distinct** `(teacher, period)`
slots, so a composite lesson's shared period is counted once no matter
how many class codes are attached to it) against `teacher.
contracted_load_minutes` (sourced from the `.tfx`'s `LoadProposed` field
- real data, not a guessed policy value). Teachers with no contracted
load recorded are skipped.

### `room_underutilization` (info)

Rooms with a confirmed capacity (`seats IS NOT NULL`) used in fewer than
20% of the cycle's lesson slots. **This threshold is a default heuristic
for surfacing candidates worth a human look, not a confirmed Sophia
College policy** - stated explicitly in each finding's evidence
(`threshold_note`). Doesn't yet exclude rooms whose `room_type` suggests
they were never meant to host regular lessons (meeting rooms, boardrooms,
quiet study) - a legitimate refinement, skipped for now rather than
asserting an interpretation of free-text room notes without confirming
it first.

### `class_room_instability` (info)

The same ongoing class (`class_name.code`, e.g. `09MAT3`) is taught in
more than one room across the cycle. Deliberately **threshold-free**,
unlike `room_underutilization` above - "more than one room" is itself the
finding, not a magnitude crossing an invented cutoff. Confirmed against
real data before building: e.g. one Year 9 Maths class, same teacher,
same roll class, in 5 different rooms across 7 lessons in the cycle - a
genuine consistency problem, not a query artifact (checked by grouping on
`class_name.id`, not `class_group_course.id`, since a handful of classes
have more than one `class_group_course` row - team-taught/split classes -
which would double-count rooms if grouped the wrong way).

### `class_teacher_inconsistency` (info)

Same shape as `class_room_instability`, for teachers instead of rooms:
the same ongoing class taught by more than one teacher across the cycle.
May be a deliberate team-teaching arrangement or genuinely accidental -
this rule doesn't and can't distinguish the two, which is exactly why
it's `info` severity and left for a human (or the AI advisor, explaining
not deciding) to judge.

Both rules see `docs/full-timetabler-plan.md` Phase B for the fuller
writeup, including four related rules from that phase's candidate list
that were investigated and **not** built - see "Not yet implemented"
below for why.

## Composite classes: reviewable, not silently trusted

`backend/app/analysis/composite.py` heuristically detects candidates:
same teacher + same room, with the same set of official class codes
recurring across at least 2 periods in the cycle (repetition is what
separates an intentional composite from a one-off double-booking - a
genuine scheduling error wouldn't repeat identically across the whole
cycle). `backend/app/analysis/composite_review.py` upserts these as
`PENDING` `composite_group` rows on every rules-engine run, **without
ever overwriting an existing review decision** - re-running detection
after a human has approved or rejected a candidate updates its
`slot_count`/`detected_at` only.

Only `APPROVED` groups suppress clashes. `PENDING` and `REJECTED` groups
still produce findings, with the composite candidate visible in the
Composite Review UI for the reviewer to act on.

Review via `POST /api/composites/candidates/{id}/approve` or `/reject`
(body: `{"reviewed_by": "...", "note": "optional"}`). Both re-run the
rules engine synchronously so findings reflect the decision immediately.

## Findings: accept a clash as intentional, don't just hide it

Not every double-booking is a mistake - e.g. a deliberate supervision
overlap. `POST /api/findings/{id}/accept-risk` (body: `{"reviewed_by":
"...", "note": "optional"}`) marks a finding `ACCEPTED_RISK`: it drops
out of the default `status=OPEN` view but is never actually hidden -
`GET /api/findings?status=ACCEPTED_RISK` (or `ALL`) still shows it, with
who accepted it, when, and why. `POST /api/findings/{id}/reopen` undoes
that. Both are logged to the audit trail (`finding_status_changed`) like
every other review decision in this app.

This survives the rules engine's next run for the same reason a
composite review decision does: `_persist()` in `app/analysis/run.py`
only ever flips a *RESOLVED* finding back to `OPEN` when it reproduces -
never an `ACCEPTED_RISK` one. A finding can only be reviewed while it's
still live; a finding the engine has already marked `RESOLVED` returns a
`409` rather than accepting a decision about something no longer there.

## Not yet implemented

From the roadmap's Milestone 1 "first rules" list, the remainder are
blocked on data or a policy value we don't have and shouldn't guess:

- `room_feature_mismatch` - no authoritative subject-to-required-feature
  mapping exists; `room.room_type` is free text from the source export's
  Notes column, not a controlled vocabulary (see `docs/data-formats.md`).
- `teacher_daily_overload`, `teacher_consecutive_load`,
  `teacher_free_period_fragmentation`, `uneven_subject_spread` - all need
  a school-confirmed threshold (what counts as "too many" consecutive
  periods, "too uneven" a spread) that doesn't exist yet in any source
  file. Implementing these means either asking the school directly or
  building a configurable-threshold mechanism first - both bigger than
  this milestone. `school_setting` (Phase A, `docs/full-timetabler-plan.md`)
  parses the school's *directional* preferences here (`optimise_spread`,
  `max_day_spread`, `successive_2_periods`, `successive_3_periods` are
  all `True`) but these are booleans, not numbers - they say the school
  wants spread and doubles, not how much spread is enough or which
  classes specifically need doubling. Investigated properly for Phase B
  rather than left purely theoretical:
  - **`teacher_free_period_fragmentation`**: real data checked (isolated
    single free periods sandwiched between two teaching periods). The
    signal is real (37 of 74 teachers have at least one, ranging up to 9
    in the cycle) but the distribution doesn't suggest an obvious
    "normal vs excessive" line - confirming this genuinely needs the
    school-confirmed threshold the roadmap already said it needs, not
    just a missing parser.
  - **`uneven_subject_spread`**: tested a same-day-repeat proxy (a class
    scheduled more than once on the same cycle day). Zero genuine
    occurrences once the pastoral/detention roll class (`RTC`, see
    `docs/data-formats.md` #5.2) is excluded - there's no spread problem
    to find in the current data via this proxy, so building the rule now
    would produce nothing to show for it.
  - **`missing_double`** (not on the original roadmap list, considered
    during Phase B planning): no per-subject "should be a double" data
    exists anywhere in the source - `Successive2Periods = True` says the
    school wants doubles used somewhere, not which specific subjects.
    Building this would mean guessing, exactly what this section exists
    to avoid.

Also deferred (roadmap Milestones 3-6, not required for this one):
change sets, constraint-based suggestion generation, full privacy/audit
controls beyond what's already true (no PII in findings, synthetic-only
fixtures in git), and the export validation gate.

## Running it

```bash
cd backend
python -m app.ingest.run      # build/refresh the working DB
python -m app.analysis.run    # sync composites, run rules, persist findings
```

Findings and composite candidates are also available live through the API
(`GET /api/findings`, `GET /api/composites/candidates`) and the GridPilot
UI's Findings / Composite Review tabs.
