# Claude Code Project Brief: Sophia College Timetable Analysis & AI Advisor

Paste everything below into Claude Code as your opening prompt inside the project folder that contains the sample export files.

---

## 1. Role and objective

You are building a local, offline-first desktop/web tool for a Queensland secondary school. The tool ingests timetable export data produced by **Timetabling Solutions** (the software the school uses to build its master timetable) and the associated **eMinerva** roll-marking export files, builds a clean internal data model, runs a rules-based analysis engine over it, and layers a locally-run AI assistant on top that explains findings and proposes concrete, human-readable adjustments (e.g. room reassignments, load rebalancing). The tool must also be able to write its suggested changes back out in a format that can be re-imported into Timetabling Solutions, without corrupting the original files.

This is a real production tool for a working school. Treat data integrity, student privacy, and non-destructive file handling as first-class requirements, not afterthoughts.

## 2. What's in this folder (read before writing any code)

The project folder contains:
- A sample **export from Timetabling Solutions** (the master timetable / timetable development export)
- The associated **eMinerva** files (roll-marking software import/export format)
- Current **student data** files
- The school's **current live timetable** file, for reference

**Do not assume you know the schema of these files in advance.** Timetabling Solutions has changed its export format across versions (older exports are proprietary/delimited text; Version 10 exports are JSON with extensions like `.tfx` for Timetable Development and `.sfx` for Student Options). eMinerva's import/export format is also not something you should guess at. The actual files in this folder are the ground truth — the docs are not.

### Phase 0 — Discovery (mandatory first step, before any feature work)

1. List every file in the folder, note extensions, sizes, and (for text-based files) the first ~50 lines.
2. For each distinct file type found, determine: encoding, structure (JSON/CSV/delimited/fixed-width/proprietary), and — for JSON/CSV — the field names, data types, and any obvious foreign-key relationships between files (e.g. teacher IDs, room IDs, class codes, period/timeslot codes).
3. Identify which file(s) represent: teachers/staff, rooms/spaces, subjects/classes/activities, timeslots/periods/cycle days, the actual timetable grid (who teaches what, where, when), and student enrolments/class memberships.
4. Identify which file(s) are the eMinerva roll-marking export/import and how they relate to the Timetabling Solutions data (they likely share teacher, room, class, and student identifiers — confirm this rather than assuming).
5. Write up findings in a `docs/data-formats.md` file in the repo: one section per file type, with a description of every field you can confidently identify, a note on anything ambiguous, and a small anonymised sample snippet for reference. **Do not commit real student names/IDs into this doc or anywhere in git history — see Section 3.**
6. Only after this discovery doc exists and you're confident in the mapping, propose the internal data model (Section 5) and confirm it with me before building the ingestion layer.

If any file is genuinely undocumented and ambiguous (e.g. an unexplained numeric code), flag it clearly rather than guessing silently — wrong assumptions here corrupt every downstream analysis.

## 3. Non-negotiable constraints

- **Student privacy first.** This tool handles real student names, class memberships and possibly demographic/support data. Nothing containing student PII may ever be sent to a cloud API, logged in plaintext to a location outside the project's local data directory, or committed to git. Add a `.gitignore` covering the actual data files, any exports, and any local database from day one, before importing real data.
- **AI must be free and local.** The "AI advisor" layer must run on local/open-source models via **Ollama** (or an equivalent free local inference runtime), not a paid API, by default. See Section 7 for the architecture — it must still be built as a pluggable interface so a paid API can be swapped in later if I choose to, but the default and the one you configure must require no API key and no per-token cost.
- **Non-destructive.** Never modify the original export files in place. All processing reads from the source files and writes to a separate working/output directory. Every export the tool produces gets a new filename with a timestamp.
- **Round-trip fidelity.** Whatever the tool exports for re-import into Timetabling Solutions must validate against the same schema/structure as the original export for that file type. Build a validation step that diffs the regenerated file's structure against the original before treating an export as "ready."
- **Offline-capable.** Aside from optionally pulling an Ollama model on first setup, the tool must run with no internet connection.
- **Incremental, reviewable build.** Work in small, logically separated commits (data discovery → parsers → data model → analysis engine → AI layer → export → UI), and pause for my confirmation after Phase 0 and after the data model is proposed, before writing the bulk of the application. Don't build the whole thing in one shot.

## 4. Core features

### 4.1 Import / parsing
- Parsers for the Timetabling Solutions export file(s) found in the folder (whatever format Phase 0 reveals).
- A parser for the eMinerva file(s), reconciled against the same teacher/room/student/class identifiers as the timetable data.
- A parser for the student data file(s), joined in as the source of truth for enrolments, year levels, and class lists.
- All parsers should fail loudly and specifically (not silently drop rows) if they hit a record they can't map to the data model.

### 4.2 Internal data model
Design (and document in `docs/data-model.md`) a normalised internal model covering, at minimum:
- **Teachers**: identifier, name, faculty, max/contracted load, subjects qualified to teach
- **Rooms/spaces**: identifier, name, capacity, room type/features (e.g. lab, PE space, general classroom), building/location if available (for travel-time analysis)
- **Subjects/classes/activities**: identifier, subject, year level, class code, teacher(s), room(s) assigned, students enrolled, number of periods per cycle
- **Timeslots**: cycle structure (e.g. 10-day or weekly cycle, periods per day), so the model correctly represents the school's actual timetable cycle rather than assuming a plain Mon–Fri week
- **Timetable entries**: the join of class + teacher + room + timeslot(s) — the actual grid
- **Students**: identifier, year level, class memberships, and (if present) any support flags relevant to placement (e.g. access needs affecting room suitability) — treat this field with extra care per Section 3

### 4.3 Rules-based analysis engine
Before any AI involvement, build deterministic checks that produce structured findings (not prose) — the AI layer explains these, it doesn't invent them. At minimum:
- **Clash detection**: any teacher, room, or student double-booked in the same timeslot
- **Room capacity mismatches**: class enrolment exceeding room capacity, or a class significantly under-filling a large room while another class is squeezed
- **Room suitability mismatches**: e.g. a practical/lab subject scheduled in a room without the required features
- **Teacher load analysis**: total periods per teacher against contracted/max load, distribution of free periods (fragmented vs consolidated), consecutive-period load, and first/last period loading
- **Room utilisation**: percentage utilisation per room per cycle, identifying chronically underused or oversubscribed spaces
- **Travel/movement analysis**: back-to-back classes for the same teacher or student cohort in distant rooms/buildings, if location data allows this
- **Gaps and structural inefficiencies**: split classes, single-period isolated lessons, uneven spread of a subject across the cycle

Each check should output a structured record: what was found, severity, which entities are involved, and the raw data needed to act on it. Store these as data, not as generated text — this is what the AI layer consumes.

### 4.4 AI advisor layer

Purpose: turn the structured findings from 4.3 into plain-English explanations and concrete, ranked suggestions a Deputy Principal or timetabler can act on (e.g. "Room 14 is at 96% utilisation while Room 9 — same capacity, same features — sits at 41%. Moving Year 9 Science 3 from Room 14 to Room 9 on Tuesday P3 would resolve the Wednesday clash with Year 11 Chemistry and free Room 14 for the oversubscribed Year 8 cohort.").

Architecture:
- Define a small internal interface, e.g. `AdvisorProvider.suggest(findings, context) -> [Suggestion]`, so the model backend is swappable.
- Default implementation: **Ollama**, running a locally-pulled open model (recommend something in the 7–8B range that runs reasonably on typical hardware — confirm what's actually available/pullable at build time rather than hardcoding a model name that may be deprecated).
- The AI layer receives only structured, de-identified findings where possible (room codes, class codes, aggregate numbers) rather than raw student names, to minimise unnecessary PII exposure even to a local model.
- Every AI-generated suggestion must cite which underlying rule-engine finding(s) it's based on, and must not fabricate data — if the model proposes a room swap, it must reference only rooms/classes that actually exist in the parsed data, and you should validate that reference before displaying the suggestion.
- Suggestions should be rankable/filterable (by severity, by faculty, by teacher, by "quick win vs structural change").

### 4.5 Export back to Timetabling Solutions
- Given an accepted set of changes (manually applied by me, or approved from the AI's suggestions), regenerate an export file in the same format/schema as the original Timetabling Solutions file, with only the approved changes applied.
- Validate the regenerated file against the structure captured in Phase 0 before presenting it as ready to import.
- Produce a clear changelog alongside the export: what changed, from what, to what, and why (linked back to the finding/suggestion that prompted it).

### 4.6 Interface
- A local web UI (this can run as a simple local server, no need for a hosted deployment) with:
  - A dashboard summarising key findings (clashes, utilisation, load balance) at a glance
  - A visual timetable grid view, filterable by teacher, room, or year level
  - A findings/suggestions list with the AI's plain-English explanation and an accept/reject/modify action per suggestion
  - An export screen showing exactly what will change before generating the output file
- Keep the UI functional and clear over polished — this is a working tool for the school, not a public product. Use Tailwind for basic styling if using a JS/React frontend.

## 5. Suggested tech stack (adjust if the discovery phase reveals a better fit)

- **Backend/parsing/analysis**: Python (pandas or plain dataclasses for the data model, FastAPI for a local API layer) — Python's JSON/CSV handling and data-analysis ecosystem suit this well. If Phase 0 shows the export is XML or another format that's cleaner to handle in another language, say so before committing to this.
- **Local storage**: SQLite for the normalised internal model, so the analysis engine and UI can query it without re-parsing files each time.
- **AI runtime**: Ollama, called via its local HTTP API.
- **Frontend**: a lightweight React app (or server-rendered if you prefer to keep it simpler) talking to the FastAPI backend.

## 6. Working style

- Build in the order: Phase 0 discovery → data model proposal (pause for my sign-off) → parsers → SQLite-backed data model → rules engine (with tests using the real reference files) → AI advisor layer → export/round-trip → UI.
- Commit at each logical milestone with a clear message, not one giant commit at the end.
- Write a short `README.md` explaining how to set up Ollama, pull the model, install dependencies, and run the tool, since this needs to be usable by me without you present.
- Where you're genuinely unsure about a school-specific timetabling convention (e.g. how the cycle days work, what counts as a "clash" for a split class, whether certain rooms are shared with another timetable stream), ask rather than assume — get it right against our actual data rather than a generic timetabling model.

## 7. First action

Start with Phase 0 discovery only. Report back what you find in the folder before writing any parser or model code.
