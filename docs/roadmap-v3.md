# Roadmap v3 — from analysis tool to timetabling system

*Written 2026-09-07, in response to: "what else needs to be added to make
this a full-fledged timetabling software solution? including all aspects
of timetabling solutions, but better. utilising AI and pc power to
improve lines, grids and the timetable itself."*

*Follows `docs/roadmap-v2.md` (staffing, authoring, design system — items
1–13 of its sequencing table are built) and `docs/solver.md` (the solver
strategy). Like every plan in this repo: recommendations with the
evidence attached, not a commitment, and explicitly not permission to
guess any value marked school-confirmed.*

---

## 0. The one-paragraph version

GridPilot is an excellent **analysis and repair** tool for a timetable
someone else built. It enters the story after blocking and allocation
have happened and stops before anything is published. To be a
*timetabling system* it needs three things it does not have — a
**demand model** (what the school intends to run), an **availability
model** (when staff actually can't be scheduled), and an **output layer**
(something a human can hold) — plus the engines that sit between them.
Everything else in this document depends on those three. The good news
from this pass: one of them is **partially recoverable from the source
file we already hold and currently ignore** (§1.1), and the biggest
single-day win in the whole document is a review queue with **412 pending
decisions and zero completed** (§1.3), which is silently holding two
built rules at zero findings.

---

## 1. Four findings from this pass, in priority order

All four came from querying the real database and the real `.tfx`, not
from reading the design docs.

### 1.1 🔴 `Meetings` is unparsed — 64 teacher-slot commitments are invisible, and the solver treats them as free — **built 2026-09-07**

`docs/full-timetabler-plan.md` §3.2 listed `Meetings` (13 records) as
unparsed because it "carried no load information." That is true, and it
missed the more important half: **`Meetings` carries `PeriodID` and
`MeetingTeachers[]`.** That is not load data. That is *availability*
data — the one thing `docs/solver.md` §4.2 calls the fatal gap and
`docs/full-timetabler-plan.md` §10.6 calls "the single highest-value
unanswered question."

Measured against the real file:

| | |
|---|---:|
| Meetings in the file | 13 |
| Meetings whose period resolves to our cycle | 12 |
| Teacher references, all resolving to a known teacher | 68 |
| **Distinct (teacher, period) commitments recoverable** | **64** |
| Distinct teachers affected | 18 |
| **Of those commitments, how many show as FREE in our model today** | **66 of 68** |

That last row is the finding. `repair_solver.py` and `suggestions.py`
both determine "is this teacher free at this slot" from
`timetable_entry` alone. For 18 staff there are slots where the answer
is currently *yes* and the truth is *no, they are in a standing
meeting*. **The mass-repair solver can today propose moving a lesson
into a teacher's meeting slot, and nothing downstream would catch it** —
`whatif.py` re-runs the rules, and no rule knows meetings exist.

This is a correctness gap, not a feature request, and it is closable
**with no school input at all** — the data is in the file the school
already gave us. It does not close the unavailability question (part-time
fractions and external commitments are still unknown and still
un-inferable, per §12.5 of the plan doc), but it converts it from "we
know nothing" to "we know the 64 hard blocks TTS itself records."

**Built:** `Meetings[]` parses into `teacher_commitment`
(source-derived, rebuilt on re-ingest like every other `.tfx` table -
`app/ingest/tfx_parser.py`'s `_ingest_meetings()`), feeds both
`repair_solver.py` and `suggestions.py` as a hard constraint via one
shared function (`availability_rules.teacher_commitment_busy()` - "one
implementation, not two that could drift"), and a new
`teacher_meeting_clash` rule (`docs/rules.md`) surfaces an existing
violation instead of only preventing future ones.

Verified against the real database, not just synthetic fixtures: the
re-ingest recovered exactly 68 commitment rows across 18 teachers (1
meeting's period doesn't resolve - a real, pre-existing gap in the
school's own file, logged as `meeting_unresolved` and left alone, not
guessed at), with every existing human review decision - 213 capability
rows, 199 room-type rows, 16 composite reviews, 5 change sets -
untouched by the re-ingest. The rules engine produced exactly 2 new
findings, matching a hand-checked query of the source file: `HENE04`
teaching 4 composite class codes during `SSSMB`, and `HOBL02` teaching
`07EP1` during `AERO`. Re-ran the repair solver against 6 real open
double-booking findings with the constraint live - solved cleanly in
under a second, read-only (confirmed no `change_set`/`proposed_change`
rows were created). Size: **S**, as estimated.

### 1.2 🔴 `suggest_fixes()` ignores the room constraints the repair solver enforces — **built 2026-09-07**

Two engines searched the same space with different rules:

| | `class_room_type_constraint` | `room_pool` |
|---|---|---|
| `repair_solver.py` (mass repair) | ✅ enforced | ✅ enforced (roadmap-v2 A2) |
| `suggestions.py` (per-finding "Suggest fixes"), before this fix | ❌ ignored | ❌ ignored |

`docs/solver.md` §9 flagged this in one line — *"the mapping exists and
is queryable, `suggest_fixes()` doesn't consult it yet"* — and it was
still true. The practical effect: the button a human presses most often
could still propose Drama in a science lab, while the solver they press
rarely could not. Same domain model, two implementations, silently
divergent.

**Built:** `required_room_type_by_class()` (promoted from an inline
dict in `repair_solver.py` into `room_type_constraints.py`) and
`pool_room_ids_by_class()` (promoted from `repair_solver.py`'s private
`_pool_room_ids_by_class` into `room_pool_rules.py`) are now the one
shared implementation both engines call - loaded once per
`suggest_fixes()` call, checked in `_try_candidate()` as a hard
constraint alongside room capacity, before anything expensive runs.

Verified with two new synthetic tests mirroring the repair solver's own
room-type and room-pool tests exactly (never propose a wrongly-typed
room; never propose a room outside a pool). Checked against the real
database too, honestly reported: **currently dormant in practice**, not
because the fix doesn't work but because there's nothing yet for it to
catch - 0 of 199 room-type candidates are `APPROVED` (§1.3's backlog) and
none of the 28 real `room_pool`-member classes currently has an open
double-booking/room-double-booking finding. The fix is correct and will
matter the moment either changes; verified live against a real
`room_double_booking` finding to confirm nothing broke (identical
candidates before and after, no console errors).

The per-entry endpoint §12.6 of the plan doc also identified (to unblock
live-drag legal-slot shading, §4.4 below) was **not** built in this
pass - scoped down to the correctness fix alone, since that refactor is
a separate, larger change to the API surface, not required for this
gap. Size: **S**, as estimated for the correctness fix; the endpoint
refactor remains open under item 8 of the sequencing table.

### 1.3 🔴 412 review decisions pending, 0 completed — two built rules are producing nothing — **room-type half built 2026-09-07**

The detect → human-confirm → rule pattern is this project's best idea
and is now built three times over. Its throughput to date:

| Queue | Detected | Reviewed | Rule it gates | Findings that rule produces |
|---|---:|---:|---|---:|
| Room-type constraints | 199 | **0** | `room_feature_mismatch` | **0** |
| Teacher capability | 213 | **0** | `teacher_not_qualified_for_class` | **0** |
| Composite groups | 16 | 16 ✅ | clash suppression | working |

Composite review worked because 16 decisions is an afternoon. 412 is
not, and no amount of search-box polish (roadmap-v2 §4.4, built) changes
that arithmetic. **Two rules built and tested against real data are
returning zero findings, and the solver's most valuable domain reduction
is switched off, because nobody can face 412 individual clicks.**

This is the highest-value unblocked item in the document and it is not a
solver problem:

- **Bulk review over a filtered set** — "confirm all 47 candidates at
  100% consistency", "confirm every capability where the teacher has
  taught that subject 5+ times this cycle." The confidence signal is
  already computed and displayed (`matching_lesson_count/total`,
  `N lesson(s) observed`).
- **Confidence-ranked ordering** so the ambiguous 20 surface first and
  the obvious 380 can go in one action.
- **Provenance stays honest**: a bulk decision records the same
  `reviewed_by` + the filter that produced the batch, so an audit can
  reconstruct exactly what was agreed to in one click.

This is the "new category of risk" I flagged last session — mass state
change from one action. It is worth doing *precisely because* the
alternative (the status quo) is that the review never happens at all,
which is strictly worse than a reviewed batch with an audit trail.

**Built for room-type constraints, deliberately not for teacher
capability - here's why.** Asked the user how aggressive this should be
before building anything: **bulk-approve above a confidence threshold**
(not "approve everything currently filtered" - too general; not
per-row checkboxes - too many clicks for the problem it solves), gated
behind **typing the exact count to confirm** (`approve 167`), since
nothing else in this app lets one action change more than one record.
`POST /room-constraints/candidates/bulk-approve` takes an explicit id
list from the frontend (not a live re-query at commit time, so what a
human confirmed is exactly what gets written), applies it in one
transaction, and logs **one** audit event for the whole batch.

The threshold itself came from the real distribution, not a guess: of
199 pending room-type candidates, **167 (84%) sit at exactly 100%
consistency** - the same ratio `room_type_constraints.py`'s own
detection heuristic already relies on, just at its top slice. Verified
live against the real database, not just synthetic fixtures: confirmed
the exact phrase requirement rejects a wrong string, approved all 167
in one action, confirmed the audit log shows one event listing all 167
ids, confirmed the 32 genuinely-ambiguous candidates (mostly 88%
ratios) were untouched and still render for individual review - then
reverted every row to `PENDING` and re-ran the rules engine to restore
the exact pre-verification state (158 open findings, matching before
and after; the transient `room_feature_mismatch` findings that appeared
during the test correctly resolved rather than left dangling).

**Teacher capability does not get the same treatment, because the data
doesn't support it.** Checked the real distribution before building
anything (same discipline `docs/room-constraints.md`'s own detection
heuristic was chosen with): `teacher_capability`'s only numeric signal
is `lesson_count` (embedded in a free-text `notes` field, not even a
structured column), and its real distribution has **no clean cutoff** -
1 through 50, with mass at both 1-2 (39 candidates) and 8 (54
candidates) and nothing resembling room-type's 84%-at-100% signal. A
structural alternative was checked too - "the teacher has only one
candidate subject at all, so there's nothing to weigh it against" -
covers just **3 of 213** real candidates, too small to matter. Building
a numeric threshold here anyway (e.g. "lesson_count ≥ 5") would be
exactly the invented-policy-value trap this project has refused
throughout. **Left open** - not because bulk review is a bad idea for
this queue, but because it needs either a different design (the
selection-checkbox option, explicitly declined for room-type, might
still be right here) or a real signal this pass didn't find. Size: **M**
for the part that shipped; the teacher-capability half stays unscoped.

### 1.4 🟡 The `.sfx` holds allocations, not unmet demand — this reframes the blocking prize

`docs/solver.md` §8 proposes the blocking optimiser as *"strong
candidate for the actual highest-value solver work, and it needs no new
data at all"*, with the motivating question: *"if we move Psychology from
Line C to Line E, how many students get their full first-preference
set?"*

Checked against the real data, that specific question is **not currently
answerable**:

| | |
|---|---:|
| `sfx_student_preference` rows | 6,756 |
| Students with preferences | 560 of 560 |
| Preferences per student | 8–18 (median 12) |
| Rows resolving to a class in the current timetable | 4,328 |
| **Satisfaction rate, every rank 1 through 18** | **100%** |

A 100% satisfaction rate at rank 18 is not a triumph of blocking; it
means these rows are the *resolved allocation*, not the wish list. The
2,428 rows that don't resolve are Year 8 rotation electives
(`08VARTS1`, `08JPN1`, `08DRA1` …) sitting on `T1A`/`T2A`/`T4D` lines
that don't exist in this term's `.tfx` at all — a different rotation
structure, not unmet demand either.

**What this rules out:** counterfactual preference-satisfaction scoring.
Without the raw pre-allocation submissions (which live in TTS
Preferences Manager, not in the `.sfx` export), we cannot say how many
students *would have* got their first choice under a different line
arrangement. Building that on this data would be inventing the input.

**What it does not rule out — and this is still a real prize.** We know
every one of 560 students' *complete actual subject set*, plus 193
subjects with `class_size_maximum`, 60 lines, and 16 curriculum
constraints. That supports a genuinely useful class of question, all
computable today:

- **Which subject pairs are structurally impossible?** Two subjects on
  one line can never be taken together — a fact about the structure,
  invisible in TTS until a student asks for both.
- **Which lines are over- and under-loaded** against `class_size_maximum`,
  and where does a line's demand exceed the classes provisioned for it?
- **Would a different assignment of subjects to lines serve the exact
  same 560 subject sets with fewer classes, or better-balanced ones?**
  This is a set-partitioning problem CP-SAT solves well, it uses only
  data we hold, and it answers "improve the lines" honestly — as
  *re-optimising against revealed demand*, not as satisfaction
  counterfactuals we can't evidence.

**Recommended:** rename the ambition rather than drop it. Build
**blocking analysis on revealed demand** (§4.1), and put "obtain raw
preference submissions from Preferences Manager" on the school question
list (§6) as what would unlock true counterfactuals later.

---

## 2. The pipeline gap map

The TTS workflow, from `docs/full-timetabler-plan.md` §1.2, with what
GridPilot actually does at each stage:

```
Curriculum  →  Blocking  →  Allocation  →  Timetable  →  Publish  →  Daily Org
 (what runs)  (what runs    (who teaches   (which slot)  (staff/     (cover,
               in parallel)  what)                        students)   changes)
```

| Stage | TTS product | GridPilot today | Gap |
|---|---|---|---|
| **Curriculum** | Version 10.1 setup | ❌ nothing — no record of intended offerings | **`teaching_requirement` (§3)** |
| **Blocking** | Version 10.1 + Preferences Manager | 🟡 read-only view (29 lines, 169 links) + per-line finding counts | Analysis, then optimisation (§4.1) |
| **Allocation** | Staffing (cloud) | 🟡 capability data (213 rows, unreviewed) + EA load policy | No allocation engine (§3.2) |
| **Timetable** | Version 10.1 solver | ✅ **stronger than TTS** — rules, repair solver, what-if, suggestions | Mode B/C (§4.2) |
| **Publish** | Daily Reports, exports | ❌ **nothing** — `.tfx` patch only | Output layer (§5) |
| **Daily Org** | Daily Organiser | ❌ deliberately refused | Decision point (§6) |

Read that honestly: GridPilot is genuinely ahead of TTS in exactly one
column, and absent from three. "Full-fledged" means filling the three,
in dependency order — and the leftmost gap is the one everything else
rests on.

---

## 3. The missing spine: a demand model

### 3.1 `teaching_requirement` — the single biggest structural hole

Every table in the database describes **what happened**: 2,181 timetable
entries, 6,726 enrolments, 248 class groups. Nothing describes **what
the school intended to run** — "Year 9 Science: 6 classes, 5 periods per
cycle each, max 28 students, must be a Science room, needs a
Science-qualified teacher."

That record is the input to three separate things GridPilot cannot
currently do:

1. **Allocation** — you cannot assign teachers to classes that aren't
   declared.
2. **Blocking** — lines are arrangements *of* requirements.
3. **Construction (Mode C)** — `docs/solver.md` §2.3's "build the cycle
   from demand data" has no demand data to build from.

It is also the missing dependency under three things already designed
and parked: `docs/staff-capability-model.md`'s full six-step precedence
(the "requirement lock/preference" steps), `docs/staffing-priority-policy.md`
(`allocation_priority`, `lock_status` are declared as fields *on*
`teaching_requirement`), and that doc's `BLOCKING` staffing-health
finding — which it describes as "one of the first useful things to build
once the capability tables land." The capability tables landed
(2026-08-17); the requirement table is what's still missing.

**Bootstrappable, like everything else here.** The current timetable
already implies most of it: each `class_name` with its period count, its
enrolment, its observed room type (199 candidates detected), and its
observed teacher (213 candidates detected). The same detect → confirm →
use pattern applies, and would produce a real curriculum model from the
resolved timetable in one pass. Size: **L**, and it unlocks more than
anything else in this document.

### 3.2 Allocation — the module TTS sells separately

With `teaching_requirement` + `teacher_capability` + EA load caps
(`agreement_load_rule`, built) + `teacher_profile.fte` (built), "who
teaches what" becomes a solvable assignment problem with a real
objective: respect capability, stay under the contact cap, honour FTE,
balance load across a faculty, minimise the number of teachers per class
(`class_teacher_inconsistency` is already the metric).

Worth noting what makes this *better* than TTS Staffing rather than a
clone: TTS allocates, then you inspect. GridPilot already has the
what-if validator, the finding-diff, and the change-set approval gate —
an allocation run lands as a reviewable proposal with an English
explanation, the same shape mass repair already proved. Size: **L**,
gated on §3.1.

---

## 4. Where AI and compute genuinely change the game

The user's ask, precisely: *improve lines, grids, and the timetable
itself*. Taking those in order.

### 4.1 Lines — blocking analysis, then blocking optimisation — **Phase 1 built 2026-09-07**

Per §1.4, honestly scoped. Two phases:

**Phase 1 — analysis (no new data, no solver).** Subject-pair
impossibility matrix; line load vs `class_size_maximum`; which lines
carry the tightest demand; which classes are structurally
over-subscribed. This is the `docs/full-timetabler-plan.md` §12.4 work,
half-built already (roadmap-v2 item 5 shipped per-line finding counts
and per-course enrolment, and deliberately stopped short of judgements
it couldn't evidence).

**Built, computed entirely from the .sfx subject-selection export cross-
referenced with real enrolment - `GET /blocking-demand`
(`app/analysis/blocking_demand.py`) and a collapsible "Subject-selection
demand" panel on the Blocking page (`BlockingDemand.tsx`).** Three
things, all facts, none asserted as a verdict:

- **Subject-pair impossibility matrix** - a subject confined to exactly
  one `sfx_line` can never be combined with another subject also
  confined to that same line (a student picks at most one class per
  line). Against the real export: **22 lines, 126 pairs** - e.g. Year 12
  Line L6 locks a student out of taking more than one of `12AIP`,
  `12CHE`, `12DRA`, `12LST`, `12PE`, `12SIS122C2`, `12TAFE`.
- **Per-line demand pressure** - real enrolment against the school's own
  stated `max_class_size`, summed per line. The tightest: Line "11" at
  95% (90/95 seats), `SP` at 94%, the Year 10 art/tech rotation lines at
  93%.
- **Under-subscribed classes** - real enrolment vs cap, for classes
  running below half full. **55 of 181** genuine elective classes, 12 of
  them at zero enrolled (`10EP4`, `10MAT4`, `11EMA2` …) - a real,
  actionable "why does this class exist with nobody in it" list.

**The one judgement this deliberately does not make: "structurally
over-subscribed."** Checked against real data first - naively joining
`sfx_class.max_class_size` to enrolment (matching blocking.py's own
"detect, never assert" discipline) found 199 of 445 classes reading as
over their cap, which fell apart on inspection: house/pastoral groups
(`IGN5`, `SOL5`, `ASM-AQU5` …) reuse the same `class_code` across every
roll class with unrelated `max_class_size` values per row, and every one
of them resolves to `entry_type = REGISTRATION`, not a taught elective.
Restricting to `class_code`s that resolve to a real `LESSON` entry (the
same LESSON-only convention `app/analysis/contact_time.py` already
established) makes `class_code` unique again and the false "over
capacity" signal disappears entirely - **0 of 181** real elective
classes currently exceed their stated cap. That absence is itself worth
recording, and is the reason "over-subscribed" isn't a heading above.

Verified against the real database (283 backend tests pass, +5 new for
this module) and live in the browser: the panel renders all three
sections against the real `.sqlite3`, numbers match a direct script
query byte-for-byte, no console errors. Phase 2 (CP-SAT
re-optimisation against this revealed demand) stays open - size **L**,
tracked separately as sequencing item #11.

**Phase 2 — re-optimisation against revealed demand (CP-SAT).** Given
560 fixed subject sets, 193 caps and 16 curriculum constraints: is there
an arrangement of subjects into lines that serves the same demand with
fewer clashes, better-balanced classes, or fewer classes overall? Same
run-compare workflow as §4.2. **This is the highest-leverage compute in
the document**, because blocking mistakes are the ones that make a
timetable impossible three months later, and it is the stage TTS splits
across two products without ever answering the counterfactual. Size:
**L**.

### 4.2 The timetable — make a solver run a first-class object — **built 2026-09-07**

`docs/solver.md` §6 specifies a `solver_run` table (mode, scope,
weights, status, objective, moves, findings resolved/introduced,
optional change set) and the run-compare workflow around it. **It was
never built** — a mass-repair run either became a change set or
vanished.

That is the difference between a button and a tool. The real workflow is
*run → inspect → "too much movement" → adjust → re-run → compare → keep
one*, and "Run 3 fixed 18 findings with 22 moves; Run 4 fixed 20 with
61" is not just a nicety — per `docs/solver.md` §3.3 it is **the
interface for the objective-weight conversation with the school**,
turning an abstract policy question into a concrete A/B choice.

**Built, deliberately scoped down from the full spec.** Every call to
`POST /solver/repair` now persists a `solver_run` row
(`app/analysis/solver_run.py`) - `GET /solver/runs` lists recent runs,
`GET /solver/runs/{id}` returns full detail including the move list. A
collapsible "solver run history" panel on the Findings page
(`SolverRunHistory.tsx`) lists them and lets two be selected for a
side-by-side comparison - exactly the "Run 3 vs Run 4" table
`docs/solver.md` describes.

Two things in the original spec were deliberately **not** built, and
here's why: **`weights_json`** isn't a column, because the solver has no
adjustable objective weights to record yet (movement-cost only,
`docs/solver.md` 3.3) - adding the column before the weights themselves
exist would be a schema guess, not a fact. **"Runs are cheap to
discard, a change set is created only when the user says keep this"**
was *not* implemented - that would change the existing "Repair with
solver" button's behaviour (today, a successful run auto-creates a
change set), and changing an existing feature's behaviour wasn't
something to do silently inside a persistence-layer change. Today's
persistence is purely additive: the existing button works exactly as it
did, and every run - kept or not - is now remembered.

Verified live against the real database: two bounded single-finding
repairs recorded two real `solver_run` rows correctly (status, move
count, `change_set_id`, most-recent-first ordering); selecting both in
the UI rendered the side-by-side comparison; `GET /solver/runs/{id}`
returned the full move list. Reverted afterward - deleted both test
change sets and their proposed changes, both `solver_run` rows, and
both audit events, confirmed findings/change-set counts matched the
pre-test baseline exactly (also caught and removed 3 unrelated stray
audit rows left over from earlier verification passes this session,
sharing the same `verification-script` actor name - a genuine, if
overdue, bonus cleanup). Size: **M**, as estimated; the discard/keep
redesign and adjustable weights stay open.

Mode B (regional rebuild) and Mode C (construction) stay where
`docs/solver.md` put them — behind teacher unavailability (§1.1 makes a
dent) and, for C, behind §3.1.

### 4.3 Infeasibility explanation — the actual product gap — **built 2026-09-07**

The most valuable single item in `docs/solver.md` (§7.2) and still
unbuilt. When a solver returns INFEASIBLE it has proven something
enormously useful in a useless form; CP-SAT can produce the minimal
contradictory subset, and the local model can turn it into *"Year 10
Science needs 5 periods across 4 lab-capable rooms, but three of those
are already committed to Year 11 — the structure can't fit, this isn't a
scheduling problem."*

**TTS tells you the clash. Nothing on the market tells you the structure
is impossible.** This is where "better than TTS" stops being a slogan.
It is a genuine language task on top of a genuine computation, it stays
strictly inside the explain-never-decide boundary
(`docs/ai-advisor.md`), and it applies to blocking runs (§4.1) as much
as timetable runs. Size: **M**, gated only on §4.2.

**Built, deliberately scoped down from a full minimal-unsatisfiable-core
extraction.** A true CP-SAT assumption-based MUS would mean
reformulating `repair_solver.py`'s model with assumption literals - a
real rewrite of a tested, load-bearing 550+ line module, for a return
that's provably correct but no more *useful* than a cheaper question:
for each timetable entry behind a finding mass-repair left unresolved,
**"if this lesson were the only thing allowed to move, is there ANY
legal slot for it at all, right now?"** - the same three-layer check
(teacher, then student, then room) `repair_solver.py`'s own
`_feasible_candidates` uses, so the answer is guaranteed consistent with
what actually makes the solver fail
(`app/analysis/infeasibility.py`). When the answer is no, the layer
that ran out is a real, provable bottleneck. When the answer is yes -
the lesson has options alone but the joint problem still failed - that's
a genuine multi-lesson interaction a single-entry check can't diagnose,
and it's reported honestly as that (`has_legal_slot: true`, no invented
cause) rather than fabricating a specific reason - the same "detect,
never assert" discipline as everywhere else in this project.

The explanation itself reuses the existing local-Ollama advisor
(`app/advisor/explain.py`, `docs/ai-advisor.md`) rather than a new AI
integration - `explain_infeasibility()` shares the same
host/model/timeout/error-handling call (`_generate()`, factored out of
what was two copies of the same ~25 lines) as the finding-explain
feature, with its own prompt built only from the structured facts
`infeasibility.py` computed. `POST /solver/runs/{id}/explain-infeasibility`
surfaces as an "Explain" link next to any solver run with unresolved
findings, in the same collapsible run-history panel §4.2 built
(`SolverRunHistory.tsx`).

Verified against the real database and a real (not mocked) local Ollama
call, twice - once via a direct API call, once end-to-end through the
browser UI. A real mass-repair run over the live timetable's 46 open
eligible findings resolved 6 and left 40 findings behind (45 distinct
entries) as genuinely unresolved; the diagnosis correctly found six real
`10SCI3` entries with `matching_rooms_total: 0` (the school has zero
rooms matching whatever pool that class is confined to - a genuine,
provable bottleneck) among 39 entries individually placeable but stuck
in joint conflicts, and the model's explanation named the `10SCI3`
bottleneck specifically and correctly described the rest as a multi-
lesson interaction rather than inventing a cause for them - unprompted,
matching the diagnosis data exactly. Reverted afterward: deleted the
verification `solver_run` row, its `change_set`/`proposed_change` rows
(still DRAFT, never approved - nothing in the live timetable itself was
ever touched), and the `mass_repair_run` audit event. 291 backend tests
pass (+8 new: 4 for the diagnosis logic, 4 for the endpoint, mocked
per `test_findings_explain_api.py`'s existing hermetic pattern).

### 4.4 Grids — live constraint feedback instead of run-then-check — **built 2026-09-07**

`docs/full-timetabler-plan.md` §7.2 item 1, still unbuilt: dragging a
lesson should shade every legal target slot *before* the drop. We
already compute exactly this — it is behind a button (`Suggest fixes`)
instead of under the cursor. Needs the per-entry candidate endpoint from
§12.6, which is the same refactor §1.2 needs. Size: **S–M** once that
lands.

Also still open from that list: **explain-on-hover** from a grid cell
(the advisor is reachable only from the Findings list), and
**side-by-side scenario diff** (the Viewing selector renders one
scenario at a time, not two next to each other).

**Built, deliberately reinterpreted for the interaction model that
actually exists.** Checked against the real UI first: this app has no
drag-and-drop anywhere - a move is proposed through `LessonInspector`'s
"Move manually" tab, four plain dropdowns (day/period/room/teacher) with
zero live feedback until "Propose this move" is clicked. Building real
drag-and-drop across `MasterTimetableGrid`/`TimetableGrid` would be a new
UI paradigm with no precedent in this codebase, reconciling awkwardly
with the click-to-select/keyboard-nav flow those grids already have -
confirmed with the user before building rather than assumed. The actual
product need - "live constraint feedback instead of run-then-check" -
maps directly onto the dropdowns that already exist.

The §12.6 per-entry candidate endpoint is real:
`GET /timetable-entries/{id}/legal-slots`
(`app/analysis/suggestions.py`'s `legal_slots_for_entry()`) answers "is
there any legal room for this lesson's teacher/students at this slot,
right now" for an arbitrary entry, no finding required - the same three-
layer check (teacher, student, room type/pool/capacity) `repair_solver.py`
and `infeasibility.py` (§4.3) use, deliberately the cheap check rather
than `suggest_fixes()`'s full re-validation: at ~50 slots × 15+ rooms per
lesson, hundreds of full rules-engine passes would be wasted work for
what is only ever a live UI hint - "Propose this move" still runs the
real, authoritative check before anything is written, exactly as it
always has. `LessonInspector` fetches this once per selected lesson and
marks illegal day/period options and rooms with ⚠, cross-filtering as the
user changes either (pick an illegal period and the day options update to
show which days it *would* work on), plus a live status line summarising
the currently-selected combination.

Verified live against the real database: opened a real lesson
(`08HIS3`, teacher Ryan Gordon), confirmed the home slot read "✓ This
slot and room look free," then changed the period dropdown to one where
that teacher has another real fixed lesson - the day/period dropdowns
correctly re-flagged and the status line correctly read "⚠ Not free -
the teacher or a shared student already has something else then,"
matching the real clash. No console errors; nothing written (read-only
throughout, no cleanup needed). 299 backend tests pass (+8 new).

Explain-on-hover and side-by-side scenario diff remain open, unbuilt -
neither shares this pass's mechanism (one needs the Ollama advisor
reachable from a grid cell, the other needs the Viewing selector to
render two scenarios at once) and each is its own follow-up.

### 4.5 A portfolio advisor, not a per-finding one

`docs/full-timetabler-plan.md` §8: the advisor explains one finding.
The next job is reading the *set* — "what's structurally wrong with Year
10?", "which three changes would most improve room consistency?" — which
needs a summarisation endpoint over a filtered finding set, and a bigger
local model. The deterministic layer still computes; the model still
only explains. Size: **M**.

### 4.6 A timetable quality score

Deliberately refused in 2026-08-06 ("inventing scoring logic just to
fill a tile"), and that refusal was right *then*. It stops being
invention once the solver's objective exists (§4.2): the score becomes
"the objective value the school's own confirmed weights produce," which
is a real number with a defensible derivation. Revisit **after** weights
are agreed, not before.

---

## 5. The output layer — a full solution hands something to a human — **printable timetables built 2026-09-07**

Currently: **zero**. No print view, no PDF, no per-person timetable
export. The only output is a patched `.tfx` for TTS to re-read. A
timetabler's actual week involves handing a timetable to 74 staff and
560 students, and today GridPilot cannot produce one.

Missing, all completely unblocked, none needing new data:

- **Per-teacher / per-room / per-roll-class printable timetables** — the
  single-entity grid already renders exactly this; it needs a print
  stylesheet and a batch export.
- **Wall chart / master grid export** — the master grid, paginated.
- **Per-student timetables** — the data exists (6,726 enrolments);
  nothing renders it. Note this is the one output touching student
  identity, so it stays read-only per §7.3.
- **CSV/JSON exports** of findings, loads, utilisation for the school's
  own reporting.

Size: **M** for the whole set. This is unglamorous and it is the
difference between "a tool the timetabler uses" and "the system the
school runs on."

**Built, deliberately scoped to print-CSS over the existing grids, not a
new rendering pipeline.** The single-entity and master grids already
render exactly what a printed timetable needs, so this is browser
print-to-PDF over those same components rather than a server-side PDF
generator: a "Print" button (`IconPrinter`, `TimetablePage.tsx`) calls
`window.print()`, and Tailwind `print:` variants hide app chrome
(sidebar, toolbar, mode/density/axis controls, the Print button itself)
and let every clipped, viewport-scrolling wrapper — `App.tsx`'s
`<main>`, `TimetablePage.tsx`'s outer container and grid wrapper,
`MasterTimetableGrid.tsx`'s and `TimetableGrid.tsx`'s inner scroll
regions — expand to their natural full height so the grid prints in
full across as many pages as it needs, instead of the one screen's
worth that's currently scrolled into view. `index.css` adds one
non-Tailwind-expressible rule, `@page { size: landscape; margin: 12mm }`,
since a timetable grid is wide, not tall.

Three items from the original scope were deliberately **not** built in
this pass, and here's why: **batch export** (all teachers/rooms/roll
classes at once) needs a print-all-entities flow with its own UI, not
just CSS, and nothing today needs more than "open this teacher, hit
print" one at a time. **CSV/JSON exports** and **per-student
timetables** are unrelated surfaces (tabular data export; a new
identity-sensitive read-only view) that don't share the print-CSS
mechanism this pass built, and per-student timetables still carry the
§7.3 student-identity caveat regardless of export format. All three
remain open, unblocked, and could each be their own small follow-up.

Verified: `npm run build` and `npm run lint` clean; live in the browser,
the Print button renders in both master-grid and single-entity modes,
and the compiled stylesheet was inspected directly (via the page's own
`document.styleSheets`) to confirm every expected rule compiled
correctly — `.print\:hidden`, `.print\:block`, `.print\:h-auto`,
`.print\:overflow-visible`, `.print\:p-0`, and the landscape `@page`
rule all present under `@media print`. No console errors in either
mode. This is a display-only change touching no data, so there is no
live-database cleanup step; the backend's 278 tests pass unaffected.
Size: **S** for what shipped (print CSS only); the deferred items keep
the set at roughly **M** overall, as originally estimated.

---

## 6. Decision points — these are yours, not mine

1. **Daily Organiser.** Deliberately refused in
   `docs/full-timetabler-plan.md` §9, on the correct grounds that it is a
   separate product with a hard dependency on a real-calendar mapping
   this project has refused to guess three times. "All aspects of
   Timetabling Solutions" includes it. Building it means first building
   a school-calendar table (cycle day → real date), which is a
   *conversation*, not an inference. **My recommendation: not yet** —
   it's the furthest from the current strength and the closest to
   TTS's.
2. **Raw preference submissions.** Would unlock true blocking
   counterfactuals (§1.4). They exist in Preferences Manager; can they be
   exported?
3. **Teacher unavailability, still #1.** §1.1 recovers the 64 meeting
   blocks. Part-time fractions, external commitments and leadership
   release still cannot be inferred — and now that `teacher_profile.fte`
   exists (roadmap-v2 §2.4), there is somewhere to put the answer.
4. **Replace or out-think?** (`§10.5` of the plan doc, still open.)
   Everything through §4 works alongside TTS. §3.1 + §3.2 + Mode C is
   where GridPilot starts trying to replace it, and that is a
   materially different commitment.

---

## 7. Sequencing

| # | Item | § | Blocked on | Size |
|---|---|---|---|---|
| 1 | ✅ Parse `Meetings` → availability constraint + rule | 1.1 | — | S |
| 2 | ✅ `suggest_fixes()` honours room-type/pool | 1.2 | — | S |
| 3 | 🟡 Bulk review — room-type done (167/199 unblocked), teacher-capability open (no clean signal found) | 1.3 | — | M |
| 4 | ✅ `solver_run` + run-compare — persistence/history/compare built; discard-until-kept + adjustable weights still open | 4.2 | — | M |
| 5 | ✅ Printable/exportable timetables — print-CSS over existing grids built; batch export, CSV/JSON, per-student deferred | 5 | — | M |
| 6 | ✅ Blocking analysis on revealed demand — Phase 1 built (impossibility matrix, line pressure, under-subscribed classes); Phase 2 CP-SAT re-optimisation is #11 | 4.1 | — | M |
| 7 | ✅ Infeasibility explanation — per-entry "is there any legal slot at all" diagnosis + local-Ollama explanation built; full MUS extraction deliberately not attempted | 4.3 | — (#4 done) | M |
| 8 | ✅ Live legal-slot feedback — §12.6 per-entry endpoint + dropdown shading built, reinterpreted from drag (no precedent in this UI) to the existing move-manually form; explain-on-hover and scenario diff still open | 4.4 | per-entry candidate endpoint (§12.6 of the plan doc - not built by #2, which fixed the room-type/pool gap but not this) | S–M |
| 9 | Portfolio advisor (set summarisation) | 4.5 | — | M |
| 10 | `teaching_requirement` — bootstrap + review | 3.1 | — | L |
| 11 | Blocking optimiser (CP-SAT) | 4.1 | #6, #10 | L |
| 12 | Teacher allocation engine | 3.2 | #10 | L |
| 13 | Parse `UnscheduledDuties` + `Groups` | 1.4, 2 | school Q3 for load | S |
| 14 | Mode B regional rebuild | 4.2 | unavailability | L |
| 15 | Quality score from agreed weights | 4.6 | #4 + school | S |
| 16 | Mode C construction (roll-over only) | 4.2 | #10, #14, go/no-go | XL |
| 17 | Daily Organiser | 6 | calendar table + explicit decision | XL |

**Items 1–6 need nothing from anyone** and are worth roughly a session
each. Item 3 is the one I'd do first regardless of order: it is the only
item that makes work already done start producing value, rather than
adding more.

**Item 10 is the fork in the road.** Everything above it improves the
tool GridPilot already is. Everything below it builds the system TTS
currently is. They are both defensible; they are not the same project,
and the second one should be started deliberately rather than drifted
into.

---

## 8. What does not change

- **Nothing auto-applies.** Every engine here — allocation, blocking,
  construction — produces a proposal into the existing change-set
  approval gate. `docs/solver.md` §11 holds for all of them.
- **The model never decides.** It explains computed facts. A bigger
  model and a harder explanation task do not move that line.
- **No guessed policy values, no guessed calendar, no invented
  thresholds.** Every number in this document was queried, not
  estimated; every gap that needs a school answer is listed in §6 rather
  than filled in.
- **Student identity stays read-only** (`full-timetabler-plan.md` §7.3),
  including in §5's per-student output.

---

## Sources

- `docs/full-timetabler-plan.md` — pipeline (§1.2), read gap (§3.2),
  write ceiling (§3.3), refusals (§9), open questions (§10), inference
  candidates (§12)
- `docs/solver.md` — three modes, the CP-SAT model, `solver_run` (§6),
  infeasibility explanation (§7.2), the blocking prize (§8)
- `docs/roadmap-v2.md` — staffing/EA, capability, authoring, design
  system; items 1–13 built
- `docs/staffing-priority-policy.md` — the `BLOCKING` staffing-health
  finding waiting on `teaching_requirement`
- `docs/staff-capability-model.md`, `docs/room-constraints.md`,
  `docs/mass-repair.md`, `docs/ai-advisor.md`
- Primary evidence: the GridPilot database and the school's real `.tfx`,
  queried 2026-09-07 — every count in §1 measured directly.
