<p align="center">
  <img src="frontend/src/assets/gridpilot-logo.png" alt="GridPilot" width="420">
</p>

<p align="center">
  <strong>A local-first co-pilot for school timetabling.</strong><br>
  Ingest a Timetabling Solutions export, analyse it, propose and validate edits, export a file it can re-read — all offline.
</p>

<p align="center">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-blue">
  <img alt="Node 20+" src="https://img.shields.io/badge/node-20%2B-339933">
  <img alt="Tests" src="https://img.shields.io/badge/tests-256%20passing-brightgreen">
  <img alt="License" src="https://img.shields.io/badge/license-unspecified-lightgrey">
  <img alt="Status" src="https://img.shields.io/badge/status-active%20development-orange">
</p>

---

GridPilot was built for Sophia College (Brisbane Catholic Education) to
sit alongside Timetabling Solutions, not replace it: load the school's
real `.tfx`/`.sfx` export, see the whole timetable, get a deterministic
list of what's actually wrong with it (clashes, capacity, load,
composite classes), propose and validate fixes without ever touching the
source data, and export an approved change back out as a file
Timetabling Solutions can re-read. Nothing here calls a cloud API —
everything runs on your machine, and the one AI layer this project uses
is local-only (Ollama), and only for *explaining* findings, never
for inventing them.

## Contents

- [What's built](#whats-built)
- [Design direction](#design-direction)
- [Quick start](#quick-start)
- [Running it](#running-it)
- [Project layout](#project-layout)
- [Documentation](#documentation)
- [Privacy and data handling](#privacy-and-data-handling)
- [Project status](#project-status)

## What's built

The original six milestones, plus two full follow-up passes
(`docs/roadmap-v2.md`, `docs/roadmap-v3.md`) — every item tested against
the school's real Term 3 export, not synthetic data alone.

### Core: ingest, analyse, edit, export

| | |
|---|---|
| ✅ **Ingestion + cross-validation** | `.tfx` (primary source) cross-checked against CSV and eMinerva exports; every mismatch surfaced as a structured discrepancy, never silently dropped. Auto-discovers the newest export file — a new term needs no code change. |
| ✅ **Timetable grid** | **Master grid** by default - every lesson, every day, at once, rows switchable between Room/Teacher/Roll class (Room is the classic timetabler's view - a clash is two lessons stacked in one cell). "Single entity" mode still filters to one teacher/room/roll class. Lessons are colour-coded by faculty (a validated, colour-blind-safe 8-colour palette, with a legend). Click any lesson to move it and see the clash-rule impact immediately; a proposed move renders live at its new slot. A **Viewing** selector lets the master grid render "through" any draft change set — hand-edited, a suggested fix, or a solver repair run — as a lightweight scenario, without touching the live timetable. A comfortable/compact **density toggle**, and full **keyboard navigation** (arrow keys to move, Enter to open a lesson) alongside the mouse. See [`docs/master-timetable.md`](docs/master-timetable.md). |
| ✅ **Search everywhere** | `Ctrl+K` opens a command palette that jumps straight to a teacher, room, or roll class's timetable, or to any page. Every review queue (Findings, Room Constraints, Teacher Capabilities, Composite Review) and the Rooms page also has its own inline search/filter box, since several of these lists run past 150–200 real entries. |
| ✅ **Deterministic rules engine** | Teacher/room/student double-booking, room capacity, teacher load, room/class-name utilisation, class room/teacher consistency, room-type mismatch, room-pool violation, unqualified-teacher, and early-career-teacher overload — 13 rules total. Composite classes and room-type/teacher-capability candidates are detected and held in **human-review queues** — never silently suppressed or auto-approved. A finding can be marked **accepted risk** - reversible, never hidden. See [`docs/rules.md`](docs/rules.md). |
| ✅ **Safe change sets** | Propose an edit, validate it with a full what-if re-run of every rule, then approve or reject. The imported timetable is **never mutated** — approval is a durable record, not a write. |
| ✅ **Constraint-based suggestions** | Searches every valid alternate room/time — and, since roadmap v2, alternate *teacher* (backed by confirmed capability data, never guessed) — rejects anything failing a hard constraint, ranks what's left by disruption and familiarity. Available from the Findings tab and the lesson editor. Deliberately **no AI involved**. |
| ✅ **Mass-repair solver** | A real CP-SAT solver (OR-Tools, not an LLM) that finds a minimal set of moves resolving a chosen batch of findings at once — swaps and chains a single-lesson search can't find. Lands as a normal change set for review; nothing auto-applies. See [`docs/mass-repair.md`](docs/mass-repair.md). |
| ✅ **Audit trail + export gate** | Every import, rules run, and review decision is logged. An approved change set exports to a re-importable `.tfx`, gated behind six validation checks. File-writing is deliberately CLI-only, never a UI button. |
| ✅ **Re-ingest persistence** | Composite-class reviews, room-type/capability decisions, change sets, and the audit trail survive a re-ingest - snapshotted by stable code, never an internal id. See [`docs/reingest-persistence.md`](docs/reingest-persistence.md). |
| ✅ **Browser-based import** | Load a `.tfx` and any number of `.sfx` files straight from the UI - no folder wrangling, no CLI. |
| ✅ **AI advisor (Ollama)** | A local model *explains* an existing finding in plain English - never suggests or applies a fix. Told about related open findings so it can flag when two findings are the same underlying clash from different sides. See [`docs/ai-advisor.md`](docs/ai-advisor.md). |
| ✅ **Dashboard** | Open findings by severity, composite/room-type/capability reviews pending, draft change sets, average room utilisation, entity counts, recent activity - every number a live query, nothing simulated. |

### Staffing, capability, rooms & blocking (roadmap v2)

| | |
|---|---|
| ✅ **Staffing Policy** | The Diocesan industrial agreement modelled as reviewable data (never hard-coded): contact-time caps, middle/senior leadership release pools by enrolment band, and a reconciliation view (pool vs. allocated release). No real EA figures are seeded - the school enters and confirms its own. |
| ✅ **Teacher Capabilities** | "Permission to teach," bootstrapped from who currently teaches what (never auto-approved - a fresh candidate is always `REVIEW_REQUIRED`), reviewed on its own page. Unblocks a `teacher_not_qualified_for_class` finding and teacher-reassignment suggestions once reviewed. |
| ✅ **Room Constraints** | Which `room_type` each class actually needs, inferred from real usage (78% of classes already use exactly one type) and confirmed by a human before it's trusted - unblocks `room_feature_mismatch` and narrows the solver's room search. |
| ✅ **Rooms** | Utilisation, declared room pools, confirmed room-type expectations, and open-finding counts per room - one page instead of cross-referencing four. |
| ✅ **Teachers** | Load (contracted vs. scheduled), faculty, middle-leadership role/tier, and a registration/career-stage profile (flags an early-career teacher at/near their contact cap or covering an unusual number of subjects) - all entered directly in GridPilot, all kept by teacher **code** so they survive a re-ingest. |
| ✅ **Blocking analytics** | Read-only option-line view, now with an open-finding badge per line and real per-course enrolment, so a timetabler can see pressure on a line without inferring it from a spreadsheet. See [`docs/full-timetabler-plan.md`](docs/full-timetabler-plan.md) Phase C. |
| ✅ **Design system pass** | Tokens instead of ad-hoc colour, tabular numerals, a measured (not eyeballed) WCAG AA contrast pass, a full-height single-scroll grid, and a consolidated toolbar. |

**Not yet built:** adding/editing teacher, student or room *records*
(only role/capability/profile fields are writable - identity stays
read-only from the import), and anything resembling a demand model,
an allocation engine, or a printable/exportable output - see
[`docs/roadmap-v3.md`](docs/roadmap-v3.md) for the honest gap analysis
against what a full timetabling system would need.

## Design direction

The UI now follows the target mockups fairly closely — a sidebar, a real
Dashboard, and an editable timetable grid all exist, and a real CP-SAT
solver now backs "Repair with solver" on the Findings page (Mode A of
`docs/solver.md` — find and fix, not generate from nothing). What's
deliberately *not* built, even though the mockups show it: branchable,
side-by-side Scenarios (today a solver run or a suggestion lands as one
draft change set the grid can render "through," not two compared at
once), a real-calendar Timetable Overview (no calendar-date mapping
exists, and guessing one was explicitly ruled out early on), and
compliance-percentage tiles (not things GridPilot actually computes).
See [`docs/project-status.md`](docs/project-status.md) for the reasoning
behind each, and [`docs/roadmap-v3.md`](docs/roadmap-v3.md) for what a
full solver build-out (regional rebuild, construction, a persisted
run-compare workflow) would still take.

<p align="center">
  <img src="docs/design/ui-mockup3.png" alt="GridPilot dashboard mockup — the most recent design reference" width="850">
</p>

## Quick start

```bash
# Backend
cd backend
pip install -e ".[dev]"

# Frontend
cd ../frontend
npm install
```

Point `TT_SOURCE_DIR` at a folder containing a Timetabling Solutions
export (`.tfx`, optionally per-year-level `.sfx` files, and the CSV/
eMinerva exports) — see [Overriding data locations](#overriding-data-locations).

## Running it

```bash
# Start both servers (separate terminals)
cd backend && python -m uvicorn app.api.main:app --port 8000
cd frontend && npm run dev
```

Open **http://localhost:5173**. With no data loaded yet, you'll land on
an import screen — choose the `.tfx` export (required) and any `.sfx`
Student Options files (optional, can be added later), and it ingests and
runs the rules engine immediately. Re-import a fresh export any time via
**Import…** in the sidebar. Sections once loaded, grouped in the
sidebar to match: **Dashboard** (a real overview - open findings,
pending reviews, room utilisation, entity counts); **Structure**
(**Blocking**, read-only option-line view); **People** (**Teachers** -
load, faculty, role, capability, career-stage profile - and **Staffing
Policy** - the EA modelled as reviewable data, contact-time and
leadership-release reconciliation); **Places** (**Rooms** - utilisation,
pools, room-type expectations, open findings); **Timetable** (the master
grid, with density and keyboard-navigation controls); **Quality**
(**Findings** - one-click "Suggest fixes", a local-AI "Explain", "Repair
with solver" for a batch fix, "Mark as intentional", search, and an
attention-count badge - plus **Composite Review**, **Room Constraints**,
and **Teacher Capabilities**, each its own human-review queue); and
**Changes** (**Change Sets** and **Audit**).

Prefer the CLI (scripting, or a file already sitting in
`Timetabler Export/`)? Same ingestion path, just triggered directly:

```bash
cd backend
python -m app.ingest.run       # builds the working database from the export folder
python -m app.analysis.run     # rules engine — findings + composite candidates
```

```bash
# Export an approved change set (dry run by default)
python -m app.export.run --change-set-id 5
python -m app.export.run --change-set-id 5 --confirm    # actually write files

# Clear working data (dry run by default)
python -m app.retention
python -m app.retention --confirm

# Tests (skip automatically without real export data present)
python -m pytest tests/ -v
```

### Running as one process (no separate frontend server)

`frontend/src/api.ts` talks to the backend over relative `/api` paths, so
a *built* frontend can be served directly by the backend on one port —
no Vite dev server needed:

```bash
cd frontend && npm run build   # writes frontend/dist
cd ../backend && python -m uvicorn app.api.main:app --port 8000
```

Open **http://localhost:8000** — the whole app, API and UI together, one
process. This is the first step toward a double-clickable `.exe`; see
[`docs/packaging.md`](docs/packaging.md) for the rest of that plan. Day-
to-day development still uses the two-server setup above (`npm run dev`
gives hot reload; a built `frontend/dist` is ignored by git and this
single-process path does nothing until you build it).

### Building the desktop .exe

```bash
cd frontend && npm run build
cd ../backend && pip install -e ".[packaging]"
pyinstaller gridpilot.spec
./dist/GridPilot/GridPilot.exe
```

Produces a standalone `GridPilot.exe` (~185MB — it bundles a full Python
runtime plus the CP-SAT solver) that opens its own window, with its own
data directory under `%LOCALAPPDATA%\GridPilot` — separate from
whatever database `TT_DATA_DIR` points at in dev. See
[`docs/packaging.md`](docs/packaging.md) for what's actually been
verified about this build versus what's still open.

### Overriding data locations

- `TT_SOURCE_DIR` — defaults to `./Timetabler Export`
- `TT_DATA_DIR` — defaults to `./data`
- `TT_OUTPUT_DIR` — defaults to `./output`
- `TT_TFX_PATH` — pin ingestion to one specific `.tfx`, overriding
  auto-discovery of the newest file under `TT_SOURCE_DIR`

## Project layout

```
backend/          FastAPI + SQLite. app/ingest, app/analysis, app/changes, app/export, app/api
frontend/          React + TypeScript + Tailwind, talks to the API only
docs/               Every design decision, written down (see below)
Timetabler Export/  Real export data goes here — gitignored, never committed
data/, output/      Working database and generated exports — gitignored
```

## Documentation

Every non-obvious decision in this project is written down, not just
coded — start with `docs/data-formats.md` if you're new to what a
Timetabling Solutions export actually contains.

| Doc | Covers |
|---|---|
| [`docs/data-formats.md`](docs/data-formats.md) | What every source file actually contains, confirmed against real data |
| [`docs/data-model.md`](docs/data-model.md) | The internal schema, and why |
| [`docs/tfx-compatibility.md`](docs/tfx-compatibility.md) | Handling a different/future export version; auto-discovery |
| [`docs/rules.md`](docs/rules.md) | The rules engine: what each rule checks, composite-class review |
| [`docs/change-sets.md`](docs/change-sets.md) | Proposed edits, what-if validation, why the source is never mutated |
| [`docs/suggestions.md`](docs/suggestions.md) | The algorithmic (non-AI) fix-suggestion engine |
| [`docs/export-validation.md`](docs/export-validation.md) | The six-gate export process, and what it genuinely can't verify |
| [`docs/reingest-persistence.md`](docs/reingest-persistence.md) | How composite reviews, change sets, and the audit trail survive a re-ingest |
| [`docs/ai-advisor.md`](docs/ai-advisor.md) | The local Ollama explain-a-finding layer: boundary, model choice, a hardware gotcha, and how it uses related findings |
| [`docs/master-timetable.md`](docs/master-timetable.md) | The whole-school grid: why it exists, how the axis switch works, why Room is the default |
| [`docs/privacy-threat-model.md`](docs/privacy-threat-model.md) | Data flows, trust boundaries, audit trail, retention/purge |
| [`docs/project-status.md`](docs/project-status.md) | Honest health review — what's solid, known weaknesses, what's next |
| [`docs/full-timetabler-plan.md`](docs/full-timetabler-plan.md) | The long game: what Timetabling Solutions actually does, what the open-source field offers, and the phased plan to go from companion tool to full timetabling program |
| [`docs/solver.md`](docs/solver.md) | **Mass optimisation**: how a "fix everything" button and from-scratch generation could actually work — CP-SAT model, why the LLM is *not* the solver, the three modes in build order, and the two constraint-data gaps that block all of it |
| [`docs/room-constraints.md`](docs/room-constraints.md) | Phase G1 of the solver plan: inferring which room_type each class needs from real usage (78% is a clean signal), human review before it's trusted, and the `room_feature_mismatch` rule it unblocks |
| [`docs/mass-repair.md`](docs/mass-repair.md) | **The mass-fix button**: a real CP-SAT solver (not an LLM) that finds a minimal set of moves to resolve chosen findings, lands them in a normal change set for review. Two real-data lessons that changed the design: student clashes had to become a native constraint, and an infeasible joint batch needs to shrink and retry, not give up entirely |
| [`docs/staff-capability-model.md`](docs/staff-capability-model.md), [`staffing-priority-policy.md`](docs/staffing-priority-policy.md), [`staffing-ux-workflows.md`](docs/staffing-ux-workflows.md) | Mapping for a larger staff-capability/allocation addendum — documented, not yet built |
| [`docs/roadmap-v2.md`](docs/roadmap-v2.md) | **Staffing, capability & design system** — the industrial agreement (EA) read as a machine-readable spec, including the finding that the `2580 min/cycle` load cap *is* the EA's 21.5h contact maximum; auto-calculated leadership release; permission-to-teach; ECT status; a full design-system pass (tokens, contrast, density, keyboard nav, search). 13 of its 16 sequencing items are built; the rest (entity authoring, editable blocking, Mode B/C solver) are gated on a still-open GUID-compatibility question and teacher-unavailability data. Also a licence review of four reference timetabling repos (verdict: nothing safely reusable) |
| [`docs/roadmap-v3.md`](docs/roadmap-v3.md) | **The current plan**: a gap analysis of what's still missing to be a full timetabling system, grounded in queries against the real database rather than assumption — an unparsed availability data source hiding in the `.tfx`, two built rules stuck at zero findings behind a 412-item unreviewed queue, why the `.sfx` preference data can't yet answer blocking counterfactuals, and the missing `teaching_requirement` spine underneath allocation, blocking and construction alike |
| [`docs/packaging.md`](docs/packaging.md) | Turning this into a double-clickable program: why not Electron/Tauri, the three phases (one process → a frozen `.exe` with a native window → an installer), and what's actually built so far |
| [`docs/design/`](docs/design/) | UI mockup and logo source assets |

## Privacy and data handling

This started as a tool for handling real student and staff data, and
that constraint shaped everything:

- **No cloud API calls anywhere in this codebase.** The planned AI layer
  is local-only (Ollama), and its job is to explain findings that
  already exist — never to generate or apply timetable changes itself.
- **No PII in logs, findings, or audit records** — every structured
  record uses codes (teacher code, room code, class code, a student's
  numeric code) and never a name or email. This is asserted by tests,
  not just intended.
- **Source data is read-only.** Ingestion never writes back into the
  export folder; every working file lives under a separate, gitignored
  `data/`/`output/` directory.
- **This repository contains no real student or staff data.** The
  `Timetabler Export/` folder (and every `.tfx`/`.sfx`/database/export
  file) is excluded from version control from the first commit — see
  `.gitignore`. Verified directly before this repo went public: every
  currently-tracked file was enumerated, and full git history was
  checked for anything that was ever committed and later removed.

Full detail, including a caveat about OneDrive sync in the original
deployment environment, in [`docs/privacy-threat-model.md`](docs/privacy-threat-model.md).

## Project status

All six `PROJECT_ROADMAP.md` milestones are complete, and two full
follow-up passes beyond it: `docs/roadmap-v2.md` (staffing/EA,
capability, design system - 13 of 16 items built) and the design work
this repo is currently on, tracked in `docs/roadmap-v3.md`. The export
path has been trial-imported into a real Timetabling Solutions instance
and read back correctly - see `docs/project-status.md` and
`docs/export-validation.md`.

What's actually left, honestly: `docs/roadmap-v3.md` is the current
answer to "what's missing to be a full timetabling system" - a demand
model (`teaching_requirement`), an allocation engine, an output layer
(there is currently no print/PDF/export beyond the `.tfx` patch), and a
persisted solver run-compare workflow, in that rough order. Two smaller
but real items sit ahead of all of them: a source section (`Meetings`)
that carries real teacher-availability data and isn't parsed yet, and
199 + 213 human-review candidates sitting unreviewed, holding two built
rules at zero findings.

---

<p align="center">
  <sub>Built with <a href="https://claude.com/claude-code">Claude Code</a> for Sophia College.</sub>
</p>
