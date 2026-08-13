# Mass Optimisation: How GridPilot Could Actually Generate and Repair Timetables

*Written 2026-08-13, in response to: "it would be good to have a big
'mass fix' or something, even creating a timetable from scratch, that
uses AI/computer power to look at where classes could fit better,
staffing, rooms etc ... that would be a game changer."*

*This is a design document, not a commitment. It expands
`docs/full-timetabler-plan.md` §Phase G (constraint model) and §Phase H
(solver) from a one-paragraph sketch into something buildable, and it is
deliberately honest about the two places where the obvious approach is
wrong.*

---

## 0. The one-paragraph version

The "golden bullet" is real and buildable, but it is **not an LLM**, and
the highest-value version of it is **not "generate from scratch."** This
is a constraint optimisation problem with 60 years of literature behind
it; the right engine is a CP-SAT solver (OR-Tools, Apache-2.0,
Python-native, runs locally), and the right first product is **mass
repair** — "fix these 20 critical clashes and 29 capacity problems while
moving as few lessons as possible" — which is tractable in seconds,
lands in the change-set pipeline that already exists, and is something
Timetabling Solutions genuinely cannot do. Full construction is the
*last* mode to build, not the first, and the real blocker on all of it is
**constraint data we don't have yet**, not solver code. The good news:
the two biggest data gaps turn out to be ~78% inferable from the
timetable already in the database.

---

## 1. What "AI" means here, precisely

This matters more than anything else in the document, so it goes first.

**The language model cannot do this job.** Not the local Ollama model,
not GPT-5, not any model. Placing 1,519 lessons into 50 time slots across
51 rooms without clashes is a combinatorial search problem, and the
search space is:

```
1,519 lessons × (50 slots × 51 rooms) placements each
                    = 2,550 choices per lesson
                    ≈ 2,550^1,519  ≈  10^5,180 candidate timetables
```

For scale: there are about 10^80 atoms in the observable universe. A
language model generating a timetable is not searching that space; it is
producing text that *looks like* a timetable, and every clash it happens
to avoid is luck. This is precisely the failure mode
`PROJECT_ROADMAP.md` Milestone 4 already legislated against — *"This
prevents the language model from inventing timetable changes"* — and the
whole project has held that line since.

**What actually solves it** is a constraint solver: software that
represents the problem as variables and constraints, then uses
propagation, clause learning, and systematic search to prove things
about the space rather than sample from it. This is the same class of
tool that does airline crew rostering and chip layout.

So the honest naming is:

| Layer | Technology | Job |
|---|---|---|
| **Optimiser** | OR-Tools CP-SAT | Decides *what* changes. Deterministic, provable, no model. |
| **Validator** | `app/analysis/whatif.py` (**exists**) | Independently re-checks the solver's output against every rule. |
| **Explainer** | Local LLM (**exists**) | Says *why* in English. Never decides anything. |

The LLM's role does not change from what it is today. It gets a bigger
and more interesting thing to explain, which is genuinely valuable (§7),
but it stays on the explanation side of the line.

---

## 2. Three modes, in the order they should be built

The request bundles three quite different capabilities. They differ by
orders of magnitude in difficulty, and — importantly — **in inverse
order to their value.**

| Mode | What it does | Size | Runtime | Value |
|---|---|---|---|---|
| **A. Mass repair** | Fix a chosen set of findings, minimising disruption | **M** | seconds–1 min | **Highest** |
| **B. Regional rebuild** | Re-solve one year level / faculty / day from scratch, rest frozen | **L** | 1–15 min | High |
| **C. Full construction** | Build the whole cycle from demand data | **XL** | hours, may not converge | Lowest per unit effort |

### 2.1 Mode A — Mass repair (build this first)

**The pitch:** "There are 20 critical clashes, 29 capacity breaches, and
78 room-instability findings open right now. Fix as many as possible,
changing as few lessons as you can."

This is the natural extension of `suggest_fixes()`, which today searches
for a **single lesson's** alternatives one finding at a time. Its
structural limitation is that it can only find fixes of the form *"move
this one lesson somewhere free."* It cannot find:

- **Swaps** — A and B exchange slots; neither slot was free, but the
  trade resolves both.
- **Chains** — A moves into B's slot, B moves into C's, C takes the gap
  A left. Extremely common in real timetabling, invisible to a
  one-lesson search.
- **Joint optimisation** — resolving 10 clashes together often costs
  fewer total moves than resolving them one at a time, because fixes
  share moves.

A solver finds all three natively. This is the single biggest capability
jump available, and it is the *smallest* of the three modes to build.

**Why it fits this codebase almost suspiciously well:** the output of a
repair run is a set of `(entry_id, new_slot, new_room)` triples. That is
*exactly* the shape of a `proposed_change`. A solver run becomes a change
set — reviewed, validated by `whatif.py`, approved by a human, exported
through the six existing gates. **No new write path, no new approval
model, no new export risk.** The riskiest part of the feature is already
built and proven (Phase 0, 2026-08-12).

### 2.2 Mode B — Regional rebuild

Freeze everything except a chosen slice — Year 9, or the Science
faculty, or all of Friday — and re-solve that slice optimally against the
frozen remainder. Bigger search, still bounded, still lands in a change
set.

This is the honest answer to *"where classes could fit better."* It is
also the mode most likely to produce a genuinely surprising, genuinely
better arrangement, because it can restructure rather than patch.

### 2.3 Mode C — Full construction

Build the entire cycle from demand data (which classes need how many
periods, who teaches them, who's enrolled). This is what TTS's allocation
engine does.

**Build this last, and be sceptical of it.** Three honest reasons:

1. **TTS already does it, and has for 30 years.** `full-timetabler-plan.md`
   §1.3 correctly identifies the solver as one of TTS's genuine
   strengths. Re-implementing a competitor's strongest feature is the
   worst possible place to compete.

2. **A from-scratch timetable discards every undocumented human
   agreement.** The current timetable encodes hundreds of facts nobody
   wrote down: this teacher has Wednesday afternoon free because they
   coach; this class is in that room because the equipment is bolted
   down; these two staff deliberately share a line. A solver optimising a
   formal objective will cheerfully destroy all of it and produce
   something that scores better and is politically unusable. This is the
   classic failure of automated rostering, and it is *why* Mode A's
   minimise-movement objective is not a limitation but the entire point.

3. **The constraint data isn't there yet** (§4). A construction run
   against today's data would produce a timetable that is clash-free and
   wrong — Drama in a science lab, a part-time teacher scheduled on their
   non-working day.

Mode C's realistic use case is **roll-over**, not green-field — next
year's timetable seeded from this year's, per `full-timetabler-plan.md`
§5(a). That framing keeps most of the human knowledge and makes the
problem far more tractable, because the previous year is a warm start.

---

## 3. The model, concretely

Using OR-Tools CP-SAT. This section is deliberately specific enough to
implement from.

### 3.1 Decision variables

For each **lesson instance** ℓ (one class's one period — 1,519 of them):

```python
# Boolean encoding: place[ℓ][s] is true iff lesson ℓ occupies slot s
place[ℓ][s]  for s in feasible_slots(ℓ)     # ~50
assign[ℓ][r] for r in feasible_rooms(ℓ)     # ~5-10 after domain reduction, not 51

model.AddExactlyOne(place[ℓ][s] for s in feasible_slots(ℓ))
model.AddExactlyOne(assign[ℓ][r] for r in feasible_rooms(ℓ))
```

**Domain reduction is what makes this tractable, and it is entirely a
data problem.** Without room-type constraints, `feasible_rooms(ℓ)` is all
51 rooms and the room-occupancy encoding needs ~3.9M booleans. With
room-type inference (§4.2) cutting it to ~8 candidate rooms per lesson,
it's ~600K — comfortably within CP-SAT's range. **The constraint data
doesn't just improve solution quality; it's what makes the model solvable
at all.** This is the concrete reason Phase G must precede Phase H.

### 3.2 Hard constraints

These map 1:1 onto rules the engine already computes, which means every
one of them has an existing, tested implementation to check the solver
against:

```python
# Teacher never in two places  (→ teacher_double_booking)
for t, s: AddAtMostOne(place[ℓ][s] for ℓ where teacher(ℓ) == t)

# Room never double-booked  (→ room_double_booking)
#   occupy[ℓ,s,r] ⟺ place[ℓ][s] ∧ assign[ℓ][r]
for r, s: AddAtMostOne(occupy[ℓ][s][r] for all ℓ)

# Student never in two classes at once  (→ student_double_booking)
#   560 students × 50 slots = 28,000 constraints; trivial for CP-SAT
for student, s: AddAtMostOne(place[ℓ][s] for ℓ in classes_of(student))

# Room capacity  (→ room_capacity_exceeded)
assign[ℓ][r] == 0  where enrolled(ℓ) > seats(r)

# Approved composites share a slot rather than clashing
for (ℓa, ℓb) in approved_composite_pairs: place[ℓa][s] == place[ℓb][s]

# Room pools (RURs, already parsed)
assign[ℓ][r] == 0  where pool(ℓ) is not None and r not in pool(ℓ)
```

Note the composite constraint: approved composites become an *equality*,
not an exception. The solver keeps parallel classes together by
construction rather than being told to ignore a clash — cleaner than the
suppression the rules engine has to do.

### 3.3 Soft objective

Weighted sum, minimised. **Every weight here is a policy decision the
school owns, not a number to invent** — the same discipline
`docs/rules.md` applies to thresholds. Four of them, however, are already
stated in the school's own `Settings` block (parsed in Phase A):

| Term | Weight source | Status |
|---|---|---|
| **Movement** (lessons displaced from current slot/room) | GridPilot default, dominant in Mode A | Defensible default |
| **Room instability** (distinct rooms per class) | `class_room_instability` already computes this | Have the metric |
| **Teacher inconsistency** (distinct teachers per class) | `class_teacher_inconsistency` | Have the metric |
| **Spread across cycle** | `Settings.OptimiseSpread = True` | **School's own stated preference** |
| **Spread across days** | `Settings.MaxDaySpread = True` | **School's own stated preference** |
| **Doubles honoured** | `Settings.Successive2Periods = True` | **School's own stated preference** |
| **Triples honoured** | `Settings.Successive3Periods = True` | **School's own stated preference** |
| **Load balance** vs `contracted_load_minutes` | `teacher_over_contracted_load` | Have the metric |

The `Settings` booleans say *what* the school optimises for but not *how
much* — they're flags, not weights, exactly as `full-timetabler-plan.md`
§4.3 found. Turning them into weights is a conversation with the school,
and §6's run-and-compare workflow is how that conversation gets had
empirically rather than in the abstract.

**In Mode A the movement weight should dominate everything else by an
order of magnitude.** A repair that fixes 20 clashes by moving 25 lessons
is a good week's work; one that fixes 20 clashes by moving 400 lessons is
a new timetable wearing a trenchcoat, and no head of timetabling will
approve it.

### 3.4 Warm start — the trick that makes repair fast

```python
for ℓ: model.AddHint(place[ℓ][current_slot(ℓ)], 1)
```

Seeding CP-SAT with the existing timetable means it starts from a
solution that is already 99% feasible and searches outward. Combined with
Large Neighbourhood Search (freeze all but a rolling subset), this is why
Mode A runs in seconds while Mode C runs for hours: **the current
timetable is an enormously valuable input, and construction throws it
away.**

---

## 4. The real blocker: constraint data, not solver code

Writing the CP-SAT model is perhaps two weeks. Getting the constraint
data right is the actual project. Here is the honest gap analysis
against the real database.

### 4.1 What we already have ✅

| Data | Source | Real counts |
|---|---|---|
| Cycle structure | `day`, `period` | 10 days, 50 lesson slots |
| Rooms + capacity | `room` | 51 rooms, 38 with confirmed seats |
| Teachers + load | `teacher` | 74, all with 2,580 min/cycle |
| Classes + demand | `timetable_entry` | 247 classes; 5–8 periods/cycle typical |
| Student enrolment | `enrolment` | 560 students, 6,726 enrolments |
| **Elective preferences** | `sfx_student_preference` | **6,756 across all 560 students** |
| **Per-subject class caps** | `sfx_subject.class_size_maximum` | 193 subjects |
| **Curriculum rules** | `sfx_constraint` | 16 (Join / Exclusive Join / Equal To / Resource) |
| Blocking lines | `blocking_line` | 29 lines, 169 class-group links |
| Room pools | `room_pool` | 1 pool, 5 rooms, 28 classes |
| Approved composites | `composite_group` | 16 groups, 47 members |

**The `.sfx` elective data being fully ingested is a bigger deal than it
looks.** Student preferences plus per-subject caps plus line structure is
most of what a *blocking* engine needs — and blocking is the step
upstream of timetabling where the really expensive structural mistakes
get made. That's a separate solver problem (§8) and arguably a more
valuable one.

### 4.2 The two real gaps, and how to close them

**Gap 1 — Class → required room type.** `docs/rules.md` correctly records
that `room_feature_mismatch` is unimplementable because `room.room_type`
is free text from the export's Notes column, not a controlled vocabulary,
and no subject→feature mapping exists. Both halves are true. But the data
is more tractable than that note implies:

```
room_type values present:   26 distinct
  Classroom 8 · Maths Classroom 4 · English Classroom 4 · Science 3
  Quiet Study 3 · Meeting Room 3 · Visual Art 2 · Senior Science 2
  Drama 2 · Learning Support 2 · Music 1 · Japanese 1 · Food Tech 1
  Engineering 1 · Senior Kitchen 1 · ... (11 more singletons)

How consistent are classes about room type *today*?
  1 distinct room_type:  180 classes (78%)
  2 distinct:             40 classes (17%)
  3 distinct:             10 classes  (4%)
  4 distinct:              1 class    (0%)
```

**78% of classes already use exactly one room type; 95% use at most
two.** That is a strong enough signal to *infer* a proposed mapping and
put it in front of a human — which is exactly the pattern this project
has already built and proven twice: **composite review** (detect
candidates → human approves → the approved record governs the rules
engine). Constraint acquisition should reuse that UX wholesale rather
than inventing a new one.

The inference is a proposal, never an assertion: *"11BIO1 has run in
Science rooms for all 8 of its lessons. Require a Science room?
[Confirm] [Any room] [Edit]"*. A human confirms in bulk, and the
confirmed mapping becomes solver input **and** unblocks
`room_feature_mismatch` as a real rule.

**Gap 2 — Teacher unavailability.** Nothing in the schema records that a
teacher is unavailable at a given slot. Part-time staff, external
commitments, leadership release — none of it is represented, and
inferring it from "they have no lesson there" is invalid (a free period
is not an unavailability). `Meetings` (13 records) and
`UnscheduledDuties` (46) were deliberately not parsed in Phase A because
they carried no load information — but for *availability* they may be
worth revisiting, since a meeting is a genuine block on a slot even at
zero load.

**This gap is fatal to Modes B and C and merely degrading to Mode A.** In
repair mode, a teacher's current slots are frozen unless the solver
chooses to move them, and movement is heavily penalised — so
unavailability violations stay rare. In construction mode, the solver
will confidently schedule a 0.6 FTE teacher across all ten days. There is
no way to infer this data; it has to be asked for, and it is the single
most important question in §10 of the plan doc.

### 4.3 Smaller gaps

- **Doubles/triples requirements per subject.** `Settings.Successive2Periods`
  is school-wide, not per-subject (`full-timetabler-plan.md` §6 dropped
  `missing_double` for exactly this reason). Inferable from current
  adjacency with the same confirm-flow as room types.
- **Room `site_no`.** Present (all rooms `site_no = 1` today). If the
  school is ever multi-campus, travel-time constraints become mandatory.
- **Teacher qualification / capability.** `docs/staff-capability-model.md`
  covers what this would take. Only needed if the solver is ever allowed
  to *reassign teachers*, which — per `suggestions.py`'s standing rule —
  it should not be without this data.

---

## 5. Where this lands in the existing architecture

The strongest argument for Mode A is how little new architecture it
needs:

```
   Findings (exists)  ──selected by user──▶  Solver run  ──▶  Change set (exists)
        ▲                                        │                  │
        │                                        ▼                  ▼
   Rules engine  ◀────re-validates────  whatif.py (exists)    Six export gates (exists)
                                                                    │
                                                                    ▼
                                                          .tfx patch (proven 2026-08-12)
```

Genuinely new: one solver module, one constraint-configuration table
group, one page to launch and compare runs. Everything downstream of "the
solver produced some moves" already exists, is tested, and has been
proven end-to-end against real Timetabling Solutions.

**The independent-validation property is worth stating explicitly.**
`whatif.py` re-runs every rule against the solver's output without
sharing any code with the solver. If the CP-SAT model has a bug — a
mis-stated constraint, an indexing error — the validator catches it,
because the two implementations are independent. `test_suggestions.py`
already applies exactly this discipline to the existing suggestion engine
(`test_no_candidate_ever_introduces_a_regression`). A solver deserves it
more, not less.

---

## 6. "It may take a few tries or goes" — designing for that

This instinct is exactly right, and it's how constraint optimisation
actually gets used in practice. Nobody runs a solver once. The real
workflow is:

```
run  →  inspect  →  "too much movement" / "Year 9 got worse"
     →  adjust weights or scope  →  re-run  →  compare  →  keep one
```

So **a solver run must be a first-class, persisted, comparable object** —
not a fire-and-forget button. Concretely:

```sql
solver_run(
  id, created_at, created_by,
  mode,                    -- REPAIR | REGIONAL | CONSTRUCT
  scope_json,              -- which findings / which region
  weights_json,            -- the objective weights used
  time_budget_seconds,
  status,                  -- RUNNING | FEASIBLE | OPTIMAL | INFEASIBLE | TIMEOUT
  objective_value,
  moves_count,
  findings_resolved, findings_introduced,
  change_set_id            -- nullable; created only if the user keeps it
)
```

Design consequences that follow directly:

- **Runs are cheap to discard.** A run produces a change set only when
  the user says "keep this." Otherwise it's a row and a result blob.
- **Runs are comparable side by side.** "Run 3 fixed 18 findings with 22
  moves; Run 4 fixed 20 with 61." That table *is* the interface for the
  weight conversation with the school in §3.3 — it turns an abstract
  policy question into a concrete A/B choice.
- **Always time-bounded.** CP-SAT returns the best solution found so far
  when the budget expires. A 30-second repair and a 30-minute repair are
  the same code path with a different number.
- **Runs are seeded deterministically** so a re-run with identical inputs
  reproduces identically — otherwise "compare two runs" is meaningless.
- This is `full-timetabler-plan.md` Phase E (scenarios) arriving through
  a different door. A kept solver run and a named scenario are the same
  object. Build them together.

---

## 7. Where the LLM genuinely earns its place

Not deciding. Three real jobs, all of which are explanation of computed
facts — the boundary `docs/ai-advisor.md` already holds:

1. **Explain a run in plain English.** *"Moved 22 lessons. Resolved all
   10 room double-bookings and 8 of 10 teacher clashes. The two it
   couldn't fix both involve HENE04 on Tuesday P4, where the only free
   rooms are too small for the combined composite."* Input is run
   statistics plus findings diff — all computed, none invented.

2. **Explain infeasibility — the highest-value one.** When a solver says
   INFEASIBLE it means *"no timetable satisfying these constraints
   exists,"* which is enormously useful information delivered in a
   useless form. CP-SAT can produce an **infeasible subset** — a minimal
   set of mutually contradictory constraints. Translating that into
   *"Year 10 Science needs 5 periods across 4 lab-capable rooms, but
   three of those rooms are already fully committed to Year 11 — the
   structure can't fit, this isn't a scheduling problem"* is a genuine
   language task on top of a genuine computation. **TTS tells you the
   clash. Nothing tells you the structure is impossible.** That is the
   real product gap.

3. **Translate intent into scope and weights.** *"Try to give the Science
   faculty more consistent rooms"* → a Mode B run scoped to Science with
   the room-instability weight raised. The model picks parameters; the
   solver does the work; the human approves the result.

---

## 8. The bigger prize hiding behind this: blocking

Worth naming, because the elective data is already sitting in the
database and this may matter more than the timetabling solver.

Timetabling is downstream of **blocking** — arranging subjects into
parallel lines so students' choices can be satisfied without clashing
(`full-timetabler-plan.md` §1.2). Most "impossible" timetables are
impossible because the blocking was wrong, and by the time you're
timetabling it's far too late to fix cheaply.

We now hold: 6,756 real student preferences, 193 subjects with caps, 60
lines, 16 curriculum constraints. That is enough to answer questions the
school currently cannot ask:

- *"If we move Psychology from Line C to Line E, how many students get
  their full first-preference set?"* — a countable number, not an
  opinion.
- *"Which two subjects clash for the most students?"*
- *"Is there any line arrangement where every student gets all six
  preferences?"* — and if not, the infeasibility explanation from §7.2.

This is also a CP-SAT problem, structurally smaller than timetabling, and
it is a capability the TTS suite splits across Preferences Manager and
the desktop product without ever answering the counterfactual. **Strong
candidate for the actual highest-value solver work**, and it needs no new
data at all.

---

## 9. Phasing

Sizes relative to `full-timetabler-plan.md`'s scale (M ≈ the Teachers
section; L ≈ the change-set subsystem).

| Phase | Work | Size | Gated on | Status |
|---|---|---|---|---|
| **G1** | `constraint` tables; room-type **inference with human confirm** (composite-review pattern) | **M** | — | **✅ done 2026-08-13** - room-type half; doubles inference not built |
| **H2** | `room_feature_mismatch` rule from G1's confirmed mapping | **S** | G1 | **✅ done 2026-08-13**, shipped alongside G1 |
| **G2** | Ask the school for teacher unavailability; ingest it | **S** + a conversation | School | Not started |
| **H1** | CP-SAT model + **Mode A repair**; `solver_run` table; run/compare UI | **L** | G1 | Not started |
| **H3** | LLM run-explanation + **infeasibility explanation** | **M** | H1 | Not started |
| **H4** | **Mode B regional rebuild**; merge with Phase E scenarios | **L** | H1, G2 | Not started |
| **H5** | **Blocking optimiser** (§8) — independent of H1–H4, no new data needed | **L** | G1-ish | Not started |
| **H6** | **Mode C construction**, as roll-over only | **XL** | Everything, + explicit go/no-go | Not started |

**G1 was the keystone, and it's built** - see `docs/room-constraints.md`
for the full design and real-data verification. It unblocks the solver's
future domain reduction, it unblocked a roadmap rule that had been stuck
since Milestone 1 (`room_feature_mismatch`, done alongside it as H2), and
it delivers value on its own with no solver at all: a confirmed
class→room-type mapping is exactly the signal that would stop
`suggest_fixes()` proposing Drama in a science lab, once that mapping is
wired into the suggestion engine's room search (not yet done - the
mapping exists and is queryable, `suggest_fixes()` doesn't consult it
yet).

**Doubles/triples inference (the other half of G1 as originally scoped)
was deliberately deferred**, not built alongside room-type: it's a
smaller, separate signal (adjacency in the timetable rather than a room
join), and shipping room-type alone - the harder, higher-value half -
first let it be validated end-to-end (detection → review → rule →
grid highlighting → resync persistence) before taking on a second
constraint type through the same pipeline.

Reasonable first target: **G1 + H1 + H3.** That is "select some findings,
hit Fix, get a reviewed change set with an English explanation" — the
mass-fix button, honestly delivered.

---

## 10. Failure modes to design for up front

| Failure | Why it happens | Mitigation |
|---|---|---|
| **Solver moves everything** | Movement weight too low | Movement dominates in Mode A; hard cap on move count; show `moves_count` before the user keeps a run |
| **INFEASIBLE** | Over-constrained, often by one bad inferred constraint | Report the infeasible subset (§7.2); allow relaxing a constraint to soft and re-running |
| **Timeout with nothing** | Model too big / domains not reduced | Time budget always set; warm start always on; LNS over subsets rather than one monolithic solve |
| **Fixes findings, breaks reality** | Constraint data incomplete — the §4.2 gaps | `whatif.py` catches rule violations; human review catches the rest. **This is why nothing auto-applies.** |
| **Degenerate "optimal"** | Objective doesn't say what we meant | Compare runs side by side (§6); tune weights empirically with the school |
| **Non-reproducible runs** | Unseeded search, parallel workers | Fix the seed; record it in `solver_run`; single-worker mode for anything the school will audit |

---

## 11. What this does not change

- **Nothing auto-applies.** A solver run produces a *proposal*. It goes
  through the same human approval gate as a change typed by hand. The
  solver is a very fast colleague with a suggestion, not an authority.
- **The LLM never decides.** §1.
- **Teacher reassignment stays off the table** until
  `docs/staff-capability-model.md`'s data exists — the solver inherits
  `suggestions.py`'s existing refusal rather than quietly getting an
  exemption because it's cleverer.
- **Student identity is still never authored** —
  `full-timetabler-plan.md` §7.3 holds regardless of what's optimising.
- **Real-calendar mapping is still not guessed** (`PROJECT_ROADMAP.md`
  correction #4). The solver works in cycle slots, exactly like the rest
  of the system.

---

## 12. The honest summary

The game-changing feature is real, and it's closer than it looks — but
it's a different feature than "AI builds the timetable."

**It is:** *select the problems you want gone, press one button, get back
a minimal, fully-validated set of moves with an English explanation of
what it did and why it couldn't do more.* That is buildable on top of
what already exists, it is something TTS structurally does not offer, and
the riskiest part of it — writing a change back into a file TTS will
accept — was already proven on 2026-08-12.

**It is not:** an LLM producing a timetable. That path produces confident
nonsense, and this project has correctly refused it from Milestone 1.

The work that actually stands between here and there is unglamorous:
**confirm what room each class needs, and find out when teachers aren't
available.** Two data problems, one of which is 78% inferable from data
already in the database, and the other of which is a single conversation
with the school.

---

## Sources & cross-references

- `PROJECT_ROADMAP.md` — Milestone 4's "prevents the language model from
  inventing timetable changes"; correction #4 (no inferred calendar)
- `docs/full-timetabler-plan.md` — §2 (OR-Tools/licensing analysis, FET
  constraint taxonomy), §5 (write tiers), §6 Phases G/H, §7.3 (identity
  governance), §10 (open questions for the school)
- `docs/rules.md` — `room_feature_mismatch` gap; threshold discipline
- `docs/suggestions.md` — the single-lesson search this generalises
- `docs/change-sets.md`, `docs/export-validation.md` — the pipeline a
  solver run lands in
- [OR-Tools CP-SAT](https://developers.google.com/optimization/cp/cp_solver)
  (Apache-2.0)
- Primary evidence: the GridPilot database, 2026-08-13 — all counts in
  §3.1 and §4 queried directly, not estimated.
