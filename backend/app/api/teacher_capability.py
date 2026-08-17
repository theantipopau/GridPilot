"""Review queue for teacher_capability candidates - "permission to
teach" (docs/roadmap-v2.md 2.2). Same shape as app/api/room_constraints.py:
approve resolves a bootstrapped candidate to ELIGIBLE, reject to
NOT_ELIGIBLE - capability_status IS the review state here, unlike
class_room_type_constraint's separate review_status column, since the
addendum's tri-state (ELIGIBLE/NOT_ELIGIBLE/REVIEW_REQUIRED) already
carries that meaning directly."""

import datetime as dt
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.analysis.run import run_analysis
from app.api.deps import get_db, get_db_writable
from app.audit import log_event

router = APIRouter()


def _serialize(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "teacher_code": row["teacher_code"],
        "faculty_code": row["faculty_code"],
        "subject_code": row["subject_code"],
        "capability_status": row["capability_status"],
        "source_type": row["source_type"],
        "notes": row["notes"],
        "effective_from": row["effective_from"],
        "effective_to": row["effective_to"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@router.get("/teacher-capabilities/candidates")
def list_teacher_capability_candidates(
    capability_status: str | None = Query(None, pattern="^(ELIGIBLE|NOT_ELIGIBLE|REVIEW_REQUIRED)$"),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    sql = "SELECT * FROM teacher_capability WHERE subject_code IS NOT NULL"
    params: list = []
    if capability_status:
        sql += " AND capability_status = ?"
        params.append(capability_status)
    sql += " ORDER BY teacher_code, subject_code"

    rows = conn.execute(sql, params).fetchall()
    return {"candidates": [_serialize(r) for r in rows]}


class ReviewRequest(BaseModel):
    reviewed_by: str
    note: str | None = None


def _review(candidate_id: int, status: str, request: ReviewRequest, conn: sqlite3.Connection) -> dict:
    existing = conn.execute("SELECT id, teacher_code, subject_code FROM teacher_capability WHERE id = ?", (candidate_id,)).fetchone()
    if existing is None:
        raise HTTPException(status_code=404, detail=f"No teacher-capability candidate {candidate_id}")

    now = dt.datetime.now(dt.UTC).isoformat()
    conn.execute(
        "UPDATE teacher_capability SET capability_status = ?, updated_at = ? WHERE id = ?",
        (status, now, candidate_id),
    )
    log_event(
        conn, "teacher_capability_reviewed",
        f"{existing['teacher_code']} x {existing['subject_code']} marked {status}",
        actor=request.reviewed_by, entity_type="teacher_capability", entity_id=candidate_id,
        detail={"capability_status": status, "note": request.note},
    )
    conn.commit()
    conn.close()

    # Re-run the rules engine so teacher_not_qualified_for_class reflects the review decision immediately.
    run_analysis()

    return {"id": candidate_id, "capability_status": status}


@router.post("/teacher-capabilities/candidates/{candidate_id}/approve")
def approve_teacher_capability_candidate(
    candidate_id: int, request: ReviewRequest, conn: sqlite3.Connection = Depends(get_db_writable)
) -> dict:
    return _review(candidate_id, "ELIGIBLE", request, conn)


@router.post("/teacher-capabilities/candidates/{candidate_id}/reject")
def reject_teacher_capability_candidate(
    candidate_id: int, request: ReviewRequest, conn: sqlite3.Connection = Depends(get_db_writable)
) -> dict:
    return _review(candidate_id, "NOT_ELIGIBLE", request, conn)
