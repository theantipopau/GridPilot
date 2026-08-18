"""Teacher list/detail, staff-role (middle-leadership tier) assignment,
and registration/career-stage profile (docs/roadmap-v2.md 2.4) - the
'People' section from the UI mockups. Name/code/faculty/load are
read-only, sourced from the .tfx import; role assignment and profile are
the only things ever written here, and only by explicit human action -
never inferred. See schema.sql's staff_role/teacher_role_assignment/
teacher_profile for why all three are keyed by teacher code, not
teacher.id."""

import datetime as dt
import sqlite3
from collections import defaultdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_db, get_db_writable
from app.audit import log_event

router = APIRouter()


def _scheduled_minutes_by_teacher(conn: sqlite3.Connection) -> dict[int, float]:
    """Distinct (teacher, period) minutes - a composite lesson (same
    teacher/room, multiple class codes at once) must count once, not once
    per class code sharing the slot. Same method as
    app.analysis.load_rules.teacher_over_contracted_load."""
    rows = conn.execute(
        """
        SELECT te.teacher_id, te.period_id, p.load_minutes
        FROM timetable_entry te
        JOIN period p ON p.id = te.period_id
        WHERE te.entry_type = 'LESSON' AND te.teacher_id IS NOT NULL
        """
    ).fetchall()
    slots: dict[int, dict[int, float]] = defaultdict(dict)
    for r in rows:
        slots[r["teacher_id"]][r["period_id"]] = r["load_minutes"]
    return {tid: sum(periods.values()) for tid, periods in slots.items()}


def _profile_by_teacher_code(conn: sqlite3.Connection) -> dict[str, dict]:
    rows = conn.execute(
        "SELECT teacher_code, registration_status, career_stage, commenced_teaching_date, fte FROM teacher_profile"
    ).fetchall()
    return {
        r["teacher_code"]: {
            "registration_status": r["registration_status"],
            "career_stage": r["career_stage"],
            "commenced_teaching_date": r["commenced_teaching_date"],
            "fte": r["fte"],
        }
        for r in rows
    }


def _role_by_teacher_code(conn: sqlite3.Connection) -> dict[str, dict]:
    rows = conn.execute(
        """
        SELECT tra.teacher_code, sr.id, sr.name, sr.tier, sr.release_minutes_per_cycle
        FROM teacher_role_assignment tra
        JOIN staff_role sr ON sr.id = tra.staff_role_id
        """
    ).fetchall()
    return {
        r["teacher_code"]: {
            "id": r["id"],
            "name": r["name"],
            "tier": r["tier"],
            "release_minutes_per_cycle": r["release_minutes_per_cycle"],
        }
        for r in rows
    }


@router.get("/teachers")
def list_teachers(conn: sqlite3.Connection = Depends(get_db)) -> dict:
    scheduled = _scheduled_minutes_by_teacher(conn)
    roles = _role_by_teacher_code(conn)
    profiles = _profile_by_teacher_code(conn)
    rows = conn.execute(
        """
        SELECT t.id, t.code, t.first_name, t.last_name, t.staff_category, t.contracted_load_minutes,
               GROUP_CONCAT(DISTINCT f.code) AS faculty_codes
        FROM teacher t
        LEFT JOIN teacher_faculty tf ON tf.teacher_id = t.id
        LEFT JOIN faculty f ON f.id = tf.faculty_id
        GROUP BY t.id
        ORDER BY t.last_name, t.first_name
        """
    ).fetchall()
    return {
        "teachers": [
            {
                "code": r["code"],
                "first_name": r["first_name"],
                "last_name": r["last_name"],
                "staff_category": r["staff_category"],
                "faculty_codes": r["faculty_codes"].split(",") if r["faculty_codes"] else [],
                "contracted_load_minutes": r["contracted_load_minutes"],
                "scheduled_load_minutes": scheduled.get(r["id"]),
                "role": roles.get(r["code"]),
                "profile": profiles.get(r["code"]),
            }
            for r in rows
        ]
    }


@router.get("/teachers/{code}")
def get_teacher(code: str, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    row = conn.execute(
        "SELECT id, code, first_name, last_name, staff_category, contracted_load_minutes FROM teacher WHERE code = ?",
        (code,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No teacher {code!r}")

    faculties = [
        r["code"] for r in conn.execute(
            "SELECT f.code FROM teacher_faculty tf JOIN faculty f ON f.id = tf.faculty_id WHERE tf.teacher_id = ?",
            (row["id"],),
        )
    ]

    return {
        "code": row["code"],
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "staff_category": row["staff_category"],
        "faculty_codes": faculties,
        "contracted_load_minutes": row["contracted_load_minutes"],
        "scheduled_load_minutes": _scheduled_minutes_by_teacher(conn).get(row["id"]),
        "role": _role_by_teacher_code(conn).get(code),
        "profile": _profile_by_teacher_code(conn).get(code),
    }


@router.get("/roles")
def list_roles(conn: sqlite3.Connection = Depends(get_db)) -> dict:
    rows = conn.execute(
        "SELECT id, name, tier, release_minutes_per_cycle, notes FROM staff_role ORDER BY tier, name"
    ).fetchall()
    return {"roles": [dict(r) for r in rows]}


class CreateRoleRequest(BaseModel):
    name: str
    tier: str | None = None
    release_minutes_per_cycle: float | None = None
    notes: str | None = None


@router.post("/roles")
def create_role(request: CreateRoleRequest, conn: sqlite3.Connection = Depends(get_db_writable)) -> dict:
    try:
        cur = conn.execute(
            "INSERT INTO staff_role (name, tier, release_minutes_per_cycle, notes, created_at) VALUES (?, ?, ?, ?, ?)",
            (request.name, request.tier, request.release_minutes_per_cycle, request.notes,
             dt.datetime.now(dt.UTC).isoformat()),
        )
    except sqlite3.IntegrityError as e:
        raise HTTPException(status_code=400, detail=f"A role named {request.name!r} already exists") from e
    conn.commit()
    return {"id": cur.lastrowid}


class AssignRoleRequest(BaseModel):
    staff_role_id: int | None  # null unassigns
    assigned_by: str


@router.post("/teachers/{code}/role")
def assign_role(code: str, request: AssignRoleRequest, conn: sqlite3.Connection = Depends(get_db_writable)) -> dict:
    teacher = conn.execute("SELECT id FROM teacher WHERE code = ?", (code,)).fetchone()
    if teacher is None:
        raise HTTPException(status_code=404, detail=f"No teacher {code!r}")

    conn.execute("DELETE FROM teacher_role_assignment WHERE teacher_code = ?", (code,))

    if request.staff_role_id is not None:
        role = conn.execute("SELECT id, name FROM staff_role WHERE id = ?", (request.staff_role_id,)).fetchone()
        if role is None:
            raise HTTPException(status_code=400, detail=f"No role {request.staff_role_id}")
        conn.execute(
            "INSERT INTO teacher_role_assignment (teacher_code, staff_role_id, assigned_at, assigned_by) "
            "VALUES (?, ?, ?, ?)",
            (code, request.staff_role_id, dt.datetime.now(dt.UTC).isoformat(), request.assigned_by),
        )
        log_event(
            conn, "teacher_role_assigned", f"Teacher {code} assigned role {role['name']!r}",
            actor=request.assigned_by, entity_type="teacher", entity_id=code,
            detail={"teacher_code": code, "role_id": request.staff_role_id, "role_name": role["name"]},
        )
    else:
        log_event(
            conn, "teacher_role_unassigned", f"Teacher {code} role unassigned",
            actor=request.assigned_by, entity_type="teacher", entity_id=code,
        )

    conn.commit()
    return {"teacher_code": code, "staff_role_id": request.staff_role_id}


class UpdateProfileRequest(BaseModel):
    registration_status: Literal["PROVISIONAL", "FULL", "UNKNOWN"] | None = None
    career_stage: Literal["GRADUATE", "EARLY_CAREER", "EXPERIENCED", "UNKNOWN"] | None = None
    commenced_teaching_date: str | None = None
    fte: float | None = None
    updated_by: str


@router.post("/teachers/{code}/profile")
def update_profile(code: str, request: UpdateProfileRequest, conn: sqlite3.Connection = Depends(get_db_writable)) -> dict:
    """Registration/career-stage/FTE - none of it in the .tfx/.sfx export
    (docs/roadmap-v2.md 2.4), entered here and only here. Upserted by
    teacher_code, not linked to any internal teacher.id - see schema.sql's
    teacher_profile comment for why."""
    teacher = conn.execute("SELECT id FROM teacher WHERE code = ?", (code,)).fetchone()
    if teacher is None:
        raise HTTPException(status_code=404, detail=f"No teacher {code!r}")
    if request.fte is not None and not (0 < request.fte <= 1.0):
        raise HTTPException(status_code=400, detail="fte must be between 0 (exclusive) and 1.0")

    now = dt.datetime.now(dt.UTC).isoformat()
    conn.execute(
        """
        INSERT INTO teacher_profile
            (teacher_code, registration_status, career_stage, commenced_teaching_date, fte, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(teacher_code) DO UPDATE SET
            registration_status = excluded.registration_status,
            career_stage = excluded.career_stage,
            commenced_teaching_date = excluded.commenced_teaching_date,
            fte = excluded.fte,
            updated_at = excluded.updated_at,
            updated_by = excluded.updated_by
        """,
        (code, request.registration_status, request.career_stage, request.commenced_teaching_date,
         request.fte, now, request.updated_by),
    )
    log_event(
        conn, "teacher_profile_updated", f"Teacher {code} profile updated",
        actor=request.updated_by, entity_type="teacher", entity_id=code,
        detail={
            "teacher_code": code, "registration_status": request.registration_status,
            "career_stage": request.career_stage, "commenced_teaching_date": request.commenced_teaching_date,
            "fte": request.fte,
        },
    )
    conn.commit()
    return {"teacher_code": code, **_profile_by_teacher_code(conn)[code]}
