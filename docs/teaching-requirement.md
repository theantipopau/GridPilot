# Teaching Requirements (the demand model)

Implements `docs/roadmap-v3.md` section 3.1 / sequencing item #10 - "the
fork in the road." Everything built before this describes an
already-resolved timetable: 2,181 timetable entries, 6,726 enrolments, 248
class groups. Nothing described what the school *intends* to run - "Year 9
Science: 6 classes, 5 periods per cycle each, a Science room, a
Science-qualified teacher." That gap blocks an allocation engine (item
#12), a real blocking optimiser (item #11), and Mode B/C solver
construction (`docs/solver.md`) alike.

## Why bootstrap, not author

`docs/staff-capability-model.md` names two paths: bootstrap one
requirement per current offering from the resolved timetable, or author
requirements from scratch for a future planning year. This builds only
the bootstrap path - it needs no new data and no authoring UI, and the
addendum recommends it for v1. The `AUTHORED` source value exists in the
schema (`source TEXT ... CHECK (source IN ('BOOTSTRAPPED_FROM_TIMETABLE',
'AUTHORED'))`) but nothing produces it yet.

## Detection

`backend/app/analysis/teaching_requirement.py`'s
`detect_teaching_requirement_candidates()`: one candidate per class_name
not covered by an `APPROVED` composite group, one per `APPROVED`
composite_group (collapsing its members, per the addendum's explicit
instruction - a composite class must not double-count as several
separate requirements it otherwise would if scored per member). Unlike
room-type detection, there is no ratio threshold to tune: every class
with at least one `LESSON` timetable_entry produces a candidate.

For each: `periods_per_cycle` is the count of distinct `(day, period)`
slots read directly off `timetable_entry`; `assigned_teacher_id`/
`assigned_room_id` are a majority vote across those lessons, with
`matching_lesson_count`/`total_lesson_count` recording how many lessons
actually match that pairing - the same majority-vote discipline
`room_type_constraints.py` established, reused rather than reinvented. A
composite requirement's `roll_class_id` and `subject_id` stay `NULL` -
it spans multiple roll classes and (often) multiple subjects by
definition, so no single value is honest.

## Review, not assertion

`backend/app/analysis/teaching_requirement_review.py`'s
`sync_teaching_requirement_candidates()` upserts into
`teaching_requirement` - `PENDING` by default, run on every rules-engine
pass. Deliberately simpler than room-type's per-field evidence refresh:
once a row is `APPROVED` or `REJECTED`, sync leaves it **entirely
untouched**, including its lesson counts. A teaching requirement is a
bundle of several facts at once (periods, teacher, room, roll class) -
unlike room-type's single reviewed field, there's no one "stored fact" to
refresh evidence against without inventing a drift policy for a
multi-field bundle. If a school's resolved schedule diverges from an
already-approved requirement, that's a real question for a human to
re-review, not something to fold quietly into a background count. Revisit
only if real drift is ever observed against real data.

Review via **Teaching Requirements** in the sidebar (Quality group,
alongside the other three review queues), or directly:
`POST /api/teaching-requirements/candidates/{id}/approve` / `/reject`
(body: `{"reviewed_by": "...", "note": "optional"}`). No bulk-approve in
this pass - unlike room-type's 100%-consistency signal, the real
distribution of `matching_lesson_count / total_lesson_count` here hasn't
been checked against the real database yet. Decide on a bulk path only
after seeing that distribution, the same discipline that ruled out an
invented cutoff for teacher-capability (`docs/roadmap-v3.md` 1.3).

## What approving actually does

Only an `APPROVED` requirement feeds the new `teaching_requirement_
blocking` finding (`backend/app/analysis/staffing_rules.py`) -
`docs/staffing-priority-policy.md` calls this "one of the first useful
things to build once the capability tables land... doesn't need a
solver, it's a straightforward query." For every approved requirement,
it checks whether *any* teacher resolves `ELIGIBLE`
(`app/analysis/capability.py::resolve()`, the same single implementation
`teacher_not_qualified_for_class` uses) against the requirement's subject
or faculty. Zero eligible teachers is a critical finding - a genuine,
provable staffing gap. Deliberately scoped to eligibility only, not the
fuller `BLOCKING`/`HIGH`/`MEDIUM`/`HEALTHY` risk banding
`staffing-priority-policy.md` describes (that needs real load accounting
a solver would provide - `remaining_capacity_minutes` isn't computable
yet). A composite requirement (no single subject) is skipped, not
silently treated as blocked.

Nothing else consumes `teaching_requirement` yet - no allocation engine,
no blocking optimiser, no solver Mode B/C. This is deliberately just the
acquisition half.

## Schema fields included ahead of use

`lock_status` and `allocation_priority` are unused today - included per
`docs/staffing-priority-policy.md`'s explicit instruction ("written now
so schema fields are in place from the start rather than retrofitted").
This is the one place in the codebase pre-declaring a column ahead of
use as a documented, deliberate choice - contrast `solver_run.weights_
json`, deliberately withheld until real weights exist. Don't read
`lock_status`/`allocation_priority` as "half-built"; they're intentionally
inert until a staged solver (`staffing-priority-policy.md` section 6)
exists to consume them.

## Re-ingest persistence

`teaching_requirement` rows are snapshotted by code and restored after a
re-ingest, exactly like `class_room_type_constraint` -
`backend/app/db/resync.py`'s `_snapshot_teaching_requirements()` /
`_restore_teaching_requirements()`. The identity that survives re-ingest
is `requirement_key`: a class code for the simple case, or the
deterministic `"COMPOSITE:<sorted member codes>"` string detection
itself uses for the composite case. A composite-path row is re-linked by
re-finding the freshly-restored `composite_group` whose member-code set
matches the snapshot's, since `composite_group` itself gets a brand new
internal id on every re-ingest (`_restore_composite_groups` never tries
to preserve the old one). A requirement whose class code no longer
exists, or whose composite's members no longer match any approved
composite, is dropped and logged
(`teaching_requirement_dropped_on_reingest`), never silently guessed at.

## What this doesn't do (yet)

- **Not verified against the real database.** Every other detect →
  review feature in this project ends with a real-data check (real
  candidate counts, a real approve/reject cycle, a real re-ingest run).
  This one hasn't had that pass yet - the session that built it had no
  working Python/Node toolchain available to run ingestion or the test
  suite. Run `python -m app.ingest.run && python -m app.analysis.run`
  against the real `Timetabler Export/` and report actual counts here
  before treating this as production-verified.
- **No bulk review** - see above; needs the real confidence distribution
  first.
- **No editing** - approve (as detected) or reject only, same limitation
  `docs/room-constraints.md` documents for the same reason: an edit path
  needs validated pickers (teacher/room/period-count) this pass didn't
  build.
- **No drift detection** - see the review section above.
- **Doesn't feed allocation, blocking, or the solver** - those are
  separate, larger items (`docs/roadmap-v3.md` #11/#12), gated on this
  landing and being verified first.
