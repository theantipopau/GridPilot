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
- **`Faculties[]`**, **`RURs[]`** ("Room Utilisation Requirements"? —
  name/purpose inferred from field shape, not confirmed — see §5),
  **`MRCGs[]`** ("Multi-Roll-Class Groups"? — groups of ClassGroups,
  purpose inferred — see §5), **`Groups[]`** (period/column allocation
  scaffolding used internally by the timetabling software, not obviously
  needed for the analysis engine).
- **`UnscheduledDuties[]`**, **`Meetings[]`**, **`YardDuties[]`**: staff
  duties/meetings outside normal teaching load — relevant to teacher load
  analysis (4.3) if the school wants total load including these.
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
the `.tfx`. The `.sfx` files are **not required** for the core clash/
utilisation/load analysis (4.3) since the `.tfx` already has resolved
lesson assignments — but they may be useful later for validating that the
resolved timetable actually matches what students selected, or for a
future "what-if" subject-change feature. Recommend treating `.sfx` as
out-of-scope for v1 unless you want that cross-check.

### 3.3 `tester.tfx` (root of project folder)

Same file shape as §3.1 but `Days: []` and `Periods: []` — an empty
template/test file, not live school data. Not part of the data model.

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

## 5. Ambiguities to confirm before building the data model

1. **`Teacher Details.csv` `Spare1`** (`T`, `GC`, `SO`, `CLT`) — guessed as
   a staff-category flag; needs confirming, and full meaning of each code.
2. **Room `Seats = 0`** (13 of 51 rooms) — does this mean "no fixed
   capacity / not used for capacity checks" (e.g. meeting rooms, quiet
   study, engineering workshops), or is it just unentered data? Affects
   whether room-capacity-mismatch checks (4.3) should skip these rooms.
3. **`RURs[]` and `MRCGs[]`** in the `.tfx` — field shapes suggest "Room
   Utilisation Requirements" and "Multi-Roll-Class Groups" but the actual
   semantics/purpose aren't confirmed from the data alone.
4. **`StudentLessons[].LessonType`** — three values occur (`O`, `C`, `S`);
   need to know what they mean (e.g. Option/Core/Support?) before relying
   on this field to distinguish lesson types.
5. **`Master Timetable Cycle.csv` (2,143 rows) vs `.tfx` `Timetable[]`
   (2,181 entries)** — small count mismatch between the two exports of
   what should be the same grid. Needs reconciling (likely the JSON
   includes rows the CSV export filters out, e.g. unassigned/incomplete
   entries) before treating either as sole ground truth.
6. **Non-teaching period codes** (`BREAK-*`, `ASM-*`, `GP-*`, and the
   `"Rengagement Room"` roll class) appear in the same fields as real
   classes throughout — the data model needs an explicit
   is-this-a-real-lesson flag rather than inferring it from code
   patterns, since the pattern isn't formally documented anywhere in the
   files.
7. **Cycle semantics**: confirm the A/B week actually alternates on a
   fixed calendar pattern (e.g. odd/even week number) — needed to map
   "Mon A" vs "Mon B" onto real calendar dates for the UI and for any
   date-aware features.
8. **Yard duty data** — confirm whether yard duty/meeting/unscheduled-duty
   load should count toward "teacher load" in the analysis engine (4.3),
   or stay a separate concern.

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
