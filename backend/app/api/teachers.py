"""Teacher list/detail and staff-role (middle-leadership tier) assignment
- the 'People' section from the UI mockups. Name/code/faculty/load are
read-only, sourced from the .tfx import; only the role assignment is
ever written here, and only by explicit human action - never inferred.
See schema.sql's staff_role/teacher_role_assignment for why role
assignments are keyed by teacher code, not teacher.id."""

import datetime as dt
import sqlite3
from collections import defaultdict

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
