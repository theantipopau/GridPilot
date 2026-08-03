# Internal Data Model — Proposal

Normalised model the ingestion layer will build from the Timetabling
Solutions `.tfx`/CSV exports and the eMinerva text exports, per
`docs/data-formats.md`. This is the internal representation the analysis
engine, AI advisor, UI, and export layer all operate on — it is not tied to
either source format.

## Design principles

- **`.tfx` is the primary source.** It's the richer, canonical export
  (has the resolved grid, class-group structure, and student lesson
  lists in one file). The CSVs and eMinerva files are used to
  cross-validate on ingest; any row present in one source but not another
  is surfaced as a discrepancy, never silently dropped (per the "fail
  loudly" requirement).
- **Every entity keeps its original identifiers.** Source GUIDs
  (`TeacherID`, `RoomID`, `PeriodID`, …) and short codes (`DIXM02`,
  `ANG1`) are stored alongside the internal surrogate ID, not replaced by
  it. Round-trip export back into Timetabling Solutions format is only
  possible if we never lose the original ID a record came from — so
  provenance is a first-class part of every table, not an afterthought.
- **Non-teaching periods are modelled explicitly**, not inferred from
  code text. `EntryType` distinguishes lesson / break / assembly /
  general-purpose / detention / registration, per the school's
  confirmed meanings.
- **Students, not just classes, carry enrolment as a first-class
  relationship**, deduplicated (mirroring `eMinervaSCourse.txt`, not the
  per-cycle-occurrence shape of `Class List Cycle.csv`).

## Entities

### Cycle structure

**`Day`** — `id, code (e.g. "Mon A"), dayNo (1–10), weekLabel ("A"|"B" derived from code)`
The school's cycle is a 10-day A/B fortnight, not Mon–Fri. `weekLabel` is
parsed out of the code for convenience but the code remains the source of
truth.

**`Period`** — `id, sourceGuid, code (FR/P1–P5/FB/SB), name, dayId, periodNo (1–8), startTime, finishTime, loadMinutes, entryKind (REGISTRATION|LESSON_SLOT|BREAK)`
`entryKind` here is about the *slot* (e.g. FB is structurally a break slot
regardless of what's scheduled in it); `EntryType` below is about what's
actually scheduled in a given slot for a given class, which can still
diverge (e.g. a duty scheduled in a break slot).

### Places and people

**`Room`** — `id, sourceGuid, code, name, seats (nullable — null where source Seats=0, treated as "no fixed capacity"), roomType (free-text from Notes, e.g. "Senior Science"), siteNo`

**`Faculty`** — `id, sourceGuid, code, name`

**`Teacher`** — `id, sourceGuid, code, firstName, lastName, email, staffCategory (TEACHER|GUIDANCE_COUNSELLOR|SUPPORT_OFFICER|COLLEGE_LEADERSHIP), facultyIds[], contractedLoadMinutes (from LoadProposed/LoadMaxYardDuty if populated, else null)`

**`YearLevel`** — `id, code (07–12)`

**`RollClass`** — `id, sourceGuid, code, yearLevelId (nullable — null for the Re-Engagement Room, which has no year level), isSupportRollClass (true for Re-Engagement Room)`

**`Student`** — `id, sourceGuid, code, firstName, lastName, preferredName, gender, rollClassId, yearLevelId, house (normalised to a fixed casing — source data has inconsistent case), homeGroup, email, supportFlags[] (reserved — none present in current export, extra-care field per privacy requirements)`

### Subjects and classes

**`Subject`** — `id, sourceCode, name, facultyId (nullable)`

**`ClassName`** (a specific offering/course code, e.g. `12RAE2`) — `id, sourceGuid, code, name, subjectId, suffix, facultyId`

**`ClassGroup`** (a roll class's block of periods for one subject line — the unit that can be team-taught or split) — `id, sourceGuid, rollClassId, blockNo, periodsPerCycle, courses: ClassGroupCourse[]`

**`ClassGroupCourse`** — `id, sourceGuid (CourseID), classGroupId, classNameId, teacherId, roomId, roomOverrides: {periodId, roomId}[] (from RoomTimetableEdits — per-period room swaps within an otherwise-stable course)`

### The timetable grid

**`TimetableEntry`** — `id, sourceRef (CSV row or Timetable[] index), dayId, periodId, rollClassId, classNameId (nullable for non-lesson entries), roomId (nullable), teacherId (nullable), entryType (LESSON|BREAK|ASSEMBLY|GENERAL_PURPOSE|DETENTION|REGISTRATION|OTHER)`
This is the join of class + teacher + room + timeslot — the actual grid,
one row per (roll class, period) that's scheduled, for the full 10-day
cycle. `entryType` is derived on ingest from the `ClassName`/`Subject`
code prefix (`BREAK-`, `ASM-`, `GP-`) and from `RollClass.isSupportRollClass`,
using the mapping confirmed with the school — this mapping lives in one
place (a lookup table in the ingestion layer) so it's easy to extend if
new non-teaching codes appear in future exports, rather than being
guessed inline wherever entry type matters.

### Enrolment

**`Enrolment`** — `id, studentId, classNameId, source (which export(s) confirmed this — for cross-validation, not shown in normal UI)`
Deduplicated student↔class membership — built from `eMinervaSCourse.txt`
and cross-checked against `.tfx` `Students[].StudentLessons[]`, **not**
built directly from `Class List Cycle.csv` (which repeats every
enrolment once per cycle occurrence and would need collapsing first).

### Yard duty (kept as a separate subsystem, per your confirmation)

**`YardDutyArea`**, **`YardDutySession`**, **`YardDutyAllocation`** — mirror
the source CSVs directly (area, the 4 daily duty windows, and
teacher-to-area-per-session assignments with a load value). Joined to
`Teacher` and `Period` but not folded into `Teacher.contractedLoadMinutes`
in v1.

## What this enables

- **Clash detection**: group `TimetableEntry` by `(dayId, periodId,
  teacherId)`, `(dayId, periodId, roomId)`, and `(dayId, periodId,
  studentId via Enrolment+RollClass)` — any group >1 is a clash.
- **Room capacity/suitability**: join `TimetableEntry` → `ClassGroupCourse`
  enrolment count (via `Enrolment`) against `Room.seats` and
  `Room.roomType`.
- **Teacher load**: sum `loadMinutes` across a teacher's `TimetableEntry`
  rows where `entryType = LESSON`, against `contractedLoadMinutes`;
  free-period fragmentation and first/last-period loading fall out of the
  same grouped-by-day view.
- **Room utilisation**: `TimetableEntry` count per room per cycle ÷ total
  lesson slots.
- **Non-teaching entries** stay queryable (e.g. "who's on GP this
  period") without polluting the above checks, since `entryType` filters
  them out by default.
- **Round-trip export**: because every table retains its `sourceGuid`/
  `sourceCode`, regenerating a `.tfx`-shaped or eMinerva-shaped file means
  walking the same entities back out through their original IDs — new
  records (from AI-approved changes) get freshly-generated GUIDs in the
  same format Timetabling Solutions uses, and the validation step diffs
  the regenerated file's structure against the original.

## Architecture decisions (confirmed 2026-08-03)

- **Publishing stays file-only.** The app produces a validated,
  correctly-formatted export for Timetabling Solutions re-import and for
  eMinerva. It does **not** connect to eMinerva or any other platform to
  push changes live — you import/upload through those systems' own
  interface, as today. This keeps the tool offline-capable and avoids
  needing stored credentials for school platforms.
- **The AI advisor can draft direct edits**, not just suggest them for
  one-by-one accept/reject. It produces a modified draft timetable (a set
  of proposed `TimetableEntry` changes), which you review as a whole diff
  against the current state before any of it is committed. Every change
  in the diff still cites the rule-engine finding(s) that justify it
  (per the original brief's 4.4), and nothing is written back to the
  working data model until you approve the diff (or individual entries
  within it).

## What I'd build first (proposed order)

1. SQLite schema mirroring the above (one migration file).
2. `.tfx` parser → populates everything except `Enrolment` (richest single
   source).
3. CSV parsers for `Room/Period/Teacher/Student/RollClass Details.csv` +
   `Master Timetable Cycle.csv` as a cross-validation pass against the
   `.tfx` import (fail loudly on any discrepancy beyond the known
   2,143-vs-2,181 count gap, which itself gets logged as a discrepancy to
   investigate, not silently absorbed).
4. `eMinervaSCourse.txt` parser → populates `Enrolment`.
5. `eMinervaTTable.txt` used only as a second cross-validation pass on
   `TimetableEntry` (redundant with Master Timetable Cycle.csv content-wise,
   but confirms eMinerva's own view matches).

Parsers for the `.sfx` (Student Options) files are deferred — not needed
for viewing/editing the current timetable or for the analysis engine, per
`docs/data-formats.md` §3.2.

Does this match how you think about the school's data? Flag anything that
looks wrong before I build the SQLite schema and ingestion layer.
