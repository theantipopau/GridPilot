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

Clash highlighting is finding-backed, not grid-derived - see "Conflict
highlighting is finding-backed, not a grid heuristic" below. Multiple
entries can still land in one cell (a composite/parallel class, most
commonly); that's shown as a small vertical stack, without implying an
error on its own.

Clicking any lesson opens the same `LessonInspector` and change-set flow
used by the single-entity view - `LessonInspector` was already
entity-agnostic (keyed by `entry_id`, not by which axis you were looking
through), so no changes were needed there to support editing from the
master grid.

## Why Room is the default axis

Asked directly; the answer was Room - "the classic timetabler's master
view. A clash is immediately visible as two lessons stacked in one cell."
Switching to Teacher or Roll class is one dropdown away.

## Pending moves render live, not as a marker (2026-08-12)

Proposing a move used to only ring the entry's *original* cell amber -
the entry never actually appeared at its new slot, so there was no way to
see the move (or a clash it created) on the grid itself. Real feedback:
*"if i do move something ... it needs to move interactively on the
timetable."*

`frontend/src/lib/pendingMoves.ts` relocates a pending entry to its
proposed day/period/room/teacher before rendering. This needed more than
overwriting the code fields - grid grouping keys off `day_code` +
`period_no` (not just the codes), and cell display uses `room_name`/
`teacher_first_name`/`teacher_last_name`, so all of it is recomputed from
`reference` (days/periods/rooms/teachers), not just the four fields the
move actually touched. The underlying assumption - that a proposed
change's `after` endpoint is always fully resolved, never a partial diff
- was verified directly against the live API (`app/changes/service.py`'s
`add_proposed_change` fills in any unspecified field from the entry's
current value) before relying on it, rather than assumed from reading the
code alone.

Applies to both `MasterTimetableGrid` and `TimetableGrid` - the transform
happens once in `TimetablePage.tsx`, upstream of whichever grid is
rendering.

## Faculty colour coding (2026-08-12)

Real feedback after the Phase 0 trial-import success: *"UI still needs
significant work. colors would help."* Cells are now colour-coded by
faculty, `frontend/src/lib/facultyColors.ts` + `FacultyLegend.tsx`.

The categorical palette is capped at 8 fixed hues (never a generated 9th
- see the dataviz skill), and this school has ~19 faculties, so this
needed real-data grounding before implementation, not just an 8-into-19
guess: only 10 faculties have any scheduled lessons at all, and the top 8
by lesson volume cover 98.5% of faculty-tagged lessons. Those 8
(`SCI`/`Math`/`Eng`/`RE`/`DT`/`Arts`/`PE`/`HUM`) get a **fixed** color
each - fixed by faculty code, not recomputed by volume rank each render,
so a future term's import can't repaint which subject is which color.
Everything else, including the **31% of LESSON entries that have no
faculty recorded at all** in the source data (mostly VET/extension
subjects - checked, not guessed: `docs/data-formats.md` §3.1) falls to a
neutral grey "Other" rather than an invented 9th hue.

The exact 8 hex values are the dataviz skill's documented default
palette, re-validated against this app's white surface before use:
`node scripts/validate_palette.js "<8 hexes>" --mode light --surface
"#ffffff"` - passes, with 3 slots (aqua/yellow/magenta) landing below
3:1 contrast and requiring a "relief" channel per the skill's rule. That
relief is satisfied by construction here: every cell always shows its
class code as visible text, never relies on the color alone to identify
what's in it - a `FacultyLegend` is also always shown alongside the
grids, since the skill requires one for any ≥2-series categorical
palette even when direct labels are present too.

Applied as a `border-left` accent (full hue) plus a low-alpha tinted
background (`${hex}1f`, ~12%) rather than a solid saturated fill, so
lesson text stays legibly dark-on-near-white - a deliberate departure
from Timetabling Solutions' own solid-fill-plus-white-text convention
(visible in a real screenshot during this work), traded for legibility
at this cell size rather than matched exactly.

## Conflict highlighting is finding-backed, not a grid heuristic (2026-08-13)

The grid used to flag a "clash" purely structurally: more than one entry
landed in the same `{row}|{day}|{period}` cell. That was wrong in both
directions - it missed real problems the structural check can't see at
all (`student_double_booking`, since a student's overlapping classes
usually sit in *different* rows/roll-classes; `room_capacity_exceeded`,
which isn't about two entries sharing a cell), and it falsely flagged
**approved composite/parallel classes**, which legitimately put two class
codes in one room/period on purpose.

`frontend/src/lib/findingHighlights.ts` replaces the heuristic with the
real thing: an index built from the same `GET /findings?status=OPEN` data
the Findings tab uses, keyed by `{day_code}|{period_code}|{entity_type}:
{code}` for every open finding that carries `slot_refs` (teacher/room/
student double-booking, room capacity - the four rule types that mean
something at the level of one lesson). Findings with no `slot_refs`
(`class_room_instability`, `teacher_over_contracted_load`, ...) describe
a whole class or teacher, not one cell, so a grid can't usefully show
them and they're deliberately excluded rather than highlighting every
lesson of an affected class.

Each rendered lesson checks up to three keys (its teacher, room, and
class code at that slot) and merges to the worst severity and the union
of matching finding titles - a lesson can be both a teacher
double-booking *and* over room capacity at once, and both should surface.
Verified against real data: the approved `NEAR01`/`GRE1` composite
(12DRA1 + 11DRA1) shows no ring anywhere in the cycle, while a genuinely
unresolved room clash at the *same* room (`BON07`, Tues A P4, where an
approved 5-class composite collides with two unrelated classes taught by
a different teacher) correctly rings red with both the teacher- and
room-double-booking titles in its tooltip.

Ring colour is severity-based (`ring-red-500` critical, `ring-orange-500`
warning) via `HIGHLIGHT_RING`, distinct from the amber ring already used
for a pending proposed move - when a lesson is both, pending wins the
ring (it's the more actionable signal in the moment) but the finding
titles are still appended to the tooltip either way. The index is built
once per Timetable page visit, not refetched as the user proposes moves:
findings only reflect the last rules-engine run against the *approved*
timetable, and nothing in a pending change set is written until it's
approved elsewhere (Change Sets page), so there's nothing new for the
rules engine to have seen yet.
