import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_db, get_db_writable
from app.changes.service import (
    ChangeSetError,
    add_proposed_change,
    approve_change_set,
    create_change_set,
    reject_change_set,
    remove_proposed_change,
    validate_change_set,
)

router = APIRouter()


def _serialize_change(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    def code(table: str, entry_id: int | None) -> str | None:
        if entry_id is None:
            return None
        r = conn.execute(f"SELECT code FROM {table} WHERE id = ?", (entry_id,)).fetchone()
        return r["code"] if r else None

    finding_ids = [
        r["finding_id"] for r in conn.execute(
            "SELECT finding_id FROM proposed_change_finding WHERE proposed_change_id = ?", (row["id"],)
        )
    ]
    return {
        "id": row["id"],
        "timetable_entry_id": row["timetable_entry_id"],
        "before": {
            "day_code": code("day", row["before_day_id"]),
            "period_code": code("period", row["before_period_id"]),
            "room_code": code("room", row["before_room_id"]),
            "teacher_code": code("teacher", row["before_teacher_id"]),
        },
        "after": {
            "day_code": code("day", row["after_day_id"]),
            "period_code": code("period", row["after_period_id"]),
            "room_code": code("room", row["after_room_id"]),
            "teacher_code": code("teacher", row["after_teacher_id"]),
        },
        "reason": row["reason"],
        "finding_ids": finding_ids,
    }


def _serialize_change_set(conn: sqlite3.Connection, change_set_id: int) -> dict:
    cs = conn.execute("SELECT * FROM change_set WHERE id = ?", (change_set_id,)).fetchone()
    if cs is None:
        raise HTTPException(status_code=404, detail=f"No change set {change_set_id}")

    changes = conn.execute(
        "SELECT * FROM proposed_change WHERE change_set_id = ? ORDER BY id", (change_set_id,)
    ).fetchall()

    return {
        "id": cs["id"],
        "name": cs["name"],
        "description": cs["description"],
        "validation_status": cs["validation_status"],
        "validation_result": json.loads(cs["validation_result_json"]) if cs["validation_result_json"] else None,
        "validated_at": cs["validated_at"],
        "approval_status": cs["approval_status"],
        "reviewed_at": cs["reviewed_at"],
        "reviewed_by": cs["reviewed_by"],
        "created_at": cs["created_at"],
        "created_by": cs["created_by"],
        "changes": [_serialize_change(conn, c) for c in changes],
    }


@router.get("/change-sets")
def list_change_sets(conn: sqlite3.Connection = Depends(get_db)) -> dict:
    rows = conn.execute(
        "SELECT cs.*, (SELECT COUNT(*) FROM proposed_change pc WHERE pc.change_set_id = cs.id) AS change_count "
        "FROM change_set cs ORDER BY cs.id DESC"
    ).fetchall()
    return {
        "change_sets": [
            {
                "id": r["id"],
                "name": r["name"],
                "description": r["description"],
                "validation_status": r["validation_status"],
                "approval_status": r["approval_status"],
                "created_at": r["created_at"],
                "created_by": r["created_by"],
                "change_count": r["change_count"],
            }
            for r in rows
        ]
    }


@router.get("/change-sets/{change_set_id}")
def get_change_set(change_set_id: int, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return _serialize_change_set(conn, change_set_id)


class CreateChangeSetRequest(BaseModel):
    name: str
    description: str | None = None
    created_by: str


@router.post("/change-sets")
def create_change_set_endpoint(request: CreateChangeSetRequest, conn: sqlite3.Connection = Depends(get_db_writable)) -> dict:
    change_set_id = create_change_set(conn, request.name, request.description, request.created_by)
    return {"id": change_set_id}


class AddChangeRequest(BaseModel):
    """Codes, not internal ids - matches every other public endpoint
    (reference/timetable) and avoids the frontend ever needing to know a
    raw database id. after_day_code/after_period_code must be given
    together (a period code alone, e.g. 'P2', repeats on every day)."""

    timetable_entry_id: int
    after_day_code: str | None = None
    after_period_code: str | None = None
    after_room_code: str | None = None
    after_teacher_code: str | None = None
    reason: str | None = None
    finding_ids: list[int] = []


def _resolve_period(conn: sqlite3.Connection, day_code: str, period_code: str) -> tuple[int, int]:
    row = conn.execute(
        "SELECT p.id AS period_id, p.day_id FROM period p JOIN day d ON d.id = p.day_id "
        "WHERE d.code = ? AND p.code = ?",
        (day_code, period_code),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=400, detail=f"No period {period_code!r} on day {day_code!r}")
    return row["day_id"], row["period_id"]


def _resolve_code(conn: sqlite3.Connection, table: str, code: str) -> int:
    row = conn.execute(f"SELECT id FROM {table} WHERE code = ?", (code,)).fetchone()
    if row is None:
        raise HTTPException(status_code=400, detail=f"No {table} with code {code!r}")
    return row["id"]


@router.post("/change-sets/{change_set_id}/changes")
def add_change(change_set_id: int, request: AddChangeRequest, conn: sqlite3.Connection = Depends(get_db_writable)) -> dict:
    if bool(request.after_day_code) != bool(request.after_period_code):
        raise HTTPException(status_code=400, detail="after_day_code and after_period_code must be given together")

    after_day_id = after_period_id = None
    if request.after_day_code and request.after_period_code:
        after_day_id, after_period_id = _resolve_period(conn, request.after_day_code, request.after_period_code)

    after_room_id = _resolve_code(conn, "room", request.after_room_code) if request.after_room_code else None
    after_teacher_id = _resolve_code(conn, "teacher", request.after_teacher_code) if request.after_teacher_code else None

    try:
        change_id = add_proposed_change(
            conn, change_set_id, request.timetable_entry_id,
            after_day_id=after_day_id, after_period_id=after_period_id,
            after_room_id=after_room_id, after_teacher_id=after_teacher_id,
            reason=request.reason, finding_ids=request.finding_ids,
        )
    except ChangeSetError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"id": change_id}


@router.delete("/change-sets/{change_set_id}/changes/{change_id}")
def delete_change(change_set_id: int, change_id: int, conn: sqlite3.Connection = Depends(get_db_writable)) -> dict:
    try:
        remove_proposed_change(conn, change_set_id, change_id)
    except ChangeSetError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"status": "removed"}


@router.post("/change-sets/{change_set_id}/validate")
def validate_endpoint(change_set_id: int, conn: sqlite3.Connection = Depends(get_db_writable)) -> dict:
    try:
        return validate_change_set(conn, change_set_id)
    except ChangeSetError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


class ReviewChangeSetRequest(BaseModel):
    reviewed_by: str


@router.post("/change-sets/{change_set_id}/approve")
def approve_endpoint(change_set_id: int, request: ReviewChangeSetRequest, conn: sqlite3.Connection = Depends(get_db_writable)) -> dict:
    try:
        approve_change_set(conn, change_set_id, request.reviewed_by)
    except ChangeSetError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"id": change_set_id, "approval_status": "APPROVED"}


@router.post("/change-sets/{change_set_id}/reject")
def reject_endpoint(change_set_id: int, request: ReviewChangeSetRequest, conn: sqlite3.Connection = Depends(get_db_writable)) -> dict:
    try:
        reject_change_set(conn, change_set_id, request.reviewed_by)
    except ChangeSetError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"id": change_set_id, "approval_status": "REJECTED"}
