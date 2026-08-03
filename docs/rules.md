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
  this milestone.

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
