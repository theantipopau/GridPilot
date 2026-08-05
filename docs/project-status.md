# Project Status and Health Review

*Written 2026-08-04, after completing all six PROJECT_ROADMAP.md
milestones. This is an honest self-assessment: what's solid, what's
known-weak, and the recommended order for what's next. Updated
2026-08-05: weakness #1 (re-ingest wiping human decisions) is fixed - see
`docs/reingest-persistence.md`.*

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

99 backend tests passing; frontend type-checks and builds clean. The
full loop the school asked for - load a `.tfx`, see it, change it,
export a file TT Solutions should re-read - exists end to end.

## Known weaknesses, in priority order

### ~~1. Re-ingesting wipes every human decision~~ - fixed 2026-08-05

`python -m app.ingest.run` used to call `fresh_database()`, which
**deleted the entire working database** before re-loading - destroying
every composite-class review decision, every change set, and the audit
trail on every re-ingest. Fixed: source-derived tables are still rebuilt
from scratch every ingest, but composite-group reviews and proposed
changes are now snapshotted by stable code (teacher/room/class/day/period
code, never an internal id) before the rebuild and re-resolved against
the fresh data afterwards; findings and the audit trail were never at
risk in the first place (findings are already keyed by code-based
`dedupe_key()`, audit events carry no source FK) and are simply left
alone. A link that can't be re-resolved is dropped and logged, never
guessed at. Verified against the real database, not just synthetic
fixtures - see `docs/reingest-persistence.md` for the full design and a
real bug (period-code collisions across the 10-day cycle) this process
caught and fixed.

### 1. The export has never been through Timetabling Solutions itself (highest remaining priority)

Already documented in `docs/export-validation.md`, but it's the second
biggest risk and only the school can close it: take one generated
`.tfx` and trial-import it into a **non-production copy** of
Timetabling Solutions. Until that's done once, the export gate's
re-ingest-through-our-own-parser check is the only evidence the output
is acceptable, and it's a proxy, not proof. This is a ~15-minute manual
task and it unlocks trust in the entire export path.

### 2. The privacy story needs one correction: OneDrive

The project lives at
`.../OneDrive - Brisbane Catholic Education/SOPHIA COLLEGE/TT Program`,
which means the source exports, the working SQLite database, and any
generated exports **do sync to BCE's OneDrive tenant**. The privacy
docs previously said "everything runs on your machine" without this
caveat - now corrected in `docs/privacy-threat-model.md`. It isn't a new
exposure (the source exports already lived in this folder, and it's the
school's own managed tenant), but a privacy document that overclaims is
worse than one that's precise.

### 3. A/B calendar mapping is still an assumption

`docs/data-formats.md` open item: nothing maps "Mon A" to real calendar
dates, and PROJECT_ROADMAP.md explicitly warns against inferring it from
ISO week parity (holidays and pupil-free days break the pattern). Fine
for now - nothing built so far needs real dates - but any future feature
that does ("what's on next Tuesday?", daily-notice generation, cover
planning) needs an explicit school-calendar table first. Don't let a
future feature quietly sneak in a week-parity guess.

### 4. Rules coverage is deliberately partial

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

1. **Trial import into TT Solutions** (weakness #1) - user task, small,
   unlocks trust in the whole loop.
2. **AI advisor (Ollama)** - the layer the original brief promised.
   Everything is staged for it: findings are structured, suggestions are
   pre-validated, evidence is codes-only. The AI's job per the roadmap
   is to *explain* findings, *summarise* trade-offs between candidate
   fixes, and *draft* changes into the same reviewable change-set
   pipeline - never to apply anything itself. `qwen3.5:9b` is already
   pulled locally.
3. **Staff capability / solver work** (the three larger planning docs) -
   still parked, correctly, until the above is stable. If/when teacher
   *records* (not just capability rules) become editable in the UI, stay
   code+role only (qualifications, faculty, roles/middle-leader,
   capabilities, load) - explicitly **not** personal-detail fields (DOB,
   home address, emergency contact) shown in `docs/design/ui-mockup2.png`,
   per the 2026-08-06 decision below.

*2026-08-06 update: **Timetable-building UX** (formerly #2 here) is
done - click a lesson in the grid, move it, see the clash-rule impact
immediately, save as a change set. The change-set/validation machinery
this was "mostly frontend work" against is exactly what made it a
same-day build. Also added: browser-based `.tfx`/`.sfx` import (no more
CLI-only ingestion). A second UI mockup was supplied showing a much
richer teacher-profile screen (`docs/design/ui-mockup2.png`) - it
includes real PII (date of birth, home address, emergency contact) with
no source in any Timetabling Solutions export; decided to keep teacher
data view-only and code+role-only for any future build, not add PII
storage - see the README's privacy section, which this project has held
to since the start.*

## Housekeeping done as part of this review

- Added `.gitattributes` normalising line endings (kills the constant
  CRLF warning noise on every commit).
- Corrected the OneDrive claim in `docs/privacy-threat-model.md`.
- This document.

*2026-08-05 update: persistence-across-re-ingest (the #1 item above at
the time) is now fixed - see `docs/reingest-persistence.md`. The
remaining sequence starts at trial import.*
