# GridPilot

A local, offline-first tool for Sophia College that ingests Timetabling
Solutions export and eMinerva roll-marking files, builds a normalised
internal model, runs deterministic checks over it (clashes, room
utilisation, teacher load), and layers a locally-run AI advisor on top
that can explain findings and draft concrete edits for review.

Everything runs on your machine. Nothing containing student or staff data
is ever sent to a cloud API by this tool - see `docs/data-formats.md`
Section 3's privacy note and the project brief
(`claude-code-timetabling-tool-prompt.md`) for the constraints this is
built against.

**Status**: data ingestion + cross-validation, a timetable grid view
(filterable by teacher/room/roll class), a deterministic rules engine
(clash/capacity/load rules, with human-reviewed composite-class handling),
safe change sets (propose an edit, validate it against a what-if re-run
of the clash rules, approve/reject - the imported timetable is never
mutated), algorithmic fix suggestions (search every valid alternate
room/time, reject anything that fails a hard constraint, rank the rest -
no AI involved), an audit trail + source-hash provenance + explicit
retention/purge, and an export gate (turn an approved change set into a
re-importable `.tfx`, gated behind six validation checks including a real
re-ingest through the app's own parser) are built and tested against the
real export in `Timetabler Export/`. The AI advisor layer is what's left
- this README will grow when that lands.

## Prerequisites

- **Python 3.11+**
- **Node.js 20+** (for the frontend)
- **Ollama** (for the AI advisor layer, once built) - https://ollama.com.
  Already installed and running on this machine with three models pulled:
  `qwen3.5:9b` (recommended default - matches the brief's 7-8B guidance),
  `qwen3.5:4b`, `qwen3.6:35b`. No further setup needed unless you want a
  different model:
  ```bash
  ollama pull qwen3.5:9b
  ```

## Setup

```bash
cd backend
pip install -e ".[dev]"
cd ../frontend
npm install
```

## Data layout

- `Timetabler Export/` - the real Timetabling Solutions + eMinerva export
  files. **Read-only.** The tool never writes here. Excluded from git via
  `.gitignore`.
- `data/` - the local working SQLite database, rebuilt from source on
  every ingest run. Excluded from git.
- `output/` - generated exports (re-import files, changelogs). Excluded
  from git.
- `docs/data-formats.md` - what every source file actually contains,
  confirmed against the real data.
- `docs/data-model.md` - the internal schema those files get ingested
  into, and why.
- `docs/rules.md` - the deterministic rules engine: what each rule
  checks, its evidence, and how composite-class review affects it.
- `docs/change-sets.md` - how proposed edits are represented, validated
  (a what-if re-run of the clash rules, never a real write), and
  approved, and why the source timetable is never mutated.
- `docs/suggestions.md` - the algorithmic fix-suggestion engine: search
  space, hard-constraint validation, scoring, and what's deliberately
  out of scope (student clashes, teacher reassignment).
- `docs/privacy-threat-model.md` - data flows, trust boundaries, the
  audit trail, source-file hash provenance, and the retention/purge
  utility.
- `docs/export-validation.md` - the export gate: the patch-not-rebuild
  strategy, all six validation gates, why file-writing is CLI-only, and
  what this tool genuinely cannot verify (actual Timetabling Solutions
  re-import - test that yourself against a non-production copy first).
- `docs/staff-capability-model.md`, `docs/staffing-priority-policy.md`,
  `docs/staffing-ux-workflows.md` - mapping for the staff teaching
  capability/allocation addendum against the schema above. Documentation
  only so far - no new tables built yet.
- `docs/design/` - UI mockup and logo assets supplied for GridPilot's
  visual direction.
- `PROJECT_ROADMAP.md`, `claude-code-complementary-timetabling-builder.md`,
  `claude-code-full-timetabling-product-spec.md`,
  `claude-code-staff-capability-and-allocation.md` - the planning
  documents behind GridPilot's larger direction, in ascending order of
  scope. Only `PROJECT_ROADMAP.md` is being actively built against right
  now; the others are read and mapped but not yet under construction.

## Running the ingestion pipeline

Builds a fresh working database from `Timetabler Export/`, cross-validates
the `.tfx` (primary source) against the CSV and eMinerva exports, and logs
any discrepancy found (see `docs/data-formats.md` for what's expected vs.
worth investigating):

```bash
cd backend
python -m app.ingest.run
```

Prints aggregate table counts only - no student or staff names are ever
printed to the console by this tool.

## Running the rules engine

After ingesting, syncs composite-class candidates and runs every rule,
persisting structured findings (see `docs/rules.md`):

```bash
cd backend
python -m app.analysis.run
```

Findings and composite candidates are then queryable via the API
(`GET /api/findings`, `GET /api/composites/candidates`) or the
Findings / Composite Review tabs in the app itself.

## Running the tests

Tests run against the real export data and are skipped automatically if
`Timetabler Export/` isn't present (e.g. in an environment without the
real files):

```bash
cd backend
python -m pytest tests/ -v
```

## Running the app

Two servers, run in separate terminals:

```bash
# Terminal 1 - API (reads data/sophia_tt.sqlite3, built by the ingest step above)
cd backend
python -m uvicorn app.api.main:app --port 8000

# Terminal 2 - frontend (proxies /api to the server above)
cd frontend
npm run dev
```

Then open http://localhost:5173. Five tabs: **Timetable** (filter by
teacher/room/roll class), **Findings** (every issue the rules engine
found - "Suggest fixes" shows ranked, pre-validated candidate moves with
a one-click "Use this" per candidate, or "Propose a fix manually" to pick
your own - see `docs/suggestions.md`), **Composite Review** (approve or
reject detected composite classes - see `docs/rules.md`), **Change
Sets** (validate and approve/reject a proposed edit - see
`docs/change-sets.md`), and **Audit** (every import, rules-engine run,
composite/change-set decision - see `docs/privacy-threat-model.md`). Run
`python -m app.analysis.run` first so there's something for
Findings/Composite Review to show.

## Exporting an approved change set

```bash
cd backend
python -m app.export.run --change-set-id 5              # dry run - validate, print gate results, write nothing
python -m app.export.run --change-set-id 5 --confirm     # write the .tfx + changelog + validation report
```

The Change Sets tab has a "Preview export" action that runs every gate
without writing anything; producing the actual file is deliberately a
terminal command, not a button. See `docs/export-validation.md` -
including what this tool can't verify (whether Timetabling Solutions
itself accepts the file - test that yourself first).

## Clearing working data

```bash
cd backend
python -m app.retention              # dry run - lists what would be deleted
python -m app.retention --confirm    # actually deletes data/ and output/
```

Never touches `Timetabler Export/`. See `docs/privacy-threat-model.md`.

## Overriding data locations

Set these environment variables if your export folder or working
directories live somewhere else:

- `TT_SOURCE_DIR` - defaults to `./Timetabler Export`
- `TT_DATA_DIR` - defaults to `./data`
- `TT_OUTPUT_DIR` - defaults to `./output`
