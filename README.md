# Sophia College Timetable Tool

A local, offline-first tool that ingests Sophia College's Timetabling
Solutions export and eMinerva roll-marking files, builds a normalised
internal model, runs deterministic checks over it (clashes, room
utilisation, teacher load), and layers a locally-run AI advisor on top
that can explain findings and draft concrete edits for review.

Everything runs on your machine. Nothing containing student or staff data
is ever sent to a cloud API by this tool - see `docs/data-formats.md`
Section 3's privacy note and the project brief
(`claude-code-timetabling-tool-prompt.md`) for the constraints this is
built against.

**Status**: data ingestion + cross-validation and a read-only timetable
grid view (filterable by teacher/room/roll class) are built and tested
against the real export in `Timetabler Export/`. Analysis engine, AI
advisor, and edit/export are not built yet - this README will grow as
those land.

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

Then open http://localhost:5173. Filter the timetable by teacher, room,
or roll class; each cell shows what's on, and a cell with more than one
entry is flagged as a clash - a first hint of what the analysis engine
(next up) will check systematically.

## Overriding data locations

Set these environment variables if your export folder or working
directories live somewhere else:

- `TT_SOURCE_DIR` - defaults to `./Timetabler Export`
- `TT_DATA_DIR` - defaults to `./data`
- `TT_OUTPUT_DIR` - defaults to `./output`
