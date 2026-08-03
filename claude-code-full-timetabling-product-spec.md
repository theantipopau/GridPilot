# Claude Code Product and Implementation Specification
## Sophia College Complementary Timetabling Workspace

> **Status:** Expanded implementation specification
>
> **Purpose:** Extend the existing timetable analysis project into an intuitive, local-first planning, construction, optimisation, review and interchange workspace that complements Timetabling Solutions.

---

# 1. Product vision

Build a timetable workspace that makes complex school planning feel simple to an authorised school leader or timetabler.

The application should hold a reliable local representation of the school's timetable planning data, including:

- teachers and their employment fractions;
- teaching qualifications and subject capability;
- leadership, pastoral, coordination and support roles;
- release allocations attached to those roles;
- classes, subjects, curricula and required lesson counts;
- students, cohorts, subject selections and class memberships;
- rooms, capacities, room types and facilities;
- cycle days, periods, breaks, fixed events and school calendar exceptions;
- teacher, room, class and student constraints;
- the current timetable;
- alternative planning scenarios;
- solver findings, proposed changes and approvals;
- source-system identifiers needed for round-trip export.

The intended workflow is:

```text
Import and validate data
        ↓
Confirm staffing, roles, release and school rules
        ↓
Create or clone a planning scenario
        ↓
Build or optimise with a deterministic solver
        ↓
Use local AI to explain, compare and draft changes
        ↓
Review and approve a scenario
        ↓
Export a validated Timetabling Solutions-compatible file
        ↓
Verify through Timetabling Solutions
        ↓
Use established exports for eMinerva and other BCE systems
```

The application is not a black box. Every allocation, warning, score and suggestion must be explainable.

**Core rule:** the solver calculates, the local AI interprets, the timetabler decides, and Timetabling Solutions remains the compatibility bridge.

---

# 2. Design principles

## 2.1 Simple on the surface, rigorous underneath

A user should be able to perform common tasks without understanding database fields, solver variables or source GUIDs.

Example:

```text
People → Select teacher → Add role → House Companion → Solis
Tier: 2
Release: 120 minutes per cycle
Effective: 2027 school year
Save
```

Behind that simple flow, the system should create a versioned role assignment, apply the correct release entitlement, adjust the teacher's available teaching load, validate the change against the employment fraction, and include the allocation in future solver runs.

## 2.2 Progressive disclosure

Show only what the user needs for the current decision.

- Default view: plain language and key values.
- Expandable detail: source, calculation, constraints and history.
- Advanced mode: weights, solver controls, raw codes and mappings.

## 2.3 No hidden consequences

Before saving an action, show its effect.

Example:

```text
Adding House Companion - Solis

Role tier: Tier 2
Release: 120 minutes per 10-day cycle
Teacher teaching capacity before: 2,400 minutes
Teacher teaching capacity after: 2,280 minutes
Current allocated teaching: 2,320 minutes
Result: 40 minutes over available capacity

[Cancel] [Adjust release] [Save and flag workload issue]
```

## 2.4 Configuration, not hard-coding

Role tiers, release values, load rules, room types, preferred doubles and timetable policies must be configurable and versioned. Do not hard-code a universal meaning for “Tier 2”. The school should define the entitlement and effective dates.

## 2.5 Safe local AI

The local model may explain data, draft structured actions and compare validated alternatives. It must not silently create timetable assignments or alter policy values.

## 2.6 Immutable imports and reversible planning

Source imports are immutable snapshots. Changes occur only in scenarios and can be undone, compared, approved or discarded.

---

# 3. Primary users and jobs

## Timetabler

- import planning data;
- configure classes, staffing and constraints;
- generate and modify scenarios;
- examine infeasibility;
- compare alternatives;
- export an approved candidate.

## College leadership user

- review staffing loads and role release;
- approve school-wide planning assumptions;
- compare timetable scenarios;
- approve a scenario for export.

## Faculty or curriculum leader

- review subject requirements and room needs;
- identify teacher eligibility and preferences;
- review allocations for their area;
- provide constraints without accessing unnecessary student information.

## Read-only reviewer

- inspect a scenario, scorecard and change summary;
- add comments;
- not edit or export.

For the first release, implement either a clearly documented single-user local mode or simple local role-based access. Do not imply enterprise identity integration unless it is deliberately implemented and tested.

---

# 4. Navigation and information architecture

Use a persistent left navigation with clear nouns:

```text
Home
Imports
People
Roles & Release
Classes
Students & Cohorts
Rooms
School Cycle
Constraints
Scenarios
Timetable
Findings
AI Advisor
Exports
Settings
Audit
```

## Home dashboard

The home page should answer:

1. Which dataset am I working on?
2. Is the data healthy enough to plan?
3. What is incomplete?
4. What scenario is active?
5. What needs my attention?
6. What is safe to do next?

Suggested layout:

```text
┌──────────────────────────────────────────────────────────────────────┐
│ 2027 Planning Workspace                     Baseline v3 · Validated │
├──────────────────────┬──────────────────────┬────────────────────────┤
│ Data health          │ Staffing             │ Active scenario        │
│ 2 warnings           │ 4 load issues        │ Draft 2027 A           │
│ 0 blocking errors    │ 3 roles unassigned   │ Feasible, not approved │
├──────────────────────┴──────────────────────┴────────────────────────┤
│ Next steps                                                         │
│ 1. Confirm role release for 3 staff                                 │
│ 2. Resolve 2 room feature mappings                                  │
│ 3. Review 5 unallocated requirements                                │
├──────────────────────────────────────────────────────────────────────┤
│ [Continue planning] [Compare scenarios] [Run validation]            │
└──────────────────────────────────────────────────────────────────────┘
```

Use plain status language:

- Ready
- Needs review
- Blocking issue
- Draft
- Feasible
- Infeasible
- Validated
- Approved
- Exported

Do not rely on colour alone. Pair colour with an icon and text.

---

# 5. People, roles and release

This area must be exceptionally easy to use because staffing decisions are frequent and affect the whole timetable.

## 5.1 Teacher profile

A teacher profile should show:

```text
Teacher code
Display name
Employment fraction
Base teaching capacity
Current classes
Current teaching allocation
Role release
Other approved release
Net teaching capacity
Unallocated capacity or overload
Availability
Eligible subjects
Preferred subjects
Home faculty
Assigned roles
Source and last updated date
```

Display calculations clearly:

```text
Base capacity                2,400 min
Employment fraction × 0.8   1,920 min
Role release                  -120 min
Other release                  -60 min
Net teaching capacity        1,740 min
Allocated teaching           1,680 min
Remaining                       60 min
```

All time values should support minutes internally. The UI may additionally display periods where the cycle contains consistent period-load values.

## 5.2 Role templates

Create reusable role templates.

Examples are school-configured, not universal defaults:

- House Companion
- Head of House
- Curriculum Leader
- Year Level Leader
- Learning Support Coordinator
- Workplace Health and Safety role
- Timetabler
- Mentor
- College Leadership role

A role template contains:

```text
name
short code
category
role tier
scope type
release calculation method
default release value
default fixed commitments
whether it affects teaching capacity
whether multiple holders are allowed
valid date range
notes
source or approval reference
```

A scoped role supports values such as:

```text
Role: House Companion
Scope type: House
Scope value: Solis
Display label: House Companion - Solis
```

## 5.3 Assign-role wizard

The default role workflow should fit in one side panel or short wizard.

### Step 1: Select role

```text
Search roles...
○ House Companion
○ Curriculum Leader
○ Year Level Leader
○ Create a new role template
```

### Step 2: Select scope

For House Companion:

```text
House
[ Solis ▼ ]
```

### Step 3: Confirm entitlement

```text
Tier                 [ Tier 2 ▼ ]
Release method       [ Minutes per cycle ▼ ]
Release amount       [ 120 ] minutes
Fixed commitments    [ Friday FR, House meeting ]
Effective from       [ date ]
Effective to         [ date / ongoing ]
```

### Step 4: Preview effect

Show teaching capacity before and after, any overload, and affected scenarios.

### Step 5: Save

Offer:

- Save role assignment
- Save and update active draft scenario
- Save without changing existing scenarios

Never silently alter an approved scenario.

## 5.4 Flexible release rules

Support these methods:

- fixed minutes per cycle;
- fixed number of standard periods per cycle;
- percentage of full-time base load;
- percentage of the teacher's employment-adjusted load;
- explicit scheduled release periods;
- formula based on role tier;
- override for an individual assignment.

Recommended normalized calculation:

```python
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

class ReleaseMethod(StrEnum):
    MINUTES_PER_CYCLE = "MINUTES_PER_CYCLE"
    PERIODS_PER_CYCLE = "PERIODS_PER_CYCLE"
    PERCENT_BASE_LOAD = "PERCENT_BASE_LOAD"
    PERCENT_ADJUSTED_LOAD = "PERCENT_ADJUSTED_LOAD"
    EXPLICIT_SLOTS = "EXPLICIT_SLOTS"

@dataclass(frozen=True)
class LoadBreakdown:
    full_time_base_minutes: int
    employment_fraction: Decimal
    employment_adjusted_minutes: int
    role_release_minutes: int
    other_release_minutes: int
    net_teaching_capacity_minutes: int
    allocated_teaching_minutes: int


def calculate_load(
    full_time_base_minutes: int,
    employment_fraction: Decimal,
    role_release_minutes: int,
    other_release_minutes: int,
    allocated_teaching_minutes: int,
) -> LoadBreakdown:
    adjusted = int(
        (Decimal(full_time_base_minutes) * employment_fraction)
        .quantize(Decimal("1"))
    )
    net = max(0, adjusted - role_release_minutes - other_release_minutes)
    return LoadBreakdown(
        full_time_base_minutes=full_time_base_minutes,
        employment_fraction=employment_fraction,
        employment_adjusted_minutes=adjusted,
        role_release_minutes=role_release_minutes,
        other_release_minutes=other_release_minutes,
        net_teaching_capacity_minutes=net,
        allocated_teaching_minutes=allocated_teaching_minutes,
    )
```

The calculation service must be the one source of truth. The API, UI and solver must not implement separate formulas.

## 5.5 Proposed schema

```sql
CREATE TABLE role_template (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    scope_type TEXT,
    default_tier_id TEXT,
    affects_teaching_capacity INTEGER NOT NULL DEFAULT 1,
    allows_multiple_holders INTEGER NOT NULL DEFAULT 1,
    valid_from TEXT,
    valid_to TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (default_tier_id) REFERENCES role_tier(id)
);

CREATE TABLE role_tier (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    rank_order INTEGER NOT NULL,
    release_method TEXT NOT NULL,
    release_value TEXT NOT NULL,
    valid_from TEXT,
    valid_to TEXT,
    policy_source TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE teacher_role_assignment (
    id TEXT PRIMARY KEY,
    teacher_id INTEGER NOT NULL,
    role_template_id TEXT NOT NULL,
    role_tier_id TEXT,
    scope_key TEXT,
    scope_label TEXT,
    release_method TEXT NOT NULL,
    release_value TEXT NOT NULL,
    release_minutes_cache INTEGER NOT NULL,
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    status TEXT NOT NULL,
    source_snapshot_id TEXT,
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (teacher_id) REFERENCES teacher(id),
    FOREIGN KEY (role_template_id) REFERENCES role_template(id),
    FOREIGN KEY (role_tier_id) REFERENCES role_tier(id),
    FOREIGN KEY (source_snapshot_id) REFERENCES source_snapshot(id)
);

CREATE TABLE role_fixed_commitment (
    id TEXT PRIMARY KEY,
    role_assignment_id TEXT NOT NULL,
    period_id INTEGER NOT NULL,
    commitment_type TEXT NOT NULL,
    location_room_id INTEGER,
    is_hard_constraint INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (role_assignment_id) REFERENCES teacher_role_assignment(id),
    FOREIGN KEY (period_id) REFERENCES period(id),
    FOREIGN KEY (location_room_id) REFERENCES room(id)
);
```

Do not use floating-point types for fractions or policy values. Use decimal-safe representations.

## 5.6 Suggested API models

```python
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field, model_validator

class AssignRoleRequest(BaseModel):
    teacher_id: int
    role_template_id: str
    role_tier_id: str | None = None
    scope_key: str | None = None
    scope_label: str | None = None
    release_method: ReleaseMethod
    release_value: Decimal = Field(ge=0)
    effective_from: date
    effective_to: date | None = None
    update_draft_scenario_ids: list[str] = []

    @model_validator(mode="after")
    def validate_dates(self):
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot precede effective_from")
        return self

class RoleImpactPreview(BaseModel):
    teacher_id: int
    before: LoadBreakdown
    after: LoadBreakdown
    affected_scenario_ids: list[str]
    blocking_issues: list[str]
    warnings: list[str]
```

Recommended endpoints:

```text
GET    /api/people
GET    /api/people/{teacher_id}
GET    /api/people/{teacher_id}/load
GET    /api/roles/templates
POST   /api/roles/templates
POST   /api/roles/preview-assignment
POST   /api/roles/assignments
PATCH  /api/roles/assignments/{id}
DELETE /api/roles/assignments/{id}
GET    /api/roles/coverage
GET    /api/roles/release-summary
```

Deletion of a historical or scenario-referenced assignment should normally become archival or end-dating rather than physical deletion.

---

# 6. Teacher load and role-release rules

Use these definitions:

```text
full-time base load
× employment fraction
= employment-adjusted capacity
− role release
− approved additional release
− fixed non-teaching load counted by policy
= net teaching capacity
```

Keep these values separate:

- contractual capacity;
- role release entitlement;
- actual timetabled release periods;
- teaching allocated;
- duties and meetings;
- unallocated capacity;
- over-allocation.

A role release entitlement and an actual release slot are not the same thing. The solver must schedule the release where policy requires identifiable release periods, but a simple minute reduction may be sufficient for roles that only alter load capacity.

Validation examples:

- role release exceeds employment-adjusted capacity;
- overlapping role assignments for a role that permits one holder only;
- missing role scope;
- role tier not effective on assignment date;
- actual release periods below entitlement;
- teacher allocated above net capacity;
- teacher has adequate minutes but unacceptable daily concentration;
- approved role exists but no fixed role commitment is scheduled.

---

# 7. Planning-data setup wizard

Provide a guided setup checklist for each planning year or cycle.

```text
1. Import baseline data
2. Confirm school cycle and calendar
3. Confirm people and employment fractions
4. Assign roles and release
5. Confirm subjects and teaching requirements
6. Confirm rooms and specialist features
7. Confirm student groups and option blocks
8. Review constraints
9. Validate planning readiness
10. Create first scenario
```

Each step shows:

- Complete
- Needs review
- Blocking
- Optional

A user may leave and resume without losing work.

## Planning readiness screen

```text
Ready
✓ 74 teaching staff mapped
✓ 51 rooms mapped
✓ A/B cycle confirmed

Needs review
! 3 teachers have no employment fraction
! 2 role assignments have no release value
! 4 rooms have unknown capacity

Blocking
× 1 teaching requirement has no eligible teacher
× 2 option blocks have conflicting student memberships
```

Use active links to take the user directly to each issue.

---

# 8. Classes and teaching requirements

A timetable builder requires a first-class representation of what needs to be scheduled.

```python
@dataclass(frozen=True)
class TeachingRequirement:
    id: str
    class_name_id: int
    periods_per_cycle: int
    minutes_per_cycle: int
    allowed_duration_patterns: tuple[tuple[int, ...], ...]
    eligible_teacher_ids: tuple[int, ...]
    preferred_teacher_ids: tuple[int, ...]
    eligible_room_ids: tuple[int, ...]
    required_room_feature_codes: tuple[str, ...]
    student_group_ids: tuple[str, ...]
    parallel_block_id: str | None
    fixed_slot_ids: tuple[int, ...]
    unavailable_slot_ids: tuple[int, ...]
    spread_rule_code: str | None
```

Examples of duration patterns:

```text
Five singles:        (1, 1, 1, 1, 1)
Two doubles + single:(2, 2, 1)
Double + three:      (2, 1, 1, 1)
Flexible:            any validated combination totalling requirement
```

Class detail view:

```text
12 Modern History 1
Required: 5 periods per cycle
Pattern: one double preferred, remaining singles
Eligible teachers: 3
Preferred teacher: selected
Room: general classroom
Students: 18
Option line: 12 B
Current state: fully scheduled
```

Provide bulk editing for common values by faculty, year level or subject.

---

# 9. Rooms and facilities

Room setup should be visual and plain-language.

Room fields:

- code and name;
- capacity and whether capacity is confirmed;
- room category;
- building or zone;
- accessibility features;
- specialist features;
- availability;
- preferred faculties or subjects;
- restrictions;
- source identifier.

Example features:

```text
Science laboratory
Wet area
Food preparation
Workshop
Drama performance space
Music equipment
Computer devices
Accessible entry
Hearing augmentation
Flexible furniture
```

Do not infer safety suitability solely from free-text room notes. Allow a user to map imported notes to controlled features and confirm the mapping.

Room picker:

```text
[Search rooms]
Filter: Capacity ≥ 24 | Science lab | Available Tue A P3

✓ LEO2  Capacity 28  Science laboratory  Same zone
✓ LEO3  Capacity 30  Science laboratory  Same zone
! ANG4  Capacity 26  No confirmed wet area
× GRE1  Capacity 20  Too small
```

---

# 10. Constraint catalogue and editor

Constraints should be understandable without solver terminology.

Constraint card:

```text
Teacher unavailable
Teacher: [select]
When: [Tue A, P1]
Rule: Must not schedule
Reason: [optional category]
Effective: [planning year]
```

Advanced detail:

```text
Constraint ID: teacher_unavailable
Type: hard
Scope: teacher
Source: user-entered
Created by: local user
Affects: all draft scenarios created after this version
```

Support:

- individual constraints;
- reusable templates;
- bulk constraints;
- scenario-only constraints;
- effective dates;
- hard or soft classification;
- weight presets: low, medium, high;
- advanced numeric weight only in advanced mode.

Natural-language AI input may draft but not immediately save a constraint:

```text
User: Try not to give Jordan a Period 1 because of morning duties.

Interpreted draft
Teacher: Jordan [matched teacher code]
Constraint: Avoid Period 1
Days: all cycle days
Type: Soft
Priority: High

[Edit] [Apply to draft scenario] [Cancel]
```

---

# 11. Solver architecture

Prefer a deterministic constraint-programming approach such as OR-Tools CP-SAT, subject to repository review.

## 11.1 Assignment variables

For each requirement `r`, valid slot `s`, eligible teacher `t`, and eligible room `m`:

```python
x[r, s, t, m] = model.NewBoolVar(f"x_{r}_{s}_{t}_{m}")
```

Avoid creating impossible combinations. Pre-filter domains using eligibility, availability, room feature and capacity requirements.

## 11.2 Hard-constraint examples

```python
# A requirement receives the required number of lesson units.
for r in requirements:
    model.Add(
        sum(x[key] for key in keys_for_requirement[r.id])
        == r.periods_per_cycle
    )

# A teacher cannot teach two unrelated physical lessons in one slot.
for teacher_id, slot_id in teacher_slot_pairs:
    model.Add(
        sum(x[key] for key in keys_for_teacher_slot[teacher_id, slot_id]) <= 1
    )

# A room cannot host two unrelated physical lessons in one slot.
for room_id, slot_id in room_slot_pairs:
    model.Add(
        sum(x[key] for key in keys_for_room_slot[room_id, slot_id]) <= 1
    )
```

Approved composite classes must not be implemented as a casual exception to `<= 1`. Model their shared physical lesson deliberately, such as a composite physical-lesson entity containing multiple official class requirements.

## 11.3 Soft-constraint penalties

```python
penalties = []

# Example: discourage first-period allocations for a teacher.
for key in avoid_first_period_keys:
    penalty = model.NewBoolVar(f"avoid_p1_{key}")
    model.Add(penalty == x[key])
    penalties.append((penalty, configured_weight))

model.Minimize(sum(var * weight for var, weight in penalties))
```

The production objective should be separated into named score categories. Persist category totals and raw measures.

## 11.4 Solve request

```python
class SolveScenarioRequest(BaseModel):
    max_solver_seconds: int = Field(default=60, ge=1, le=3600)
    random_seed: int = 1
    objective_profile_id: str
    preserve_locked_assignments: bool = True
    explain_infeasibility: bool = True
```

Do not present runtime defaults as school policy. They are operational configuration.

## 11.5 Infeasibility

When no feasible solution exists:

- do not return an empty timetable as if it were successful;
- identify unallocated requirements;
- report the constraints most closely associated with the conflict where supported;
- produce plain-language explanations based on structured evidence;
- propose only explicit, reviewable relaxations of soft constraints;
- never automatically relax hard constraints.

---

# 12. Scenario workspace

Use a three-panel layout:

```text
┌────────────────────┬──────────────────────────────┬──────────────────┐
│ Filters            │ Timetable grid               │ Inspector        │
│                    │                              │                  │
│ Teacher            │ Mon A Tue A Wed A...         │ Selected lesson  │
│ Room               │ P1                           │ Constraints      │
│ Class              │ P2                           │ Valid moves      │
│ Year               │ ...                          │ Score impact     │
│ Findings           │                              │ Change history   │
└────────────────────┴──────────────────────────────┴──────────────────┘
```

Features:

- teacher, room, class, year level and cohort views;
- search by code or name;
- drag and drop with validation preview;
- lock an assignment;
- multi-select compatible lessons;
- undo and redo;
- before-and-after view;
- conflict overlays;
- display composite groups as one physical lesson with multiple official codes;
- quick access to teacher load and room availability;
- keyboard-accessible editing alternatives.

## Cell appearance

A timetable cell should show:

```text
12MHI1
Teacher code
Room code
18 students
```

Use badges for:

- Locked
- Composite
- Changed
- Warning
- Conflict
- AI suggestion

Do not expose student names in the general grid.

---

# 13. Local AI advisor

The AI advisor should be task-focused rather than a generic chat window.

Suggested quick actions:

```text
Explain this conflict
Find valid alternatives
Compare selected scenarios
Summarise teacher load issues
Draft a constraint
Explain the score
Prepare an export summary
```

## Tool-like internal contract

```python
class AdvisorActionType(StrEnum):
    EXPLAIN_FINDING = "EXPLAIN_FINDING"
    DRAFT_CONSTRAINT = "DRAFT_CONSTRAINT"
    REQUEST_VALID_MOVES = "REQUEST_VALID_MOVES"
    COMPARE_SCENARIOS = "COMPARE_SCENARIOS"
    SUMMARISE_SCORE = "SUMMARISE_SCORE"

class AdvisorRequest(BaseModel):
    action_type: AdvisorActionType
    scenario_id: str
    entity_refs: list[dict]
    finding_ids: list[str] = []
    user_instruction: str

class AdvisorProposal(BaseModel):
    interpreted_instruction: str
    structured_action: dict | None
    evidence_finding_ids: list[str]
    referenced_entity_ids: list[str]
    deterministic_validation_status: str
    warnings: list[str]
```

Before showing a proposal:

1. parse model output as structured JSON;
2. reject invalid fields;
3. verify every entity ID exists;
4. run deterministic validation;
5. attach finding evidence;
6. show Apply, Modify and Reject controls.

The model should receive codes and aggregates wherever names are unnecessary.

---

# 14. Imports and mappings

Continue using the actual discovered source files as ground truth.

Import wizard stages:

```text
Choose files
→ Detect formats
→ Parse safely
→ Map identifiers
→ Compare sources
→ Review discrepancies
→ Create immutable snapshot
```

An import issue should use a safe structure:

```python
class ImportIssue(BaseModel):
    severity: Literal["INFO", "WARNING", "BLOCKING"]
    file_name: str
    record_index: int | None
    field_name: str | None
    source_identifier: str | None
    issue_code: str
    message: str
```

Do not include a person's name or email in an error when a row number and source ID are sufficient.

Provide mapping screens for:

- teacher identity;
- room code;
- subject/class code;
- period and cycle day;
- role code;
- employment fraction;
- room feature;
- unknown source field.

Mappings should be saved as versioned configuration and reused only when the new source is compatible.

---

# 15. Calendar and A/B cycle

Do not derive the school cycle solely from odd/even ISO weeks.

Create explicit date mapping:

```sql
CREATE TABLE school_calendar_day (
    calendar_date TEXT PRIMARY KEY,
    cycle_day_id INTEGER,
    is_teaching_day INTEGER NOT NULL,
    day_status TEXT NOT NULL,
    note TEXT,
    FOREIGN KEY (cycle_day_id) REFERENCES day(id)
);
```

Calendar UI:

- start with a proposed A/B sequence;
- allow holidays and pupil-free days to be marked;
- allow an interrupted cycle to continue or reset according to the school's decision;
- show the mapped cycle day on every teaching date;
- keep the timetable cycle separate from calendar dates.

---

# 16. Findings and validation

Use one shared finding model for imported-data issues, timetable violations and planning warnings.

```python
class FindingSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    BLOCKING = "BLOCKING"

class Finding(BaseModel):
    id: str
    scenario_id: str | None
    rule_id: str
    severity: FindingSeverity
    title: str
    entity_refs: list[dict]
    slot_refs: list[dict]
    evidence: dict
    proposed_action_ids: list[str] = []
    status: Literal["OPEN", "ACKNOWLEDGED", "RESOLVED", "ACCEPTED_RISK"]
```

Initial rules:

- teacher double booking;
- room double booking;
- student double booking;
- incomplete teaching requirement;
- ineligible teacher;
- teacher unavailable;
- room unavailable;
- insufficient room capacity;
- missing room feature;
- teacher over net capacity;
- role release not represented;
- excessive consecutive load;
- fragmented release/non-contact time;
- uneven subject spread;
- excessive room movement;
- unconfirmed composite candidate;
- fixed-event displacement;
- unresolved source mapping.

Every rule needs a plain-language definition, evidence fields, exclusions and synthetic tests.

---

# 17. Export and BCE interoperability

The program should treat Timetabling Solutions as the verified interchange point unless a downstream BCE format has separately been examined and validated.

Export workflow:

```text
Approved scenario
→ validate hard constraints
→ validate identifiers and referential integrity
→ generate candidate file
→ parse generated file again
→ compare reconstructed timetable to approved scenario
→ generate changelog and validation report
→ human download
→ trial import into copied/non-production Timetabling Solutions data
→ verified Timetabling Solutions workflow
→ established BCE/eMinerva exports
```

Export package:

```text
scenario-name_timestamp.tfx
scenario-name_timestamp_changelog.csv
scenario-name_timestamp_validation.json
scenario-name_timestamp_summary.html
```

Do not modify source files. Keep export behind an experimental flag until repeated round-trip tests and non-production import checks pass.

---

# 18. Audit and versioning

Create append-only audit events.

```sql
CREATE TABLE audit_event (
    id TEXT PRIMARY KEY,
    occurred_at TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    scenario_id TEXT,
    summary TEXT NOT NULL,
    before_json TEXT,
    after_json TEXT,
    source_snapshot_id TEXT
);
```

Audit events should include:

- import completed;
- mapping changed;
- employment fraction changed;
- role assigned or ended;
- release adjusted;
- constraint created or changed;
- scenario created;
- solve started and completed;
- assignment locked or moved;
- scenario validated;
- scenario approved;
- export generated.

Redact unnecessary PII from audit payloads.

---

# 19. Settings and school configuration

Settings sections:

```text
School identity
Planning year
Cycle and calendar
Load policies
Role tiers
Role templates
Faculties and subjects
Room features
Constraint defaults
Solver profiles
Local AI model
Data directories
Retention and purge
Experimental exports
```

Each policy setting should contain:

- value;
- unit;
- effective date;
- source/approval note;
- last changed date;
- impact preview where applicable.

Provide safe defaults only where the value is technical, not policy-based.

---

# 20. Accessibility and usability requirements

- Meet keyboard-navigation expectations for all major workflows.
- Do not make drag and drop the only editing method.
- Use labels as well as icons.
- Use plain language before technical terminology.
- Provide immediate field validation.
- Keep destructive actions rare and reversible.
- Preserve filters and selected scenario while navigating.
- Provide global search for teachers, classes, rooms and scenarios.
- Use consistent Save, Preview, Validate, Approve and Export verbs.
- Never label a draft as published or final.
- Warn before leaving unsaved configuration.
- Provide first-run sample mode using synthetic data.
- Ensure tables can be filtered, sorted and exported where appropriate.

---

# 21. Suggested frontend component structure

```text
frontend/src/
  app/
    routes.tsx
    shell/
  features/
    imports/
    people/
      PeopleList.tsx
      TeacherProfile.tsx
      TeacherLoadCard.tsx
    roles/
      RoleTemplateList.tsx
      AssignRoleDrawer.tsx
      RoleImpactPreview.tsx
      ReleaseSummary.tsx
    classes/
    rooms/
    constraints/
    scenarios/
      ScenarioWorkspace.tsx
      ScenarioCompare.tsx
      SolvePanel.tsx
    timetable/
      TimetableGrid.tsx
      AssignmentInspector.tsx
      MovePreview.tsx
    findings/
    advisor/
    exports/
    settings/
  components/
    StatusBadge.tsx
    EntityPicker.tsx
    ConfirmedValue.tsx
    ImpactSummary.tsx
    EmptyState.tsx
```

Example role drawer interface:

```tsx
export function AssignRoleDrawer({ teacher, templates, onPreview, onSave }) {
  const [roleId, setRoleId] = useState("");
  const [scope, setScope] = useState("");
  const [tierId, setTierId] = useState("");
  const [release, setRelease] = useState("0");
  const [impact, setImpact] = useState(null);

  async function preview() {
    const result = await onPreview({
      teacher_id: teacher.id,
      role_template_id: roleId,
      scope_key: scope,
      role_tier_id: tierId,
      release_method: "MINUTES_PER_CYCLE",
      release_value: release,
    });
    setImpact(result);
  }

  return (
    <section aria-labelledby="assign-role-title" className="space-y-6">
      <header>
        <h2 id="assign-role-title" className="text-xl font-semibold">
          Add a role for {teacher.displayName}
        </h2>
        <p className="text-sm text-slate-600">
          The impact on teaching capacity will be shown before saving.
        </p>
      </header>

      <EntityPicker label="Role" value={roleId} onChange={setRoleId} items={templates} />
      <EntityPicker label="Scope" value={scope} onChange={setScope} items={getScopes(roleId)} />
      <EntityPicker label="Tier" value={tierId} onChange={setTierId} items={getTiers(roleId)} />

      <label className="block">
        <span className="text-sm font-medium">Release per cycle, minutes</span>
        <input
          type="number"
          min="0"
          value={release}
          onChange={(event) => setRelease(event.target.value)}
          className="mt-1 w-full rounded-lg border p-2"
        />
      </label>

      <button type="button" onClick={preview}>Preview impact</button>
      {impact && <RoleImpactPreview impact={impact} />}
      <button type="button" disabled={!impact?.canSave} onClick={() => onSave(impact.request)}>
        Save role assignment
      </button>
    </section>
  );
}
```

Treat this as illustrative code. Adapt it to the repository's established component, state-management and API patterns.

---

# 22. Backend service boundaries

```text
backend/app/
  imports/
  snapshots/
  people/
  roles/
  load/
  requirements/
  rooms/
  calendar/
  constraints/
  composites/
  scenarios/
  solver/
  findings/
  advisor/
  validation/
  export/
  audit/
```

Key services:

```python
class RoleService:
    def preview_assignment(self, request: AssignRoleRequest) -> RoleImpactPreview: ...
    def assign(self, request: AssignRoleRequest, actor_id: str): ...
    def end_assignment(self, assignment_id: str, end_date: date, actor_id: str): ...

class LoadService:
    def calculate_teacher_load(self, teacher_id: int, as_of: date) -> LoadBreakdown: ...
    def calculate_scenario_load(self, scenario_id: str, teacher_id: int) -> LoadBreakdown: ...

class ScenarioService:
    def create_from_snapshot(self, snapshot_id: str, name: str): ...
    def apply_validated_change(self, scenario_id: str, change_id: str): ...
    def compare(self, left_id: str, right_id: str): ...

class SolverService:
    def solve(self, scenario_id: str, request: SolveScenarioRequest): ...

class ExportService:
    def validate(self, scenario_id: str): ...
    def generate_candidate(self, scenario_id: str): ...
```

Use database transactions around each user action that changes multiple records. Write the audit event in the same transaction where possible.

---

# 23. Testing requirements

## Role and release tests

- assign a scoped role such as House Companion - Solis;
- tier default populates release;
- user override is recorded distinctly;
- employment fraction affects net capacity;
- overlapping effective dates are validated;
- role with required scope cannot be saved without scope;
- ending a role restores capacity for later effective dates;
- approved scenarios are not silently updated;
- draft scenario receives an explicit refresh proposal;
- decimal calculation is stable;
- policy version effective dates are respected.

## Solver tests

- feasible synthetic timetable;
- infeasible teacher availability;
- unavailable room;
- capacity failure;
- specialist feature failure;
- role release reducing teacher capacity;
- fixed role commitment;
- approved composite physical lesson;
- rejected composite candidate remains a clash;
- interrupted A/B calendar;
- deterministic result with fixed seed;
- time-limited solver retains valid best solution;
- no hard constraint is silently relaxed.

## Export tests

- source file remains byte-for-byte unchanged;
- generated file can be re-parsed;
- reconstructed assignments equal approved scenario;
- unchanged records retain source IDs;
- only approved changes appear in changelog;
- export blocked for unvalidated scenario;
- export blocked for unresolved hard violation.

## Privacy tests

- no names or emails in solver logs;
- no real data in fixtures;
- error report uses source IDs and row numbers;
- AI payload builder removes unnecessary identifying fields;
- support bundle redacts configured fields.

---

# 24. Seed configuration example

Provide a development-only synthetic seed, clearly labelled as illustrative:

```json
{
  "roleTiers": [
    {
      "code": "TIER_1",
      "name": "Tier 1",
      "releaseMethod": "MINUTES_PER_CYCLE",
      "releaseValue": "60"
    },
    {
      "code": "TIER_2",
      "name": "Tier 2",
      "releaseMethod": "MINUTES_PER_CYCLE",
      "releaseValue": "120"
    }
  ],
  "roleTemplates": [
    {
      "code": "HOUSE_COMPANION",
      "name": "House Companion",
      "scopeType": "HOUSE",
      "defaultTierCode": "TIER_2",
      "affectsTeachingCapacity": true
    }
  ],
  "scopes": {
    "HOUSE": [
      { "key": "HOUSE_A", "label": "Example House A" },
      { "key": "HOUSE_B", "label": "Example House B" }
    ]
  }
}
```

Do not put actual policy release values into a synthetic seed unless confirmed and deliberately entered by an authorised user.

---

# 25. Delivery phases

## Phase 1: UX and configuration foundation

- application shell and navigation;
- planning workspace selector;
- People area;
- role templates and tiers;
- assign-role wizard;
- load preview and calculation service;
- audit records;
- synthetic fixtures and tests.

## Phase 2: Construction-ready model

- source snapshots;
- teaching requirements;
- availability;
- controlled room features;
- class patterns;
- scenario overlays;
- planning readiness validator.

## Phase 3: Constraint engine

- shared finding model;
- hard validation rules;
- soft constraints and weights;
- constraint editor;
- composite approval workflow.

## Phase 4: Solver proof of concept

- OR-Tools adapter;
- feasible synthetic build;
- infeasibility reporting;
- transparent score categories;
- deterministic regression tests.

## Phase 5: Scenario workspace

- timetable grid editing;
- locks;
- validated moves;
- undo/redo;
- scenario compare;
- approval state machine.

## Phase 6: Local AI advisor

- constrained action types;
- structured output validation;
- entity verification;
- explanation and comparison;
- draft constraint workflow;
- privacy-safe payload tests.

## Phase 7: Interchange

- candidate `.tfx` writer based on discovered source version;
- round-trip validation;
- changelog and report;
- experimental export flag;
- documented non-production import verification.

## Phase 8: Operational hardening

- backup and recovery;
- retention and purge;
- accessibility review;
- performance testing;
- redacted support bundle;
- user guide;
- verified operational procedure for downstream systems.

---

# 26. Claude Code first task

Read the current repository before changing code, including the existing project brief, README, format discovery, data model, schema, ingestion code, API, frontend and composite detection.

Then create these documents first:

```text
docs/product-scope.md
docs/ux-workflows.md
docs/role-release-model.md
docs/construction-gap-analysis.md
docs/constraint-catalogue.md
docs/privacy-threat-model.md
docs/export-validation.md
```

Next, produce a proposed migration and implementation plan for **Phase 1 only**.

Phase 1 must deliver a complete vertical slice:

```text
Open People
→ select a teacher
→ view current load
→ add House Companion role
→ select a house scope
→ select/configure Tier 2
→ preview release impact
→ save assignment
→ view updated load
→ see an audit event
→ see any affected draft-scenario warning
```

Use synthetic test data. Do not modify live source exports. Do not guess Sophia College policy values. Where the repository does not contain a confirmed value, make it configurable and label it as requiring confirmation.

Before implementing a new framework or replacing existing code, explain why the current repository pattern cannot support the requirement.

---

# 27. Definition of done for the intuitive role workflow

The role workflow is complete when an authorised user can:

- find a teacher quickly;
- understand the teacher's capacity without calculating it manually;
- add a scoped role in a short guided flow;
- see a human-readable label such as `House Companion - Solis`;
- select a tier and see its source and release entitlement;
- override release only with an explicit reason;
- preview the load and scenario effect before saving;
- save without changing an approved scenario;
- undo or end-date the assignment;
- see the calculation and audit history;
- use the same data in validation and solver runs;
- complete the workflow using keyboard controls;
- receive clear, actionable validation messages.

---

# 28. Final product test

A successful product should allow a school leader to say:

> Select this teacher. Give them House Companion - Solis at Tier 2. Show the release. Tell me whether they are overloaded. Apply it to my 2027 draft. Rebuild only what is affected. Explain the difference. Let me approve the result. Export a candidate that Timetabling Solutions can verify.

The application should guide that process through explicit, reversible and validated steps, without requiring the user to understand solver syntax or source-file internals.
