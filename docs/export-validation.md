# Export Validation Gate

Implements PROJECT_ROADMAP.md's Milestone 6: turning an APPROVED change
set into a `.tfx` file Timetabling Solutions can re-import. This is the
highest-stakes piece of GridPilot built so far - a bad export could
corrupt the school's real timetable data - so it's built and tested more
conservatively than anything else in this project.

## Strategy: patch, never rebuild

`app/export/tfx_writer.py` loads the original `.tfx` as plain JSON and
mutates **only** the specific `Timetable[]` entries an approved change
touches, found via `timetable_entry.source_ref` (exactly
`"tfx:Timetable[<index>]"`, set during ingestion - see
`app/ingest/tfx_parser.py`). Every other byte of the structure - every
other top-level array, every untouched `Timetable[]` entry - is left
completely alone.

This isn't just simpler than reconstructing the whole file from our
normalised SQLite model; it's *safer*. Rebuilding risks silently
dropping a field we didn't think to model (the `.tfx` has `RURs[]` and
`MRCGs[]` sections we still don't fully understand - see
`docs/data-formats.md`). Patching means we never have to fully
understand those sections to export safely - we just never touch them.

## The six gates

An export is not "ready" unless every one of these passes
(`app/export/validate.py`):

1. **`json_round_trip`** - the patched structure survives a JSON
   serialise/parse cycle unchanged. Catches anything that snuck a
   non-JSON-safe value into the patch.
2. **`structural_comparison`** - same top-level keys as the original,
   same array length for every one of them. We only ever mutate fields
   *within* existing `Timetable[]` entries, never add or remove records
   anywhere - a length mismatch means something is badly wrong.
3. **`unchanged_record_fidelity`** - every `Timetable[]` entry *not*
   touched by the change set, and every other top-level array in its
   entirety, is byte-for-byte identical to the original. Provable
   directly (not just assumed) because of the patch-not-rebuild strategy.
4. **`referential_integrity`** - every touched entry's `PeriodID`,
   `RoomID` (if non-blank), and `TeacherID` (if non-blank) actually exist
   somewhere in the patched file's own `Periods[]`/`Rooms[]`/`Teachers[]`
   arrays. A self-consistency check on the output file itself, not just
   trust in our internal database.
5. **`change_set_reconciliation`** - re-ingests the patched file through
   `app.ingest.tfx_parser` (the application's real, production parser -
   not a simplified check) into a throwaway temp database, then confirms
   every proposed change's after-values show up exactly where expected.
6. **`no_new_clashes`** - runs the same clash rules used everywhere else
   in GridPilot against that re-ingested copy, and confirms nothing new
   appears compared to the current working database. Composite-class
   review decisions are copied into the temp database first, matched by
   each group's exact member-class-code set (not just teacher+room, which
   the real data shows can be ambiguous - see `docs/rules.md`) so an
   approved composite doesn't get spuriously reported as a new clash.

Gates 5 and 6 together are the strongest proof available that the output
is genuinely correct: not "we're confident the patch logic is right," but
"we fed the actual output file through our own real parser and it
produced exactly what was expected." Verified against real data in
~0.3 seconds per export (`test_export_gate_passes_for_a_genuinely_valid_
change_set` in `backend/tests/test_export_real.py`).

## What this can't prove

**This tool cannot verify that Timetabling Solutions itself accepts the
generated file** - there's no way to drive that Windows application from
here. Gate 5's re-ingestion through our own parser is the closest
available proxy: if our parser (built by carefully reverse-engineering
the real `.tfx` schema - see `docs/data-formats.md`) accepts it and
reproduces the expected state, that's strong evidence the file is
well-formed, but it is not the same as Timetabling Solutions confirming
it. PROJECT_ROADMAP.md is explicit about this gap too: **"test re-import
against a non-production copy of Timetabling Solutions"** before trusting
generated output against anything real. Do that before ever feeding a
GridPilot export into your production Timetabling Solutions data.

## CLI-only, behind an explicit flag

```bash
cd backend
python -m app.export.run --change-set-id 5              # dry run: validate, print gate results, write nothing
python -m app.export.run --change-set-id 5 --confirm     # write files only if every gate passes
```

Per PROJECT_ROADMAP.md's "keep export behind an experimental flag":
**producing a file is deliberately not a button in the UI.** The
Change Sets tab has a **"Preview export"** action for an approved change
set (`GET /api/change-sets/{id}/export-preview`) that runs every gate
above and shows the results - including gates 5 and 6's full re-ingest
and re-check - but never writes anything. Actually producing the file
requires running the CLI command yourself, with `--confirm`. This matches
the same posture already established for `app/retention.py`'s purge
utility: an action with real consequences for real data is a terminal
command a person chooses to run, not a click.

## Output and "backup"

Each successful `--confirm` run writes three files under `output/`,
uniquely timestamped and never overwritten (checked explicitly before
writing):

```
{change-set-name-slug}_{change_set_id}_{timestamp}.tfx
{change-set-name-slug}_{change_set_id}_{timestamp}_changelog.json
{change-set-name-slug}_{change_set_id}_{timestamp}_validation.json
```

PROJECT_ROADMAP.md asks for "backup and timestamped output filename" -
here that's the same thing: because nothing is ever overwritten, `output/`
is itself a complete history of every export ever generated, so there's
no separate backup step. An `export_generated` audit event is also
recorded (see `docs/privacy-threat-model.md`).

## What's still out of scope

- **eMinerva/BCE-facing exports.** Only a Timetabling Solutions-compatible
  `.tfx` is produced. The original brief and PROJECT_ROADMAP.md are both
  explicit that Timetabling Solutions is the interoperability bridge -
  generate a candidate here, verify it there, then use the school's
  already-established process for downstream exports.
- **Multi-change-set exports.** One change set per export run. Combining
  several approved change sets into one export is a reasonable future
  extension but isn't needed yet and adds real complexity (overlapping
  edits to the same entry would need their own conflict-resolution rule).
