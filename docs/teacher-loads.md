# Teacher loads

A whole-staff view of who is carrying how much, built on the same numbers
the `teacher_over_contracted_load` finding judges - so this page and the
Findings page cannot disagree. Backend: `app/analysis/teacher_loads.py`
(`GET /api/teacher-loads`); page: `frontend/src/pages/TeacherLoadsPage.tsx`.

## What it shows

Per teacher: minutes scheduled against contracted minutes (a bar with a tick
at 100% - an over-contract teacher visibly pokes past it), minutes remaining,
and how the load falls across the cycle (one small column per day of the
10-day cycle, so a teacher with five lessons on Monday and one on Tuesday
looks different from an evenly spread one at a glance). Expanding a row adds
teaching periods, class and subject counts, year levels, hours per cycle, FTE
and leadership release where they've been entered, and a link to that
teacher's timetable.

Above the list: a summary strip (how many are timetabled, median load, most
loaded, number over contract) and a distribution of teachers by percent of
contracted load. Clicking a bar lists just those teachers. Sort by load,
minutes remaining, subjects taught or name; filter by faculty or "over
contract only"; the list defaults to teaching staff (`staff_category =
TEACHER`) with an "All staff" switch.

## What counts, and what deliberately doesn't

- **Scheduled minutes are distinct (teacher, period) slots.** A composite
  lesson - several class codes sharing one physical lesson - counts once,
  however many codes share it. Same method as the load rule.
- **Contact entry types come from `contact_time.py`**: `LESSON` only until a
  school confirms a wider definition in the staffing policy. The page states
  which types it is counting.
- **No "under-loaded" or "balanced" label.** That would be an invented policy
  threshold, which this project has refused throughout (`docs/roadmap-v3.md`
  section 8). The page reports facts - contracted, scheduled, remaining, spread
  - and leaves judgement to the people reading it.
- **Remaining is not "available to teach more".** Part-time fractions,
  leadership release, duties, meetings and yard duty aren't counted, because
  the school hasn't confirmed whether they count toward load
  (`docs/full-timetabler-plan.md` section 4.1). The page says so under the list.

## First real numbers (T4 2026, imported 2026-10-05)

40 teaching staff, 39 timetabled; none over contract; median 74% of
contracted load, range 12%-93%; the most-loaded five all sit at 2,400 of
2,580 minutes. HENE04 is the outlier on breadth: 18 classes across 11
subjects, where the median timetabled teacher has 6 classes and 5 subjects and
the next highest has 10 and 10. (The class count includes every class code
attached to a shared lesson, so a teacher running composite blocks reads high.)

## Not built

- A per-teacher 10x5 period grid inside the expanded row (the existing
  single-entity timetable already shows it; the row links there instead).
- Loads for a *proposed* change set or solver run - this reads the live
  timetable only.
- Faculty roll-ups: TTS staff belong to several overlapping faculties
  (including pseudo-faculties like DUTIES and Teachers), so summing by
  faculty would double-count people.
