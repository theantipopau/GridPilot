# .tfx/.sfx Compatibility and Auto-Discovery

Written 2026-08-04 in response to three direct questions: is the
ingestion pipeline resilient to a *different* `.tfx` file (a future
term's export, a newer Timetabling Solutions version)? Can it actually
read the real files sitting in the project folder? And what about the
per-year-level Student Options (`.sfx`) files - are those wired in at
all? Answered by actually inspecting and parsing every `.tfx`/`.sfx`
file present, not from memory - see the verification section below.

## What was found

Every file in `Timetabler Export/TT files/` parses as valid JSON and has
the expected shape:

| File | Format | File ID | Top-level sections |
|---|---|---|---|
| `TT 2026 Term Three Week 4.tfx` | Timetable | `Timetabling Solutions X TD 10.1.1.86` | 24 |
| `YR 7 2026 Term 3.sfx` | Student Options | `Timetabling Solutions X SO 10.1.1.86` | 8 |
| `YR 8 2026 Term 3.sfx` | Student Options | same | 8 |
| `YR 9 2026 Term 3.sfx` | Student Options | same | 8 |
| `YR 10 2026 Term 3.sfx` | Student Options | same | 9 |
| `YR 11 2026.sfx` | Student Options | same | 9 |
| `YR 12 2026.sfx` | Student Options | same | 8 |

Note the section count already varies between `.sfx` files of the
*same* version (Year 12's file has no `StudentFiles` section; Years 7-9
have no `Constraints` section) - confirming that even within one known
version, optional sections really are optional, not a fixed contract.
This shaped the parser design below: every `.sfx` section is treated as
optional (missing = zero rows), while `.tfx` has a fixed set of sections
this application actually depends on (see below).

## Backwards/forwards compatibility coding improvements made

Three changes, all in `backend/app/ingest/tfx_parser.py` and
`backend/app/config.py`:

### 1. A real compatibility check, not a raw `KeyError`

Before this change, a `.tfx` missing an expected section (or a
completely different file handed to the parser by mistake) would fail
with whatever Python exception happened to surface first - a `KeyError`
deep in `_ingest_timetable`, unhelpful and hard to diagnose.
`check_tfx_compatibility()` now runs first and:

- **Hard-fails with a clear message** (`IngestError`, not a raw
  exception) only for genuine incompatibilities: a Student Options file
  handed to the timetable parser, or a file missing one of the 11
  sections this parser actually reads (`Days`, `Periods`, `YearLevels`,
  `Rooms`, `Teachers`, `Faculties`, `RollClasses`, `ClassNames`,
  `ClassGroups`, `Timetable`, `Students`).
- **Logs, doesn't fail, for softer signals**: a `File ID` version string
  different from `KNOWN_TFX_VERSION` (`tfx_version_drift`, warning), or a
  top-level section this parser doesn't recognise
  (`tfx_unknown_sections`, warning) - both as `ingest_discrepancy` rows,
  visible in the Findings/Audit UI, not silent. A future Timetabling
  Solutions version that adds a new top-level section (there's real
  precedent - `RURs`/`MRCGs` are already present and only partially
  understood, see `docs/data-formats.md` #4) would surface as a visible
  warning instead of silently ignoring data or silently crashing.

`ingest_run.source_file_id` now records the exact version string every
ingest ran against, alongside the existing SHA-256 hash - both together
answer "what exactly did this analysis run against" precisely.

### 2. Auto-discovery instead of one hardcoded filename

`TFX_PATH` used to be a single hardcoded path
(`TT 2026 Term Three Week 4.tfx`) - a new term's export with a different
filename would have silently kept analysing the *old* file, or required
a code change. Now:

- `find_tfx_files()` / `find_sfx_files()` glob the source folder for
  every `.tfx`/`.sfx` present.
- `default_tfx_path()` picks the most recently modified `.tfx` unless
  `TT_TFX_PATH` is set explicitly.
- `python -m app.ingest.run` accepts `--tfx <path>` to target a specific
  file (prints which file it's using either way, so it's never ambiguous
  after the fact).
- `run_full_ingest()` still accepts an explicit `tfx_path`/`sfx_paths`
  for tests and scripting, defaulting to auto-discovery when omitted.

A future term's export just needs to land in `Timetabler Export/` - no
code change, and the CLI tells you which file it picked.

### 3. Student Options (`.sfx`) ingestion, wired into the same pipeline

Previously discovered (Phase 0) but explicitly left unbuilt - see
`docs/data-formats.md` §3.2's original "recommend treating `.sfx` as
out-of-scope for v1" note. Built now: `backend/app/ingest/sfx_parser.py`
ingests every auto-discovered `.sfx` file into namespaced `sfx_*` tables
(see `docs/data-model.md`'s "Student Options data" section for the full
shape and why they're namespaced separately from the `.tfx` tables
despite similar-sounding names).

Verified against all six real files: 6 files, 60 lines, 193 subjects,
193 options, 503 classes, 6,756 student preferences ingested cleanly,
**zero** unlinked student codes (every `.sfx` student matched an
existing `.tfx` student - a real cross-validation result, not assumed).

## What this does *not* yet handle

Being precise about the actual limits of "backwards compatible":

- **A genuinely different Timetabling Solutions major version** (a "TD
  11" instead of "TD 10") would still ingest - the compatibility check
  only hard-fails on a *missing* required section, and a new major
  version is more likely to add sections than remove the ones this
  parser depends on - but it's untested territory. The version-drift
  warning exists specifically so this shows up visibly rather than
  silently, so you'd see it and could investigate rather than trust it
  blindly.
- **Field-level changes within a known section** (a renamed key, a
  restructured nested object) aren't detected by this layer at all - the
  compatibility check only looks at *which sections exist*, not their
  internal shape. A field rename would still surface as an error, just a
  less friendly one (a `KeyError` or `None` where a value was expected)
  further down in the relevant `_ingest_*` method. Hardening every field
  access individually wasn't done here - it would meaningfully increase
  code volume for a scenario (Timetabling Solutions silently renaming a
  field within the same major version) that has no precedent in the data
  gathered so far.
- **The `.sfx` data isn't used by anything downstream yet.** It's
  ingested and queryable, not yet wired into the rules engine, change
  sets, or export. See `docs/data-model.md` for what that could unlock.

## Verification

Every claim above was checked directly this session, not assumed:

```bash
# Confirmed every real .tfx/.sfx parses and inventoried their top-level keys
python3 -c "... json.load every file under Timetabler Export, print keys ..."

# Full pipeline against real data, auto-discovery exercised (no explicit paths)
python -m app.ingest.run
# -> sfx_file: 6, sfx_student_preference: 6756, 0 unlinked

# Full test suite
python -m pytest tests/ -q
# -> 93 passed
```

`backend/tests/test_tfx_compatibility.py` (8 tests) and
`backend/tests/test_sfx_parser.py` (8 tests) cover the compatibility
layer and `.sfx` ingestion synthetically; `test_ingest_full.py` adds
three real-data assertions (version string recorded, all six `.sfx`
auto-discovered, zero unlinked students).
