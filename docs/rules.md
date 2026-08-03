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

From the roadmap's Milestone 1 "first rules" list - deferred to keep this
milestone's scope to what its definition of done actually requires:

- `room_capacity_exceeded`
- `room_feature_mismatch`
- `teacher_daily_overload`
- `teacher_consecutive_load`
- `teacher_free_period_fragmentation`
- `room_underutilization`
- `uneven_subject_spread`

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
