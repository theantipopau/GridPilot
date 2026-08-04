# Project Status and Health Review

*Written 2026-08-04, after completing all six PROJECT_ROADMAP.md
milestones. This is an honest self-assessment: what's solid, what's
known-weak, and the recommended order for what's next.*

## Where things stand

All six roadmap milestones are built, tested against the real Term 3
export, and committed:

| Area | State |
|---|---|
| Ingestion + cross-validation (.tfx primary, CSV/eMinerva checks) | Done, 0 unexplained discrepancies against real data |
| Timetable grid view (teacher/room/roll-class) | Done |
| Rules engine (3 clash rules + capacity/load/utilisation) | Done - 251 findings on current data |
| Composite classes as human-reviewed candidates | Done - 16 detected, review workflow live |
| Safe change sets (what-if validation, approve gate) | Done |
| Constraint-based fix suggestions (no AI) | Done |
| Audit trail, source hashing, retention/purge | Done |
| Export gate (.tfx out, 6 validation gates, CLI-only write) | Done |

74 backend tests passing; frontend type-checks and builds clean. The
full loop the school asked for - load a `.tfx`, see it, change it,
export a file TT Solutions should re-read - exists end to end.

## Known weaknesses, in priority order

### 1. Re-ingesting wipes every human decision (highest priority)

`python -m app.ingest.run` calls `fresh_database()`, which **deletes the
entire working database** before re-loading. That destroys:

- every composite-class review decision (approved/rejected),
- every change set, including APPROVED ones,
- every finding's status and identity,
- the entire audit trail (which Milestone 5 built specifically to be
  durable).

This was the right simplification while building - each milestone wanted
a clean slate - but it's wrong for real operation. The school will
re-export from Timetabling Solutions regularly (weekly or more), and
each re-ingest currently throws away all accumulated review work.

**Recommended fix**: split "derived from the source file" data (wipe and
reload freely) from "human decision" data (composite reviews, change
sets, findings status, audit) and re-attach the latter across ingests by
stable keys - composite groups already have a natural key (teacher +
room + member-class-code set), findings already have `dedupe_key`, and
change sets could re-resolve their entries via the source GUIDs kept on
every row. This should land **before** the school starts using GridPilot
routinely, or the first Monday-morning re-ingest will silently discard a
week of review decisions.

### 2. The export has never been through Timetabling Solutions itself

Already documented in `docs/export-validation.md`, but it's the second
biggest risk and only the school can close it: take one generated
`.tfx` and trial-import it into a **non-production copy** of
Timetabling Solutions. Until that's done once, the export gate's
re-ingest-through-our-own-parser check is the only evidence the output
is acceptable, and it's a proxy, not proof. This is a ~15-minute manual
task and it unlocks trust in the entire export path.

### 3. The privacy story needs one correction: OneDrive

The project lives at
`.../OneDrive - Brisbane Catholic Education/SOPHIA COLLEGE/TT Program`,
which means the source exports, the working SQLite database, and any
generated exports **do sync to BCE's OneDrive tenant**. The privacy
docs previously said "everything runs on your machine" without this
caveat - now corrected in `docs/privacy-threat-model.md`. It isn't a new
exposure (the source exports already lived in this folder, and it's the
school's own managed tenant), but a privacy document that overclaims is
worse than one that's precise.

### 4. A/B calendar mapping is still an assumption

`docs/data-formats.md` open item: nothing maps "Mon A" to real calendar
dates, and PROJECT_ROADMAP.md explicitly warns against inferring it from
ISO week parity (holidays and pupil-free days break the pattern). Fine
for now - nothing built so far needs real dates - but any future feature
that does ("what's on next Tuesday?", daily-notice generation, cover
planning) needs an explicit school-calendar table first. Don't let a
future feature quietly sneak in a week-parity guess.

### 5. Rules coverage is deliberately partial

Four roadmap rules remain unimplemented because each needs a
school-confirmed threshold or data that doesn't exist in any source file
(consecutive-load limits, free-period fragmentation, subject spread,
room features). Documented in `docs/rules.md`. The fastest way to unlock
these is a short conversation with the school about actual policy
values, then a small config mechanism - not more code speculation.

## What's next (recommended order)

The school's stated goals, in their words: better **visual clarity for
building a timetable**, and **AI to fix the huge gaps in manual labor**.
Suggested sequence:

1. **Persistence across re-ingests** (weakness #1) - unglamorous, but
   everything else is built on sand until review decisions survive a
   re-import.
2. **Trial import into TT Solutions** (weakness #2) - user task, small,
   unlocks trust in the whole loop.
3. **Timetable-building UX** - the current grid is read-only-plus-tabs.
   The supplied mockup (`docs/design/ui-mockup.png`) shows the target: a
   grid you edit in place, with a lesson inspector, drag/move actions
   that create proposed changes automatically, and clash/composite
   badges inline. The change-set machinery underneath already exists -
   this is mostly frontend work wiring the grid to it.
4. **AI advisor (Ollama)** - the layer the original brief promised.
   Everything is staged for it: findings are structured, suggestions are
   pre-validated, evidence is codes-only. The AI's job per the roadmap
   is to *explain* findings, *summarise* trade-offs between candidate
   fixes, and *draft* changes into the same reviewable change-set
   pipeline - never to apply anything itself. `qwen3.5:9b` is already
   pulled locally.
5. **Staff capability / solver work** (the three larger planning docs) -
   still parked, correctly, until the above is stable.

## Housekeeping done as part of this review

- Added `.gitattributes` normalising line endings (kills the constant
  CRLF warning noise on every commit).
- Corrected the OneDrive claim in `docs/privacy-threat-model.md`.
- This document.
