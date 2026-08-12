# Data Formats — Phase 0 Discovery

Findings from inspecting the sample export files in `Timetabler Export/` and
`tester.tfx`. This document describes **structure only** — no real student or
staff names, emails, or IDs appear anywhere below. Field names in ALL CAPS or
`Code` form are the software's own labels, not identifying data.

Source software: **Timetabling Solutions** (Version 10 — JSON exports,
`.tfx`/`.sfx`), plus flat CSV exports it can also produce, plus **eMinerva**
roll-marking import text files.

## 1. File inventory

| File | Format | Rows/records | Contains PII |
|---|---|---|---|
| `Room Details.csv` | CSV | 51 rooms | No |
| `Period Details.csv` | CSV | 80 periods | No |
| `Timetable Days.csv` | CSV | 10 days | No |
| `Year Level Details.csv` | CSV | 6 year levels | No |
| `Roll Class Details.csv` | CSV | 20 roll classes | No |
| `Yard Duty Areas.csv` | CSV | 18 areas | No |
| `Yard Duty Session Details.csv` | CSV | 40 sessions | No |
| `Period and Yard Duty Sessions.csv` | CSV | 120 rows | No |
| `Yard Duty Allocations.csv` | CSV | ~230 rows | Yes — teacher code only |
| `Teacher Details.csv` | CSV | 74 teachers | Yes — name, email |
| `Student Details.csv` | CSV | 560 students | Yes — name, email, guardian email cols (empty in sample) |
| `Master Timetable Cycle.csv` | CSV | 2,143 rows | No (codes only) |
| `Class List Cycle.csv` | CSV | 44,780 rows | Yes — student code + GUID |
| `eMinervaSCourse.txt` | CSV-like text (comma, quoted) | 6,726 rows | Yes — student name |
| `eMinervaTTable.txt` | CSV-like text (comma, quoted) | 2,143 rows | No (codes only) |
| `TT files/TT 2026 Term Three Week 4.tfx` | JSON | full master timetable | Yes — student & teacher names, emails |
| `TT files/YR 7–12 *.sfx` (×6) | JSON | one per year level | Yes — student names, emails |
| `tester.tfx` (root) | JSON | empty stub (no Days/Periods populated) | No — appears to be a blank template, not live data |

All CSVs are UTF-8 with BOM, comma-delimited, quoted where the value contains
a comma or is a name, header row present. The `.tfx`/`.sfx` files are UTF-8
JSON (also with a BOM).

## 2. Timetabling Solutions CSV exports

### 2.1 Reference/lookup tables

**`Room Details.csv`**: `No, Room Name, Room Code, Seats, Notes, Site No`
Room Code is the short join key used everywhere else (e.g. `ANG1`, `LEO3`).
`Seats` is capacity; **13 of 51 rooms have `Seats = 0`** (meeting rooms,
quiet study, some Spoleto/engineering spaces) — ambiguous, see §5.
`Notes` doubles as a loose "room type/feature" tag (`Classroom`,
`"Senior Science"`, `Drama`, `Music`, `"Meeting Room"`, `Guidance`,
`"Learning Support"`, `"Re Engagement Room"`, etc.) — free text, not a
controlled vocabulary. `Site No` is always `1` in this sample (single-site
school, so building/location for travel-time analysis isn't distinguishable
from this field alone — room name prefixes like `Angelo`/`Leo`/`Greccio`
appear to encode building, informally).

**`Period Details.csv`**: `No, Day Code, Day No, Period No, Period Name,
Period Code, Load, Start Time, Finish Time, Period Guid`
80 rows = 10 cycle days × 8 periods/day. `Day Code` values are `Mon A` …
`Fri B`, i.e. the school runs a **10-day fortnightly (A/B week) cycle**, not
a plain Mon–Fri week. Period slots per day: `FR` (Fratelli, 10 min
homeroom/pastoral), `P1`–`P5` (60/58 min lessons), `FB`/`SB` (first/second
break, 0 load). `Load` is teaching-load minutes (0 for breaks), distinct
from wall-clock duration. `Period Guid` is the stable join key used inside
the `.tfx`/`.sfx` JSON.

**`Timetable Days.csv`**: `No, Day Name, Day Code` — the 10 day codes,
Day Name and Day Code are identical in this export.

**`Year Level Details.csv`**: 6 rows, Year Level Name/Code both `07`–`12`.

**`Roll Class Details.csv`**: 20 rows mapping Roll Class → Year Level (e.g.
`10A`→`10`), plus one non-standard row `"Rengagement Room"` (code `RTC`)
with blank year level — a pastoral/support roll group rather than a normal
class, see §5.

**`Yard Duty Areas.csv` / `Yard Duty Session Details.csv` / `Period and
Yard Duty Sessions.csv` / `Yard Duty Allocations.csv`**: define supervision
areas (e.g. "Angelo/Leo Roaming Before School"), the 4 daily duty windows
(before school, 2 breaks, after school) per cycle day, and which teacher
(by `Teacher Code`) is rostered to which area/session with a `Load` value.
This is a distinct sub-system from the teaching timetable but shares the
teacher code and period GUID join keys. Out of scope for the core analysis
engine (4.3) unless the school wants yard duty load folded into overall
teacher load — flagging as a question, see §5.

### 2.2 Entity tables

**`Teacher Details.csv`**: `No, Teacher Name, Teacher Code, First Name,
Middle Name, Family Name, Teacher Email, Spare1, Spare2, Spare3, Teacher
Guid`. `Teacher Code` (e.g. `DIXM02`) is the short code used in every other
file; `Teacher Guid` is the GUID used inside the `.tfx` JSON. `Spare1`
holds one of four values — `T`, `GC`, `SO`, `CLT` — almost certainly a
staff-category flag (Teacher / Guidance Counsellor / Support Officer /
College Leadership Team, guessed) but **not confirmed — ambiguous, see
§5**. `Spare2`/`Spare3` empty in this sample.

**`Student Details.csv`**: `No, Student Name, Student Code, First Name,
Middle Name, Family Name, Preferred Name, BOS Code, Gender, Roll Class,
Year Level, House, Home Group, Study Stream, Student Email, Submit Order,
Parent/Caregiver Email 1-4, Spare1-3, Student Guid`. `Student Code` is a
6-digit number, used as the join key in the eMinerva files and CSVs;
`Student Guid` is the JSON join key. `BOS Code`, `Study Stream`,
`Parent/Caregiver Email *`, `Spare1-3` are empty in this sample — present
in the schema but unpopulated for this export. **`House` values are
inconsistently cased** (`AQUA` vs `Aqua` etc. across rows) — a data-quality
issue to normalise on ingest, not a schema ambiguity.

### 2.3 The timetable grid

**`Master Timetable Cycle.csv`**: `No, Day Code, Period Code, Roll Class
Code, Class Code, Teacher Code, Room Code, Teacher Guid, Period Guid`.
2,143 data rows. This is the actual master grid: one row per
(day, period, class-offering) — i.e. every lesson that runs, for every
period it runs in, across the full 10-day cycle. This is the primary
source for clash detection, room utilisation, and teacher load.

**`Class List Cycle.csv`**: `No, Roll Class Code, Class Code, Student Code,
Student Guid`. 44,780 rows = exactly 560 students × 80 cycle periods (one
row per student per period-slot, not a deduplicated enrolment list — a
given student's fixed subject for a period repeats every time that period
recurs across the cycle). This is how student-level clash/attendance
checks and cohort travel analysis would be built, but it needs to be
reduced to distinct (student, class) pairs for enrolment purposes — see
data model note in §5.

## 3. Timetabling Solutions JSON exports (Version 10)

### 3.1 `.tfx` — Timetable Development file (master export)

`TT files/TT 2026 Term Three Week 4.tfx`, ~2.7 MB, single JSON object.
Top-level keys:

```
File ID, Settings, Days, Periods, YardDutySessions, YearLevels,
YardDutyAreas, Teachers, TeacherFiles, Faculties, UnscheduledDuties,
Meetings, Rooms, ClassNames, RollClasses, RURs, ClassGroups, MRCGs,
StudentFiles, YardDuties, Groups, Timetable, Students, PublishedTimetables
```

Everything is joined by GUID-style IDs (`TeacherID`, `RoomID`,
`ClassNameID`, `PeriodID`, `RollClassID`, `StudentID`, `CourseID`, …), which
correspond 1:1 to the `*Guid` columns in the CSV exports and are stable
across exports (confirmed by spot-checking a teacher's GUID in both
`Teacher Details.csv` and `Teachers[]` here).

Key sections for the data model:
- **`Timetable[]`** (2,181 entries): `{RollClassID, PeriodID, ClassNameID,
  RoomID, TeacherID}` — the master grid, JSON equivalent of `Master
  Timetable Cycle.csv` (slightly higher count — needs reconciling, see
  §5).
- **`ClassGroups[]`** (248): the actual "class offerings" — a roll class +
  block of periods, each with one or more `ClassGroupCourses[]`
  (`CourseID, TeacherID, RoomID, ClassNameID`), i.e. a class can have
  multiple teacher/room assignments (e.g. team-taught or split classes),
  and each course can carry `RoomTimetableEdits[]` — per-period room
  overrides (e.g. one lesson in that block relocated to a different room
  on a specific period). This is the structural source for "split
  classes" (4.3 gap analysis).
- **`Students[].StudentLessons[]`**: each student's actual list of
  `{RollClassCode, ClassCode, LessonType}` — three `LessonType` values
  occur across the file: `O`, `C`, `S`. Meaning unconfirmed — see §5.
- **`Faculties[]`**, **`RURs[]`** ("Room Utilisation Requirements" —
  confirmed a room-choice constraint, see §5 item 4), **`MRCGs[]`**
  ("Multi-Roll-Class Groups" — confirmed the option-line/blocking-pattern
  structure, see §5 item 4), **`Groups[]`** (period/column allocation
  scaffolding used internally by the timetabling software, not obviously
  needed for the analysis engine).
- **`Settings`** (1 record): school-wide load default and the school's
  own optimisation preferences (`OptimiseSpread`, `MaxDaySpread`,
  `Successive2Periods`, `Successive3Periods`) — parsed 2026-08-12,
  `docs/full-timetabler-plan.md` Phase A. `TeacherProposedLoad` is the
  fallback used when a teacher's own `LoadProposed` is `0` (TTS's "use
  the school default" convention, not "no load") — fixed a real bug
  where 30 of 74 teachers had `NULL` contracted load and were silently
  excluded from load analysis.
- **`UnscheduledDuties[]`**, **`Meetings[]`**, **`YardDuties[]`**: staff
  duties/meetings outside normal teaching load — relevant to teacher load
  analysis (4.3) if the school wants total load including these.
  Investigated 2026-08-12 alongside the Phase A work above and
  deliberately **not** parsed yet: in the real export, all 46
  `UnscheduledDuties[]` are template/definition rows referenced nowhere
  else in the file (zero actual assignments this term), and all 13
  `Meetings[]` carry `Load: 0` for every one of their 18 assigned
  teachers - both currently carry no incremental information for load
  analysis. `Meetings[]` does have real `{TeacherID, PeriodID}`
  assignments though, which could matter for availability/clash checks
  even at zero load - worth a real conversation with the school before
  parsing, not worth guessing at.
- **`PublishedTimetables[]`** (45 entries): metadata about past published
  snapshots (name, dates, archive) — likely just a version history, not
  needed for the current-state model.

### 3.2 `.sfx` — Student Options files (one per year level)

`TT files/YR 7–12 *.sfx`, 190 KB–370 KB each. Top-level keys:

```
File ID, Settings, Lines, Subjects, Options, Constraints, Classes,
Students, StudentFiles
```

This is a **different data set from the `.tfx`**: it's the subject
*selection/options* structure (elective lines, option blocks, class-size
caps, join/exclude constraints between options) used when students choose
subjects, not the resolved timetable. `Students[].StudentPreferences[]`
here lists `{OptionID, ClassID}` — a student's *selected* option/class,
which is presumably the input that produced the `StudentLessons[]` seen in
the `.tfx`.

**Now wired in** (added 2026-08-04, `backend/app/ingest/sfx_parser.py`):
every `.sfx` under the source folder is auto-discovered and ingested into
`sfx_line`/`sfx_subject`/`sfx_option`/`sfx_class`/`sfx_student_preference`/
`sfx_constraint` tables - namespaced `sfx_*` since the concepts overlap
with but differ from the `.tfx`-derived tables. Preferences link to the
existing `student` table by code; a code with no match (expected for a
next-year planning file) is kept by code only, never dropped. Cross-
validated against the real files: **every** student code across all six
`.sfx` files matched an existing student from the `.tfx` - zero
unlinked, a good sign the planning data and the resolved timetable are
in sync right now. See `docs/data-model.md`'s "Student Options data"
section and `docs/rules.md` for what this could unlock (option-line
constraint checks, "does the resolved timetable match what students
actually selected") - not built yet, this milestone is ingestion only.

### 3.3 `tester.tfx` (historical)

An earlier discovery pass found an empty template/test file at the
project root (`Days: []`, `Periods: []`). It's since been removed from
git entirely per `docs/privacy-threat-model.md` - tracking any `.tfx`
path risked becoming a real-data leak if it were ever overwritten
locally without updating `.gitignore`. Noted here only so the removal
isn't a mystery if you go looking for it.

## 4. eMinerva roll-marking export/import files

Both files are plain comma-delimited text with a quoted header row (same
dialect as the CSVs above, just `.txt` extension).

**`eMinervaTTable.txt`**: `Period, ClassName, Room, Teacher, SDayName,
FDayName, Subject, YearLevel`. 2,143 rows — same row count and same
(day, class, room, teacher) content as `Master Timetable Cycle.csv`, just
re-shaped for eMinerva's import format (`Period` here is the **period
number within the day, 1–8**). Checked across all 2,143 rows:
`SDayName` and `FDayName` are identical in every single row (start/finish
day fields exist for sessions spanning multiple days, but none do in this
dataset — likely safe to treat as one field for this school). `YearLevel`
is empty in **every** row — not populated in this export. This confirms
**eMinerva's timetable import is a straightforward re-projection of the
Timetabling Solutions master grid** — same entities, different column
layout, joined by the same `ClassName`/`Room`/`Teacher` short codes.

**`eMinervaSCourse.txt`**: `StudentCode, ClassName, YearLevel, FirstName,
LastName, MiddleName, Subject`. 6,726 rows, all distinct
`(StudentCode, ClassName)` pairs — i.e. **this is the deduplicated
student ↔ class enrolment list** (unlike `Class List Cycle.csv`, which
repeats each enrolment once per cycle occurrence). `StudentCode` matches
`Student Details.csv`'s `Student Code` format and values. Includes rows
for non-teaching "classes" like `BREAK-12`, `ASM-SOL2` (assembly, by
House), `GP-WB12` (pastoral/group period) alongside real subjects — these
share the same `Class Code` namespace as teaching classes and appear in
`Master Timetable Cycle.csv` too, so the data model needs a way to flag
"non-teaching period" rather than assume every class code is a lesson —
see §5.

**Relationship to Timetabling Solutions confirmed**: both eMinerva files
key off the exact same short codes (`Student Code`, `Teacher Code`, `Room
Code`, `Class Code`, `Day Code`) as the Timetabling Solutions CSV exports —
no separate ID scheme, no fuzzy matching needed. The eMinerva files are a
strict subset/re-projection of the Timetabling Solutions master data, not
an independently-sourced system.

## 5. Ambiguities

Resolved with the school (2026-08-03):

1. **`Teacher Details.csv` `Spare1`** — confirmed staff-category flag:
   `T` = Teacher, `GC` = Guidance Counsellor, `SO` = Support Officer,
   `CLT` = College Leadership Team.
2. **Non-teaching period codes** — confirmed meanings: `BREAK-*` = break
   time, `ASM-*` = assembly, `GP-*` = "general purpose" (used as an
   early-leave/study block for Year 11/12), `"Rengagement Room"` roll
   class = the school's detention room. These are real, schedulable
   entries but are **not lessons** — the data model needs an explicit
   category (see `EntryType` in `docs/data-model.md`) rather than
   inferring "is this teaching" from the code text.

Still open (default assumption noted, revisit if wrong):

3. **Room `Seats = 0`** (13 of 51 rooms) — assuming this means "no fixed
   capacity / not used for capacity checks" (meeting rooms, quiet study,
   engineering workshops) rather than unentered data. Room-capacity-
   mismatch checks (4.3) will skip these rooms under this assumption.
4. ~~**`RURs[]` and `MRCGs[]`** in the `.tfx`~~ — **both resolved and
   now parsed** (2026-08-12, `docs/full-timetabler-plan.md` Phase A).
   MRCGs, cross-referenced against `Timetabler Export/import data/2026
   Blocking Pattern.xlsx` (added 2026-08-03): the spreadsheet's "LINE 1",
   "LINE 2"... column structure (subjects that run in parallel so
   students can pick one per line) matches the MRCG `DefaultCode` naming
   pattern exactly (`"12 A"`, `"12 B"`, `"10A B"`, etc. = year level +
   line letter). MRCGs are **option-line/blocking-column groupings**, not
   composite-class markers (see item 9 below - a different, real
   phenomenon this file doesn't explicitly encode) - now in `blocking_line`/
   `blocking_line_class_group`. `RURs[]` ("Room Utilisation
   Requirements") confirmed by tracing a real `RURReferences[].ReferencesID`
   value to `ClassNames[].ClassNameID`: a room-choice constraint - "one of
   these classes must use one of these rooms" - now in `room_pool`/
   `room_pool_room`/`room_pool_class_name`.
5. **`StudentLessons[].LessonType`** (`O`, `C`, `S`) — likely
   Option/Core/Support given the school runs elective lines, but treated
   as an opaque passthrough field in v1 rather than relied upon for any
   check.
6. ~~**`Master Timetable Cycle.csv` (2,143 rows) vs `.tfx` `Timetable[]`
   (2,181 entries)**~~ — **Resolved by cross-validation** (see
   `backend/app/ingest/csv_validate.py`). The gap is exactly the 38
   `Timetable[]` entries with no `ClassNameID` assigned at all — the CSV
   export omits these, the `.tfx` doesn't. Ingesting the `.tfx` and
   diffing against the CSV leaves zero unexplained rows on either side.
   One extra quirk found in the process: `Master Timetable Cycle.csv`
   writes the literal string `<Blank>` (not an empty cell) for a missing
   Teacher Code or Room Code in a handful of rows — the ingester
   normalises this to match the `.tfx`'s empty-string convention.
7. **Cycle semantics**: assuming the A/B week alternates on a fixed
   calendar pattern (e.g. odd/even ISO week number) until told otherwise
   — needed to map "Mon A"/"Mon B" onto real calendar dates.
8. **Yard duty data** — kept as a separate concern from teaching load in
   v1's teacher load analysis (4.3), not summed into it, since it's a
   distinct sub-system. Easy to fold in later if wanted.
9. **Composite classes** (flagged by the school 2026-08-04, e.g. `9GEO`
   and `10GEO`) — confirmed real and not rare: scanning the `.tfx`
   `Timetable[]` for slots where the same teacher + room are shared
   across periods but the `ClassNameID`/roll class differ finds **101
   period-slots across ~14 distinct class-code groupings** (e.g.
   `09GEO1`+`10GEO1` both taught by the same teacher in the same room at
   five matching periods across the cycle; similar patterns for STU/STUX
   study blocks, PE, Drama, and several Year 11/12 VET subjects pairing
   with Year 12/11 equivalents). Nothing in the `.tfx` marks these as a
   single physical lesson — they're stored as fully separate
   `ClassGroupCourse`/`Timetable[]` records that happen to coincide on
   teacher+room+period, which is exactly what happens when small-enrolment
   classes across year levels are physically merged. Cross-checked
   against `2026 Blocking Pattern.xlsx`: it confirms low individual class
   sizes for the `GEO` pair (9 and 11 students) consistent with why
   they'd be merged, but the spreadsheet doesn't explicitly flag the
   merge either — it has to be inferred from the resolved schedule.
   **Data model impact**: clash detection, teacher load, and room
   utilisation all need to treat a detected composite group as one unit,
   not double/triple-count it as simultaneous separate bookings. See
   `docs/data-model.md`'s composite-class section.

## 6. Anonymised sample snippets (fabricated, illustrative only)

Master Timetable Cycle.csv row shape:
```
No,Day Code,Period Code,Roll Class Code,Class Code,Teacher Code,Room Code,Teacher Guid,Period Guid
1,"Mon A",FR,10A,10ENG1,SMIJ01,ANG3,{GUID},{GUID}
```

Teacher Details.csv row shape:
```
No,Teacher Name,Teacher Code,First Name,Middle Name,Family Name,Teacher Email,Spare1,Spare2,Spare3,Teacher Guid
1,"Smith Jordan",SMIJ01,Jordan,,Smith,jordan.smith@example.edu.au,T,,,{GUID}
```

Student Details.csv row shape:
```
No,Student Name,Student Code,First Name,...,Roll Class,Year Level,House,Home Group,...
1,"Doe Alex",100001,Alex,...,10A,10,AQUA,AQU1,...
```

eMinervaSCourse.txt row shape:
```
StudentCode,ClassName,YearLevel,FirstName,LastName,MiddleName,Subject
"100001","10ENG1","10","Alex","Doe","","10ENG"
```
