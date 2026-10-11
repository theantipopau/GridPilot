"""Authored-people API - adding new students and staff between exports.

Everything here writes to app/db/schema.sql's authored_student /
authored_teacher tables, never to the exported `student`/`teacher`
rows - those are rebuilt from the .tfx on every ingest (see
app/db/resync.py), so any direct write would be silently wiped. The
tables are deliberately not in resync's delete list: an authored person
survives re-ingest, and when a later export gains their code, the
authored copy is automatically retired (remove_superseded_authored_
people, called from resync during every re-ingest).

Merging into the UI reads happens over in the existing list endpoints
(teachers.py, students listing) by LEFT JOINing these tables in, so the
pages show one combined roster flagged by source rather than two
separate lists the user has to keep apart in their head.
"""

import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.analysis.authored_people import (
    add_authored_student,
    add_authored_teacher,
    authored_people,
    update_authored_student,
    update_authored_teacher,
)
from app.api.deps import get_db, get_db_writable

router = APIRouter()


@router.get("/students")
def list_students(conn: sqlite3.Connection = Depends(get_db)) -> dict:
    """The People/Students roster: exported students (read-only facts from
    the current .tfx) merged with authored students (added here between
    exports), one list flagged by `source`. The export stays the source
    of truth for everything it carries; authored rows survive re-ingest
    until the export learns the same code, at which point resync.py
    retires the authored copy automatically."""
    students = [
        dict(r) | {"source": "EXPORTED"}
        for r in conn.execute(
            """
            SELECT s.code, s.first_name, s.last_name, s.preferred_name, s.gender,
                   s.house, s.home_group, s.email,
                   rc.code AS roll_class_code, yl.code AS year_level_code
            FROM student s
            LEFT JOIN roll_class rc ON rc.id = s.roll_class_id
            LEFT JOIN year_level yl ON yl.id = s.year_level_id
            ORDER BY s.last_name, s.first_name
            """
        )
    ]
    authored = [
        dict(r) | {"source": "AUTHORED"}
        for r in conn.execute(
            """
            SELECT code, first_name, last_name, preferred_name, gender,
                   house, home_group, email,
                   roll_class_code, year_level_code
            FROM authored_student
            ORDER BY last_name, first_name
            """
        )
    ]
    return {
        "students": students + authored,
        "authored_count": len(authored),
    }


@router.get("/authored-people")
def get_authored_people(conn: sqlite3.Connection = Depends(get_db_writable)) -> dict:
    """Diagnostic/debug view of exactly what's authored vs what came in
    on the export - the main list pages merge this in themselves."""
    return authored_people(conn)


class AuthoredStudentRequest(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    first_name: str | None = None
    last_name: str | None = None
    preferred_name: str | None = None
    gender: str | None = None
    roll_class_code: str | None = None
    year_level_code: str | None = None
    house: str | None = None
    home_group: str | None = None
    email: str | None = None
    entered_by: str = Field(min_length=1)


@router.post("/authored-students")
def post_authored_student(request: AuthoredStudentRequest, conn: sqlite3.Connection = Depends(get_db_writable)) -> dict:
    """Adding a student no export has ever carried. Refuses a code that
    exists in the export OR this table (a duplicate submit can't create
    two rows for one student) - 409, not 500, because it's an expected
    user mistake worth guiding them on."""
    try:
        authored_student_id = add_authored_student(conn, **request.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return {"id": authored_student_id, "code": request.code, "source": "AUTHORED"}


class UpdateAuthoredStudentRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    preferred_name: str | None = None
    gender: str | None = None
    roll_class_code: str | None = None
    year_level_code: str | None = None
    house: str | None = None
    home_group: str | None = None
    email: str | None = None
    updated_by: str = Field(min_length=1)


@router.post("/authored-students/{code}")
def post_update_authored_student(
    code: str, request: UpdateAuthoredStudentRequest, conn: sqlite3.Connection = Depends(get_db_writable)
) -> dict:
    try:
        update_authored_student(conn, code, **request.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"code": code, "source": "AUTHORED"}


class AuthoredTeacherRequest(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    staff_category: Literal["TEACHER", "GUIDANCE_COUNSELLOR", "SUPPORT_OFFICER", "COLLEGE_LEADERSHIP"] | None = None
    contracted_load_minutes: float | None = Field(default=None, ge=0)
    faculty_codes: list[str] = Field(default_factory=list)
    entered_by: str = Field(min_length=1)


@router.post("/authored-teachers")
def post_authored_teacher(request: AuthoredTeacherRequest, conn: sqlite3.Connection = Depends(get_db_writable)) -> dict:
    try:
        authored_teacher_id = add_authored_teacher(conn, **request.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return {"id": authored_teacher_id, "code": request.code, "source": "AUTHORED"}


class UpdateAuthoredTeacherRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    staff_category: Literal["TEACHER", "GUIDANCE_COUNSELLOR", "SUPPORT_OFFICER", "COLLEGE_LEADERSHIP"] | None = None
    contracted_load_minutes: float | None = Field(default=None, ge=0)
    faculty_codes: list[str] = Field(default_factory=list)
    updated_by: str = Field(min_length=1)


@router.post("/authored-teachers/{code}")
def post_update_authored_teacher(
    code: str, request: UpdateAuthoredTeacherRequest, conn: sqlite3.Connection = Depends(get_db_writable)
) -> dict:
    try:
        update_authored_teacher(conn, code, **request.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"code": code, "source": "AUTHORED"}
