# Claude Code Addendum: Staff Teaching Capability, Preferences and Allocation Priority

## Purpose

Extend the complementary timetabling product so that each staff member has a transparent, configurable teaching-capability profile. The timetable builder must use this profile when assigning classes, repairing clashes and identifying valid cover options.

The system must distinguish carefully between:

1. **Can teach**: the staff member is approved as eligible for the subject and year range.
2. **Preferred to teach**: the staff member is a preferred allocation, but alternatives remain valid.
3. **Must teach**: the class has an approved fixed or strongly protected teacher assignment.
4. **Should not normally teach**: technically possible, but only used as a last resort and clearly flagged.
5. **Cannot teach**: not eligible and must never be allocated by the solver.

Do not infer teaching capability from a teacher's current timetable alone. Current allocations may be used as evidence for review, but capability must be confirmed or imported from an authoritative source.

---

## 1. Intended user experience

### Teacher profile example

```text
Matt Hurley

Teaching capacity
Net teaching capacity: 1,740 minutes per cycle
Currently allocated: 1,680 minutes
Remaining: 60 minutes

Subject capability
✓ Modern History       Years 11–12   Must/preferred allocation
✓ History              Years 7–10    Preferred
✓ Religion             Years 7–12    Preferred
✓ Mathematics          Years 7–10    Eligible
○ Mathematics          Years 11–12   Not eligible

Roles and release
House Companion - Solis
Tier 2
Release: configured value

Preferences
Prefer senior Modern History
Prefer at least one junior History class
Avoid more than three consecutive teaching periods

[Edit capabilities] [Add preference] [View timetable]
```

The example labels and values are illustrative. Do not insert them as factual staff records without authorised confirmation.

### Capability editor

The simplest interaction should be:

```text
People → Select teacher → Teaching capability → Add subject
```

Then:

```text
Subject area       [ Mathematics ▼ ]
Curriculum/course  [ All junior Mathematics ▼ ]
Year range         [ Year 7 ] to [ Year 10 ]
Capability         [ Eligible ▼ ]
Preference         [ Normal ▼ ]
Evidence/source    [ School-confirmed ▼ ]
Effective from     [ 2027 planning year ▼ ]
Notes              [ optional ]
```

For a specialist allocation:

```text
Subject/course     Modern History
Year range         Years 11–12
Capability         Eligible
Allocation status  Required teacher for selected class
Teacher            Matt Hurley
Class              11 Modern History 1
Reason/source      Approved staffing decision
```

Before saving, preview affected scenarios and any classes that gain or lose eligible teachers.

---

## 2. Capability hierarchy

Use a hierarchy that supports broad subject areas and precise course-level exceptions.

```text
Learning area
  → subject
      → course/version
          → year range
              → specific class offering
```

Example:

```text
Humanities
  → History
      → Modern History
          → Years 11–12

Mathematics
  → Mathematics
      → Junior Mathematics
          → Years 7–10
```

A broad rule may be narrowed by a more specific rule. The most specific active rule wins.

Example:

```text
Teacher is eligible for Mathematics Years 7–10.
Teacher is not eligible for Year 10 Extension Mathematics.
```

The course-specific exclusion overrides the broad junior Mathematics eligibility for that course only.

---

## 3. Allocation statuses

Create explicit enums rather than one ambiguous preference score.

```python
from enum import StrEnum

class CapabilityStatus(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"

class AllocationPreference(StrEnum):
    REQUIRED = "REQUIRED"
    STRONGLY_PREFERRED = "STRONGLY_PREFERRED"
    PREFERRED = "PREFERRED"
    NEUTRAL = "NEUTRAL"
    FALLBACK = "FALLBACK"
    AVOID = "AVOID"

class CapabilitySource(StrEnum):
    IMPORTED = "IMPORTED"
    SCHOOL_CONFIRMED = "SCHOOL_CONFIRMED"
    STAFF_DECLARED = "STAFF_DECLARED"
    CURRENT_TIMETABLE_INFERRED = "CURRENT_TIMETABLE_INFERRED"
```

`CURRENT_TIMETABLE_INFERRED` must always create `REVIEW_REQUIRED`, never automatic eligibility.

### Meaning

- `REQUIRED`: hard assignment for a specific requirement or class, subject to availability and feasibility validation.
- `STRONGLY_PREFERRED`: high-weight soft preference.
- `PREFERRED`: ordinary soft preference.
- `NEUTRAL`: valid allocation without preference.
- `FALLBACK`: valid but used after better matches.
- `AVOID`: valid only if required for feasibility, with a visible warning.
- `NOT_ELIGIBLE`: hard exclusion.

Do not represent “Matt is the Modern History teacher” merely as a high numerical weight if it is an approved fixed staffing decision. Model it as a requirement-level teacher lock or `REQUIRED` allocation.

---

## 4. Proposed schema

```sql
CREATE TABLE subject_area (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    parent_id TEXT,
    source_guid TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (parent_id) REFERENCES subject_area(id)
);

CREATE TABLE curriculum_course (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    subject_area_id TEXT NOT NULL,
    minimum_year_level INTEGER,
    maximum_year_level INTEGER,
    source_guid TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (subject_area_id) REFERENCES subject_area(id)
);

CREATE TABLE teacher_capability (
    id TEXT PRIMARY KEY,
    teacher_id INTEGER NOT NULL,
    subject_area_id TEXT,
    curriculum_course_id TEXT,
    minimum_year_level INTEGER,
    maximum_year_level INTEGER,
    capability_status TEXT NOT NULL,
    default_preference TEXT NOT NULL DEFAULT 'NEUTRAL',
    source_type TEXT NOT NULL,
    source_reference TEXT,
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    review_status TEXT NOT NULL DEFAULT 'CONFIRMED',
    notes TEXT,
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (teacher_id) REFERENCES teacher(id),
    FOREIGN KEY (subject_area_id) REFERENCES subject_area(id),
    FOREIGN KEY (curriculum_course_id) REFERENCES curriculum_course(id),
    CHECK (subject_area_id IS NOT NULL OR curriculum_course_id IS NOT NULL),
    CHECK (minimum_year_level IS NULL OR maximum_year_level IS NULL OR minimum_year_level <= maximum_year_level)
);

CREATE TABLE requirement_teacher_preference (
    id TEXT PRIMARY KEY,
    teaching_requirement_id TEXT NOT NULL,
    teacher_id INTEGER NOT NULL,
    preference TEXT NOT NULL,
    priority_order INTEGER,
    reason TEXT,
    source_reference TEXT,
    is_locked INTEGER NOT NULL DEFAULT 0,
    effective_from TEXT,
    effective_to TEXT,
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    FOREIGN KEY (teaching_requirement_id) REFERENCES teaching_requirement(id),
    FOREIGN KEY (teacher_id) REFERENCES teacher(id)
);
```

Add uniqueness rules through migrations after reviewing the existing database conventions. Prevent duplicate active capability rules with the same teacher, subject/course, year range and effective period.

---

## 5. Capability resolution service

Create one service used by the UI, validator and solver.

```python
from dataclasses import dataclass
from datetime import date

@dataclass(frozen=True)
class CapabilityDecision:
    teacher_id: int
    requirement_id: str
    eligible: bool
    preference: AllocationPreference | None
    matched_rule_id: str | None
    specificity: int
    reasons: tuple[str, ...]
    review_required: bool = False

class CapabilityService:
    def resolve(
        self,
        teacher_id: int,
        requirement_id: str,
        as_of: date,
    ) -> CapabilityDecision:
        """Resolve the most specific active capability and preference.

        Precedence:
        1. requirement-specific locked assignment;
        2. requirement-specific teacher preference;
        3. exact curriculum course and year;
        4. subject and year-range rule;
        5. parent learning-area rule;
        6. no match means not eligible until reviewed.
        """
        ...
```

Do not duplicate this resolution logic in SQL queries, API handlers, frontend code and solver adapters.

### Resolution rules

1. Ignore expired or not-yet-effective records.
2. A requirement-level locked teacher takes precedence.
3. An exact course rule takes precedence over a broad subject rule.
4. A narrower year range takes precedence over a wider range.
5. `NOT_ELIGIBLE` at equal specificity overrides eligibility.
6. Conflicting equally specific rules create a blocking data-quality finding.
7. No confirmed matching capability means the teacher is not solver-eligible.
8. An inferred capability requires human confirmation before solver use.

---

## 6. Preferred senior teachers and allocation order

Do not implement “build Years 11 and 12 first” only as procedural code. Represent allocation importance in the planning model so it remains transparent and configurable.

Add to `TeachingRequirement`:

```text
allocation_priority
curriculum_criticality
teacher_continuity_priority
scarcity_score
lock_status
```

Suggested priority bands:

```python
class RequirementPriority(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    STANDARD = "STANDARD"
    FLEXIBLE = "FLEXIBLE"
```

Possible school-configured default profile:

```text
1. Locked or required teacher allocations
2. Senior specialist subjects with few eligible teachers
3. Other Year 11–12 subjects
4. Subjects requiring specialist rooms
5. Junior subjects with limited eligible teachers
6. Junior subjects with a broad eligible-teacher pool
```

This is a suggested model, not a factual Sophia College policy. Make it editable and show the active profile before solving.

### Important technical distinction

A CP-SAT solver does not need to literally allocate senior classes first to protect them. Better options are:

- hard-lock approved teacher/class pairs;
- apply high penalties when strong senior preferences are not met;
- calculate teacher scarcity and protect scarce capability;
- use decision strategies or staged solving only where testing shows value;
- preserve full feasibility across all requirements.

A staged workflow may still be useful for user understanding:

```text
Stage 1: Lock approved staffing decisions
Stage 2: Protect scarce senior/specialist capability
Stage 3: Allocate remaining senior requirements
Stage 4: Allocate junior and flexible requirements
Stage 5: Improve load, spread, room stability and movement
```

However, after each stage, run a whole-model feasibility check. Do not create early allocations that make the remaining timetable impossible.

---

## 7. Scarcity-aware allocation

The solver should recognise that some staff capabilities are scarce.

For each requirement:

```python
def eligible_teachers(requirement, teachers, capability_service, as_of):
    return [
        teacher
        for teacher in teachers
        if capability_service.resolve(
            teacher.id, requirement.id, as_of
        ).eligible
    ]
```

Calculate a planning indicator:

```python
@dataclass(frozen=True)
class RequirementStaffingHealth:
    requirement_id: str
    eligible_teacher_count: int
    available_teacher_count: int
    preferred_teacher_count: int
    remaining_capacity_minutes: int
    risk: str
```

Do not treat raw eligible-teacher count as sufficient. A teacher may be eligible but unavailable or have no remaining load capacity.

Suggested risk labels:

- `BLOCKING`: no eligible and available teacher;
- `HIGH`: only one feasible teacher;
- `MEDIUM`: limited feasible pool;
- `HEALTHY`: multiple feasible options.

Thresholds must be configurable or derived transparently, not hidden constants.

### Preserve scarce teachers

If only one or two staff can teach a senior specialist course, avoid consuming their capacity on classes that many other staff can teach unless required.

Illustrative objective term:

```python
# Higher opportunity cost when assigning a scarce-capability teacher
# to a broadly teachable requirement.
for assignment in candidate_assignments:
    opportunity_cost = calculate_opportunity_cost(
        teacher_id=assignment.teacher_id,
        requirement_id=assignment.requirement_id,
        staffing_health=staffing_health,
    )
    objective_terms.append(assignment.variable * opportunity_cost)
```

Document the formula and expose its effect in the scenario scorecard.

---

## 8. Solver integration

Pre-filter assignment variables to confirmed eligible teachers.

```python
for requirement in requirements:
    decisions = {
        teacher.id: capability_service.resolve(
            teacher.id,
            requirement.id,
            planning_date,
        )
        for teacher in teachers
    }

    valid_teachers = [
        teacher_id
        for teacher_id, decision in decisions.items()
        if decision.eligible and not decision.review_required
    ]

    if not valid_teachers:
        findings.append(
            Finding.blocking(
                rule_id="requirement_has_no_eligible_teacher",
                entity_refs=[{"type": "requirement", "id": requirement.id}],
                evidence={"review_required_candidates": [
                    teacher_id
                    for teacher_id, decision in decisions.items()
                    if decision.review_required
                ]},
            )
        )
        continue
```

### Required teacher

```python
required_preferences = [
    p for p in preferences
    if p.requirement_id == requirement.id
    and p.preference == AllocationPreference.REQUIRED
]

if len(required_preferences) > 1 and not requirement.is_team_taught:
    raise ConfigurationError(
        f"Requirement {requirement.id} has multiple required teachers"
    )
```

For a valid required teacher:

```python
model.Add(
    sum(
        variable
        for key, variable in assignment_vars.items()
        if key.requirement_id == requirement.id
        and key.teacher_id == required_teacher_id
    ) == requirement.periods_per_cycle
)
```

### Preferred teachers

```python
PREFERENCE_PENALTY = {
    AllocationPreference.STRONGLY_PREFERRED: 0,
    AllocationPreference.PREFERRED: 10,
    AllocationPreference.NEUTRAL: 30,
    AllocationPreference.FALLBACK: 80,
    AllocationPreference.AVOID: 200,
}

for key, variable in assignment_vars.items():
    decision = decisions_by_key[key]
    penalty = PREFERENCE_PENALTY[decision.preference]
    objective_terms.append(variable * penalty)
```

These numbers are illustrative only. Store objective values in a versioned solver profile and allow advanced users to inspect them.

---

## 9. Class staffing screen

Add a staffing view by class/requirement:

```text
11 Modern History 1
5 periods per cycle · Senior specialist

Required teacher
Matt Hurley                              [Locked]

Other eligible teachers
Teacher B       Eligible, fallback       120 min remaining
Teacher C       Review required          capability inferred

Staffing health
Preferred staff available: Yes
Risk: Medium
Reason: One confirmed preferred teacher

[Edit staffing] [Unlock] [View capability evidence]
```

For a junior class:

```text
Year 7 Mathematics 3
5 periods per cycle

Candidate teachers
✓ Teacher A   Preferred       180 min remaining
✓ Matt Hurley Eligible        60 min remaining
✓ Teacher B   Neutral         240 min remaining
× Teacher C   Not eligible

Suggested allocation
Teacher A
Reason: preferred, sufficient capacity, no senior-specialist opportunity cost
```

The reason must come from structured rules, not invented AI text.

---

## 10. Bulk capability management

Provide three modes.

### By teacher

Select a teacher and add multiple subject/year capabilities.

### By subject

Select `Junior Mathematics` and tick all approved staff members.

### Matrix

```text
                 Y7 Maths  Y8 Maths  Y9 Maths  Y10 Maths  Modern History
Matt Hurley         ✓         ✓         ✓          ✓            ★
Teacher B           ✓         ✓         ✓          ✓            ○
Teacher C           ✓         ✓         ○          ○            ×
```

Legend:

- `★` required/strongly preferred;
- `✓` eligible;
- `○` review required or fallback, distinguish with text and accessible labels;
- `×` not eligible.

The matrix needs keyboard-accessible controls and must not depend on symbols or colour alone.

### Import/export configuration

Allow capability configuration to be exported and imported as a separate local planning file using source IDs/codes. Validate every teacher and course reference. Do not place actual staff data in repository fixtures.

---

## 11. AI-assisted capability review

The local AI may help organise confirmed information but must not decide professional capability.

Acceptable:

```text
Show teachers confirmed for junior Mathematics.
Which unallocated classes have only one eligible teacher?
Draft a capability entry for review based on this authorised staffing list.
Explain why Matt was not selected for Year 7 Mathematics 3.
```

Not acceptable:

```text
Infer who is good at Mathematics from emails.
Rank teachers by teaching quality.
Decide who should teach senior classes based on perceived performance.
```

Capability and preference are administrative planning data entered or confirmed by authorised staff, not performance judgements generated by AI.

Every AI-drafted capability must remain `REVIEW_REQUIRED` until confirmed.

---

## 12. Findings

Add these deterministic findings:

```text
requirement_has_no_eligible_teacher
requirement_has_no_available_eligible_teacher
capability_rule_conflict
capability_requires_review
required_teacher_unavailable
required_teacher_over_capacity
multiple_required_teachers
senior_specialist_not_preferred
scarce_teacher_used_for_flexible_requirement
teacher_assigned_outside_year_range
teacher_assigned_to_ineligible_course
preference_not_met
capability_expiring_during_planning_period
```

Each finding must include:

- requirement ID;
- teacher IDs where relevant;
- matched capability rule IDs;
- availability/load evidence;
- hard or soft status;
- suggested review action;
- no unnecessary names or emails in stored evidence.

---

## 13. API additions

```text
GET    /api/subject-areas
GET    /api/courses
GET    /api/people/{teacher_id}/capabilities
POST   /api/people/{teacher_id}/capabilities
PATCH  /api/capabilities/{id}
POST   /api/capabilities/{id}/confirm
POST   /api/capabilities/preview-impact
GET    /api/requirements/{id}/eligible-teachers
GET    /api/requirements/{id}/staffing-health
POST   /api/requirements/{id}/teacher-preferences
POST   /api/requirements/{id}/lock-teacher
DELETE /api/requirements/{id}/teacher-lock
GET    /api/staffing/matrix
POST   /api/staffing/bulk-update
```

Example response:

```python
class EligibleTeacherOption(BaseModel):
    teacher_id: int
    capability_status: CapabilityStatus
    preference: AllocationPreference
    matched_capability_id: str
    available: bool
    remaining_capacity_minutes: int
    opportunity_cost: int
    reasons: list[str]

class RequirementStaffingResponse(BaseModel):
    requirement_id: str
    options: list[EligibleTeacherOption]
    required_teacher_id: int | None
    staffing_health: RequirementStaffingHealth
    blocking_findings: list[str]
```

---

## 14. Frontend components

```text
features/
  people/
    TeacherCapabilityCard.tsx
    CapabilityEditorDrawer.tsx
    CapabilityHistory.tsx
  staffing/
    StaffingMatrix.tsx
    SubjectStaffingView.tsx
    RequirementStaffingPanel.tsx
    EligibleTeacherPicker.tsx
    StaffingHealthBadge.tsx
    PreferenceEditor.tsx
```

Illustrative teacher picker:

```tsx
function EligibleTeacherPicker({ requirement, options, value, onChange }) {
  return (
    <fieldset className="space-y-3">
      <legend className="font-semibold">Teacher allocation</legend>
      {options.map((option) => (
        <label key={option.teacher_id} className="block rounded-xl border p-3">
          <input
            type="radio"
            name={`teacher-${requirement.id}`}
            value={option.teacher_id}
            checked={value === option.teacher_id}
            disabled={!option.available || option.capability_status !== "ELIGIBLE"}
            onChange={() => onChange(option.teacher_id)}
          />
          <span className="ml-2 font-medium">{option.display_code}</span>
          <span className="ml-2 text-sm text-slate-600">
            {option.preference_label} · {option.remaining_capacity_minutes} min remaining
          </span>
          <ul className="ml-6 mt-1 text-sm text-slate-600">
            {option.reasons.map((reason) => <li key={reason}>{reason}</li>)}
          </ul>
        </label>
      ))}
    </fieldset>
  );
}
```

Adapt to existing repository conventions and ensure a person's display name is only included where the authorised screen genuinely needs it.

---

## 15. Tests

Create synthetic tests for:

1. teacher eligible for History and Religion;
2. teacher eligible for Mathematics only in Years 7–10;
3. Year 11 Mathematics rejected for that teacher;
4. exact course exclusion overriding broad subject eligibility;
5. required Modern History teacher locked successfully;
6. required teacher unavailable causing infeasibility;
7. preferred teacher selected over neutral teacher when otherwise equivalent;
8. neutral teacher selected when preferred teacher lacks capacity;
9. fallback teacher used only to preserve feasibility;
10. avoid teacher allocation produces a warning and penalty;
11. inferred capability excluded until confirmed;
12. conflicting capability rules block solving;
13. capability effective dates respected;
14. scarce specialist teacher preserved from a broadly teachable junior class;
15. junior class assigned to another eligible teacher when that protects a senior specialist requirement;
16. team teaching permits multiple required teachers where configured;
17. locked teacher survives scenario re-solve;
18. capability change does not silently alter approved scenarios;
19. capability-impact preview identifies affected draft scenarios;
20. no staff names or emails appear in solver logs.

---

## 16. Claude Code implementation sequence

### Step A: Documentation

Create:

```text
docs/staff-capability-model.md
docs/staffing-priority-policy.md
docs/staffing-ux-workflows.md
```

Map this addendum against the existing teacher, subject, class, faculty and teaching-requirement schema.

### Step B: Schema and service

- Add subject hierarchy/course mappings only where the existing schema does not already provide them.
- Add teacher capability and requirement preference tables.
- Implement `CapabilityService.resolve()`.
- Implement effective-date and specificity tests.

### Step C: Vertical UI slice

Implement:

```text
People → teacher → Teaching capability
→ add Mathematics Years 7–10
→ mark History and Religion eligible
→ set Modern History as preferred
→ preview affected requirements
→ save and audit
```

Use synthetic fixtures.

### Step D: Requirement staffing

Implement:

```text
Classes → requirement → Eligible teachers
→ set preferred or required teacher
→ preview load and feasibility
→ save to draft planning configuration
```

### Step E: Solver integration

- Exclude non-eligible and review-required candidates.
- Enforce required teachers.
- Penalise non-preferred and fallback options through a versioned solver profile.
- Add scarcity-aware opportunity cost.
- Persist allocation reasons and score contribution.

### Step F: Explainability

For every selected teacher, store:

```text
matched capability rule
preference rule
availability result
load capacity result
scarcity/opportunity-cost result
constraint and objective contribution
```

Display those facts in the UI. The local AI may convert them into plain language but cannot replace them.

---

## 17. Acceptance criteria

This feature is complete when an authorised user can:

- open a teacher profile;
- add several subject areas;
- limit a capability to a year range such as Years 7–10;
- define a precise senior course capability;
- mark a teacher as preferred or required for a class;
- see where the teacher is eligible but not preferred;
- see all eligible teachers for a class;
- understand why a teacher is unavailable or excluded;
- identify classes with no feasible teacher;
- identify scarce senior/specialist capability;
- run a scenario in which confirmed capabilities constrain assignments;
- preserve required senior allocations;
- use remaining eligible staff for junior classes;
- inspect the reason behind each allocation;
- change capability data without silently rewriting an approved scenario;
- audit every change;
- complete the workflow without editing solver code or raw database values.

---

## 18. Product behaviour example

Given confirmed planning data:

```text
Teacher MH
- Modern History Years 11–12: eligible, required for 11MHI1
- History Years 7–10: preferred
- Religion Years 7–12: preferred
- Mathematics Years 7–10: eligible
- Mathematics Years 11–12: not eligible
```

The timetable builder should behave as follows:

1. Reserve MH for `11MHI1` as an approved required assignment.
2. Subtract MH's role release and already allocated senior load from remaining capacity.
3. Include MH among valid candidates for a Year 7 Mathematics class.
4. Prefer another suitable Mathematics teacher if assigning MH would consume scarce capacity needed for History, Religion or locked senior commitments.
5. Assign MH to the Year 7 Mathematics class only if the allocation is valid and is the best feasible result under the active solver profile.
6. Never assign MH to Year 11 or 12 Mathematics under the stated capability profile.
7. Explain the final decision using capability, preference, availability, capacity and scarcity evidence.

All names and values in this example are illustrative until entered and confirmed within the application.
