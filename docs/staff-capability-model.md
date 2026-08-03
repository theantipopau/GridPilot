# Staff Capability Model — mapped against the existing schema

Maps the "Staff Teaching Capability, Preferences and Allocation Priority"
addendum (`claude-code-staff-capability-and-allocation.md`, added
2026-08-04) onto the schema already built (`docs/data-model.md`,
`backend/app/db/schema.sql`). Written before any new tables are created,
per the addendum's own Step A and this project's working style of
proposing a model and pausing for sign-off first.

## The core gap: requirements vs. resolved schedule

Everything built so far (`docs/data-model.md`) describes an **already
resolved** timetable: `TimetableEntry` says what *is* happening, in a
specific room, at a specific period, taught by a specific teacher - built
by ingesting Timetabling Solutions' output.

The addendum assumes a **`TeachingRequirement`** concept: an abstract
statement of demand ("this roll class needs N periods/cycle of Modern
History") that exists *before* a teacher or room is assigned to it - the
input a solver consumes, not the output. **We don't have this table yet.**
It's the single biggest net-new piece, and everything else in the
addendum (capability resolution, preferences, scarcity, solver
integration) is built on top of it.

Two ways to get `TeachingRequirement` rows to work with:

1. **Bootstrap from the resolved timetable** (recommended for v1): for
   every existing `ClassGroupCourse`, generate one `TeachingRequirement`
   whose `periods_per_cycle` equals what's already scheduled for it, and
   whose `assigned_teacher_id`/`assigned_room_id` are set to the current
   allocation. This makes the whole capability/preference/staffing-health
   layer immediately useful against real data - "who's eligible for this
   class," "is Matt's allocation valid," "what's the staffing health of
   9GEO" - **without needing a solver at all**. Composite classes (see
   `docs/data-model.md`) should collapse to one `TeachingRequirement` per
   `CompositeGroup`, not one per member class code, or scarcity/load
   numbers double-count.
2. **Author from scratch for a future planning year** (e.g. 2027) once
   the school wants to build next year's timetable rather than analyse
   this year's - this is where a real solver (addendum Section 6-8)
   becomes necessary, and is a substantially larger, separate build.

This doc addresses (1). The solver (addendum Steps E onward) is out of
scope until (1) is built, used, and confirmed useful on its own.

## Schema mapping

| Addendum concept | Existing table | Verdict |
|---|---|---|
| Learning area (`subject_area` top level) | `faculty` | Reuse as-is. 19 faculties already ingested (Humanities, Mathematics, Science, English, HPE, Religion, Arts, Design Tech, Languages, Study, Sport, ...). |
| Subject / curriculum course | `subject` | **Collapse two addendum levels into one.** Timetabling Solutions' `SubjectCode`/`SubjectName` is already course-grained (`11MHIS` = "Modern History", `11GMA` = "General Mathematics", not a broad "History"/"Mathematics" bucket) - there's no natural intermediate "subject" node distinct from "course" in the source data. Propose using `subject` directly as the addendum's `curriculum_course`, and **not** introducing a separate `curriculum_course` table, unless you tell me the school actually distinguishes them (e.g. "History" as a thing separate from "Modern History" for capability purposes) - flagging rather than assuming. |
| Year range on a course | *(missing)* | **Net new.** `subject` has no year-level range today - it's implicit per `class_name`/`class_group` instance, not stored at the subject level. Need `minimum_year_level`/`maximum_year_level` columns (nullable - not every subject is year-range-bound, e.g. senior-only VET certs). |
| Specific class offering | `class_name` + `class_group_course` | Reuse as-is. |
| `teacher_capability` | *(missing)* | **Net new**, matches addendum's proposal closely. FK to `subject_area` (`faculty`) OR `subject` (course), not both required - matches the addendum's `CHECK (subject_area_id IS NOT NULL OR curriculum_course_id IS NOT NULL)`. |
| `TeachingRequirement` | *(missing - see above)* | **Net new, foundational.** Bootstrap-generated from `ClassGroupCourse` for v1. |
| `requirement_teacher_preference` | *(missing)* | **Net new**, depends on `TeachingRequirement` existing first. |
| Teacher | `teacher` | Reuse as-is. Already has `contracted_load_minutes` (addendum's "net teaching capacity" - close enough to reuse; addendum's mockup shows this broken down further, see load breakdown below). |

## Proposed new tables (additive - nothing existing changes shape)

```sql
ALTER TABLE subject ADD COLUMN minimum_year_level INTEGER;
ALTER TABLE subject ADD COLUMN maximum_year_level INTEGER;

CREATE TABLE teaching_requirement (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL CHECK (source IN ('BOOTSTRAPPED_FROM_TIMETABLE', 'AUTHORED')),
    class_group_course_id INTEGER REFERENCES class_group_course(id),  -- set when source = BOOTSTRAPPED_FROM_TIMETABLE
    composite_group_id INTEGER REFERENCES composite_group(id),        -- set instead, when this requirement covers a composite
    roll_class_id INTEGER REFERENCES roll_class(id),
    subject_id INTEGER NOT NULL REFERENCES subject(id),
    periods_per_cycle INTEGER NOT NULL,
    assigned_teacher_id INTEGER REFERENCES teacher(id),
    assigned_room_id INTEGER REFERENCES room(id),
    lock_status TEXT NOT NULL DEFAULT 'UNLOCKED' CHECK (lock_status IN ('UNLOCKED', 'LOCKED')),
    allocation_priority TEXT CHECK (allocation_priority IN ('CRITICAL', 'HIGH', 'STANDARD', 'FLEXIBLE')),
    planning_year TEXT NOT NULL,
    CHECK (class_group_course_id IS NOT NULL OR composite_group_id IS NOT NULL)
);

CREATE TABLE teacher_capability (
    id INTEGER PRIMARY KEY,
    teacher_id INTEGER NOT NULL REFERENCES teacher(id),
    faculty_id INTEGER REFERENCES faculty(id),
    subject_id INTEGER REFERENCES subject(id),
    minimum_year_level INTEGER,
    maximum_year_level INTEGER,
    capability_status TEXT NOT NULL CHECK (capability_status IN ('ELIGIBLE', 'NOT_ELIGIBLE', 'REVIEW_REQUIRED')),
    default_preference TEXT NOT NULL DEFAULT 'NEUTRAL'
        CHECK (default_preference IN ('REQUIRED', 'STRONGLY_PREFERRED', 'PREFERRED', 'NEUTRAL', 'FALLBACK', 'AVOID')),
    source_type TEXT NOT NULL CHECK (source_type IN ('IMPORTED', 'SCHOOL_CONFIRMED', 'STAFF_DECLARED', 'CURRENT_TIMETABLE_INFERRED')),
    source_reference TEXT,
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (faculty_id IS NOT NULL OR subject_id IS NOT NULL)
);

CREATE TABLE requirement_teacher_preference (
    id INTEGER PRIMARY KEY,
    teaching_requirement_id INTEGER NOT NULL REFERENCES teaching_requirement(id),
    teacher_id INTEGER NOT NULL REFERENCES teacher(id),
    preference TEXT NOT NULL
        CHECK (preference IN ('REQUIRED', 'STRONGLY_PREFERRED', 'PREFERRED', 'NEUTRAL', 'FALLBACK', 'AVOID')),
    is_locked INTEGER NOT NULL DEFAULT 0,
    reason TEXT,
    source_reference TEXT,
    effective_from TEXT,
    effective_to TEXT,
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL
);
```

Matches the addendum's shapes closely (TEXT ids swapped for INTEGER to
match this project's existing surrogate-key convention rather than mixing
key styles; `subject_area_id`/`curriculum_course_id` renamed to
`faculty_id`/`subject_id` to match the existing table names they map to).

Per the addendum's own instruction: `CURRENT_TIMETABLE_INFERRED` capability
rows must always resolve to `REVIEW_REQUIRED`, never automatic eligibility
- enforced in `CapabilityService.resolve()`, not by a DB constraint alone
(a DB check can't see the resolution-time distinction between "inferred,
unreviewed" and "inferred, since confirmed").

## `CapabilityService.resolve()` - precedence, mapped to SQL joins

The addendum's six-step precedence (requirement lock → requirement
preference → exact course+year → faculty+year-range → parent faculty →
unmatched = not eligible) becomes, in practice, an ordered set of queries
against `teacher_capability` filtered by `effective_from`/`effective_to`,
returning the *most specific* active match:

1. `requirement_teacher_preference` where `teaching_requirement_id` = this
   requirement and `is_locked` = 1 → done, `REQUIRED`, skip everything else.
2. `requirement_teacher_preference` (unlocked) for this requirement → use
   its `preference` value.
3. `teacher_capability` where `subject_id` = this requirement's subject
   and year range covers the roll class's year level.
4. `teacher_capability` where `faculty_id` = this subject's faculty and
   year range covers the roll class's year level (broader match).
5. No match → `NOT_ELIGIBLE`, not `REVIEW_REQUIRED` - the addendum is
   explicit that missing data means excluded, not silently allowed.

Specificity ties (e.g. two `subject_id`-level rules, one `ELIGIBLE` one
`NOT_ELIGIBLE`, both active) become a `capability_rule_conflict` finding
per addendum Section 12, not a silent pick.

This resolves once, in one Python service (`app/analysis/capability.py`,
to be built), called by the API, the findings engine, and later the
solver - never duplicated as raw SQL in more than one place, per the
addendum's explicit instruction.

## Open questions before building this

1. Does the school actually distinguish "subject" from "course" (e.g.
   would "History" ever need a capability rule broader than any specific
   history course)? Assumed no for now - see table above.
2. Where does authoritative capability data come from initially? The
   addendum says "must be confirmed or imported from an authoritative
   source," not inferred from the current timetable alone. Is there an
   existing staff list (e.g. in the HR/admin system, or one of the
   `import data` spreadsheets) with subject qualifications, or does this
   start empty and get built up teacher-by-teacher through the UI?
3. `contracted_load_minutes` on `teacher` today comes straight from the
   `.tfx` `LoadProposed` field. The mockup's load breakdown (Ordinary
   Class Contact, Fratelli, Middle Leadership Release, PPCT Entitlement,
   Yard Duty, Supervision, Replacement Cover) is far more granular than
   anything in the source export - none of those categories exist in the
   Timetabling Solutions or eMinerva data. Confirm whether this
   granularity needs to be entered/maintained separately in GridPilot, or
   whether there's another source system for it.
