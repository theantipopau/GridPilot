"""Parses the Timetabling Solutions .tfx (Version 10, JSON) export - the
primary source for the internal data model. See docs/data-formats.md #3.1
and docs/data-model.md."""

import json
import sqlite3
from pathlib import Path
from typing import Any

from app.ingest.classification import (
    TEACHER_STAFF_CATEGORY,
    classify_entry_type,
    classify_period_kind,
)
from app.ingest.errors import IngestError


def load_tfx(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


# -- Format compatibility ---------------------------------------------------
# The version string this parser was built and verified against. A different
# minor/patch version is a warning-level discrepancy (the format is unlikely
# to have changed shape); a file that isn't a "TD" (Timetable Development)
# file at all, or is missing a section this parser requires, is a hard error
# with a message that says exactly what's wrong - never a raw KeyError.
KNOWN_TFX_VERSION = "Timetabling Solutions X TD 10.1.1.86"

REQUIRED_SECTIONS = (
    "Days", "Periods", "YearLevels", "Rooms", "Teachers", "Faculties",
    "RollClasses", "ClassNames", "ClassGroups", "Timetable", "Students",
)

# Modelled, but optional - parsed if present (see _ingest_settings/
# _ingest_blocking_lines/_ingest_room_pools below), never required, since
# an older/different export might lack them and that shouldn't be a hard
# failure (docs/full-timetabler-plan.md Phase A).
KNOWN_MODELLED_OPTIONAL_SECTIONS = ("Settings", "MRCGs", "RURs")

# Present in the known format but deliberately not modelled (see
# docs/data-formats.md and docs/full-timetabler-plan.md #4 for why
# Meetings/UnscheduledDuties were investigated and parked - zero load data
# and zero references respectively, in the real export). Their presence is
# expected; their absence is fine.
KNOWN_UNMODELLED_SECTIONS = (
    "File ID", "YardDutySessions", "YardDutyAreas", "YardDuties",
    "TeacherFiles", "StudentFiles", "UnscheduledDuties", "Meetings",
    "Groups", "PublishedTimetables",
)


def check_tfx_compatibility(data: dict[str, Any]) -> tuple[str | None, list[str], list[str]]:
    """Returns (file_id, missing_required_sections, unknown_sections).
    Raises IngestError only for hard incompatibilities - the caller
    decides how to surface the softer signals."""
    file_id = data.get("File ID")
    if isinstance(file_id, str) and " SO " in file_id:
        raise IngestError(
            f"This is a Student Options (.sfx) file ({file_id!r}), not a timetable (.tfx) file - "
            "it belongs to the .sfx ingestion path, not this parser."
        )

    missing = [s for s in REQUIRED_SECTIONS if s not in data]
    if missing:
        raise IngestError(
            f"File is missing required section(s) {missing} - either it isn't a Timetabling Solutions "
            f"TD export, or the format has changed. File ID: {file_id!r}"
        )

    known = set(REQUIRED_SECTIONS) | set(KNOWN_MODELLED_OPTIONAL_SECTIONS) | set(KNOWN_UNMODELLED_SECTIONS)
    unknown = sorted(k for k in data.keys() if k not in known)
    return (file_id if isinstance(file_id, str) else None), missing, unknown


def _blank_to_none(v: Any) -> Any:
    return None if v == "" else v


class TfxIngester:
    """Holds source-GUID -> internal-id maps built up as each section is
    ingested, so later sections (which reference earlier ones by GUID)
    can resolve foreign keys."""

    def __init__(self, conn: sqlite3.Connection, data: dict[str, Any], ingest_run_id: int):
        self.conn = conn
        self.data = data
        self.ingest_run_id = ingest_run_id
        self.day_id_by_source: dict[str, int] = {}
        self.period_id_by_source: dict[str, int] = {}
        self.period_kind_by_source: dict[str, str] = {}
        self.year_level_id_by_source: dict[str, int] = {}
        self.room_id_by_source: dict[str, int] = {}
        self.faculty_id_by_source: dict[str, int] = {}
        self.teacher_id_by_source: dict[str, int] = {}
        self.roll_class_id_by_source: dict[str, int] = {}
        self.roll_class_code_by_source: dict[str, str] = {}
        self.subject_id_by_code: dict[str, int] = {}
        self.class_name_id_by_source: dict[str, int] = {}
        self.class_name_subject_code_by_id: dict[int, str | None] = {}
        self.class_group_id_by_source: dict[str, int] = {}
        self.yard_duty_area_id_by_source: dict[str, int] = {}
        self.yard_duty_session_id_by_source: dict[str, int] = {}
        # Set by _ingest_settings(), used by _ingest_teachers() as the
        # fallback when a teacher's own LoadProposed is 0 - see
        # docs/full-timetabler-plan.md #4.1.
        self.default_teacher_load_minutes: float | None = None

    def log_discrepancy(self, check_name: str, severity: str, description: str, detail: dict | None = None) -> None:
        self.conn.execute(
            "INSERT INTO ingest_discrepancy (ingest_run_id, check_name, severity, description, detail_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (self.ingest_run_id, check_name, severity, description, json.dumps(detail) if detail else None),
        )

    def run(self) -> None:
        self._check_compatibility()
        self._ingest_settings()
        self._ingest_days()
        self._ingest_periods()
        self._ingest_year_levels()
        self._ingest_rooms()
        self._ingest_teachers()
        self._ingest_faculties()
        self._ingest_roll_classes()
        self._ingest_subjects_and_class_names()
        self._ingest_class_groups()
        self._ingest_blocking_lines()
        self._ingest_room_pools()
        self._ingest_timetable()
        self._ingest_students_and_enrolment()
        self._ingest_yard_duty()
        self.conn.commit()

    def _check_compatibility(self) -> None:
        """Hard-fails with a clear message for a genuinely incompatible
        file; records softer signals (version drift, unknown sections) as
        discrepancies so a future format change is visible, not silent."""
        file_id, _missing, unknown = check_tfx_compatibility(self.data)

        self.conn.execute(
            "UPDATE ingest_run SET source_file_id = ? WHERE id = ?",
            (file_id, self.ingest_run_id),
        )
        if file_id and file_id != KNOWN_TFX_VERSION:
            self.log_discrepancy(
                "tfx_version_drift", "warning",
                f"File ID {file_id!r} differs from the version this parser was verified against "
                f"({KNOWN_TFX_VERSION!r}) - ingestion continues, but check the results carefully.",
                {"file_id": file_id, "verified_against": KNOWN_TFX_VERSION},
            )
        if unknown:
            self.log_discrepancy(
                "tfx_unknown_sections", "warning",
                f"{len(unknown)} top-level section(s) this parser doesn't recognise: {unknown} - "
                "likely a newer Timetabling Solutions format. They are ignored on ingest; the export "
                "path's patch strategy carries them through untouched.",
                {"sections": unknown},
            )

    # -- School-wide settings -----------------------------------------

    def _ingest_settings(self) -> None:
        """Settings[] is a single-element list holding one dict - the
        school's own optimisation preferences and load default. Optional
        (KNOWN_MODELLED_OPTIONAL_SECTIONS): an export missing it just
        leaves school_setting empty and default_teacher_load_minutes None,
        never a hard failure."""
        settings_list = self.data.get("Settings") or []
        settings = settings_list[0] if settings_list else {}
        if not settings:
            return

        teacher_proposed_load_minutes = (settings.get("TeacherProposedLoad") or 0) / 100.0 or None
        self.default_teacher_load_minutes = teacher_proposed_load_minutes

        self.conn.execute(
            "INSERT INTO school_setting (id, teacher_proposed_load_minutes, optimise_spread, max_day_spread, "
            "successive_2_periods, successive_3_periods, academic_periods, timetable_notice) "
            "VALUES (1, ?, ?, ?, ?, ?, ?, ?)",
            (
                teacher_proposed_load_minutes,
                1 if settings.get("OptimiseSpread") else 0,
                1 if settings.get("MaxDaySpread") else 0,
                1 if settings.get("Successive2Periods") else 0,
                1 if settings.get("Successive3Periods") else 0,
                settings.get("AcademicPeriods"),
                _blank_to_none(settings.get("TimetableNotice")),
            ),
        )

    # -- Cycle structure ----------------------------------------------

    def _ingest_days(self) -> None:
        cur = self.conn.cursor()
        for i, d in enumerate(self.data.get("Days", []), start=1):
            code = d["Code"]
            week_label = code.strip()[-1].upper()
            cur.execute(
                "INSERT INTO day (source_day_id, code, day_no, week_label) VALUES (?, ?, ?, ?)",
                (d.get("DayID"), code, i, week_label),
            )
            self.day_id_by_source[d["DayID"]] = cur.lastrowid

    def _ingest_periods(self) -> None:
        cur = self.conn.cursor()
        for p in self.data.get("Periods", []):
            day_id = self._require(self.day_id_by_source, p["DayID"], "Periods[].DayID", p)
            entry_kind = classify_period_kind(p["Code"])
            load_minutes = (p.get("Load") or 0) / 100.0
            cur.execute(
                "INSERT INTO period (source_guid, code, name, day_id, period_no, start_time, finish_time, "
                "load_minutes, entry_kind) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (p["PeriodID"], p["Code"], p["Name"], day_id, p["PeriodNo"], p.get("StartTime"),
                 p.get("FinishTime"), load_minutes, entry_kind),
            )
            pid = cur.lastrowid
            self.period_id_by_source[p["PeriodID"]] = pid
            self.period_kind_by_source[p["PeriodID"]] = entry_kind

    def _ingest_year_levels(self) -> None:
        cur = self.conn.cursor()
        for yl in self.data.get("YearLevels", []):
            cur.execute(
                "INSERT INTO year_level (source_year_level_id, code) VALUES (?, ?)",
                (yl.get("YearLevelID"), yl["Code"]),
            )
            self.year_level_id_by_source[yl["YearLevelID"]] = cur.lastrowid

    # -- Places and people ----------------------------------------------

    def _ingest_rooms(self) -> None:
        cur = self.conn.cursor()
        for r in self.data.get("Rooms", []):
            seats = r.get("Seats") or None  # 0 -> NULL, "no fixed capacity" per docs/data-formats.md #5
            cur.execute(
                "INSERT INTO room (source_guid, code, name, seats, room_type, site_no) VALUES (?, ?, ?, ?, ?, ?)",
                (r["RoomID"], r["Code"], r["Name"], seats, _blank_to_none(r.get("Notes")), r.get("SiteNo")),
            )
            self.room_id_by_source[r["RoomID"]] = cur.lastrowid

    def _ingest_teachers(self) -> None:
        cur = self.conn.cursor()
        for t in self.data.get("Teachers", []):
            spare = t.get("SpareField1")
            staff_category = TEACHER_STAFF_CATEGORY.get(spare)
            if spare and not staff_category:
                self.log_discrepancy(
                    "teacher_staff_category", "warning",
                    f"Unknown teacher SpareField1 code '{spare}' - not in confirmed T/GC/SO/CLT set",
                    {"teacher_code": t["Code"]},
                )
            # LoadProposed=0 in the source means "use the school default",
            # not "no load" - confirmed against the real export, where the
            # only two values present were 0 and the exact school default
            # (Settings.TeacherProposedLoad). Without this fallback, every
            # teacher whose file says 0 silently drops out of
            # teacher_over_contracted_load (WHERE contracted_load_minutes
            # IS NOT NULL) - 30 of 74 teachers in the real data. See
            # docs/full-timetabler-plan.md #4.1.
            load_proposed = (t.get("LoadProposed") or 0) / 100.0
            contracted_load_minutes = load_proposed or self.default_teacher_load_minutes
            cur.execute(
                "INSERT INTO teacher (source_guid, code, first_name, last_name, email, staff_category, "
                "contracted_load_minutes) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (t["TeacherID"], t["Code"], t.get("FirstName"), t.get("LastName"),
                 _blank_to_none(t.get("Email")), staff_category, contracted_load_minutes),
            )
            self.teacher_id_by_source[t["TeacherID"]] = cur.lastrowid

    def _ingest_faculties(self) -> None:
        cur = self.conn.cursor()
        for f in self.data.get("Faculties", []):
            cur.execute(
                "INSERT INTO faculty (source_guid, code, name) VALUES (?, ?, ?)",
                (f["FacultyID"], f["Code"], f["Name"]),
            )
            faculty_id = cur.lastrowid
            self.faculty_id_by_source[f["FacultyID"]] = faculty_id
            for ft in f.get("FacultyTeachers", []):
                teacher_id = self.teacher_id_by_source.get(ft["TeacherID"])
                if teacher_id is None:
                    self.log_discrepancy(
                        "faculty_teacher_unresolved", "warning",
                        "FacultyTeachers references a TeacherID not found in Teachers[]",
                        {"faculty_code": f["Code"]},
                    )
                    continue
                cur.execute(
                    "INSERT OR IGNORE INTO teacher_faculty (teacher_id, faculty_id) VALUES (?, ?)",
                    (teacher_id, faculty_id),
                )

    def _ingest_roll_classes(self) -> None:
        cur = self.conn.cursor()
        for rc in self.data.get("RollClasses", []):
            year_level_id = None
            if rc.get("YearLevelID"):
                year_level_id = self.year_level_id_by_source.get(rc["YearLevelID"])
            is_support = 1 if not rc.get("YearLevelID") else 0
            cur.execute(
                "INSERT INTO roll_class (source_guid, code, year_level_id, is_support_roll_class) "
                "VALUES (?, ?, ?, ?)",
                (rc["RollClassID"], rc["Code"], year_level_id, is_support),
            )
            self.roll_class_id_by_source[rc["RollClassID"]] = cur.lastrowid
            self.roll_class_code_by_source[rc["RollClassID"]] = rc["Code"]

    # -- Subjects and classes --------------------------------------------

    def _ingest_subjects_and_class_names(self) -> None:
        cur = self.conn.cursor()
        for c in self.data.get("ClassNames", []):
            subject_code = c.get("SubjectCode")
            subject_id = None
            if subject_code:
                subject_id = self.subject_id_by_code.get(subject_code)
                if subject_id is None:
                    faculty_id = self.faculty_id_by_source.get(c.get("FacultyID"))
                    cur.execute(
                        "INSERT INTO subject (source_code, name, faculty_id) VALUES (?, ?, ?)",
                        (subject_code, c.get("SubjectName") or subject_code, faculty_id),
                    )
                    subject_id = cur.lastrowid
                    self.subject_id_by_code[subject_code] = subject_id
            faculty_id = self.faculty_id_by_source.get(c.get("FacultyID"))
            cur.execute(
                "INSERT INTO class_name (source_guid, code, name, subject_id, suffix, faculty_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (c["ClassNameID"], c["Code"], c.get("Name"), subject_id, c.get("Suffix"), faculty_id),
            )
            class_name_id = cur.lastrowid
            self.class_name_id_by_source[c["ClassNameID"]] = class_name_id
            self.class_name_subject_code_by_id[class_name_id] = subject_code

    def _ingest_class_groups(self) -> None:
        cur = self.conn.cursor()
        for cg in self.data.get("ClassGroups", []):
            roll_class_id = self._require(self.roll_class_id_by_source, cg["RollClassID"], "ClassGroups[].RollClassID", cg)
            cur.execute(
                "INSERT INTO class_group (source_guid, roll_class_id, block_no, periods_per_cycle) "
                "VALUES (?, ?, ?, ?)",
                (cg["ClassGroupID"], roll_class_id, cg.get("BlockNo"), cg.get("Periods")),
            )
            class_group_id = cur.lastrowid
            self.class_group_id_by_source[cg["ClassGroupID"]] = class_group_id

            for course in cg.get("ClassGroupCourses", []):
                class_name_id = None
                if course.get("ClassNameID"):
                    class_name_id = self.class_name_id_by_source.get(course["ClassNameID"])
                    if class_name_id is None:
                        raise IngestError(
                            f"ClassGroupCourse {course.get('CourseID')} references unknown ClassNameID "
                            f"{course['ClassNameID']!r} not present in ClassNames[]"
                        )
                teacher_id = self.teacher_id_by_source.get(course.get("TeacherID")) if course.get("TeacherID") else None
                room_id = self.room_id_by_source.get(course.get("RoomID")) if course.get("RoomID") else None
                cur.execute(
                    "INSERT INTO class_group_course (source_guid, class_group_id, class_name_id, teacher_id, room_id) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (course.get("CourseID"), class_group_id, class_name_id, teacher_id, room_id),
                )
                course_id = cur.lastrowid

                for edit in course.get("RoomTimetableEdits", []):
                    period_id = self.period_id_by_source.get(edit.get("PeriodID"))
                    override_room_id = self.room_id_by_source.get(edit.get("RoomID"))
                    if period_id is None or override_room_id is None:
                        self.log_discrepancy(
                            "room_override_unresolved", "warning",
                            "RoomTimetableEdits entry references a PeriodID/RoomID not found",
                            {"course_guid": course.get("CourseID")},
                        )
                        continue
                    cur.execute(
                        "INSERT OR IGNORE INTO class_group_course_room_override "
                        "(class_group_course_id, period_id, room_id) VALUES (?, ?, ?)",
                        (course_id, period_id, override_room_id),
                    )

    # -- Blocking lines and room pools --------------------------------------

    def _ingest_blocking_lines(self) -> None:
        """MRCGs[] - the blocking pattern / option lines. Optional
        (KNOWN_MODELLED_OPTIONAL_SECTIONS). A MRCGClassGroups entry
        referencing a ClassGroupID not seen in ClassGroups[] is logged and
        skipped, never a hard failure - this is exploratory structural
        data, not load-bearing for the timetable grid itself."""
        cur = self.conn.cursor()
        for m in self.data.get("MRCGs", []):
            cur.execute(
                "INSERT INTO blocking_line (source_guid, default_code, code, name) VALUES (?, ?, ?, ?)",
                (m["MRCGID"], m.get("DefaultCode", ""), _blank_to_none(m.get("Code")), _blank_to_none(m.get("Name"))),
            )
            blocking_line_id = cur.lastrowid

            for cg in m.get("MRCGClassGroups", []):
                class_group_id = self.class_group_id_by_source.get(cg.get("ClassGroupID"))
                if class_group_id is None:
                    self.log_discrepancy(
                        "blocking_line_class_group_unresolved", "warning",
                        "MRCGClassGroups entry references a ClassGroupID not found in ClassGroups[]",
                        {"mrcg_id": m["MRCGID"]},
                    )
                    continue
                cur.execute(
                    "INSERT OR IGNORE INTO blocking_line_class_group (blocking_line_id, class_group_id) "
                    "VALUES (?, ?)",
                    (blocking_line_id, class_group_id),
                )

    def _ingest_room_pools(self) -> None:
        """RURs[] ("Room Utilisation Requirements") - "one of these classes
        must use one of these rooms". Optional
        (KNOWN_MODELLED_OPTIONAL_SECTIONS). RURReferences[].ReferencesID
        was confirmed (by tracing a real value) to point at
        ClassNames[].ClassNameID - anything that doesn't resolve is logged
        and skipped rather than assumed."""
        cur = self.conn.cursor()
        for r in self.data.get("RURs", []):
            cur.execute(
                "INSERT INTO room_pool (source_guid, code, name, type_is_class) VALUES (?, ?, ?, ?)",
                (r["RURID"], _blank_to_none(r.get("Code")), _blank_to_none(r.get("Name")),
                 1 if r.get("TypeIsClass") else 0),
            )
            room_pool_id = cur.lastrowid

            for rr in r.get("RURRooms", []):
                room_id = self.room_id_by_source.get(rr.get("RoomID"))
                if room_id is None:
                    self.log_discrepancy(
                        "room_pool_room_unresolved", "warning",
                        "RURRooms entry references a RoomID not found in Rooms[]",
                        {"rur_id": r["RURID"]},
                    )
                    continue
                cur.execute(
                    "INSERT OR IGNORE INTO room_pool_room (room_pool_id, room_id) VALUES (?, ?)",
                    (room_pool_id, room_id),
                )

            for ref in r.get("RURReferences", []):
                class_name_id = self.class_name_id_by_source.get(ref.get("ReferencesID"))
                if class_name_id is None:
                    self.log_discrepancy(
                        "room_pool_class_name_unresolved", "warning",
                        "RURReferences entry references a ClassNameID not found in ClassNames[]",
                        {"rur_id": r["RURID"]},
                    )
                    continue
                cur.execute(
                    "INSERT OR IGNORE INTO room_pool_class_name (room_pool_id, class_name_id) VALUES (?, ?)",
                    (room_pool_id, class_name_id),
                )

    # -- The timetable grid -----------------------------------------------

    def _ingest_timetable(self) -> None:
        cur = self.conn.cursor()
        for i, t in enumerate(self.data.get("Timetable", [])):
            period_source = t.get("PeriodID")
            period_id = self.period_id_by_source.get(period_source)
            if period_id is None:
                raise IngestError(f"Timetable[{i}] references unknown PeriodID {period_source!r}")
            day_id = self.conn.execute("SELECT day_id FROM period WHERE id = ?", (period_id,)).fetchone()[0]

            roll_class_source = t.get("RollClassID")
            roll_class_id = self.roll_class_id_by_source.get(roll_class_source)
            if roll_class_id is None:
                raise IngestError(f"Timetable[{i}] references unknown RollClassID {roll_class_source!r}")

            class_name_source = _blank_to_none(t.get("ClassNameID"))
            class_name_id = None
            subject_code = None
            if class_name_source:
                class_name_id = self.class_name_id_by_source.get(class_name_source)
                if class_name_id is None:
                    raise IngestError(f"Timetable[{i}] references unknown ClassNameID {class_name_source!r}")
                subject_code = self.class_name_subject_code_by_id.get(class_name_id)

            room_id = self.room_id_by_source.get(_blank_to_none(t.get("RoomID")))
            teacher_id = self.teacher_id_by_source.get(_blank_to_none(t.get("TeacherID")))

            period_kind = self.period_kind_by_source[period_source]
            entry_type = classify_entry_type(period_kind, subject_code)

            cur.execute(
                "INSERT INTO timetable_entry (source_ref, day_id, period_id, roll_class_id, class_name_id, "
                "room_id, teacher_id, entry_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (f"tfx:Timetable[{i}]", day_id, period_id, roll_class_id, class_name_id, room_id, teacher_id, entry_type),
            )

    # -- Students and enrolment -------------------------------------------

    def _ingest_students_and_enrolment(self) -> None:
        cur = self.conn.cursor()
        code_to_id = {}
        for row in self.conn.execute("SELECT id, code FROM roll_class"):
            code_to_id[row["code"]] = row["id"]
        code_to_year_level_id = {}
        for row in self.conn.execute("SELECT id, code FROM year_level"):
            code_to_year_level_id[row["code"]] = row["id"]

        for s in self.data.get("Students", []):
            roll_class_id = code_to_id.get(s.get("RollClass"))
            year_level_id = code_to_year_level_id.get(s.get("YearLevel"))
            house = (s.get("House") or "").strip().upper() or None
            cur.execute(
                "INSERT INTO student (source_guid, code, first_name, last_name, preferred_name, gender, "
                "roll_class_id, year_level_id, house, home_group, email) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (s["StudentID"], s["Code"], s.get("FirstName"), s.get("LastName"), s.get("PreferredName"),
                 s.get("Gender"), roll_class_id, year_level_id, house, _blank_to_none(s.get("HomeGroup")),
                 _blank_to_none(s.get("Email"))),
            )
            student_id = cur.lastrowid

            for lesson in s.get("StudentLessons", []):
                class_code = lesson.get("ClassCode")
                row = self.conn.execute("SELECT id FROM class_name WHERE code = ?", (class_code,)).fetchone()
                if row is None:
                    self.log_discrepancy(
                        "student_lesson_unresolved", "warning",
                        f"StudentLessons references ClassCode '{class_code}' not found in ClassNames[]",
                        {"student_code": s["Code"]},
                    )
                    continue
                cur.execute(
                    "INSERT OR IGNORE INTO enrolment (student_id, class_name_id, source) VALUES (?, ?, ?)",
                    (student_id, row["id"], "tfx"),
                )

    # -- Yard duty ----------------------------------------------------------

    def _ingest_yard_duty(self) -> None:
        cur = self.conn.cursor()
        for a in self.data.get("YardDutyAreas", []):
            cur.execute(
                "INSERT INTO yard_duty_area (source_area_id, code, name, site_no) VALUES (?, ?, ?, ?)",
                (a.get("YardDutyAreaID"), a["Code"], a["Name"], a.get("SiteNo")),
            )
            self.yard_duty_area_id_by_source[a["YardDutyAreaID"]] = cur.lastrowid

        for s in self.data.get("YardDutySessions", []):
            period_id = self.period_id_by_source.get(s.get("PeriodID"))
            if period_id is None:
                self.log_discrepancy(
                    "yard_duty_session_unresolved", "warning",
                    "YardDutySessions entry references a PeriodID not found in Periods[]",
                    {"session_code": s.get("Code")},
                )
                continue
            cur.execute(
                "INSERT INTO yard_duty_session (source_guid, code, name, period_id, precedes_period) "
                "VALUES (?, ?, ?, ?, ?)",
                (s["YardDutySessionID"], s["Code"], s["Name"], period_id, 1 if s.get("Precedes") else 0),
            )
            self.yard_duty_session_id_by_source[s["YardDutySessionID"]] = cur.lastrowid

        for d in self.data.get("YardDuties", []):
            area_id = self.yard_duty_area_id_by_source.get(d.get("YardDutyAreaID"))
            teacher_id = self.teacher_id_by_source.get(d.get("TeacherID"))
            session_id = self.yard_duty_session_id_by_source.get(d.get("YardDutySessionID"))
            if area_id is None or teacher_id is None or session_id is None:
                self.log_discrepancy(
                    "yard_duty_allocation_unresolved", "warning",
                    "YardDuties entry references an area/teacher/session not found",
                    {"yard_duty_id": d.get("YardDutyID")},
                )
                continue
            cur.execute(
                "INSERT INTO yard_duty_allocation (yard_duty_area_id, teacher_id, yard_duty_session_id, load_minutes) "
                "VALUES (?, ?, ?, ?)",
                (area_id, teacher_id, session_id, (d.get("Load") or 0) / 100.0),
            )

    @staticmethod
    def _require(mapping: dict, key: str, field_name: str, record: dict) -> int:
        value = mapping.get(key)
        if value is None:
            raise IngestError(f"{field_name} references unknown id {key!r} in record {record}")
        return value


def ingest_tfx(conn: sqlite3.Connection, tfx_path: Path, ingest_run_id: int) -> TfxIngester:
    data = load_tfx(tfx_path)
    ingester = TfxIngester(conn, data, ingest_run_id)
    ingester.run()
    return ingester
