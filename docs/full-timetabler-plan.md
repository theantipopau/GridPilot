# GridPilot → Full Timetabling Program: Execution Plan

*Written 2026-08-12. This is a plan and a set of recommendations, not a
commitment to build all of it. It is deliberately opinionated about
sequencing, because the wrong order here wastes months.*

*2026-08-12 update: Phase A is done - see the status note at the top of
§6.*

*2026-08-12 update 2: Phases B and C are done - see §6. Phase 0 (§6, the
trial-import) also passed today, using a real move made in the master
grid (ANG3 → ANG1), exported and confirmed readable by Timetabling
Solutions itself. This unblocks scoping Tier 1+ write work (§5) for the
first time.*

---

## 0. The one-paragraph version

GridPilot today is an excellent **reader and analyser** of a Timetabling
Solutions export, with a deliberately narrow write path (move an existing
lesson, patch it back into the source file). Becoming a full timetabling
program means crossing three thresholds, in this order: **read the whole
file** (we currently parse 14 of 24 sections — the blocking pattern is
one of the 10 we ignore), **author entities and structure** (not just
patch them), and **generate** (a solver). The single most important
sequencing rule in this document: *we cannot responsibly build any of
that until one generated `.tfx` has been successfully re-imported into a
real copy of Timetabling Solutions* — a ~15-minute task that has been the
#1 open risk since 2026-08-04 and gates every write feature below.

---

## 1. What we're up against: Timetabling Solutions

### 1.1 The product suite

Timetabling Solutions is used by **over 60% of independent schools in
Australia**. It is not one program but five, and GridPilot is currently
adjacent to only the first:

| Product | What it does | GridPilot equivalent |
|---|---|---|
| **Version 10.1** (desktop) | Construct, manage, publish the timetable. Interactive *or* automatic allocation. "Clash Matrix" problem identification. Multi-campus. | Partially — we read, analyse, and patch its file |
| **Staffing** (cloud) | Create staffing loads, define staffing constraints, semesterisation, blocked and composite classes, manual or automatic teacher→class assignment | Teachers page + roles; composite review. No allocation. |
| **Preferences Manager** (cloud) | Students enter subject selections online; SSO (OIDC/SAML), curriculum rules, parent approval | None — but we ingest the `.sfx` output of it |
| **Course Manager** (cloud) | Collaborative student course-change management, composite class support | None |
| **Daily Reports / Daily Organiser** | Staff portal: personal timetable, class lists, activities, changes, bulletin. Cover/relief management. | None |

**Read that table honestly:** replacing this suite wholesale is a
multi-year effort against a 30-year-incumbent with deep institutional
lock-in. That is not the near-term goal, and the plan below does not
pretend otherwise. The realistic goal is to become **the place you think
about the timetable**, while TTS remains the place it is generated and
published — and to make the boundary between those two thin enough that
the balance can shift later if it earns the right to.

### 1.2 Their actual workflow — evidence from the file itself

The `Settings` block of the school's own `.tfx` (which GridPilot
currently does not parse) reveals the TTS pipeline directly:

```
LastBlocking    46213.53      ← blocking happened first
LastAllocation  46233.59      ← allocation happened ~20 days later
```

So the TTS workflow is:

```
Curriculum/structure  →  Blocking  →  Allocation  →  Timetable  →  Publish  →  Daily Org
   (what runs)          (what runs    (who teaches   (which slot)   (staff/      (cover,
                        in parallel)   what)                        students)     changes)
```

**Blocking** is the step where subjects are grouped into parallel *lines*
(the "option lines" / "blocking pattern") so that a student can pick one
subject per line without clashing. **Allocation** is assigning teachers to
those class groups. GridPilot currently enters the story *after both*,
looking only at the resolved grid — which is precisely why it can spot
clashes but cannot yet explain *why* the structure produced them.

### 1.3 Where TTS is strong, and where it is genuinely weak

**Strong:** the solver and the blocking engine; decades of edge cases;
publishing and daily organisation; a support/training organisation behind
it.

**Weak — and this is the whole opportunity:**

- **Windows desktop, dense, modal.** Skill development is via
  "Instructor Led Training, Self Paced Manuals and Videos" — i.e. the UI
  needs a course to operate.
- **Run-then-check, not live feedback.** You allocate, then inspect a
  Clash Matrix to find out what broke.
- **No explanation layer.** It tells you *that* there is a clash, never
  *why the structure made it likely*.
- **No versioning you can reason about.** Save-file discipline, not
  branchable scenarios you can compare side by side.
- **Analysis is a report, not a conversation.**

GridPilot already beats it on the last three for the narrow slice it
covers. That is the wedge.

---

## 2. The open-source landscape: what to borrow

| Project | Stack / licence | Worth taking | Worth avoiding |
|---|---|---|---|
| **[FET](https://lalescu.ro/liviu/fet/)** | C++/Qt, **AGPL-3.0** | Its **constraint taxonomy** is the best free spec of what school timetabling actually needs — see below. Hierarchical students (years → groups → subgroups) is a better model than our flat roll classes. | The code (AGPL is viral — do not copy source into this project). The UI is a wall of dialogs. |
| **[UniTime](https://github.com/UniTime/unitime)** | Java, open source | Multi-manager coordination (departments editing concurrently); **student sectioning** as a first-class problem; exam timetabling. | University-shaped; very heavy for a single secondary school. |
| **[Timefold](https://timefold.ai)** (ex-OptaPlanner) | Java/Python, **AGPL** | Constraint-as-code modelling, school-timetabling quickstart. | AGPL again; its **Python is documented as significantly slower than its Java** — bad fit for a Python backend. |
| **Google OR-Tools CP-SAT** | C++/Python, **Apache-2.0** | **My recommendation for the eventual solver.** Permissive licence, Python-native, proven on exactly this class of problem. | Model-building is lower-level than Timefold; you write the constraints yourself. |

**Licensing trap worth stating plainly:** FET and Timefold are both AGPL.
Borrowing their *ideas and constraint vocabulary* is completely fine and
recommended. Copying their *code* would make GridPilot AGPL too. OR-Tools
(Apache-2.0) is the safe engine choice.

### FET's constraint catalogue — the spec we should aim at

FET's feature list is effectively a free requirements document. Its
constraints fall into two families, and GridPilot currently implements
roughly four of ~40:

**Time constraints:** activity preferred starting times/slots; min/max
days between activities; consecutive/ordered/grouped activities;
non-overlapping activities; teacher unavailable periods; teacher max/min
days per week; teacher max gaps per day/week; teacher max continuous
hours; teacher min resting hours; student unavailable periods; student
max days; student early-start restriction; student max gaps; min resting
hours; per-activity-tag hour limits.

**Space constraints:** room unavailable periods; home room for
teacher/student set; preferred rooms by subject / by activity tag / by
specific activity; **max room changes per day/week**; min gap between
room changes; **same room for consecutive activities**; max different
rooms occupied.

Note how many of those map directly onto what you asked for — *"look for
consistent rooms, teachers, improve loads"* is, in FET's vocabulary,
`same room for consecutive activities` + `max room changes per day` +
`teacher max/min days` + `max gaps`. We do not need to invent this
vocabulary; we need to implement a chosen subset of it.

---

## 3. Where GridPilot actually stands

### 3.1 Built and solid

Ingestion + cross-validation, deterministic rules engine (6 rules, 251
findings on real data), composite-class human review, safe change sets
with what-if validation, algorithmic fix suggestions, audit trail,
six-gate export, re-ingest persistence, browser import, Dashboard,
Teachers + roles, master timetable grid, accept-risk, local AI advisor.
131 tests.

### 3.2 The read gap — we parse 14 of 24 `.tfx` sections

Measured against the school's real file today:

| Section | Records | Parsed? | Why it matters |
|---|---:|---|---|
| Days, Periods, YearLevels, Rooms, Teachers, Faculties, RollClasses, ClassNames, ClassGroups, Timetable, Students, YardDuty×3 | — | ✅ | The current model |
| **MRCGs** | **29** | ❌ | **This is the blocking pattern / option lines** |
| **Settings** | 1 | ❌ | School-wide load default + the school's own optimisation preferences |
| **UnscheduledDuties** | 46 | ❌ | Real teacher load not counted anywhere today |
| **Meetings** | 13 | ❌ | Same — load and availability |
| **Groups** | 108 | ❌ | TTS's internal period/block allocation scaffolding |
| **RURs** | 1 | ❌ | Room-pool constraint ("these classes must use one of these rooms") |
| PublishedTimetables | 45 | ❌ | Version history — genuinely not needed |
| TeacherFiles / StudentFiles | 1 / 6 | ❌ | Attached-file metadata — not needed |

### 3.3 The write ceiling

`backend/app/export/tfx_writer.py` is explicitly **"patch, never
rebuild"** — it loads the original JSON and mutates only the specific
`Timetable[]` entries an approved change touches, keyed by
`source_ref = "tfx:Timetable[<index>]"`. Every other byte is untouched.

That design decision is *excellent* and is exactly why the export gate's
fidelity checks are trivially provable. It is also, by construction, a
hard ceiling: **you cannot patch your way to a new file, a new teacher,
or a new student.** Crossing it is the central architectural work of this
plan (§5).

---

## 4. Three findings from this research to act on immediately

These fell out of the research and are worth doing regardless of how much
of the rest of the plan gets built. **All three fixed 2026-08-12** as
part of Phase A (§6) - see the ✅ note under each.

### 4.1 🔴 40% of teachers are silently excluded from load analysis

`app/analysis/load_rules.py` filters
`WHERE contracted_load_minutes IS NOT NULL`. In the real database:

```
contracted: 2580.0  → 44 teachers
contracted: None    → 30 teachers   ← never load-checked, silently
```

The parser sets `load_proposed = (t.get("LoadProposed") or 0) / 100.0`
then stores `load_proposed or None` — so a teacher whose file value is
`0` becomes `NULL` and drops out of the rule entirely. But `0` in TTS
does not mean "no load"; it means **"use the school default"** — and that
default is sitting in the `Settings` block we don't parse:

```
Settings.TeacherProposedLoad = 258000   →  ÷100  →  2580.00 minutes/cycle
```

which is *exactly* the value the other 44 teachers carry. Parsing
`Settings` and using it as the fallback immediately makes load analysis
cover 74 teachers instead of 44. **This is a real bug with a known fix
and it directly serves the "improve teacher loads" goal.**

**✅ Fixed.** `TfxIngester._ingest_settings()` now runs before
`_ingest_teachers()`; `contracted_load_minutes` falls back to
`Settings.TeacherProposedLoad` when a teacher's own value is 0. Verified
against the real data: 0 of 74 teachers now have a `NULL` contracted
load (was 30), and re-running the rules engine immediately surfaced a
genuinely new finding that was invisible before - `MCGK13` scheduled
3000 min/cycle against their 2580 min contracted load, 420 minutes over.

### 4.2 🟡 The blocking pattern is already in the file, unparsed

`MRCGs` (Multi-Roll-Class Groups) — 29 records — *are* the blocking
pattern. `DefaultCode` encodes year level + line letter, and the named
ones are unambiguous:

```
DefaultCode  Code      Name                 class groups
'10A B'      10ENG     10 English                     4    ← 4 English classes in parallel on Line B
'10A C'      10MAT     10 Maths                       4
'10A D'      Science                                  4
'10A A'      10 RE     10RE                           4
'10A J/K/L'            ELE1 / ELE2 / ELE3          4/8/4    ← the elective lines
'8A L'       8ARN      8 Arts Rotation                4
'8A K'       8SPO      8 Sport                        9
'12 A'…'12 F'                                         2    ← Year 12 option lines
```

This corroborates the inference already recorded in
`docs/data-formats.md` §5.4 against `2026 Blocking Pattern.xlsx` — but
now from the primary source, with counts. **The data you asked to see is
already in the file; we just aren't reading it.**

**✅ Fixed.** `TfxIngester._ingest_blocking_lines()` parses all 29 MRCGs
into `blocking_line`/`blocking_line_class_group` - 169 class-group links
total, matching the raw file exactly, zero unresolved references. Still
read-only (no UI yet - that's Phase C).

### 4.3 🟡 The school's own soft-constraint preferences are in `Settings`

`docs/project-status.md` weakness #4 says four roadmap rules are blocked
because they "need a school-confirmed threshold". Some of those
thresholds are in the file:

```
OptimiseSpread        True     ← the school wants lessons spread across the cycle
MaxDaySpread          True     ← ...and spread across days
Successive2Periods    True     ← doubles are wanted
Successive3Periods    True     ← triples are wanted
AcademicPeriods       80
TeacherProposedLoad   258000
TeacherSpareField1    'Role'   ← independently confirms the Spare1 = staff role finding
```

We can implement spread/doubles analysis **matching what the school's own
software is already optimising for**, rather than inventing thresholds —
which is exactly the "don't guess a policy value" discipline this project
has held throughout.

**✅ Parsed.** `school_setting` now holds all four booleans plus
`academic_periods` and `timetable_notice`. Not yet *used* by any rule -
that's Phase B, next.

**A fourth thing this pass turned up, not in the original plan:** `RURs`
("Room Utilisation Requirements", 1 record in the real file) - confirmed
by tracing a real `RURReferences[].ReferencesID` to `ClassNames[].ClassNameID`
- are a room-choice constraint ("one of these classes must use one of
these rooms"), not a single fixed room. Parsed into `room_pool`/
`room_pool_room`/`room_pool_class_name` (5 rooms, 28 class-name
references, all resolved). Also investigated and **deliberately not
parsed**: `Meetings` (13 records, all `Load: 0` for their 18 assigned
teachers - no incremental load information right now) and
`UnscheduledDuties` (46 records, referenced nowhere else in the file -
defined but unassigned this term). See `docs/data-formats.md` §3.1 for
the full writeup.

---

## 5. The architecture: five write tiers

Everything in "become a real timetabling program" is a question of *how
much of the file we are willing to author*. Five tiers, each a real
increment, each needing its own round-trip proof:

| Tier | Capability | Requires | Status |
|---|---|---|---|
| **0** | Patch existing `Timetable[]` entries (move a lesson) | — | ✅ Built, **unproven against real TTS** |
| **1** | Add/remove `Timetable[]` entries (create/delete a lesson) | Minting `PeriodID`-keyed entries; no new GUIDs | Not built |
| **2** | Author entity collections — Teachers, Rooms, ClassNames, Students | **GUID minting**; provenance tracking; identity governance (§7.3) | Not built |
| **3** | Author structure — ClassGroups, **MRCGs (blocking)** | Tier 2 + understanding `Groups[]` scaffolding | Not built |
| **4** | Author a whole file — **roll-over** to a new year | Tiers 2–3 + `Settings`/`Days`/`Periods` emission | Not built |
| **5** | Green-field file for a school that has never used TTS | Everything | **Recommend never** |

### Two decisions I'd make now

**(a) "Create a new file" should mean *roll-over*, not green-field.**
Schools do not create a timetable from nothing; they create *next year's*
from *this year's*. Starting from an existing `.tfx` as a skeleton —
preserving `Settings`, `Days`, `Periods`, and every section we don't
understand — keeps the "patch, never rebuild" safety property for the
~40% of the file we will never need to model, while letting us fully
author the parts we do. This turns Tier 4 from "reverse-engineer the
entire format" into "author 8 sections, copy the rest". Enormous
risk reduction for essentially no loss of capability.

**(b) The GUID question must be answered empirically, early.**
Every entity in the `.tfx` is keyed by a GUID that is stable across
exports. Tier 2 requires minting new ones. *Does TTS accept a GUID it did
not generate?* Nobody knows. This is a one-hour experiment (add one
teacher with a minted GUID, re-import into a non-production copy) and it
determines whether Tier 2+ is straightforward or requires a
negotiated-ID handshake. **Do this experiment before scoping Tier 2.**

---

## 6. The phased plan

Sizes are T-shirts relative to work already done in this project (M ≈ the
Teachers section; L ≈ the whole change-set + validation subsystem).

### Phase 0 — Prove the existing write path 🔒 *gates everything below* · **✅ done 2026-08-12**
**School task, ~15 minutes.** Take one generated `.tfx` and trial-import
it into a **non-production** copy of TTS. Until this passes, every write
tier is built on an unproven foundation. This had been open since
2026-08-04 and was the highest-leverage 15 minutes available.

**Done, and it passed.** A GridPilot-proposed room move (ANG3 → ANG1) was
exported and opened directly in Timetabling Solutions' own Master
Timetables view - not just re-parsed by our own code, the actual
incumbent software read the file back correctly. This is the first real
evidence the export path produces something TTS itself accepts, not just
something that round-trips through our own parser. Every Tier 1+ write
capability (§5) was gated on exactly this.

Still open: the **GUID minting experiment** from §5(b) - this run moved
an *existing* lesson (patched an existing `Timetable[]` entry, Tier 0),
which doesn't touch entity creation. Whether TTS accepts a GUID it didn't
generate itself is still untested and still gates Tier 2 (entity
authoring, Phase D).

---

### Phase A — Read the whole file · **M** · *no write risk* · **✅ done 2026-08-12**
Parsed `Settings`, `MRCGs`, `RURs`. Deferred `Meetings`/`UnscheduledDuties`
after investigation found zero incremental load information in the real
export this term (§4.3) - can be revisited once there's a real
conversation with the school about what should count toward load.

- Fixed the 30-teacher load blind spot (§4.1) — school-default fallback
  in `TfxIngester._ingest_teachers()`. Verified: 0/74 teachers now `NULL`,
  and a genuinely new finding surfaced (`MCGK13`, 420 min/cycle over).
- New tables: `school_setting`, `blocking_line`/`blocking_line_class_group`
  (from MRCGs - 29 lines, 169 class-group links), `room_pool`/
  `room_pool_room`/`room_pool_class_name` (from RURs - 1 pool, 5 rooms,
  28 class-name references). All source-derived, wired into
  `resync.py`'s rebuild-on-reingest list like every other source table -
  verified by re-running ingest twice against the same database.
- 6 new tests (`test_ingest_tfx.py`, `test_tfx_compatibility.py`); 137
  passing overall (was 131).

**Shipped value alone:** load analysis is now trustworthy and complete
(74/74 teachers, not 44/74) and the blocking pattern is captured in the
database, ready for Phase B/C to use - **not yet surfaced anywhere in
the UI or the rules engine**, which is exactly what those two phases are
for.

---

### Phase B — Analysis TTS can't give them · **M–L** · *no write risk* · **partially done 2026-08-12**
This is the "AI to fix the huge gaps in manual labour" ask, and it is
where GridPilot is *already* better than the incumbent. Seven candidate
rules were investigated against the real data before building anything -
same discipline as Phase A. Two were genuine, threshold-free signals;
five needed either a policy value the school hasn't confirmed, or turned
out to have nothing behind them in the current data:

| Rule | Verdict | Why |
|---|---|---|
| `class_room_instability` | **✅ built** | genuine signal, no threshold needed - "more than one room" is itself the finding. Confirmed real: one Y9 Maths class in 5 rooms across 7 lessons. 78/247 classes affected. |
| `class_teacher_inconsistency` | **✅ built** | same shape, for teachers. 22/247 classes affected. |
| `teacher_load_imbalance` (under-load) | ❌ dropped | tested it directly: 73 of 74 teachers would flag, because `contracted_load` covers non-lesson duties (meetings, coordination, leadership) that aren't in scheduled lesson minutes. Not asymmetric with the existing over-load rule the way it looked on paper - pure noise. |
| `teacher_day_spread` / `subject_spread` | ❌ dropped | tested a same-day-repeat proxy: zero genuine occurrences once the pastoral/detention roll class is excluded. `Settings.MaxDaySpread`/`OptimiseSpread` are booleans (the school *wants* spread), not numeric thresholds - still the roadmap's original blocker, just now partially informed. |
| `teacher_gap_fragmentation` | ❌ dropped | this is `teacher_free_period_fragmentation` from the original roadmap, already known to need a school-confirmed threshold. Real distribution checked (37/74 teachers have isolated gaps, up to 9 in the cycle) - genuinely ambiguous where "normal" ends, confirming the roadmap was right to shelve it rather than revealing a parsing gap. |
| `missing_double` | ❌ dropped | no per-subject "should be a double" data exists anywhere in the source. `Successive2Periods = True` is a school-wide preference, not a per-subject flag. Building this means guessing. |

Full reasoning and evidence in `docs/rules.md`'s "Consistency rules" and
"Not yet implemented" sections. 6 new tests; 143 passing (was 137).

Plus the **AI advisor's next job** (§8, still pending): move from
per-finding explanation to **portfolio analysis** over the master
timetable - `RULE_GUIDANCE` for the two new rules is in place, but that's
still one-finding-at-a-time explanation, not a summarisation endpoint.

**Shipped value:** answers the "consistent rooms, consistent teachers"
half of the ask directly, without writing a single byte. The "improve
loads" half stayed unbuilt on purpose - the data doesn't support it yet
without either a school conversation or richer non-lesson-duty data (see
`docs/full-timetabler-plan.md` §4.3's `Meetings`/`UnscheduledDuties` note).

---

### Phase C — Blocking pattern, read-only → editable · **M** · **read-only half done 2026-08-12**
The board TTS makes you infer from spreadsheets, now a real page
(**Blocking** in the sidebar, `GET /api/blocking-lines`): one grid per
TTS grouping label, rows = roll class, columns = line, cell = the
class(es)/teacher/room on that line for that roll class.

Building it against the real data corrected an assumption from Phase A:
the row-group label (`"10A"`, `"12"`, etc) is **not reliably a year
level**, despite most of them looking exactly like one. Group `"12"`
turned out to cover every roll class's Fratelli/Assembly/Break slot -
7A through the RTC support class - not Year 12 specifically. The page
shows TTS's own grouping code verbatim ("Group 12") rather than the
"Year group 12" label it shipped with for about ten minutes before this
was caught in browser verification - see `docs/data-formats.md` #5 item
4 for the correction.

Editable — drag a class group between lines — is Tier 3 and waits on
Phase 0. 2 new tests; 145 passing (was 143).

**Value:** for the first time the school can *see* why the structure
produces the clashes the Findings page reports.

---

### Phase D — Entity authoring · **L** · 🔒 *gated on Phase 0*
Teachers, rooms, class names; students **scoped** (§7.3).

Core new concept: **provenance**. Every entity row gains
`origin ∈ {IMPORTED, AUTHORED}` and authored rows carry a minted GUID.
The re-ingest machinery (`docs/reingest-persistence.md`) already knows how
to preserve app-owned data across a wipe — authored entities extend that
same pattern rather than inventing a new one.

---

### Phase E — Scenarios · **M** *(smaller than it looks)*
Deferred twice, and each time correctly. But it's now cheap: a scenario
is **a named, long-lived change set you can view the timetable
through** — and `app/analysis/whatif.py` already applies a change set to
an in-memory copy of the timetable and re-runs every rule. That is 80% of
a scenario engine. What's missing is a scenario selector in the UI and
making the grid/Findings read "through" the active scenario. This is
mostly plumbing, not architecture.

---

### Phase F — Roll-over: author a whole file · **L** · 🔒
Template-based per §5(a). New year, same school: copy `Settings`/`Days`/
`Periods`/unmodelled sections, regenerate entities + structure +
timetable. Extend the six export gates with **section-coverage** and
**GUID-integrity** checks.

---

### Phase G — Explicit constraint model · **L**
Today constraints are implicit in hard-coded rules. A real timetabler
needs them as *data*: per-teacher unavailability, room pools (RURs give
us the format), subject→room preference, doubles requirements, max
gaps. Adopt a subset of FET's taxonomy (§2). This is the prerequisite for
a solver — and it is independently useful, because it makes the rules
engine configurable instead of hard-coded.

---

### Phase H — Solver · **XL** · *separate go/no-go decision*
OR-Tools CP-SAT (Apache-2.0, Python-native). **Assisted, not
autonomous** — consistent with everything this project has done:

- *Not* "Run Solver → here's your timetable."
- Instead: "fill these 14 unallocated lessons", "rebalance these 6
  over-loaded teachers", "find a room-stable arrangement for Year 9" —
  bounded sub-problems whose output lands in the **existing change-set
  review pipeline** and must be approved like any human edit.

Every solver result already has a validator: `whatif.py`. That is a
genuinely strong position to build a solver from.

---

## 7. UI/UX

### 7.1 Information architecture

Current sidebar: Dashboard · Timetable · Teachers · Findings · Composite
Review · Change Sets · Audit.

Target, grouped (the flat list stops scaling around 10 items):

```
OVERVIEW     Dashboard
STRUCTURE    Curriculum · Blocking · Classes
PEOPLE       Teachers · Students
PLACES       Rooms
TIMETABLE    Master grid · Scenarios
QUALITY      Findings · Composite Review · Constraints
CHANGES      Change Sets · Audit · Export
```

### 7.2 The five interactions that beat TTS

1. **Live constraint feedback, not run-then-check.** Dragging a lesson
   should shade every legal target slot *before* the drop. We already
   compute this (`suggestions.py` searches the full legal space) — it's
   currently behind a button instead of under the cursor.
2. **A better Clash Matrix.** TTS's headline diagnostic is a matrix. Ours
   should be the master grid with a severity heat overlay, filterable by
   rule — same information, spatially situated instead of in a separate
   report.
3. **Explain-on-hover.** The AI advisor is behind a click on a list item.
   It should be reachable from any cell in the grid.
4. **Branch and compare.** Two scenarios side by side, diff highlighted.
   TTS has save files; we can have real comparison.
5. **Search everything.** One box: teacher code, room, class, student —
   jump straight to their grid.

### 7.3 🔒 Identity governance — a line to hold

"Adding students" deserves a explicit boundary, because it is a genuine
step change in this project's risk profile.

There is a difference between GridPilot **holding** imported student data
(already true — 560 students) and GridPilot **becoming the place student
identity is created and edited** (new). The school's SIS is the system of
record for who a student *is*; TTS/eMinerva is the pipe.

**Recommendation, consistent with the 2026-08-06 decision to keep teacher
records code+role only and reject the mockup's DOB/address/emergency-
contact fields:**

- **Author timetable-relevant facts only** — class enrolment, option
  preferences, roll-class placement, cohort membership.
- **Never author identity fields** — name, email, DOB, address, guardian
  contacts. Those stay read-only, sourced from import.
- Same rule for teachers: code, name-from-import, faculty, load, role,
  capability — authorable; personal details — never.

This keeps the existing privacy posture intact while still delivering
everything a timetabler actually needs to do.

---

## 8. The AI advisor's next job

Today: explains one finding, with related findings for context. Good, and
just improved. The next step is what you actually asked for — **pattern
analysis across the master timetable**.

The boundary stays exactly where it is: **the deterministic layer
computes, the model explains.** Phase B's rules produce the numbers
(room-instability counts, load distributions, spread metrics); the
advisor's new job is to read that *portfolio* and answer questions like:

- "Which three changes would most improve room consistency?" — ranked
  from computed candidates, never invented.
- "Why is this teacher's load hard to fix?" — from their actual
  constraint set.
- "What's structurally wrong with Year 10?" — reading blocking lines +
  findings together.

Two additions make this work:

1. **A summarisation endpoint** over a *set* of findings (the current one
   is per-finding), so the model sees the shape of the problem.
2. **A bigger model when the hardware allows.** `docs/ai-advisor.md`
   already documents `GRIDPILOT_OLLAMA_MODEL` as an env var and the
   `think: false` requirement. Portfolio reasoning is a harder task than
   single-finding explanation — this is the natural moment to point it at
   the 9070XT.

---

## 9. What we deliberately won't build

Consistent with the project's practice of writing down refusals:

- **Green-field file creation (Tier 5)** — roll-over covers the real use
  case at a fraction of the risk.
- **Student identity authoring** — §7.3.
- **A publishing/parent portal** — TTS Preferences Manager and the school's
  existing systems own this; competing there is scope suicide.
- **Daily Organiser / cover management** — a genuinely separate product
  with a hard dependency on the **real-calendar mapping this project has
  refused to guess three times** (`PROJECT_ROADMAP.md` immediate
  correction #4). It needs an explicit school-calendar table first.
- **Autonomous solving** — §Phase H.
- **Copying FET or Timefold source** — AGPL (§2).

---

## 10. Open questions for the school

1. **Trial-import the export** (Phase 0) — the 15 minutes that unblocks
   everything.
2. **Does TTS accept a minted GUID?** Determines Tier 2 difficulty.
3. **Should meetings + unscheduled duties + yard duty count toward
   contracted load?** Currently none of them do; 46 + 13 + 246 records
   are being ignored in every load figure GridPilot reports.
4. **Is `2580 min/cycle` the right default?** Now empirically confirmed
   that TTS's own file treats it as the default for *every* teacher who
   doesn't carry an explicit different value (all 74 teachers now
   resolve to exactly 2580) - the open question is whether that's the
   right number for the ~30 who were previously unmeasured, not whether
   the parsing is correct.
5. **Is the goal to replace TTS, or to out-think it?** Everything through
   Phase E works alongside TTS. Phases F–H are where the answer starts to
   cost real money and time.

---

## 11. Recommended sequencing

```
NOW (no write risk, high value, ~2–3 build sessions):
  Phase 0  ← ✅ done 2026-08-12 - trial import passed against real TTS
  Phase A  ← read whole file; fixes the 40% load blind spot - ✅ done 2026-08-12
  Phase B  ← rooms/teachers ✅ done 2026-08-12; loads dropped (needs school input, see §6)
  Phase C  ← blocking pattern, read-only - ✅ done 2026-08-12

THEN (gated on Phase 0 passing):
  Phase D  ← entity authoring
  Phase E  ← scenarios (cheaper than it sounds)

DECISION POINT — "replace or out-think?" (§10.5)
  Phase F  ← roll-over / new file
  Phase G  ← constraint model
  Phase H  ← solver
```

The first block is the highest value-to-risk ratio in this document: it
directly answers *"look at the master timetable, run the local AI to look
for consistent rooms, teachers, improve loads"*, it fixes a real bug
affecting 40% of staff, it surfaces the blocking pattern you asked to
see — and it does all of that without writing a single byte back to the
school's data.

---

## Sources

- [Timetabling Solutions — Products](https://www.timetabling.com.au/products)
- [Timetabling Solutions — Why schools choose](https://www.timetabling.com.au/best-timetabling-software-australia)
- [FET — Free Timetabling Software](https://lalescu.ro/liviu/fet/) · [feature list](https://lalescu.ro/liviu/fet/features.html)
- [UniTime on GitHub](https://github.com/UniTime/unitime)
- [Timefold Solver (Python)](https://github.com/TimefoldAI/timefold-solver-python)
- [Blocking and setting explained](https://teachers.institute/managing-teaching-learning/innovative-timetabling-techniques/)
- Primary evidence: the school's own `TT 2026 Term Three Week 4.tfx`
  (`Settings`, `MRCGs`, section counts) and the GridPilot database.
