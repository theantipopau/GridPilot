# Master Timetable

The Timetable tab's default view: every lesson in the school, all days, at
once - not just one teacher/room/roll class at a time. Requested directly
("actually seeing the master timetable, all lessons across all days")
after the per-entity `GET /timetable` view (still available as "Single
entity") proved too narrow for spotting patterns across the whole school.

## Backend

`GET /timetable/all` (`backend/app/api/timetable.py`) returns every
`timetable_entry` row, unfiltered - same columns as the existing
per-entity `GET /timetable`, now shared via `TIMETABLE_ENTRY_COLUMNS`/
`TIMETABLE_ENTRY_JOINS` so the two endpoints can't drift apart. Against
the real Sophia College data that's 2,181 entries across 74 teachers, 51
rooms, and 20 roll classes - small enough to fetch once and group
client-side with no pagination or virtualization needed.

## Frontend

`MasterTimetableGrid.tsx` renders one row per entity of a chosen **axis**
(Room by default, switchable to Teacher or Roll class) against day/period
columns - the classic timetabler's grid, not a per-entity card view. Row
count and column count come straight from `reference` (already loaded);
the grid only groups the entries fetched from `/timetable/all` by
`{axisCode}|{day_code}|{period_no}`.

Clash detection reuses the exact same rule as the single-entity grid: more
than one entry in a cell is a real clash *for that row's entity* (a room
can't hold two classes at once; a teacher can't teach two at once) -
that's the whole reason the axis matters, not just cosmetic grouping. A
clashing cell gets a red ring and background, matching `TimetableGrid.tsx`'s
existing convention.

Clicking any lesson opens the same `LessonInspector` and change-set flow
used by the single-entity view - `LessonInspector` was already
entity-agnostic (keyed by `entry_id`, not by which axis you were looking
through), so no changes were needed there to support editing from the
master grid.

## Why Room is the default axis

Asked directly; the answer was Room - "the classic timetabler's master
view. A clash is immediately visible as two lessons stacked in one cell."
Switching to Teacher or Roll class is one dropdown away.
