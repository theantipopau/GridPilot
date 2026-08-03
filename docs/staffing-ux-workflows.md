# Staffing UX Workflows

Maps the addendum's UI sections (1, 9, 10) and the supplied
`docs/design/ui-mockup.png` against what the frontend actually has today,
and what the next vertical slice (addendum Step C/D) needs to add.

## Current state (as of this doc)

`frontend/src/App.tsx` is a single page: a header, one filter bar
(teacher/room/roll class), and a two-week timetable grid. No routing, no
sidebar, no People section, no per-teacher profile page - none of the
navigation structure the mockup shows exists yet.

The mockup depicts a considerably larger product: a left sidebar (Home,
Imports, People, Roles & Release, Classes, Students & Cohorts, Rooms,
Timetable, Scenarios, Constraints, Findings, AI Advisor, Exports,
Settings, Audit), a scenario selector, a Lesson Inspector side panel, a
teacher profile page, and a Scenarios comparison view. Building all of
that is a much larger effort than the capability addendum alone - this
doc scopes down to just what the addendum's Step C/D vertical slice
needs, using the mockup purely as the visual/branding reference for how
it should look, not a commitment to build every screen shown in it right
now.

## Vertical slice this addendum needs (addendum Section 16, Step C/D)

```
People → Teacher list → Teacher profile → Teaching capability tab
  → Add subject/faculty capability (form: subject, year range, capability, preference, source, effective-from, notes)
  → Mark existing capability eligible/preferred
  → Preview which requirements gain/lose eligible teachers before saving
  → Save + see it reflected in the profile

Classes → Requirement (or class) → Eligible teachers panel
  → See ranked candidate list (preference, remaining capacity, reasons)
  → Set preferred or required teacher
  → Preview load/feasibility impact
  → Save
```

This requires, at minimum, introducing **routing** (currently none) and
a **People section** as the first new area of the app, before the
Classes-side staffing panel makes sense to build - the addendum's own
sequencing (Step C before Step D) agrees with this order.

## Screen-by-screen mapping

### Teacher profile (addendum Section 1, mockup bottom-left)

Tabs shown in the mockup: Profile, Employment & Load, Roles & Release,
Capabilities, Availability, Classes, History.

Of these, only **Employment & Load** has a real data source today
(`teacher.contracted_load_minutes`, and it's a single number, not the
mockup's granular breakdown - see open question 3 in
`docs/staff-capability-model.md`). **Capabilities** is what this addendum
adds. The rest (Roles & Release, Availability, History/audit) aren't
addressed by this addendum and have no backing data yet - out of scope
until raised separately.

Propose building **Capabilities** first (it's what this addendum is
for), with Profile/Employment & Load as the minimum surrounding shell
needed to reach it via navigation, rather than the full seven-tab page.

### Capability editor (addendum Section 1)

```
Subject area / Curriculum course   [ dropdown, sourced from faculty/subject ]
Year range                          [ two selects, min/max year level ]
Capability                          [ Eligible | Not eligible | Review required ]
Preference                          [ Required | Strongly preferred | Preferred | Neutral | Fallback | Avoid ]
Evidence/source                     [ Imported | School-confirmed | Staff-declared | Current-timetable-inferred ]
Effective from                      [ planning year ]
Notes                               [ optional text ]
```

Maps directly onto the `teacher_capability` table proposed in
`docs/staff-capability-model.md`. The "preview affected scenarios"
step (addendum: "Before saving, preview affected scenarios and any
classes that gain or lose eligible teachers") needs the
`CapabilityService.resolve()` re-run against all current
`teaching_requirement` rows for that teacher's subjects before commit -
a real computation, not a static preview.

### Eligible teacher picker / requirement staffing panel (addendum Section 9)

```
{Requirement label}
{periods_per_cycle} periods per cycle · {priority label}

Required teacher: {name}  [Locked]              -- if REQUIRED preference exists
-- or --
Candidate teachers
✓ {name}   {preference label}   {remaining_capacity} min remaining
✓ {name}   {preference label}   {remaining_capacity} min remaining
× {name}   Not eligible

Staffing health: {risk label}
Reason: {structured reason, not free text}
```

Backed by `GET /api/requirements/{id}/eligible-teachers` and
`GET /api/requirements/{id}/staffing-health` (addendum Section 13) -
both callable once `CapabilityService` exists, independent of any solver.

### Staffing matrix (addendum Section 10)

```
                 Y7 Maths  Y8 Maths  ...  Modern History
Teacher A           ✓         ✓              ★
Teacher B           ✓         ✓              ○
```

A bulk-editing grid across all teachers × subjects. Useful, but explicitly
lower priority than the single-teacher and single-requirement flows above
- the addendum's own Step C/D sequencing puts per-teacher and
per-requirement editing first. Legend must not rely on colour/symbol
alone (addendum's explicit accessibility requirement) - needs visible
text labels alongside `★ / ✓ / ○ / ×`.

## AI advisor boundary (addendum Section 11)

Once the AI advisor layer is built (still pending - see
`docs/data-model.md`'s architecture decisions), it must never be the
thing deciding capability or preference. Acceptable: "show teachers
confirmed for junior Mathematics," "explain why Matt wasn't selected for
Year 7 Mathematics 3" (from stored `reasons`, not invented). Not
acceptable: inferring capability from anything (emails, informal
signals) or ranking teachers by perceived quality. Every AI-drafted
capability entry is created as `REVIEW_REQUIRED` and never auto-confirmed.

## What's deliberately not addressed here

- Scenarios, Constraints (as a distinct screen from Findings), Imports,
  Students & Cohorts, Rooms-as-a-section, Exports, Settings, Audit - all
  visible in the mockup, none in scope for this addendum. Each would need
  its own scoping pass before being built.
- The Lesson Inspector's "Composites" field in the mockup - directly
  relevant to `docs/data-model.md`'s composite-class detection work, but
  a separate, smaller piece that doesn't depend on the capability model.
