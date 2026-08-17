# Roadmap v2 — staffing, generation, and the interface

*Written 2026-08-17. A follow-up to `docs/full-timetabler-plan.md`, which
remains the architectural spine (write tiers, phase gating, the "what we
won't build" list). This document covers the ground that plan doesn't:
the **staffing/industrial layer**, **authoring** (students, staff, rooms,
blocking), and a concrete **design-system pass** on the interface.*

*Like every other plan in this repo, this is a set of recommendations
with the evidence attached — not a commitment to build all of it, and
explicitly not permission to guess any value marked "school-confirmed".*

---

## 0. The headline: the industrial agreement is a machine-readable spec

The single most valuable thing this pass turned up isn't in any of the
four reference repositories. It's that **the Catholic Employers Single
Enterprise Collective Agreement — Diocesan Schools of Queensland
2023–2026** (the agreement covering Brisbane Catholic Education, IEU-QNT
being the union party) specifies release time and teaching load as
**tables and formulas keyed on school enrolment** — i.e. as something a
program can compute and check, not prose a human has to interpret.

Three findings from reading it against the real database, in descending
order of importance:

### 0.1 🟢 The `2580` figure is not a TTS default — it's the EA contact-time cap

`docs/full-timetabler-plan.md` §4.1 established that every teacher
resolves to `contracted_load_minutes = 2580`, sourced from TTS's
`Settings.TeacherProposedLoad = 258000`, and §10.4 left open the question
*"is 2580 min/cycle the right default?"*

It is, and now we know why:

```
EA Schedule 3, S3.3.2 (secondary):  max 21.5 hours contact time per week
                        21.5 h  ×  60           =  1290 min / week
                        1290    ×  2 weeks      =  2580 min / 10-day cycle
```

Sophia's cycle is 10 days across weeks A and B — exactly two weeks. The
number TTS carries as a school default is precisely the industrial
maximum. **`teacher_over_contracted_load` has been enforcing an
industrial entitlement all along, not an arbitrary configuration
value.** That materially raises the stakes of the rule and should be
said plainly in `docs/rules.md`: a finding there is a potential EA
breach, not a nice-to-have balance issue.

> Open question §10.4 in `docs/full-timetabler-plan.md` can be closed,
> replaced by a much narrower one: does Sophia run the 30.5-hour or the
> 31-hour week (S3.3.1 allows both), and does that change the contact cap?
> The 21.5-hour contact maximum reads as fixed across both, but that's
> worth one confirmation rather than an inference.

### 0.2 🟡 We are measuring contact time more narrowly than the EA defines it

`load_rules.py`'s `teacher_over_contracted_load` filters
`WHERE te.entry_type = 'LESSON'`. The EA is broader:

> S3.3.3 — contact time includes programmed teaching time, programmed
> sporting, administrative/pastoral care classes and assembly time.

`REGISTRATION` (pastoral care) and `ASSEMBLY` entries carry real
`load_minutes` in our data and are currently excluded. Measured against
the live database:

| Definition | Teachers over 2580 | Teachers at 90–100% of cap | Highest non-outlier |
|---|---:|---:|---:|
| `LESSON` only (today) | 1 | 7 | 2460 |
| EA S3.3.3 contact | 1 | **9** | **2560** |

25 teachers' measured contact time rises under the EA definition. **No
one newly crosses the cap in this term's data** — so this is not a fire —
but two more teachers land in the 90–100% band and the highest
non-outlier moves to 20 minutes under the industrial maximum. That's a
materially different risk picture from the same underlying timetable.

**Recommendation:** change the rule to count EA-defined contact types,
but *not* silently — this changes what "load" means in every number the
app reports, so it needs one confirmation from the school first (does
Sophia treat its `REGISTRATION` slot as the EA's "administrative/pastoral
care class"? Almost certainly yes, but it's their call, not ours).
Yard duty stays **excluded** and that's now confirmed rather than assumed
— see §0.3.

### 0.3 🟢 Yard duty and meetings are settled: they are *not* contact time

`docs/full-timetabler-plan.md` §10.3 asked whether meetings, unscheduled
duties, and yard duty (46 + 13 + 246 ignored records) should count toward
load. The EA answers it:

> S3.3.16 — "other duties" includes class/playground/transport
> supervision, staff meetings, movement between classes, school worship,
> parent/teacher consultations…

Those are the *remainder* of the 30.5/31-hour week, explicitly distinct
from the 21.5-hour contact component. **Excluding them from the contact
calculation is correct.** They belong in a future *total-hours* view
(the 30.5-hour envelope), which is a different and lower-priority
measure than the contact cap. Question §10.3 can be closed as answered.

### 0.4 The middle-leadership release pool is a lookup table

> EA Schedule 2, S2.16 / Table 3 — Middle Leadership in Diocesan
> Secondary Schools: enrolment band → **Middle Leadership Units** and
> **hours to distribute over a year**.

The 551–600 enrolment band carries **66 units / 652 hours per year**.
Sophia has 560 students in the ingested data, which puts it in that band
— *but the DB student count is not necessarily the school's official
enrolment figure for EA purposes* (census date, enrolments not in the
timetable export, etc). The band must be confirmed, not computed from
our student table and trusted.

Senior leadership (S2.9, Table 1) works differently — a per-position FTE
release proportion, also enrolment-banded.

This is what makes "release time, auto calculated" (the original ask) a
real feature rather than a guess: **the school-level pool is a table
lookup; the per-teacher allocation is a human distribution decision
against that pool.** GridPilot's job is to compute the pool, track the
distribution, and flag when they don't reconcile — never to invent
either.

**Sources.** [Diocesan Schools of Queensland 2023–2026 agreement (QCEC)](https://eb.qcec.catholic.edu.au/wp-content/uploads/2023/10/20231012-Diocesan-EB10-proposed-EA-Access-Period-V3.pdf) ·
[QCEC explanation of terms](https://eb.qcec.catholic.edu.au/wp-content/uploads/2023/11/20231012-Diocesan-EB10-Explanation-of-Terms-Access-Period-V3.pdf) ·
[IEU-QNT collective bargaining](https://ieuqnt.org.au/category/collective-bargaining/) ·
[FWC-approved RI Schools agreement 2023–2026](https://stuartholme.com/wp-content/uploads/AG2023-3539-RI-Schools-Agreement-2023-2026-Final-with-UTs.pdf)

⚠️ **Every clause cited above was read from a *proposed-agreement access
period* PDF.** Before a single number is hard-coded, the school's HR/IEU
representative must confirm the operative agreement and its current
figures. The design below deliberately stores all of it as **reviewable
data with a citation field**, never as constants in Python — same
discipline as every other unconfirmed policy value in this project.

---

## 1. Review of the four reference repositories

Asked: *do any contain code which may be useful to us? if so, adapt.*

Short answer: **no code worth adapting, and for three of the four we
legally could not adapt it even if there were.** Longer answer, because
the *reasons* are useful:

| Repo | Stack | Licence | Verdict |
|---|---|---|---|
| [ravi-kp/Automatic-TimeTable-Generation-For-An-Institute](https://github.com/ravi-kp/Automatic-TimeTable-Generation-For-An-Institute) | PHP + MySQL/XAMPP | **NONE** | Unusable. No licence = all rights reserved. Also a 2019 PHP/MySQL university app — wrong stack, wrong domain (institute course allocation, not a school cycle). |
| [kusal-tharindu/Timetable-Management-System](https://github.com/kusal-tharindu/Timetable-Management-System) | Java Swing + MySQL | **MIT** ✅ | Legally reusable, practically irrelevant. A NetBeans desktop CRUD app for lecture-hall booking and seat reservations. No solver, no constraint model, no cycle concept. Nothing to take. |
| [rocristoi/openTimetables](https://github.com/rocristoi/openTimetables) | **Python + OR-Tools CP-SAT** + React | **NONE** | The closest to us by stack, and the only one worth reading. Cannot copy (no licence). Its *model* is instructive mostly as a counter-example — see below. |
| [sisardor/FET-scheduling-system](https://github.com/sisardor/FET-scheduling-system) | PHP/JS front-end over FET | **NONE** | Unusable, and doubly so: it is a front-end for FET, which is **GPL/AGPL**. `docs/full-timetabler-plan.md` §2 already rules out taking FET code for exactly this reason. |

**On the licence point specifically:** a public GitHub repo with no
LICENSE file is *not* public domain. Absent a licence, default copyright
applies and no reuse right is granted. GridPilot's `.gitignore`-and-
provenance discipline exists precisely so this project can be honest
about where every line came from; copying unlicensed code would undo
that. Reading them for *ideas* is fine and is what we did.

### 1.1 What openTimetables actually teaches us (a negative result, and three positives)

Its CP-SAT model is a dense five-dimensional boolean:

```python
# openTimetables/Backend/backend.py — read, not copied
self._assignment[lvl_idx, sub_idx, tch_idx, slt_idx, loc_idx] = model.NewBoolVar(...)
```

**The negative result — and it's a genuinely useful one.** At Sophia's
real scale that formulation is ~20 roll classes × 141 subjects × 74
teachers × 50 slots × 51 rooms ≈ **750 million booleans**, which is not
a tuning problem, it's a wall. This is precisely the naive shape
`docs/solver.md` §3 rejected in favour of enumerating *feasible
candidates only*, and it's why `repair_solver.py` runs a real repair in
~4 seconds. Seeing an independent project hit the same design fork and
take the expensive branch is decent confirmation we chose correctly.

Three positives, all of which **corroborate designs already written down
in this repo but not yet built**:

1. **`C1: CURRICULUM`** — `sum(assignments for (level, subject)) ==
   required_slots`. This is exactly the `TeachingRequirement` concept
   `docs/staff-capability-model.md` identifies as "the single biggest
   net-new piece". Independent arrival at the same abstraction is a good
   sign the model is right.
2. **`specialtie_teachers(subject)`** — variables are only created where
   the teacher is qualified for the subject; everything else is pinned
   to zero. This is `teacher_capability` from the same doc, and it shows
   its *real* role: capability data isn't a nice-to-have staffing
   feature, **it's the primary domain-reduction mechanism that makes
   from-scratch generation tractable at all.** That reframes it from a
   "staffing" item to a solver prerequisite.
3. **`PREFERRED_TEACHERS` / `PREFERRED_TEACHERS_TIME_SLOTS`** — maps
   one-to-one onto `requirement_teacher_preference`, including the
   distinction between "this teacher, solver picks the slot" and "this
   teacher at this fixed slot".

**Net:** zero lines adapted. One design decision independently
validated, one deferred design (`staff-capability-model.md`) promoted
from "nice staffing feature" to "prerequisite for Phase H Mode C", and
one licence trap avoided.

---

## 2. Staffing: capability, roles, release, and ECT status

This is the largest net-new area and the one the EA research makes
tractable. It builds on `docs/staff-capability-model.md` (already
written, not built) and supersedes its "open questions" §2 with real
answers where the EA provides them.

### 2.1 Schema

Extends the proposal in `docs/staff-capability-model.md` rather than
replacing it. New here: the EA-derived tables and the ECT/registration
fields.

```sql
-- The agreement itself, as reviewable data. Never constants in Python.
CREATE TABLE industrial_agreement (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,               -- 'Diocesan Schools of Queensland 2023-2026'
    source_reference TEXT,            -- URL or document reference
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    confirmed_by TEXT,                -- who at the school signed off on these figures
    confirmed_at TEXT
);

-- EA Schedule 3: the contact-time envelope. One row per teacher category.
CREATE TABLE agreement_load_rule (
    id INTEGER PRIMARY KEY,
    agreement_id INTEGER NOT NULL REFERENCES industrial_agreement(id),
    sector TEXT NOT NULL CHECK (sector IN ('SECONDARY', 'PRIMARY')),
    ordinary_hours_per_week REAL NOT NULL,        -- 30.5 or 31 (S3.3.1)
    max_contact_hours_per_week REAL NOT NULL,     -- 21.5 (S3.3.2)
    prep_correction_pct REAL,                     -- 0.20 (S3.3.4)
    max_cover_periods_per_year INTEGER,           -- 10 (S3.3.5)
    clause_reference TEXT
);

-- EA Schedule 2 Table 3: middle-leadership pool by enrolment band.
CREATE TABLE agreement_leadership_band (
    id INTEGER PRIMARY KEY,
    agreement_id INTEGER NOT NULL REFERENCES industrial_agreement(id),
    tier TEXT NOT NULL CHECK (tier IN ('MIDDLE', 'SENIOR')),
    enrolment_min INTEGER NOT NULL,
    enrolment_max INTEGER NOT NULL,
    units INTEGER,                    -- MIDDLE: 66 for the 551-600 band
    hours_per_year REAL,              -- MIDDLE: 652 for the 551-600 band
    release_fte REAL,                 -- SENIOR: proportion of teaching load
    clause_reference TEXT
);

-- The school's own enrolment figure for EA purposes - explicitly NOT
-- derived from COUNT(*) on our student table (see §0.4).
CREATE TABLE school_enrolment_declaration (
    id INTEGER PRIMARY KEY,
    planning_year TEXT NOT NULL,
    official_enrolment INTEGER NOT NULL,
    as_at_date TEXT,
    entered_by TEXT NOT NULL,
    note TEXT
);

-- Teacher registration / career stage. Identity-adjacent but
-- timetable-relevant, so allowed under docs/full-timetabler-plan.md 7.3.
ALTER TABLE teacher ADD COLUMN registration_status TEXT
    CHECK (registration_status IN ('PROVISIONAL', 'FULL', 'UNKNOWN'));
ALTER TABLE teacher ADD COLUMN career_stage TEXT
    CHECK (career_stage IN ('GRADUATE', 'EARLY_CAREER', 'EXPERIENCED', 'UNKNOWN'));
ALTER TABLE teacher ADD COLUMN commenced_teaching_date TEXT;
ALTER TABLE teacher ADD COLUMN fte REAL;   -- 1.0, 0.6 etc - drives the pro-rata cap
```

Plus the three tables `docs/staff-capability-model.md` already specifies
verbatim — `teaching_requirement`, `teacher_capability`,
`requirement_teacher_preference` — which §1.1 above independently
validates. Build those *as written there*; nothing in this pass changes
their shape.

### 2.2 "Permission to teach" — `teacher_capability`

The addendum model in `docs/staff-capability-model.md` §"CapabilityService"
stands as written: an ordered precedence resolution (requirement lock →
requirement preference → exact subject+year → faculty+year-range → no
match = `NOT_ELIGIBLE`), resolved once in `app/analysis/capability.py`,
never duplicated as raw SQL.

Two rules it unlocks, both currently impossible:

- `teacher_not_qualified_for_class` — a scheduled lesson whose teacher
  resolves to `NOT_ELIGIBLE` for that subject. Severity `critical`;
  this is a compliance question, not a preference.
- `capability_rule_conflict` — two equally-specific active rules
  disagreeing (one `ELIGIBLE`, one `NOT_ELIGIBLE`). Surfaced for human
  resolution, never silently resolved by pick-one.

**And it unblocks `class_teacher_inconsistency` suggestions** — the
boundary hit earlier in this project's life, where the suggestion engine
correctly refused to guess a replacement teacher. With
`teacher_capability` populated, "who else could take this class" becomes
a *search over a known-legal set* rather than a guess, and the
`suggest_fixes()` scope restriction in `docs/suggestions.md` can finally
be relaxed for that rule — with the same "rank by disruption, explain
why each candidate works" treatment every other suggestion type gets.

**The unresolved input problem stays unresolved.** `docs/staff-capability-model.md`
§"Open questions" #2 asks where authoritative capability data comes
from, and nothing in this pass answers it. The `source_type` enum
already encodes the safe default: `CURRENT_TIMETABLE_INFERRED` must
always resolve to `REVIEW_REQUIRED`, never automatic eligibility. So
v1 can bootstrap "who currently teaches what" as *candidates for
review* — the same detect→confirm pattern that worked for room types —
and the school confirms or corrects. That is the only honest starting
point without an HR feed.

### 2.3 Release time, auto-calculated

The feature as asked for, decomposed into the part that's arithmetic and
the part that isn't:

```python
# app/analysis/release.py  (new)

def leadership_pool(conn, planning_year: str) -> LeadershipPool:
    """School-level entitlement: a pure table lookup on the declared
    enrolment (school_enrolment_declaration), NOT on COUNT(*) students.
    Returns units + hours/year for MIDDLE, and per-position FTE for
    SENIOR, straight from agreement_leadership_band."""

def allocated_release(conn, planning_year: str) -> dict[str, float]:
    """What has actually been handed out: sum of
    teacher_role_assignment -> staff_role.release_minutes_per_cycle,
    annualised. This is a human distribution decision, recorded."""

def reconcile(conn, planning_year: str) -> ReleaseReconciliation:
    """pool vs allocated. Over-allocation is a budget finding; under-
    allocation is an unused entitlement. Both are worth surfacing;
    neither is auto-corrected."""
```

New rule `leadership_release_over_allocated` (severity `warning`): the
sum of release granted exceeds the EA pool for the declared enrolment
band. New dashboard tile: *"Middle leadership: 640 of 652 hours
allocated"*.

**What stays manual, deliberately:** who gets which role, and how many
hours each role carries. The EA gives a pool and a unit count, not an
org chart. `staff_role.release_minutes_per_cycle` remains human-entered
— the change is that it's now checked against a real entitlement instead
of floating free.

**Pro-rata for part-time staff** is the one piece of genuine arithmetic
subtlety: a 0.6 FTE teacher's contact cap is `0.6 × 2580 ≈ 1548`
min/cycle, not 2580. `teacher.fte` above exists for this. We do not have
FTE in the source export today — it is not in the `.tfx`, and *it cannot
be inferred from a light timetable* (`docs/solver.md` §4.2 makes the same
argument for teacher unavailability, and it applies identically here).
Until FTE is entered, the load rule must keep using the full-time cap and
**say so in the finding's evidence**, rather than silently comparing a
part-timer against a full-time number.

### 2.4 Early-career teachers

The EA's graduate-teacher provisions (clause 4.21 — induction, mentoring,
support for full registration) are largely *process* obligations rather
than timetable arithmetic, so the honest scope here is narrow:

- Store `career_stage` / `registration_status` / `commenced_teaching_date`
  (§2.1) and surface them on the Teachers page.
- Rule `early_career_teacher_overloaded` — an ECT at or near the contact
  cap, or carrying an unusual number of distinct subject preparations
  (a real workload driver the raw minute count misses entirely).
- **Flag, don't enforce.** Any specific ECT release entitlement must come
  from the confirmed agreement plus school policy. Do not encode a
  number here on the strength of this document.

Worth being explicit: the mentoring/induction/portfolio provisions in
4.21 are HR workflow, not timetabling, and GridPilot should not grow into
them — same boundary as the deliberate refusal to build Daily Organiser
or a parent portal (`docs/full-timetabler-plan.md` §9).

---

## 3. Authoring: students, staff, rooms, blocking

All four are **Tier 2/3 write capability** per `docs/full-timetabler-plan.md`
§5 and all four are gated on the same unanswered experiment: **does TTS
accept a GUID it did not generate?** (§5(b)). That is a ~1 hour test
against a non-production copy and it determines whether this whole
section is straightforward or needs a negotiated-ID handshake. *Nothing
in §3 should be built before that test is run.*

### 3.1 Importing student data

Already ingested: 560 students, 6,726 enrolments, 6,756 `.sfx`
preference rows. What's missing is **authoring** — adding a student who
joined mid-year, or changing an elective choice.

Boundary, restating `docs/full-timetabler-plan.md` §7.3 because it
matters most here: **author timetable-relevant facts only** (enrolment,
option preference, roll-class placement). **Never author identity
fields** (name, DOB, address, guardian contacts) — the SIS is the system
of record for who a student *is*.

```
POST /api/students/{code}/enrolments      add/remove a class enrolment
POST /api/students/{code}/preferences     record an elective preference change
```

Both land in the existing **change-set pipeline** — proposed, validated
by `whatif.py` (an enrolment change can create a `student_double_booking`
or push a room over capacity), reviewed, then applied. Reusing that
pipeline rather than inventing a second write path is the whole point.

### 3.2 Adding staff

`origin ∈ {IMPORTED, AUTHORED}` on `teacher`, per §5 Tier 2. Authored
teachers carry a minted GUID and must survive re-ingest via the existing
`resync.py` snapshot/restore mechanism (`docs/reingest-persistence.md`)
— extending that pattern, not building a parallel one.

Same identity boundary as students: code, name-from-import, faculty,
load, role, capability are authorable; personal details are not.

### 3.3 Adding rooms, and using the room data we already ignore

Two separate things:

**(a) Authoring rooms** — Tier 2, same provenance/GUID treatment.
Straightforward once the GUID question is settled.

**(b) Using `room_pool` — done 2026-08-17.** The RUR data (1 pool, 5
rooms, 28 class-name references) sat in the database unread since Phase
A. Now:

- Rule `room_pool_violation` (`docs/rules.md`) — a class in a room
  outside its declared pool. Fires on 2 real lessons (`12PHY1` in
  `ANG7`, `11BIO1` in `SPO05`).
- Solver constraint — `repair_solver._feasible_candidates()` restricts a
  pooled class's candidate rooms to its pool for *every* repair, not
  just ones targeting a `room_pool_violation` finding directly, exactly
  as `class_room_type_constraint` already does. Confirmed against real
  data: `solve_repair()` resolves both real violations by moving each
  class into an actual pool room.

**Rooms page — done 2026-08-17.** `GET /api/rooms` +
`frontend/src/pages/RoomsPage.tsx`: utilisation (used lesson slots /
total lesson slots, the same calculation `room_underutilization`
already uses), type, capacity, pool membership (with the pool's other
rooms in a tooltip), which classes an *approved*
`class_room_type_constraint` expects in a room of that type, and an
open-finding count per room. Read-only, matching (a) above — sidebar
gets a new **Places** group per the target IA in
`docs/full-timetabler-plan.md` §7.1. Verified against the real data:
RUR 1's five rooms show their pool correctly, `RIE05`/`RIE06`/`RIE07`
show non-zero open-finding counts consistent with the real
`room_pool_violation` findings from (b).

### 3.4 More blocking patterns

The Blocking page is read-only (Phase C). Making it *editable* is Tier 3
and the highest-value authoring capability of the four, because blocking
is where clashes are actually caused — `docs/full-timetabler-plan.md`
§1.2 traces the TTS pipeline showing blocking precedes allocation, and
`docs/solver.md` flags blocking optimisation as "a separate, arguably
larger prize" needing no new data (all 6,756 preference rows are already
ingested).

Sequenced:

1. **Read-only analytics — done 2026-08-17, partially.** Shipped: an
   open-finding-count badge per line (any finding touching a class,
   teacher, or room that line's class groups actually use - "structurally
   responsible for," not mutually exclusive, since one finding like a
   teacher double-booking can implicate two lines at once) and each
   course's real enrolment shown as plain fact. **Deliberately not
   shipped: "under-subscribed offerings" as a judgement, or the
   per-line student-preference-pressure metric from §12.4 of
   `docs/full-timetabler-plan.md`.** Checking the real data before
   building either turned up something too ambiguous to build on
   confidently: several "10A A/B/C/D"-shaped lines show exactly 0
   enrolled for their `10D` roll-class offering (`10RE4`, `10ENG4`,
   `10MAT4`, `10SCI4`, ...) despite `10D` carrying 228 real enrolment
   rows elsewhere in the database - meaning those particular students
   are very likely routed through a different offering entirely (a
   composite, a support pathway) rather than genuinely having zero
   uptake. Flagging that as "under-subscribed" would be a false
   positive dressed as a rule. The `.sfx` preference-pressure join has a
   real but partial link (only 245 of 303 `sfx_class` codes match a
   `class_name` code, ~81%) - not necessarily wrong, but not verified
   clean either. Both stay documented-not-built rather than guessed,
   same discipline as every dropped rule in §6 Phase B of
   `docs/full-timetabler-plan.md`. Enrolment is shown as raw data
   specifically so a human can look at that `10D` pattern and judge it
   themselves.
2. **Then** drag-a-class-group-between-lines authoring, once (1)'s
   remaining pieces are trustworthy and the GUID question is settled.

Doing (2) before (1) would be authoring a structure we can't yet
evaluate.

### 3.5 Creation of timetables

`docs/solver.md` Mode C. Nothing here changes its conclusion: **the
constraint data, not the solver code, is the blocker**, and construction
is the lowest value per unit of effort of the three modes.

What §1.1 and §2 above *do* change is the dependency order — it is now
concrete:

```
teacher_capability + teaching_requirement   (§2, prunes the domain)
        ↓
teacher unavailability                      (STILL UNANSWERED - §10.6)
        ↓
Mode B regional rebuild  →  Mode C construction (roll-over only)
```

Teacher unavailability remains the hard blocker it has always been, and
it remains un-inferable. Nothing in the EA supplies it either — the
agreement caps *how much* a teacher works, never *when* they are
available. It is a school-answered question and it gates both remaining
solver modes.

---

## 4. Interface: a real design system

The UI has grown feature-by-feature with Tailwind utilities chosen
per-component. It's consistent-ish by habit rather than by construction.
This section makes it explicit, and is **the one section here with no
external blockers** — all of it is buildable immediately.

### 4.1 Tokens, not ad-hoc utilities

Tailwind v4 is already in use (`@import "tailwindcss"` in
`frontend/src/index.css`), so tokens belong in an `@theme` block in that
file. Everything below is currently implicit and scattered:

```css
@theme {
  /* Type. A UI face with real tabular figures - the grid lives or dies
     on digit alignment across period columns. */
  --font-sans: "Inter var", "Inter", system-ui, -apple-system, "Segoe UI", sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, "Cascadia Mono", monospace;

  /* Type scale - currently text-xs/[10px]/[11px] are sprinkled by feel */
  --text-grid:    0.6875rem;  /* 11px - dense grid cell secondary line */
  --text-body:    0.875rem;   /* 14px - default UI text */
  --text-heading: 1.125rem;

  /* Semantic colour, not raw slate-N. Severity already has meaning in
     this app (findings) - it should have exactly one definition. */
  --color-surface:        oklch(1 0 0);
  --color-surface-sunken: oklch(0.985 0.002 250);
  --color-border:         oklch(0.92 0.004 250);
  --color-ink:            oklch(0.28 0.01 250);
  --color-ink-muted:      oklch(0.55 0.01 250);

  --color-severity-critical: oklch(0.58 0.20 25);
  --color-severity-warning:  oklch(0.72 0.16 65);
  --color-severity-info:     oklch(0.65 0.10 240);
  --color-pending:           oklch(0.76 0.15 80);   /* amber - pending move */
  --color-scenario:          oklch(0.58 0.19 300);  /* violet - scenario/solver */
}
```

Note the last two: amber-for-pending and violet-for-solver/scenario are
*already* de facto conventions in the code (`ring-amber-400` on pending
moves, violet on the scenario selector and repair panel). Naming them
makes them intentional and stops the next feature inventing a third.

**Do not touch `lib/facultyColors.ts`.** That palette was validated
colour-blind-safe and is load-bearing; it is a categorical scale and
must stay independent of the semantic tokens above. The rule to write
down: *semantic colour communicates state; the faculty palette
communicates identity; they never borrow from each other.*

### 4.2 Readability in the grid

The density fix already landed (capped stacking, day-boundary borders).
Remaining, in impact order:

1. **`font-variant-numeric: tabular-nums`** on every time and count
   column. Proportional digits make period times and load minutes ragged
   and genuinely harder to scan down a column. One CSS line; the single
   highest readability-per-effort item in this document.
2. **Sticky row-label contrast.** The frozen first column is
   `bg-white` over `even:bg-slate-50/60` striped rows, so the stripe
   disappears behind the label — the eye loses the row on a wide
   horizontal scroll. Give the sticky column its own surface token and a
   real right-edge shadow rather than a 1px border.
3. **A density toggle** (comfortable / compact). Timetablers scanning
   the whole school want compact; someone reviewing one teacher wants
   comfortable. Currently one hard-coded density serves both badly.
4. **Contrast audit.** `text-slate-400` on `bg-slate-50` (used for
   period sub-headers) is around 3:1 — below WCAG AA for body text. It's
   used for genuinely secondary information so it's defensible, but it
   should be a deliberate `--color-ink-muted` decision at a checked
   ratio, not an accident of utility choice.
5. **Empty-cell treatment.** The `·` in every empty master-grid cell is
   visual noise at 51 rows × 50 columns. A near-invisible tint reads
   better than a glyph repeated ~2,000 times.

### 4.3 Layout

- **Full-height grid with internal scroll.** The master grid currently
  sits in a `max-h-[75vh]` box inside a page that also scrolls — two
  nested scroll contexts, which is the single most-felt awkwardness in
  daily use. The grid should own the viewport below the toolbar and
  scroll internally, once.
- **Toolbar consolidation.** Mode / axis / scenario controls are three
  separate bordered blocks; they're one control group and should read
  as one.
- **Keyboard navigation.** `Ctrl+K` exists. Arrow-key cell movement and
  `Enter` to open the inspector would make the grid usable without a
  mouse — the thing that most distinguishes a professional data tool
  from a web page, and the thing TTS's desktop UI actually does well.

### 4.4 Sequencing note

§4 is deliberately buildable *now* and depends on nothing in §2 or §3.
If the school's answers to the EA and GUID questions are slow to come
back, this is the section to work on meanwhile.

---

## 5. What to do next, in order

| # | Item | Blocked on | Size |
|---|---|---|---|
| 1 | ✅ Tokens + tabular numerals + sticky-column contrast (§4.1, §4.2) | — | S |
| 2 | ✅ Full-height grid, toolbar consolidation (§4.3) | — | S |
| 3 | ✅ `room_pool` rule + solver constraint (§3.3b) | — | S |
| 4 | ✅ Rooms page (§3.3) | — | M |
| 5 | ✅ Blocking analytics, read-only (§3.4.1) — partial, see §3.4 | — | M |
| 6 | EA tables + release reconciliation (§2.1, §2.3) | **school confirms the agreement figures** | M |
| 7 | Contact-time definition change (§0.2) | **school confirms `REGISTRATION` = pastoral care** | S |
| 8 | `teacher_capability` + bootstrap-for-review (§2.2) | nothing to start; HR feed to finish | L |
| 9 | `class_teacher_inconsistency` suggestions | #8 | M |
| 10 | Entity authoring — students, staff, rooms (§3.1–3.3a) | **GUID minting experiment** | L |
| 11 | Editable blocking (§3.4.2) | #10 + #5 | L |
| 12 | Mode B / Mode C solver (§3.5) | #8 + **teacher unavailability** | XL |

Items 1–5 need no answers from anyone and are worth roughly a session
each. Items 6–7 are small once two short questions come back. Everything
from 10 down is gated on the GUID experiment that has been open since
2026-08-04.

## 6. Questions for the school, consolidated

Closed by this pass: ~~is 2580 the right load default~~ (§0.1),
~~should yard duty and meetings count toward load~~ (§0.3).

Still open, in priority order:

1. **When is each teacher unavailable?** Unchanged as the highest-value
   unanswered question. Gates all remaining solver work.
2. **Does TTS accept a minted GUID?** ~1 hour. Gates all authoring.
3. **Confirm the operative EA and its current figures** — is the
   2023–2026 Diocesan agreement the one in force, and are the Schedule 2
   / Schedule 3 numbers cited in §0 current? (HR or IEU rep.)
4. **What is Sophia's official enrolment for EA banding purposes**, and
   is it the 551–600 band? (Not the same as our 560 student rows.)
5. **Is the `REGISTRATION` slot the EA's "administrative/pastoral care
   class"?** Determines §0.2.
6. **Where does teacher subject-qualification data come from?** Still
   unanswered from `docs/staff-capability-model.md`; determines whether
   §2.2 is an import or a term of manual review.
7. **Which teachers are part-time, and at what FTE?** Not in the export,
   not inferable, and required before any load figure is trustworthy for
   those staff.
