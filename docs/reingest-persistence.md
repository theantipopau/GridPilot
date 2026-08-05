# Re-ingest Persistence

Written 2026-08-05, closing out `docs/project-status.md`'s top-priority
known weakness: re-ingesting used to wipe every human decision
(composite-class reviews, change sets, the audit trail) because
`app.ingest.run.run_full_ingest()` called `fresh_database()`, which
deletes the entire working SQLite file before reloading. The school will
re-export from Timetabling Solutions regularly - every re-ingest was
silently discarding accumulated review work. See `app/db/resync.py` for
the implementation.

## The fix

Tables now fall into two groups:

- **Source-derived** (`day`, `period`, `room`, `teacher`,
  `timetable_entry`, `enrolment`, the `sfx_*` tables, ...) - rebuilt from
  scratch every ingest, exactly as before. There's no meaningful way to
  "diff" a resolved timetable against a new export; a clean rebuild is
  correct.
- **Human-decision** (`composite_group`/`composite_group_member`,
  `change_set`/`proposed_change`/`proposed_change_finding`, `finding`,
  `audit_event`, `ingest_run`, `ingest_discrepancy`) - preserved across
  the rebuild.

`finding` and `audit_event` need no special handling at all: findings are
already keyed by `dedupe_key()` (teacher/room/class/day/period **codes**,
never an internal integer id - see `app/analysis/models.py`), and audit
events carry no foreign key into any source table. Both are simply left
alone by the rebuild.

`composite_group`/`composite_group_member` and `change_set`'s child
`proposed_change`/`proposed_change_finding` are the hard part: their rows
hold live integer foreign keys (`teacher_id`, `room_id`, `class_name_id`,
`timetable_entry_id`, ...) into the source tables that are about to be
deleted and recreated with new autoincrement ids. `app/db/resync.py`
handles this in three steps:

1. **Snapshot by code, not by id**, before anything is deleted - a
   composite group's teacher/room/member-class identity, a proposed
   change's roll-class/day/period/room/teacher identity. Internal ids are
   only ever stable *within* one ingest, never *across* two.
2. **Rebuild** the source tables (`SOURCE_TABLES_IN_DELETE_ORDER`,
   respecting every foreign key among them).
3. **Restore by re-resolving each snapshotted code** against the
   freshly-ingested rows, and re-inserting. A code that no longer
   resolves (a teacher left, a room was renamed, the lesson slot a
   proposed change targeted no longer exists) means that one row is
   **dropped, not guessed at** - logged via `audit_event`
   (`composite_review_dropped_on_reingest` /
   `proposed_change_dropped_on_reingest`) so it's visible, never silent,
   per the project's standing "fail loudly" rule. A change set that loses
   a proposed change this way is reset to `NOT_VALIDATED` so it gets
   re-checked before anyone approves it.

## A real bug this caught

The first version of the proposed-change restore matched a lesson slot's
period by `{period_code: period_id}` alone. Against the synthetic test
fixture (one period per code) this looked correct. Against the real
10-day A/B cycle it wasn't: period codes repeat once per day (`P1` exists
once on every one of the 10 days - `schema.sql`'s only uniqueness
guarantee is `UNIQUE (day_id, period_no)`, never on code alone), so the
lookup silently resolved to whichever day's `P1` happened to be inserted
last. Verified against the real database (create a change set, re-run
`python -m app.ingest.run` against the same real `.tfx`, check what
survived): the change was dropped when it shouldn't have been. Fixed by
scoping the lookup to `(day_id, period_code)`, and
`tests/test_resync.py::test_proposed_change_moved_to_a_different_day_with_the_same_period_code_resolves_correctly`
locks it in - a case the original synthetic fixture couldn't have caught,
since it only had one period per code.

## What this doesn't (yet) do

- A **restored** change set's `validation_status` is left as-is rather
  than forced back to `NOT_VALIDATED` - only a change set that actually
  lost a proposed change gets reset. A cleanly-restored change set could
  still be validating against subtly different underlying data (e.g. a
  different class now occupies a nearby slot); re-validating is one click
  away, but isn't forced automatically. Deliberate scope boundary: ingest
  and the analysis/validation layer are separate steps in this
  architecture today, and forcing that coupling here felt like more
  machinery than the problem warranted.
- `ingest_run`/`ingest_discrepancy` now accumulate indefinitely across
  every ingest rather than being scoped to "the current run" - a minor
  side effect of no longer wiping the file, not something actively
  managed yet. Not a correctness problem (nothing sums across runs), just
  something to revisit if the working database grows large after months
  of routine use.
