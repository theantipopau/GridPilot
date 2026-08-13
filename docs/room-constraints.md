# Room-Type Constraints

Implements `docs/solver.md` section 4.2 / Phase G1: infers which
`room_type` a class actually requires, from how it has already been
scheduled, and puts that inference in front of a human before trusting
it for anything. Nothing in the source export declares this explicitly -
`room.room_type` is free text from the export's Notes column, not a
controlled vocabulary (`docs/data-formats.md`).

## Why this exists

Two independent things wanted this data and neither had it:

1. **`room_feature_mismatch`** - a Milestone 1 roadmap rule, blocked
   since the very first rules-engine pass for exactly this reason (see
   `docs/rules.md`'s "Not yet implemented" section, before this).
2. **A future solver's room domain** - `docs/solver.md` section 3.1:
   without this constraint, a CP-SAT model has to consider all 51 rooms
   for every one of 1,519 lessons (~3.9M booleans); with it, the domain
   shrinks to the handful of rooms of the right type (~600K). The
   constraint data isn't just quality, it's what makes the model
   tractable at all.

## Real-data grounding before building anything

Checked against the live database first, same discipline as every rule
in this project: of 231 classes scheduled in at least one typed room,
**180 (78%) already use exactly one `room_type` for every lesson**, and
220 (95%) use at most two. Strong enough to *propose*, nowhere near
strong enough to *assert* - hence a review queue, not a silent rule.

## Detection

`backend/app/analysis/room_type_constraints.py`'s
`detect_room_type_candidates()`: for each class, group its lessons by the
`room_type` of the room they're in (lessons in an untyped/`NULL` room
contribute no evidence either way). If one type covers at least
`MIN_RATIO` (0.7, a documented default heuristic - same status as
`room_underutilization`'s threshold, not a confirmed school policy) of at
least `MIN_LESSONS` (2 - a single typed lesson is never enough signal on
its own) of the class's lessons, that type is proposed as a candidate.

## Review, not assertion

`backend/app/analysis/room_type_review.py`'s `sync_room_type_candidates()`
upserts candidates into `class_room_type_constraint` - **one row per
class** (a class has at most one required type), `PENDING` by default.
Runs on every rules-engine pass (`app/analysis/run.py`), same as
composite-class detection.

Critically, once a human has reviewed a class's row (`APPROVED` or
`REJECTED`), **the `room_type` itself is never rewritten** by a later
sync - only the supporting evidence counts (`matching_lesson_count`/
`total_lesson_count`) refresh, and they refresh against the *reviewed*
type, never against whatever happens to be the current majority. This is
a deliberate difference from `composite_review.py`, where the reviewed
key (teacher, room, member-class-set) can't drift - here the reviewed
field, `room_type`, is exactly the thing usage could drift away from. A
class whose usage shifts after approval shows updated counts next to the
same room_type, so a human revisiting later sees the current picture
without the enforcement silently changing underneath them.

Review via **Room Constraints** in the sidebar, or directly:
`POST /api/room-constraints/candidates/{id}/approve` /
`/reject` (body: `{"reviewed_by": "...", "note": "optional"}`). Both
re-run the rules engine synchronously, same as composite review.

## What approving actually does

Only an `APPROVED` constraint feeds `room_feature_mismatch`
(`backend/app/analysis/room_feature_rules.py`): any lesson of that class
scheduled in a room of a different `room_type` (including an untyped
room - "we don't know what this room is" is not the same as "it's the
right type") becomes a `warning`-severity finding, with the exact required
vs. actual type in its evidence. A `PENDING` or `REJECTED` constraint
produces nothing - same suppression discipline as
`composite_group.review_status`.

Because the finding carries `slot_refs` and `entity_refs` like every
other slot-scoped finding, it's picked up automatically by the grid's
finding-highlighting layer (`docs/master-timetable.md`) with no extra
wiring - an orange ring on the exact mismatched lesson, tooltip named.

## Verified against real data

Approved `12RAE1 → Classroom` (7/8 lessons, 88% - the same class used as
the worked example in `docs/suggestions.md`'s room-consolidation
section). Immediately produced: *"Class 12RAE1 scheduled in LEO4 (Maths
Classroom), not a Classroom room, at Fri B P2"* - the exact minority-room
lesson `suggest_fixes()` already proposes moving to LEO2 for consistency,
now independently flagged for a different, equally real reason (wrong
room type). Confirmed correctly highlighted on both the master and
single-entity timetable grids, then reverted (reset to `PENDING`, rules
re-run) so no test-authored review decision was left in the school's
real data - same cleanup discipline this project has applied to every
other piece of live-data verification.

## Re-ingest persistence

`class_room_type_constraint` rows are snapshotted by class code and
restored after a re-ingest, exactly like `composite_group` -
`backend/app/db/resync.py`'s `_snapshot_room_type_constraints()` /
`_restore_room_type_constraints()`. A constraint whose class code no
longer exists in the new export is dropped and logged
(`room_type_constraint_dropped_on_reingest`), never silently guessed at.

## What this doesn't do (yet)

- **Doesn't narrow any solver's search** - there is no solver yet
  (`docs/solver.md` H1+). This is purely the constraint-acquisition half
  of Phase G1.
- **Doesn't offer "Edit to a different type"** - only Approve (the
  detected type) or Reject (any room is fine). A reviewer who disagrees
  with the *detected* type entirely has no UI path to say "actually it's
  X" - they'd reject and the class simply has no enforced constraint.
  Deliberately deferred: it needs a room_type picker validated against
  the real vocabulary, and the 78%/95% real-data numbers suggest the
  detected type is very rarely wrong in a way "Edit" would fix rather
  than "Reject" already covering.
- **Doesn't touch `class_teacher_inconsistency`'s sibling problem** -
  there's no equivalent "required teacher" concept, deliberately: see
  `docs/suggestions.md`'s note on why teacher reassignment is never
  suggested without subject-qualification data.
