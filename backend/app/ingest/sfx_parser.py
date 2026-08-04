"""Ingests Timetabling Solutions Student Options (.sfx) files - the
per-year-level exports holding the elective/option-line structure: lines
(elective bands), subjects with class-size caps, options, classes, each
student's subject preferences, and join/limit constraints.

Format notes, confirmed against the six real files (see
docs/data-formats.md):
- File ID is "Timetabling Solutions X SO <version>" - "SO" (Student
  Options), vs "TD" for .tfx timetable files.
- Top-level sections vary between files of the same version: Year 12's
  file has no StudentFiles, Years 7-9 have no Constraints. Every section
  is therefore treated as optional; a missing one ingests zero rows.
- Students[] carries names/emails, but per the standing no-PII rule this
  parser never copies them: preferences link to the existing student
  table by code, and keep only the code when the student isn't in the
  current .tfx (e.g. a next-year planning file)."""

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from app.ingest.errors import IngestError

KNOWN_SFX_VERSION = "Timetabling Solutions X SO 10.1.1.86"


def load_sfx(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def _log(conn: sqlite3.Connection, run_id: int, check_name: str, severity: str,
         description: str, detail: dict | None = None) -> None:
    conn.execute(
        "INSERT INTO ingest_discrepancy (ingest_run_id, check_name, severity, description, detail_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (run_id, check_name, severity, description, json.dumps(detail) if detail else None),
    )


def _dominant_year_level(students: list[dict]) -> str | None:
    counts: dict[str, int] = {}
    for s in students:
        yl = s.get("YearLevel")
        if yl:
            counts[yl] = counts.get(yl, 0) + 1
    return max(counts, key=counts.get) if counts else None


def ingest_sfx_file(conn: sqlite3.Connection, path: Path, ingest_run_id: int) -> dict[str, int]:
    data = load_sfx(path)

    file_id = data.get("File ID")
    if isinstance(file_id, str) and " TD " in file_id:
        raise IngestError(
            f"{path.name}: this is a timetable (.tfx) file ({file_id!r}), not a Student Options file."
        )
    if isinstance(file_id, str) and file_id != KNOWN_SFX_VERSION:
        _log(conn, ingest_run_id, "sfx_version_drift", "warning",
             f"{path.name}: File ID {file_id!r} differs from the verified version "
             f"({KNOWN_SFX_VERSION!r}) - check results carefully.",
             {"file": path.name, "file_id": file_id})

    students = data.get("Students", [])
    cur = conn.execute(
        "INSERT INTO sfx_file (ingest_run_id, file_name, source_file_id, sha256, year_level_code) "
        "VALUES (?, ?, ?, ?, ?)",
        (ingest_run_id, path.name, file_id if isinstance(file_id, str) else None,
         hashlib.sha256(path.read_bytes()).hexdigest(), _dominant_year_level(students)),
    )
    sfx_file_id = cur.lastrowid

    line_id_by_guid: dict[str, int] = {}
    for line in data.get("Lines", []):
        cur = conn.execute(
            "INSERT INTO sfx_line (sfx_file_id, source_guid, code, name, subgrid) VALUES (?, ?, ?, ?, ?)",
            (sfx_file_id, line.get("LineID"), line.get("Code", ""), line.get("Name"), line.get("Subgrid")),
        )
        if line.get("LineID"):
            line_id_by_guid[line["LineID"]] = cur.lastrowid

    subject_id_by_guid: dict[str, int] = {}
    for subj in data.get("Subjects", []):
        cur = conn.execute(
            "INSERT INTO sfx_subject (sfx_file_id, source_guid, code, name, units, class_size_maximum) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (sfx_file_id, subj.get("SubjectID"), subj.get("Code", ""), subj.get("Name"),
             subj.get("Units"), subj.get("ClassSizeMaximum")),
        )
        if subj.get("SubjectID"):
            subject_id_by_guid[subj["SubjectID"]] = cur.lastrowid

    option_id_by_guid: dict[str, int] = {}
    for opt in data.get("Options", []):
        cur = conn.execute(
            "INSERT INTO sfx_option (sfx_file_id, source_guid, sfx_subject_id, code, name) "
            "VALUES (?, ?, ?, ?, ?)",
            (sfx_file_id, opt.get("OptionID"), subject_id_by_guid.get(opt.get("SubjectID")),
             opt.get("OptionCode"), opt.get("OptionName")),
        )
        if opt.get("OptionID"):
            option_id_by_guid[opt["OptionID"]] = cur.lastrowid

    class_id_by_guid: dict[str, int] = {}
    for cls in data.get("Classes", []):
        cur = conn.execute(
            "INSERT INTO sfx_class (sfx_file_id, source_guid, sfx_option_id, sfx_line_id, class_code, "
            "subject_code, roll_class_code, max_class_size) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (sfx_file_id, cls.get("ClassID"), option_id_by_guid.get(cls.get("OptionID")),
             line_id_by_guid.get(cls.get("LineID")), cls.get("ClassCode"), cls.get("SubjectCode"),
             cls.get("RollClassCode"), cls.get("Maximum Class Size")),
        )
        if cls.get("ClassID"):
            class_id_by_guid[cls["ClassID"]] = cur.lastrowid

    student_id_by_code = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM student")}
    preference_count = 0
    unlinked_students: set[str] = set()
    for s in students:
        code = s.get("StudentCode")
        if not code:
            continue
        student_id = student_id_by_code.get(code)
        if student_id is None:
            unlinked_students.add(code)
        for order, pref in enumerate(s.get("StudentPreferences", []), start=1):
            conn.execute(
                "INSERT INTO sfx_student_preference (sfx_file_id, student_id, student_code, sfx_option_id, "
                "sfx_class_id, preference_order) VALUES (?, ?, ?, ?, ?, ?)",
                (sfx_file_id, student_id, code, option_id_by_guid.get(pref.get("OptionID")),
                 class_id_by_guid.get(pref.get("ClassID")), order),
            )
            preference_count += 1

    if unlinked_students:
        _log(conn, ingest_run_id, "sfx_students_not_in_tfx", "info",
             f"{path.name}: {len(unlinked_students)} student code(s) have no match in the current "
             "timetable - expected for planning files covering future enrolments. Preferences kept "
             "by code only.",
             {"file": path.name, "count": len(unlinked_students)})

    for constraint in data.get("Constraints", []):
        cur = conn.execute(
            "INSERT INTO sfx_constraint (sfx_file_id, source_guid, type_str, note, limit_value) "
            "VALUES (?, ?, ?, ?, ?)",
            (sfx_file_id, constraint.get("ConstraintID"), constraint.get("TypeStr"),
             constraint.get("Note"), constraint.get("Limit")),
        )
        constraint_id = cur.lastrowid
        for co in constraint.get("ConstraintOptions", []):
            conn.execute(
                "INSERT INTO sfx_constraint_option (sfx_constraint_id, sfx_option_id) VALUES (?, ?)",
                (constraint_id, option_id_by_guid.get(co.get("OptionID"))),
            )

    conn.commit()
    return {
        "lines": len(line_id_by_guid),
        "subjects": len(subject_id_by_guid),
        "options": len(option_id_by_guid),
        "classes": len(class_id_by_guid),
        "preferences": preference_count,
        "unlinked_students": len(unlinked_students),
    }


def ingest_all_sfx(conn: sqlite3.Connection, paths: list[Path], ingest_run_id: int) -> dict[str, dict[str, int]]:
    """Ingests every .sfx found; a folder with none is fine (returns {})."""
    results = {}
    for path in paths:
        results[path.name] = ingest_sfx_file(conn, path, ingest_run_id)
    return results
