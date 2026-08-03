# Claude Code Implementation Brief: Complementary Timetabling Builder

## 1. Product direction

Extend the existing Sophia College Timetable Tool from a timetable analysis application into a **complementary timetable construction and optimisation system** that works alongside Timetabling Solutions.

The application is not intended to replace Timetabling Solutions or BCE administration platforms. It should provide a safer, more transparent local workspace in which authorised school staff can:

1. import timetable, staffing, room, class, enrolment and school-constraint data;
2. validate and normalise those sources into a versioned internal model;
3. construct or revise a timetable using deterministic constraints and optimisation;
4. use a locally hosted AI assistant to explain issues, collect human instructions, compare alternatives and support decision-making;
5. review every proposed change in a clear before-and-after interface;
6. export a validated Timetabling Solutions-compatible file;
7. use Timetabling Solutions as the interoperability and verification bridge before producing the established exports for relevant BCE systems.

The essential design principle is:

> The constraint solver calculates. The local AI interprets and assists. The authorised timetabler decides. Timetabling Solutions validates interoperability.

Do not allow a language model to directly invent or silently apply timetable allocations.

## 2. Relationship to existing work

Retain the current:

- offline-first architecture;
- `.tfx`-first ingestion and source-identifier preservation;
- CSV and eMinerva cross-validation;
- SQLite-backed normalised model;
- read-only timetable grid;
- structured composite-class detection;
- local Ollama provider approach;
- non-destructive handling of source files;
- requirement that all exports be new, timestamped files;
- privacy rule preventing school data from being sent to cloud AI services.

Build the construction system on top of this foundation rather than replacing it.

## 3. Scope boundaries

### In scope

- Importing existing timetable and associated reference data.
- Starting from either an existing timetable or an unallocated planning dataset.
- Building, repairing and optimising timetable allocations.
- Human-defined hard and soft constraints.
- Scenario creation and comparison.
- Local AI explanations and natural-language interaction.
- Controlled export to Timetabling Solutions-compatible formats.
- Generation of the existing eMinerva/BCE-facing export files only after the Timetabling Solutions-compatible output has passed validation.

### Out of scope for the first construction release

- Direct write access to eMinerva or other BCE production systems.
- Cloud-hosted AI processing of identifiable school data.
- Unattended publication of a timetable.
- Automatic acceptance of AI suggestions.
- Replacing Timetabling Solutions as the final source of import/export compatibility.
- Student subject-selection optimisation from `.sfx` files, unless later introduced as a separate milestone.

## 4. Revised architecture

Use five explicit layers.

### Layer A: Source snapshots

Every import creates an immutable `SourceSnapshot` containing:

- source file name and type;
- SHA-256 hash;
- import timestamp;
- source software/version where available;
- parser version;
- validation result;
- links to imported entity records;
- optional user label, such as `2027 planning baseline`.

Never edit imported source records in place.

### Layer B: Canonical planning model

Extend the existing data model to represent both scheduled and unscheduled requirements.

Add or confirm the following concepts:

- `TeachingRequirement`: class/course, required periods per cycle, duration, eligible teachers, preferred teacher, eligible rooms, room-feature needs, student/cohort membership and spread requirements.
- `TeacherAvailability`: teacher, available/unavailable slot, reason category, hard/soft status.
- `RoomAvailability`: room, available/unavailable slot, hard/soft status.
- `StudentGroup`: a set of students or a cohort whose simultaneous requirements must be considered.
- `ParallelBlock`: courses that must or may run concurrently, including option lines.
- `FixedEvent`: assembly, registration, meeting, duty, intervention, pastoral or other immovable event.
- `ConstraintDefinition`: typed school rule with parameters, weight, scope, source and enabled state.
- `PlanningAssignment`: requirement + teacher + room + timeslot.
- `Scenario`: a named timetable proposal derived from a source snapshot.
- `ScenarioAssignment`: an overlay representing an unchanged, added, moved or removed allocation.

Preserve all source identifiers required for export fidelity.

### Layer C: Constraint and optimisation engine

Use a deterministic constraint solver as the timetable-building engine. Prefer Google OR-Tools CP-SAT unless repository constraints or discovery demonstrate a better local alternative.

The solver must:

- operate entirely locally;
- be reproducible when given the same input, configuration and random seed;
- separate hard constraints from weighted soft constraints;
- report infeasibility rather than silently relaxing hard constraints;
- identify, where practicable, the set of constraints contributing to infeasibility;
- support time-limited solving and retain the best feasible solution found;
- emit structured solver metrics without names or emails in logs.

### Layer D: Local AI advisor

Ollama remains an advisory interface, not the mathematical engine.

The AI may:

- translate a timetabler's instruction into a draft structured constraint;
- explain solver findings and trade-offs;
- summarise differences between scenarios;
- describe why a requirement is currently infeasible;
- suggest which soft constraint weights could be reviewed;
- prepare human-readable change summaries.

The AI must not:

- create an allocation that has not passed deterministic validation;
- change hard constraints without explicit approval;
- invent teachers, rooms, classes, students, periods or capacities;
- receive unnecessary student names or contact details;
- write directly to the approved scenario or export files.

Any natural-language request must be converted into a previewable structured action. The user must approve that action before it affects a scenario.

### Layer E: Export and interoperability

Exports follow this controlled path:

1. approved scenario;
2. full deterministic validation;
3. generation of a new Timetabling Solutions-compatible file;
4. structural and referential comparison with the source format;
5. human review of the changelog;
6. trial import into a non-production or copied Timetabling Solutions dataset;
7. Timetabling Solutions validation and established downstream export process;
8. generation or handling of BCE-facing/eMinerva files only through confirmed formats and approved operational procedures.

Do not claim compatibility with a BCE system unless an actual source file, documented format or verified import workflow has been examined.

## 5. Constraint catalogue

Create `docs/constraint-catalogue.md`. Each constraint must have an ID, description, hard/soft classification, parameters, evidence source, default weight, exemptions and tests.

### Required hard constraints

- A teacher cannot teach two unrelated physical lessons in one timeslot.
- A room cannot host two unrelated physical lessons in one timeslot.
- A student cannot be allocated to two required lessons in one timeslot.
- A requirement must receive its required number and duration of periods.
- Only an eligible teacher may teach a requirement.
- Teacher unavailability must be respected.
- Room unavailability must be respected.
- Fixed events must remain fixed.
- Room capacity must be respected where capacity is known and configured as enforceable.
- Required room features must be present.
- Composite classes approved by a human must be treated as one physical lesson where appropriate.
- Parallel option blocks must preserve the student-choice structure represented by the planning data.

### Initial soft constraints

- Balanced teacher load across the cycle.
- Limits on excessive consecutive teaching periods.
- Reduced first/last-period concentration.
- Consolidated or appropriately distributed non-contact periods.
- Even lesson spread across the fortnight.
- Avoidance of isolated single lessons where undesirable.
- Preferred double-period patterns for practical subjects.
- Reduced travel between distant buildings or room zones.
- Stable classroom allocation where practical.
- Improved room utilisation without displacing specialist requirements.
- Preferred teacher and room allocations.
- Reduced changes from the imported baseline timetable.
- Balanced student daily load.

Do not hard-code Sophia-specific policy values. Store them in school configuration with a source, effective date and user-visible explanation.

## 6. Scenario workflow

Implement a scenario-based workflow:

1. **Import baseline**: create an immutable source snapshot.
2. **Data health review**: block solving if critical mappings or identifiers are unresolved.
3. **Configure requirements**: show unscheduled requirements, staffing options, room needs and constraints.
4. **Create scenario**: clone the baseline as an overlay, not a copied mutable database.
5. **Solve**: generate a feasible proposal using hard constraints and weighted objectives.
6. **Review**: show timetable grid, findings, unallocated requirements and score breakdown.
7. **Adjust**: permit manual moves and natural-language draft instructions, each validated before application.
8. **Compare**: compare at least two scenarios using consistent metrics.
9. **Approve**: capture the approver, date, scenario version and validation result.
10. **Export**: generate a timestamped file and machine-readable plus human-readable changelog.

A scenario must have an explicit state:

- `DRAFT`
- `SOLVING`
- `FEASIBLE`
- `INFEASIBLE`
- `VALIDATED`
- `APPROVED`
- `EXPORTED`
- `ARCHIVED`

Only an approved, currently validated scenario may be exported.

## 7. Timetable scoring

Provide a transparent scorecard rather than one unexplained total.

Suggested categories:

- feasibility: pass/fail;
- unresolved hard violations;
- teacher load balance;
- student experience;
- curriculum spread;
- room suitability;
- room utilisation;
- staff movement;
- baseline disruption;
- unallocated requirements.

Show raw measures and weighted contributions. The user must be able to see why Scenario A scores differently from Scenario B. Do not describe a scenario as "best" unless the configured score and validation results support that label.

## 8. Import experience

Build an import wizard with these stages:

1. select a source folder or supported files;
2. identify file types;
3. preview source snapshot and detected software version;
4. run schema and encoding checks;
5. map or confirm ambiguous fields;
6. display discrepancies between `.tfx`, CSV and eMinerva sources;
7. classify problems as blocking, warning or informational;
8. create the source snapshot only after validation;
9. provide a de-identified import report.

The wizard must never log student or staff names merely to report a parsing error. Use source file, row/index, field and internal/source identifier.

## 9. Manual editing safeguards

Every drag/drop or form-based timetable edit must run a fast validation before it can be applied.

The preview should show:

- current assignment;
- proposed assignment;
- hard conflicts;
- soft-score impact;
- affected teacher, room, class and cohort codes;
- related approved composite groups;
- source finding or user instruction;
- undo availability.

Support undo/redo within a draft scenario. Maintain an append-only audit record of scenario changes.

## 10. Local AI interaction pattern

Add a local chat/advisor panel focused on controlled actions.

Examples of acceptable requests:

- "Explain why this class is unallocated."
- "Find valid rooms for this science class."
- "Draft a constraint preventing this teacher from Period 1."
- "Compare the staff-load impact of these two scenarios."
- "Suggest the least disruptive valid move for this clash."

Each response that proposes an action must include:

- the interpreted instruction;
- the structured constraint or proposed change;
- entities referenced;
- supporting findings;
- deterministic validation result;
- expected score impact;
- `Apply`, `Modify` and `Reject` controls.

Validate every referenced entity ID against the canonical model before displaying the proposal.

## 11. Privacy, security and governance

Add `docs/privacy-threat-model.md` and enforce:

- local processing by default;
- no cloud AI endpoint in the default build;
- no PII in Git, logs, fixtures, screenshots or documentation;
- synthetic test datasets only;
- role-appropriate local access controls if more than one user can access the application;
- encryption expectations documented for the device and working directory;
- configurable retention and secure purge of working databases and generated exports;
- visible source snapshot and scenario version on all exports;
- audit records for import, constraint change, solve, manual edit, approval and export;
- redacted support bundles for troubleshooting.

Add a startup check that warns if the configured source, data or output directory appears to be inside a Git-tracked path.

## 12. Export validation gate

Create `docs/export-validation.md`. An export is not ready unless all checks pass:

- supported format/version identified;
- schema/shape compatible with source;
- no missing or duplicate required identifiers;
- all foreign-key references resolve;
- unchanged source records retain fidelity;
- only approved scenario changes appear in the diff;
- hard constraints have zero unresolved violations;
- composite handling matches approved composite groups;
- generated file can be parsed again by the application's own parser;
- re-parsed canonical assignments match the approved scenario;
- changelog and validation report are generated;
- filename includes scenario/version and timestamp;
- original files remain untouched.

Initially place construction export behind an `experimental_export` feature flag.

## 13. API and module plan

Suggested backend modules:

```text
backend/app/
  snapshots/
  planning/
  constraints/
  solver/
  scenarios/
  findings/
  advisor/
  validation/
  export/
  audit/
```

Suggested API groups:

```text
/api/snapshots
/api/imports
/api/requirements
/api/constraints
/api/scenarios
/api/scenarios/{id}/solve
/api/scenarios/{id}/validate
/api/scenarios/{id}/compare
/api/scenarios/{id}/changes
/api/scenarios/{id}/approve
/api/scenarios/{id}/export
/api/advisor
```

Do not expose names, emails or raw student records in endpoints that only require codes or aggregates.

## 14. Testing strategy

Tests must use synthetic data and include:

- a small feasible timetable;
- a deliberately infeasible timetable;
- teacher and room clashes;
- student-choice conflicts;
- fixed events;
- unavailable teachers and rooms;
- specialist-room requirements;
- approved and rejected composite candidates;
- a room with unknown capacity;
- non-teaching entries;
- an interrupted A/B calendar mapping;
- deterministic solve using a fixed seed;
- scenario comparison;
- manual edit validation;
- export round-trip reconstruction;
- proof that original source files are unchanged;
- checks that logs and generated reports contain no synthetic names/emails where identifiers suffice.

Add golden-file tests only with fully synthetic export fixtures.

## 15. Delivery milestones

### Milestone A: Construction-ready model

- Add source snapshots, teaching requirements, availability, constraints and scenarios.
- Add migrations and synthetic fixtures.
- Document all new entities.

### Milestone B: Constraint catalogue and validator

- Implement hard-constraint validation against existing timetable assignments.
- Persist structured violations.
- Add constraint-management UI.

### Milestone C: Solver proof of concept

- Build a small synthetic timetable from unscheduled requirements.
- Demonstrate reproducible feasible and infeasible outputs.
- Produce transparent objective metrics.

### Milestone D: Existing-data scenario

- Convert the imported Sophia timetable into a baseline scenario.
- Repair selected conflicts without changing source data.
- Compare baseline and repaired scenarios.

### Milestone E: Local AI advisor

- Add structured natural-language constraint drafting.
- Add explanations and scenario summaries.
- Enforce entity validation and human approval.

### Milestone F: Timetabling Solutions export

- Implement approved-scenario export and full round-trip validation.
- Keep behind the experimental flag.
- Produce changelog and validation report.

### Milestone G: Operational hardening

- Audit, purge, backup, recovery, error handling, privacy review and user documentation.
- Document the verified procedure for passing an exported timetable through Timetabling Solutions and then into established BCE systems.

## 16. First implementation task

Do not begin with the AI chat or export writer.

Start by reviewing the current schema, migrations, parser outputs, composite detection and API models. Then produce:

1. `docs/construction-gap-analysis.md`, mapping the existing implementation to this brief;
2. `docs/constraint-catalogue.md`, with the first hard and soft constraints;
3. a proposed schema migration for source snapshots, teaching requirements, constraint definitions and scenarios;
4. a minimal synthetic dataset suitable for solver tests;
5. an implementation plan for Milestones A to C.

Do not alter live timetable data. Do not write the solver until the construction gap analysis and schema proposal are internally consistent with the existing ingestion model.

## 17. Acceptance criteria for the first construction release

The first construction release is acceptable when an authorised user can:

- import and validate a supported baseline dataset;
- see all scheduled and unscheduled teaching requirements;
- configure teacher and room availability plus documented constraints;
- generate at least one feasible local scenario using deterministic optimisation;
- see unresolved requirements and the reason for infeasibility;
- manually adjust a scenario with immediate validation;
- compare scenarios using transparent metrics;
- obtain local AI explanations without sending data to a cloud AI service;
- approve a scenario through an auditable action;
- generate a Timetabling Solutions-compatible candidate export;
- re-import that generated file into the application's parser with complete assignment equivalence;
- retain the original source files without modification.
