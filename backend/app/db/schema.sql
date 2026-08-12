-- Sophia College timetable internal data model.
-- Every entity that originates from a Timetabling Solutions export keeps its
-- source identifier (GUID and/or short code) so exports can be regenerated
-- and diffed against the original structure. See docs/data-model.md.

PRAGMA foreign_keys = ON;

-- Provenance / ingestion bookkeeping -----------------------------------

CREATE TABLE IF NOT EXISTS ingest_run (
    id INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    tfx_source_path TEXT,
    -- SHA-256 of the source .tfx file at ingest time - proves exactly
    -- which export version a given run (and everything downstream of it:
    -- findings, composite candidates, change sets) was analysed against.
    tfx_source_sha256 TEXT,
    -- The file's own "File ID" version string, e.g.
    -- "Timetabling Solutions X TD 10.1.1.86" - recorded so version drift
    -- across future exports is visible (see tfx_parser.check_tfx_compatibility).
    source_file_id TEXT,
    notes TEXT
);

-- Structured, non-PII discrepancy log. Cross-validation mismatches between
-- sources (e.g. .tfx vs Master Timetable Cycle.csv) are recorded here
-- rather than silently dropped or only printed to a console.
CREATE TABLE IF NOT EXISTS ingest_discrepancy (
    id INTEGER PRIMARY KEY,
    ingest_run_id INTEGER NOT NULL REFERENCES ingest_run(id),
    check_name TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'error')),
    description TEXT NOT NULL,
    detail_json TEXT
);

-- Cycle structure --------------------------------------------------------

CREATE TABLE IF NOT EXISTS day (
    id INTEGER PRIMARY KEY,
    source_day_id TEXT,
    code TEXT NOT NULL UNIQUE,      -- e.g. "Mon A"
    day_no INTEGER NOT NULL,        -- 1-10
    week_label TEXT NOT NULL        -- "A" | "B", parsed from code
);

CREATE TABLE IF NOT EXISTS period (
    id INTEGER PRIMARY KEY,
    source_guid TEXT UNIQUE,
    code TEXT NOT NULL,             -- FR, P1-P5, FB, SB
    name TEXT NOT NULL,
    day_id INTEGER NOT NULL REFERENCES day(id),
    period_no INTEGER NOT NULL,     -- 1-8 within the day
    start_time TEXT,
    finish_time TEXT,
    load_minutes REAL NOT NULL DEFAULT 0,
    entry_kind TEXT NOT NULL CHECK (entry_kind IN ('REGISTRATION', 'LESSON_SLOT', 'BREAK')),
    UNIQUE (day_id, period_no)
);

-- School-wide settings (source: .tfx Settings[0]) ----------------------------
-- Single-row table - the school's own optimisation preferences and load
-- default, previously unparsed. teacher_proposed_load_minutes is the
-- fallback used when a teacher's own LoadProposed is 0 (TTS's "use the
-- school default" convention, not "no load") - see
-- docs/full-timetabler-plan.md #4.1 and TfxIngester._ingest_teachers.
-- Rebuilt from scratch every ingest, like every other source-derived table.
CREATE TABLE IF NOT EXISTS school_setting (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    teacher_proposed_load_minutes REAL,
    optimise_spread INTEGER,
    max_day_spread INTEGER,
    successive_2_periods INTEGER,
    successive_3_periods INTEGER,
    academic_periods INTEGER,
    timetable_notice TEXT
);

-- Places and people -------------------------------------------------------

CREATE TABLE IF NOT EXISTS room (
    id INTEGER PRIMARY KEY,
    source_guid TEXT UNIQUE,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    seats INTEGER,                  -- NULL where source Seats=0 (no fixed capacity)
    room_type TEXT,                 -- free text, from Notes
    site_no INTEGER
);

CREATE TABLE IF NOT EXISTS faculty (
    id INTEGER PRIMARY KEY,
    source_guid TEXT UNIQUE,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS teacher (
    id INTEGER PRIMARY KEY,
    source_guid TEXT UNIQUE,
    code TEXT NOT NULL UNIQUE,
    first_name TEXT,
    last_name TEXT,
    email TEXT,
    staff_category TEXT CHECK (staff_category IN ('TEACHER', 'GUIDANCE_COUNSELLOR', 'SUPPORT_OFFICER', 'COLLEGE_LEADERSHIP')),
    contracted_load_minutes REAL
);

CREATE TABLE IF NOT EXISTS teacher_faculty (
    teacher_id INTEGER NOT NULL REFERENCES teacher(id),
    faculty_id INTEGER NOT NULL REFERENCES faculty(id),
    PRIMARY KEY (teacher_id, faculty_id)
);

CREATE TABLE IF NOT EXISTS year_level (
    id INTEGER PRIMARY KEY,
    source_year_level_id TEXT,
    code TEXT NOT NULL UNIQUE       -- "07".."12"
);

CREATE TABLE IF NOT EXISTS roll_class (
    id INTEGER PRIMARY KEY,
    source_guid TEXT UNIQUE,
    code TEXT NOT NULL UNIQUE,
    year_level_id INTEGER REFERENCES year_level(id),  -- NULL for support roll classes
    is_support_roll_class INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS student (
    id INTEGER PRIMARY KEY,
    source_guid TEXT UNIQUE,
    code TEXT NOT NULL UNIQUE,
    first_name TEXT,
    last_name TEXT,
    preferred_name TEXT,
    gender TEXT,
    roll_class_id INTEGER REFERENCES roll_class(id),
    year_level_id INTEGER REFERENCES year_level(id),
    house TEXT,                     -- normalised casing on ingest
    home_group TEXT,
    email TEXT
    -- support_flags intentionally omitted: none present in current export.
    -- Add only when a real, confirmed field exists - do not guess a shape.
);

-- Subjects and classes -----------------------------------------------------

CREATE TABLE IF NOT EXISTS subject (
    id INTEGER PRIMARY KEY,
    source_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    faculty_id INTEGER REFERENCES faculty(id)
);

CREATE TABLE IF NOT EXISTS class_name (
    id INTEGER PRIMARY KEY,
    source_guid TEXT UNIQUE,
    code TEXT NOT NULL UNIQUE,      -- e.g. "12RAE2"
    name TEXT,
    subject_id INTEGER REFERENCES subject(id),
    suffix TEXT,
    faculty_id INTEGER REFERENCES faculty(id)
);

CREATE TABLE IF NOT EXISTS class_group (
    id INTEGER PRIMARY KEY,
    source_guid TEXT UNIQUE,
    roll_class_id INTEGER NOT NULL REFERENCES roll_class(id),
    block_no INTEGER,
    periods_per_cycle INTEGER
);

CREATE TABLE IF NOT EXISTS class_group_course (
    id INTEGER PRIMARY KEY,
    source_guid TEXT UNIQUE,        -- CourseID
    class_group_id INTEGER NOT NULL REFERENCES class_group(id),
    class_name_id INTEGER REFERENCES class_name(id),
    teacher_id INTEGER REFERENCES teacher(id),
    room_id INTEGER REFERENCES room(id)
);

-- Per-period room overrides within an otherwise-stable course
-- (source: ClassGroupCourse.RoomTimetableEdits[])
CREATE TABLE IF NOT EXISTS class_group_course_room_override (
    id INTEGER PRIMARY KEY,
    class_group_course_id INTEGER NOT NULL REFERENCES class_group_course(id),
    period_id INTEGER NOT NULL REFERENCES period(id),
    room_id INTEGER NOT NULL REFERENCES room(id),
    UNIQUE (class_group_course_id, period_id)
);

-- Blocking lines (source: .tfx MRCGs) ----------------------------------------
-- The option-line / blocking-pattern structure: which class groups run in
-- parallel so a student can pick one subject per line without a clash.
-- See docs/data-formats.md #5.4 and docs/full-timetabler-plan.md Phase A/C.
-- Source-derived like class_group - rebuilt from scratch every ingest.
CREATE TABLE IF NOT EXISTS blocking_line (
    id INTEGER PRIMARY KEY,
    source_guid TEXT NOT NULL UNIQUE,   -- MRCGID
    default_code TEXT NOT NULL,         -- year level + line letter, e.g. "10A B" - always present
    code TEXT,                          -- school-assigned short code, e.g. "10ENG" - often blank
    name TEXT                           -- e.g. "10 English" - often blank
);

CREATE TABLE IF NOT EXISTS blocking_line_class_group (
    blocking_line_id INTEGER NOT NULL REFERENCES blocking_line(id),
    class_group_id INTEGER NOT NULL REFERENCES class_group(id),
    PRIMARY KEY (blocking_line_id, class_group_id)
);

-- Room pools (source: .tfx RURs - "Room Utilisation Requirements") ----------
-- "one of these classes must use one of these rooms" - a room-choice
-- constraint, not necessarily a single fixed room. TypeIsClass distinguishes
-- a class-scoped pool from other RUR kinds TTS may support (unconfirmed -
-- see docs/data-formats.md #5). RURReferences[] were confirmed by tracing a
-- real ReferencesID to point at ClassNames[].ClassNameID.
CREATE TABLE IF NOT EXISTS room_pool (
    id INTEGER PRIMARY KEY,
    source_guid TEXT NOT NULL UNIQUE,   -- RURID
    code TEXT,
    name TEXT,
    type_is_class INTEGER
);

CREATE TABLE IF NOT EXISTS room_pool_room (
    room_pool_id INTEGER NOT NULL REFERENCES room_pool(id),
    room_id INTEGER NOT NULL REFERENCES room(id),
    PRIMARY KEY (room_pool_id, room_id)
);

CREATE TABLE IF NOT EXISTS room_pool_class_name (
    room_pool_id INTEGER NOT NULL REFERENCES room_pool(id),
    class_name_id INTEGER NOT NULL REFERENCES class_name(id),
    PRIMARY KEY (room_pool_id, class_name_id)
);

-- The timetable grid --------------------------------------------------------

CREATE TABLE IF NOT EXISTS timetable_entry (
    id INTEGER PRIMARY KEY,
    source_ref TEXT,                -- provenance: e.g. "tfx:Timetable[123]" or CSV row no
    day_id INTEGER NOT NULL REFERENCES day(id),
    period_id INTEGER NOT NULL REFERENCES period(id),
    roll_class_id INTEGER NOT NULL REFERENCES roll_class(id),
    class_name_id INTEGER REFERENCES class_name(id),   -- NULL for non-lesson entries
    room_id INTEGER REFERENCES room(id),
    teacher_id INTEGER REFERENCES teacher(id),
    entry_type TEXT NOT NULL CHECK (entry_type IN
        ('LESSON', 'BREAK', 'ASSEMBLY', 'GENERAL_PURPOSE', 'DETENTION', 'REGISTRATION', 'OTHER'))
);

CREATE INDEX IF NOT EXISTS idx_timetable_entry_period_teacher ON timetable_entry(period_id, teacher_id);
CREATE INDEX IF NOT EXISTS idx_timetable_entry_period_room ON timetable_entry(period_id, room_id);
CREATE INDEX IF NOT EXISTS idx_timetable_entry_period_rollclass ON timetable_entry(period_id, roll_class_id);

-- Enrolment ------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS enrolment (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES student(id),
    class_name_id INTEGER NOT NULL REFERENCES class_name(id),
    source TEXT NOT NULL,           -- which export(s) confirmed this, e.g. "eminerva,tfx"
    UNIQUE (student_id, class_name_id)
);

-- Yard duty (kept separate from teaching load, per school confirmation) -----

CREATE TABLE IF NOT EXISTS yard_duty_area (
    id INTEGER PRIMARY KEY,
    source_area_id TEXT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    site_no INTEGER
);

CREATE TABLE IF NOT EXISTS yard_duty_session (
    id INTEGER PRIMARY KEY,
    source_guid TEXT UNIQUE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    period_id INTEGER NOT NULL REFERENCES period(id),
    precedes_period INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS yard_duty_allocation (
    id INTEGER PRIMARY KEY,
    yard_duty_area_id INTEGER NOT NULL REFERENCES yard_duty_area(id),
    teacher_id INTEGER NOT NULL REFERENCES teacher(id),
    yard_duty_session_id INTEGER NOT NULL REFERENCES yard_duty_session(id),
    load_minutes REAL NOT NULL DEFAULT 0
);

-- Composite classes: human-reviewed, not silently trusted -------------------
-- Detected candidates (see app/analysis/composite.py) are upserted here as
-- PENDING. A clash rule only suppresses a clash for an APPROVED group - a
-- PENDING or REJECTED group still produces a clash finding. Re-running
-- detection must never clobber an existing review decision - see
-- app/analysis/composite_review.py for the upsert-by-member-set logic.

CREATE TABLE IF NOT EXISTS composite_group (
    id INTEGER PRIMARY KEY,
    teacher_id INTEGER NOT NULL REFERENCES teacher(id),
    room_id INTEGER NOT NULL REFERENCES room(id),
    review_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (review_status IN ('PENDING', 'APPROVED', 'REJECTED')),
    slot_count INTEGER NOT NULL,
    detected_at TEXT NOT NULL,
    reviewed_at TEXT,
    reviewed_by TEXT,
    review_note TEXT
);

CREATE TABLE IF NOT EXISTS composite_group_member (
    composite_group_id INTEGER NOT NULL REFERENCES composite_group(id),
    class_name_id INTEGER NOT NULL REFERENCES class_name(id),
    PRIMARY KEY (composite_group_id, class_name_id)
);

-- Findings ---------------------------------------------------------------
-- Structured output of the deterministic rules engine. entity/slot refs are
-- codes and internal ids only - never names or emails (see
-- docs/rules.md and PROJECT_ROADMAP.md's privacy correction). Upserted by
-- dedupe_key on every rules-engine run (app/analysis/run.py), not wiped -
-- a finding keeps its id and any human-set status (ACCEPTED_RISK included)
-- across re-runs and re-ingests, as long as the same underlying issue still
-- reproduces; one that stops reproducing is marked RESOLVED, never deleted.
-- reviewed_at/by/note record a human's ACCEPTED_RISK/OPEN decision, same
-- shape as composite_group's review columns above.

CREATE TABLE IF NOT EXISTS finding (
    id INTEGER PRIMARY KEY,
    dedupe_key TEXT NOT NULL UNIQUE,
    rule_id TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
    title TEXT NOT NULL,
    entity_refs_json TEXT NOT NULL,
    slot_refs_json TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    suggested_actions_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'ACKNOWLEDGED', 'RESOLVED', 'ACCEPTED_RISK')),
    first_seen_at TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    reviewed_at TEXT,
    reviewed_by TEXT,
    review_note TEXT
);

CREATE INDEX IF NOT EXISTS idx_finding_rule ON finding(rule_id);
CREATE INDEX IF NOT EXISTS idx_finding_severity ON finding(severity);
CREATE INDEX IF NOT EXISTS idx_finding_status ON finding(status);

-- Change sets ---------------------------------------------------------------
-- Proposed edits, kept entirely separate from the imported timetable_entry
-- rows - approving a change set never mutates timetable_entry (see
-- PROJECT_ROADMAP.md's "Separate source truth from proposed changes").
-- validation_status and approval_status are deliberately distinct: a change
-- set can be re-validated repeatedly while still in draft, and can only be
-- approved once it is VALID.

CREATE TABLE IF NOT EXISTS change_set (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    validation_status TEXT NOT NULL DEFAULT 'NOT_VALIDATED'
        CHECK (validation_status IN ('NOT_VALIDATED', 'VALID', 'INVALID')),
    validation_result_json TEXT,
    validated_at TEXT,
    approval_status TEXT NOT NULL DEFAULT 'DRAFT'
        CHECK (approval_status IN ('DRAFT', 'APPROVED', 'REJECTED')),
    reviewed_at TEXT,
    reviewed_by TEXT,
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS proposed_change (
    id INTEGER PRIMARY KEY,
    change_set_id INTEGER NOT NULL REFERENCES change_set(id),
    timetable_entry_id INTEGER NOT NULL REFERENCES timetable_entry(id),
    before_day_id INTEGER NOT NULL REFERENCES day(id),
    before_period_id INTEGER NOT NULL REFERENCES period(id),
    before_room_id INTEGER REFERENCES room(id),
    before_teacher_id INTEGER REFERENCES teacher(id),
    after_day_id INTEGER NOT NULL REFERENCES day(id),
    after_period_id INTEGER NOT NULL REFERENCES period(id),
    after_room_id INTEGER REFERENCES room(id),
    after_teacher_id INTEGER REFERENCES teacher(id),
    reason TEXT
);

-- Which findings this change is meant to address - the "originating
-- finding IDs" the roadmap asks for. Safe to reference finding.id long
-- term because findings are now upserted by dedupe_key (see
-- app/analysis/run.py), not wiped and recreated every run.
CREATE TABLE IF NOT EXISTS proposed_change_finding (
    proposed_change_id INTEGER NOT NULL REFERENCES proposed_change(id),
    finding_id INTEGER NOT NULL REFERENCES finding(id),
    PRIMARY KEY (proposed_change_id, finding_id)
);

-- Student Options (.sfx) files ---------------------------------------------
-- The per-year-level Student Options exports (e.g. "YR 10 2026 Term 3.sfx")
-- hold the elective/option-line structure: lines (elective bands), subjects
-- with class-size caps, options, the classes built on each line, and every
-- student's subject preferences. Namespaced sfx_* because the concepts
-- overlap with but differ from the .tfx-derived tables (an sfx "Subject"
-- carries ClassSizeMaximum/Units; the tfx subject doesn't).
--
-- Privacy note: student rows are NOT created from .sfx files - preferences
-- link to the existing student table by code where possible, and keep only
-- the code (never a name) when the student isn't in the current .tfx (e.g.
-- a next-year planning file). Codes only, per the standing no-PII rule.

CREATE TABLE IF NOT EXISTS sfx_file (
    id INTEGER PRIMARY KEY,
    ingest_run_id INTEGER NOT NULL REFERENCES ingest_run(id),
    file_name TEXT NOT NULL,
    source_file_id TEXT,            -- e.g. "Timetabling Solutions X SO 10.1.1.86"
    sha256 TEXT,
    year_level_code TEXT            -- dominant Students[].YearLevel in the file
);

CREATE TABLE IF NOT EXISTS sfx_line (
    id INTEGER PRIMARY KEY,
    sfx_file_id INTEGER NOT NULL REFERENCES sfx_file(id),
    source_guid TEXT,
    code TEXT NOT NULL,
    name TEXT,
    subgrid INTEGER
);

CREATE TABLE IF NOT EXISTS sfx_subject (
    id INTEGER PRIMARY KEY,
    sfx_file_id INTEGER NOT NULL REFERENCES sfx_file(id),
    source_guid TEXT,
    code TEXT NOT NULL,
    name TEXT,
    units INTEGER,
    class_size_maximum INTEGER
);

CREATE TABLE IF NOT EXISTS sfx_option (
    id INTEGER PRIMARY KEY,
    sfx_file_id INTEGER NOT NULL REFERENCES sfx_file(id),
    source_guid TEXT,
    sfx_subject_id INTEGER REFERENCES sfx_subject(id),
    code TEXT,
    name TEXT
);

CREATE TABLE IF NOT EXISTS sfx_class (
    id INTEGER PRIMARY KEY,
    sfx_file_id INTEGER NOT NULL REFERENCES sfx_file(id),
    source_guid TEXT,
    sfx_option_id INTEGER REFERENCES sfx_option(id),
    sfx_line_id INTEGER REFERENCES sfx_line(id),
    class_code TEXT,
    subject_code TEXT,
    roll_class_code TEXT,
    max_class_size INTEGER
);

CREATE TABLE IF NOT EXISTS sfx_student_preference (
    id INTEGER PRIMARY KEY,
    sfx_file_id INTEGER NOT NULL REFERENCES sfx_file(id),
    student_id INTEGER REFERENCES student(id),   -- NULL when the student isn't in the current .tfx
    student_code TEXT NOT NULL,
    sfx_option_id INTEGER REFERENCES sfx_option(id),
    sfx_class_id INTEGER REFERENCES sfx_class(id),
    preference_order INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sfx_constraint (
    id INTEGER PRIMARY KEY,
    sfx_file_id INTEGER NOT NULL REFERENCES sfx_file(id),
    source_guid TEXT,
    type_str TEXT,
    note TEXT,
    limit_value INTEGER
);

CREATE TABLE IF NOT EXISTS sfx_constraint_option (
    sfx_constraint_id INTEGER NOT NULL REFERENCES sfx_constraint(id),
    sfx_option_id INTEGER REFERENCES sfx_option(id)
);

-- Audit trail --------------------------------------------------------------
-- PROJECT_ROADMAP.md Milestone 5: an audit event for imports, rule runs,
-- composite approvals, change-set approvals, and (once built) exports.
-- Append-only from the application's perspective - nothing here ever
-- deletes or edits a prior event. `actor` is a free-text name (this is a
-- single-user local desktop tool with no login system - see
-- docs/privacy-threat-model.md), never an email. `detail_json` follows the
-- same no-PII rule as everything else: codes and ids, never names.

CREATE TABLE IF NOT EXISTS audit_event (
    id INTEGER PRIMARY KEY,
    occurred_at TEXT NOT NULL,
    actor TEXT NOT NULL,
    event_type TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    summary TEXT NOT NULL,
    detail_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_event(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_event_occurred ON audit_event(occurred_at);

-- Staff roles / middle leadership tiers --------------------------------------
-- App-owned, not derived from any Timetabling Solutions export - there is
-- no source data for "this teacher is a Head of Department with N minutes
-- release per cycle" anywhere in the .tfx/.sfx files. Entered and managed
-- entirely within GridPilot. Deliberately not in app/db/resync.py's
-- SOURCE_TABLES_IN_DELETE_ORDER - these two tables are never wiped on
-- re-ingest, same treatment as composite_group/change_set.
--
-- teacher_role_assignment references the teacher by CODE, not by
-- teacher.id - teacher is a source-derived table that's fully rebuilt
-- (new surrogate ids) on every re-ingest (see app/db/resync.py), so a
-- role assignment keyed by the old integer id would silently point at
-- the wrong teacher - or nothing - the moment a new export is loaded.
-- The code is the one thing about a teacher that's stable across terms.

CREATE TABLE IF NOT EXISTS staff_role (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,          -- e.g. "Head of Department"
    tier TEXT,                          -- free text, e.g. "Tier 1" - school's own naming, not GridPilot's
    release_minutes_per_cycle REAL,     -- nullable - a role can exist without a confirmed time value yet
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS teacher_role_assignment (
    id INTEGER PRIMARY KEY,
    teacher_code TEXT NOT NULL UNIQUE,  -- one active role per teacher in v1; re-assigning replaces it
    staff_role_id INTEGER NOT NULL REFERENCES staff_role(id),
    assigned_at TEXT NOT NULL,
    assigned_by TEXT NOT NULL
);
