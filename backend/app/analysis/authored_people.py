"""Authored people - new students and staff the school adds *between*
exports, which no .tfx/.sfx export knows about yet.

`student` and `teacher` are source-derived tables (app/db/resync.py
SOURCE_TABLES_IN_DELETE_ORDER): fully rebuilt from the export on every
ingest, with new surrogate ids each time. Writing an authored row
directly into either would be silently wiped on the next import - the
same mistake teacher_profile originally avoided by keying off teacher
*code*, not id.

Design, matching every other app-owned table in schema.sql:
- Two companion tables, `authored_student` and `authored_teacher`, keyed
  by the same code the source export uses. Neither ever stores a value
  for a teacher/student that exists in the current export - writing an
  edit to one of those is a correction to a source fact, and this app's
  standing rule is that the export stays the source of truth.
- The API layer exposes them as "new" students/teachers merged into the
  normal list pages, flagged with source: "AUTHORED" vs "EXPORTED",
  so the UI never has to know which table a row came from.
- Every insert/update logs an audit event - people data is exactly the
  kind of fact that needs the append-only trail (who added a student,
  when, and what their roll class was at the time).
"""

import datetime as dt
import json
import sqlite3

from app.audit import log_event

MAX_CODE_LENGTH = 20
MAX_NAME_LENGTH = 100


def _now() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def _validate_code(code: str, entity_name: str) -> str:
    """Normalise and reject an empty/oversized code. Codes are what every
    other table joins people on (see schema.sql's `student.code UNIQUE`,
    `teacher.code UNIQUE`) - a code that duplicates one in the current
    export means "this student/teacher already came in on the last
    import" and is refused, never merged."""
    code = code.strip()
    if not code:
        raise ValueError(f"An empty code is not a valid {entity_name} code.")
    if len(code) > MAX_CODE_LENGTH:
        raise ValueError(f"{entity_name} code exceeds {MAX_CODE_LENGTH} characters: {code!r}")
    return code


def _validate_names(fields: dict[str, str | None], entity_name: str) -> None:
    for key, value in fields.items():
        if value is None:
            continue
        if len(value.strip()) > MAX_NAME_LENGTH:
            raise ValueError(f"{entity_name} {key} exceeds {MAX_NAME_LENGTH} characters")


def add_authored_student(
    conn: sqlite3.Connection,
    *,
    code: str,
    first_name: str | None = None,
    last_name: str | None = None,
    preferred_name: str | None = None,
    gender: str | None = None,
    roll_class_code: str | None = None,
    year_level_code: str | None = None,
    house: str | None = None,
    home_group: str | None = None,
    email: str | None = None,
    entered_by: str,
) -> int:
    """Insert a new student that no export has ever carried. Refuses a
    code that already exists in either the export or this table, so a
    double-submit can't silently create two rows for one student."""
    code = _validate_code(code, "student")
    # An exported row with the same code means this student already arrived
    # via the last import - refusing (never silently merging) is the same
    # discipline resync.py applies to every human decision.
    if conn.execute("SELECT 1 FROM student WHERE code = ?", (code,)).fetchone():
        raise ValueError(
            f"Student {code!r} is already in the current export - edit it there (re-export), "
            "not here; this table only holds students no export has ever carried."
        )
    _validate_names({
        "first_name": first_name, "last_name": last_name,
        "preferred_name": preferred_name, "email": email,
    }, "student")

    roll_class_id = None
    if roll_class_code:
        row = conn.execute("SELECT id FROM roll_class WHERE code = ?", (roll_class_code,)).fetchone()
        if row is None:
            raise ValueError(f"No roll class {roll_class_code!r} in the current export.")
        roll_class_id = row["id"]

    year_level_id = None
    if year_level_code:
        row = conn.execute("SELECT id FROM year_level WHERE code = ?", (year_level_code,)).fetchone()
        if row is None:
            raise ValueError(f"No year level {year_level_code!r} in the current export.")
        year_level_id = row["id"]

    now = _now()
    try:
        cur = conn.execute(
            """
            INSERT INTO authored_student
                (code, first_name, last_name, preferred_name, gender, roll_class_code,
                 year_level_code, house, home_group, email, created_at, updated_at, updated_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (code, first_name, last_name, preferred_name, gender, roll_class_code,
             year_level_code, house, home_group, email, now, now, entered_by),
        )
    except sqlite3.IntegrityError as e:
        raise ValueError(
            f"A student with code {code!r} already exists - either they came in on the last "
            "export, or they were added here before."
        ) from e
    conn.commit()
    log_event(
        conn, "authored_student_added", f"Student {code} added in GridPilot (not present in the last export)",
        actor=entered_by, entity_type="student", entity_id=code,
        detail={"student_code": code, "roll_class_code": roll_class_code, "year_level_code": year_level_code},
    )
    conn.commit()
    return cur.lastrowid


def update_authored_student(
    conn: sqlite3.Connection,
    code: str,
    *,
    first_name: str | None = None,
    last_name: str | None = None,
    preferred_name: str | None = None,
    gender: str | None = None,
    roll_class_code: str | None = None,
    year_level_code: str | None = None,
    house: str | None = None,
    home_group: str | None = None,
    email: str | None = None,
    updated_by: str,
) -> None:
    """Update an *authored* student's facts. Editing an exported student
    is deliberately out of scope: that would mean GridPilot disagreeing
    with the source export, which re-ingest would then silently undo."""
    _validate_names({
        "first_name": first_name, "last_name": last_name,
        "preferred_name": preferred_name, "email": email,
    }, "student")

    if roll_class_code is not None:
        row = conn.execute("SELECT id FROM roll_class WHERE code = ?", (roll_class_code,)).fetchone()
        if row is None:
            raise ValueError(f"No roll class {roll_class_code!r} in the current export.")

    if year_level_code is not None:
        row = conn.execute("SELECT id FROM year_level WHERE code = ?", (year_level_code,)).fetchone()
        if row is None:
            raise ValueError(f"No year level {year_level_code!r} in the current export.")

    cur = conn.execute(
        """
        UPDATE authored_student SET
            first_name = ?, last_name = ?, preferred_name = ?, gender = ?,
            roll_class_code = ?, year_level_code = ?, house = ?, home_group = ?,
            email = ?, updated_at = ?, updated_by = ?
        WHERE code = ?
        """,
        (first_name, last_name, preferred_name, gender, roll_class_code, year_level_code,
         house, home_group, email, _now(), updated_by, code),
    )
    if cur.rowcount == 0:
        raise ValueError(f"No authored student {code!r} - students that came from the export can't be edited here.")
    conn.commit()
    log_event(
        conn, "authored_student_updated", f"Authored student {code} updated",
        actor=updated_by, entity_type="student", entity_id=code,
        detail={"student_code": code},
    )
    conn.commit()


def add_authored_teacher(
    conn: sqlite3.Connection,
    *,
    code: str,
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
    staff_category: str | None = None,
    contracted_load_minutes: float | None = None,
    faculty_codes: list[str] | None = None,
    entered_by: str,
) -> int:
    """Insert a new teacher the export doesn't know about. Same rule as
    add_authored_student: a code that collides with either the export or
    this table is refused, never merged."""
    code = _validate_code(code, "teacher")
    if conn.execute("SELECT 1 FROM teacher WHERE code = ?", (code,)).fetchone():
        raise ValueError(
            f"Teacher {code!r} is already in the current export - edit it there (re-export), "
            "not here; this table only holds teachers no export has ever carried."
        )
    _validate_names({"first_name": first_name, "last_name": last_name, "email": email}, "teacher")

    if staff_category is not None and staff_category not in (
        "TEACHER", "GUIDANCE_COUNSELLOR", "SUPPORT_OFFICER", "COLLEGE_LEADERSHIP"
    ):
        raise ValueError(
            f"staff_category {staff_category!r} isn't one the app recognises - "
            "use TEACHER, GUIDANCE_COUNSELLOR, SUPPORT_OFFICER or COLLEGE_LEADERSHIP."
        )

    for faculty_code in faculty_codes or []:
        row = conn.execute("SELECT id FROM faculty WHERE code = ?", (faculty_code,)).fetchone()
        if row is None:
            raise ValueError(f"No faculty {faculty_code!r} in the current export.")

    now = _now()
    try:
        cur = conn.execute(
            """
            INSERT INTO authored_teacher
                (code, first_name, last_name, email, staff_category, contracted_load_minutes,
                 faculty_codes_json, created_at, updated_at, updated_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (code, first_name, last_name, email, staff_category, contracted_load_minutes,
             json.dumps(faculty_codes or []), now, now, entered_by),
        )
    except sqlite3.IntegrityError as e:
        raise ValueError(
            f"A teacher with code {code!r} already exists - either they're in the current export, "
            "or they were added here before."
        ) from e
    conn.commit()
    log_event(
        conn, "authored_teacher_added", f"Teacher {code} added in GridPilot (not present in the last export)",
        actor=entered_by, entity_type="teacher", entity_id=code,
        detail={"teacher_code": code, "staff_category": staff_category,
                "faculty_codes": faculty_codes or []},
    )
    conn.commit()
    return cur.lastrowid


def update_authored_teacher(
    conn: sqlite3.Connection,
    code: str,
    *,
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
    staff_category: str | None = None,
    contracted_load_minutes: float | None = None,
    faculty_codes: list[str] | None = None,
    updated_by: str,
) -> None:
    """Update an authored teacher. Exported teachers stay readonly, same
    rule as authored students."""
    _validate_names({"first_name": first_name, "last_name": last_name, "email": email}, "teacher")

    if staff_category is not None and staff_category not in (
        "TEACHER", "GUIDANCE_COUNSELLOR", "SUPPORT_OFFICER", "COLLEGE_LEADERSHIP"
    ):
        raise ValueError(
            f"staff_category {staff_category!r} isn't one the app recognises - "
            "use TEACHER, GUIDANCE_COUNSELLOR, SUPPORT_OFFICER or COLLEGE_LEADERSHIP."
        )

    for faculty_code in faculty_codes or []:
        row = conn.execute("SELECT id FROM faculty WHERE code = ?", (faculty_code,)).fetchone()
        if row is None:
            raise ValueError(f"No faculty {faculty_code!r} in the current export.")

    cur = conn.execute(
        """
        UPDATE authored_teacher SET
            first_name = ?, last_name = ?, email = ?, staff_category = ?,
            contracted_load_minutes = ?, faculty_codes_json = ?,
            updated_at = ?, updated_by = ?
        WHERE code = ?
        """,
        (first_name, last_name, email, staff_category, contracted_load_minutes,
         json.dumps(faculty_codes or []), _now(), updated_by, code),
    )
    if cur.rowcount == 0:
        raise ValueError(f"No authored teacher {code!r} - teachers that came from the export can't be edited here.")
    conn.commit()
    log_event(
        conn, "authored_teacher_updated", f"Authored teacher {code} updated",
        actor=updated_by, entity_type="teacher", entity_id=code,
        detail={"teacher_code": code},
    )
    conn.commit()


def authored_people(conn: sqlite3.Connection) -> dict:
    """Full authored-people set, so the UI can show 'added in GridPilot,
    not yet in any export' properly, and resync.py can drop stale
    authored rows that now collide with a fresh export."""
    students = [
        dict(r) | {"faculty_codes": [], "source": "AUTHORED"}
        for r in conn.execute("SELECT * FROM authored_student ORDER BY code")
    ]
    for s in students:
        s.pop("faculty_codes_json", None)
    teachers = []
    for r in conn.execute("SELECT * FROM authored_teacher ORDER BY code"):
        teacher = dict(r) | {"source": "AUTHORED"}
        teacher["faculty_codes"] = json.loads(teacher.pop("faculty_codes_json") or "[]")
        teachers.append(teacher)
    return {"students": students, "teachers": teachers}


def remove_superseded_authored_people(conn: sqlite3.Connection) -> dict:
    """After a re-ingest, any authored row whose code now exists in the
    freshly imported export is redundant - the export is the source of
    truth, so the authored copy is removed and the fact logged."""
    dropped_students = 0
    for r in conn.execute(
        "SELECT a.code FROM authored_student a JOIN student s ON s.code = a.code"
    ).fetchall():
        conn.execute("DELETE FROM authored_student WHERE code = ?", (r["code"],))
        dropped_students += 1
        log_event(
            conn, "authored_student_superseded_by_export",
            f"Authored student {r['code']} removed - the new export now carries this student.",
            entity_type="student", entity_id=r["code"],
        )
    dropped_teachers = 0
    for r in conn.execute(
        "SELECT a.code FROM authored_teacher a JOIN teacher t ON t.code = a.code"
    ).fetchall():
        conn.execute("DELETE FROM authored_teacher WHERE code = ?", (r["code"],))
        dropped_teachers += 1
        log_event(
            conn, "authored_teacher_superseded_by_export",
            f"Authored teacher {r['code']} removed - the new export now carries this teacher.",
            entity_type="teacher", entity_id=r["code"],
        )
    conn.commit()
    return {"students": dropped_students, "teachers": dropped_teachers}
