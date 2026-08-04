# Privacy and Audit

Implements PROJECT_ROADMAP.md's Milestone 5. Most of this was already
true by construction (every prior milestone was built under the same
no-PII rule); this document consolidates it, closes the remaining gaps
(audit trail, source-hash provenance, retention/purge), and states
plainly what's genuinely out of scope for a local single-user tool.

## Data flow and trust boundaries

```
Timetabler Export/ (read-only, real student/staff data)
        |
        v  ingestion (app/ingest/) - never writes back here
data/sophia_tt.sqlite3 (working DB, gitignored)
        |
        v  rules engine, change sets, suggestions (all read/write this DB only)
        |
        v  API (FastAPI, localhost:8000) - serves the local UI only
        |
        v  frontend (Vite dev server, localhost:5173)
```

**Nothing in this tool talks to the network beyond localhost.** No cloud
API calls exist anywhere in the codebase today. When the AI advisor layer
is eventually built, the brief's constraint (Ollama only, local inference)
governs it - see `docs/data-model.md`'s architecture decisions.

**One important caveat the above does not cover: OneDrive.** The project
directory (including `Timetabler Export/`, `data/sophia_tt.sqlite3`, and
`output/`) currently lives inside a `OneDrive - Brisbane Catholic
Education` folder, so everything in it syncs to BCE's OneDrive tenant.
That's outside this tool's control - the tool itself never initiates any
network transfer - and it isn't a *new* exposure (the source exports
already lived in this folder before this project existed, and it's the
school's own managed tenant, presumably with its own compliance
posture). But "everything stays on this machine" would be an overclaim:
the accurate statement is "this tool sends nothing anywhere; the folder
it lives in is cloud-synced by the school's own OneDrive." If strictly
local storage is ever required, move the working directories out of
OneDrive via `TT_SOURCE_DIR`/`TT_DATA_DIR`/`TT_OUTPUT_DIR`.

**The one external-facing surface** is `Timetabler Export/` itself -
read-only, and every ingestion path (`app/ingest/`) only ever opens files
under `SOURCE_DIR` for reading. `app/config.py`'s `DATA_DIR`/`OUTPUT_DIR`
split exists specifically so nothing the app writes can land back in the
source folder by accident.

## What was already true, verified for this milestone

- **Synthetic fixtures only in git.** Every test that needs timetable
  data either builds it from `tests/synthetic.py` (fabricated codes like
  `T1`, `CLASSA`, `100001`) or skips itself entirely when the real
  `Timetabler Export/` folder isn't present (`pytest.mark.skipif`). No
  real name, email, or student code has ever been committed.
- **The working database and generated exports are gitignored.**
  `.gitignore` excludes `/data/`, `/output/`, `*.sqlite3`, and the entire
  `/Timetabler Export/` tree.
- **No PII in application logs or exception traces**, checked directly
  for this milestone: every `print()` statement in the codebase (ingest
  progress, composite detection) outputs codes only. Every discrepancy
  logged during ingestion (`ingest_discrepancy.detail_json`) carries
  codes, never names. `test_finding_entity_refs_never_contain_names` and
  `test_audit_detail_never_contains_a_name_by_convention` assert this
  holds for the two other structured-record types (findings, audit
  events) that could plausibly leak a name if someone stopped being
  careful in a future change.
- **Local, single-user desktop mode - by omission, not by a flag.**
  There is no user table, no login, no session concept anywhere in the
  schema or API. `actor` fields (audit events, composite/change-set
  reviews) are free-text names typed into the UI at the time, not an
  authenticated identity - this is a conscious choice for a tool one
  person runs on their own machine, not a gap to fix later unless the
  school actually needs multiple people acting through it independently.

## What this milestone added

### Audit trail (`audit_event` table, `app/audit.py`)

One `log_event()` helper, called from every place PROJECT_ROADMAP.md
asks for: import completion, rules-engine runs, composite-class
approve/reject, change-set approve/reject. Append-only - nothing in the
application ever updates or deletes an `audit_event` row. `detail_json`
follows the same no-PII rule as findings: codes and aggregate counts,
never names (a school-facing `note` field on composite/change-set
reviews is free text a person types, so it's the one place a name could
theoretically end up if someone typed one deliberately - documented as a
convention to avoid, not something the system can enforce automatically).

Read via `GET /api/audit` (optionally filtered by `event_type`) and the
**Audit** tab in the UI.

### Source-file hash (`ingest_run.tfx_source_sha256`)

Every ingest run now records the SHA-256 of the `.tfx` file it read,
computed before parsing starts. This is what "prove which timetable
version was analysed" (PROJECT_ROADMAP.md) actually means in practice:
if a finding, a composite candidate, or a change set's validation result
is ever in question, the exact byte-for-byte source file is identifiable
from `ingest_run`, not just a filename and a timestamp that could refer
to an edited-in-place file.

### Retention and purge (`app/retention.py`)

```bash
cd backend
python -m app.retention              # dry run - lists what would be deleted
python -m app.retention --confirm    # actually deletes
```

Deletes everything under `data/` and `output/` - never anything under
`Timetabler Export/`, which isn't in its search path at all (`
test_purge_never_touches_source_dir` asserts this). Deliberately **CLI-only,
not exposed over the API** - a destructive, whole-database action should
require someone at a terminal choosing to run it, not be one click away
in a UI. Defaults to a dry run; nothing is deleted without `--confirm`.

One necessary tradeoff: purging the working database also purges that
database's own `audit_event` history, since the audit log lives inside
the same file being deleted. A purge is an intentional clean slate, not
a selectively-forgetful edit - back up `data/sophia_tt.sqlite3` first if
the audit history needs to survive the purge.

## What's still out of scope

- **Encryption at rest** for the working SQLite database - not
  implemented. Reasonable for a school-managed device with disk
  encryption already in place at the OS level; would need revisiting if
  this ever runs somewhere that assumption doesn't hold.
- **Redacted support bundles** - if this tool ever needs to be debugged
  by someone other than the person running it, there's no automated way
  yet to export a diagnostic bundle with names stripped. Not built
  because nobody has needed to debug it remotely yet.
- **Multi-user access control** - genuinely out of scope until the school
  says more than one person needs to use this independently; see "single-
  user desktop mode" above.
