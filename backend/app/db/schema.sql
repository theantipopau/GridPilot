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
-- docs/rules.md and PROJECT_ROADMAP.md's privacy correction). Recomputed
-- from scratch on every rules-engine run (app/analysis/run.py clears and
-- repopulates this table), same pattern as ingest_discrepancy.

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
    computed_at TEXT NOT NULL
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
