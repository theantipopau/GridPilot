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
