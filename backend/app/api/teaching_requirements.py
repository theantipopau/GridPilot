import datetime as dt
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.analysis.run import run_analysis
from app.api.deps import get_db, get_db_writable
from app.audit import log_event

router = APIRouter()


def _serialize_candidate(conn: sqlite3.Connection, requirement_id: int) -> dict:
    r = conn.execute(
        """
        SELECT tr.id, tr.requirement_key, tr.source, tr.periods_per_cycle, tr.matching_lesson_count,
               tr.total_lesson_count, tr.planning_year, tr.lock_status, tr.allocation_priority,
               tr.review_status, tr.detected_at, tr.reviewed_at, tr.reviewed_by, tr.review_note,
               tr.composite_group_id, cn.code AS class_code, s.source_code AS subject_code,
               rc.code AS roll_class_code, at.code AS assigned_teacher_code, ar.code AS assigned_room_code
        FROM teaching_requirement tr
        LEFT JOIN class_name cn ON cn.id = tr.class_name_id
        LEFT JOIN subject s ON s.id = tr.subject_id
        LEFT JOIN roll_class rc ON rc.id = tr.roll_class_id
        LEFT JOIN teacher at ON at.id = tr.assigned_teacher_id
        LEFT JOIN room ar ON ar.id = tr.assigned_room_id
        WHERE tr.id = ?
        """,
        (requirement_id,),
    ).fetchone()
    if r is None:
        raise HTTPException(status_code=404, detail=f"No teaching-requirement candidate {requirement_id}")

    member_class_codes = None
    if r["composite_group_id"] is not None:
        member_class_codes = [
            row["code"]
            for row in conn.execute(
                "SELECT cn.code AS code FROM composite_group_member cgm "
                "JOIN class_name cn ON cn.id = cgm.class_name_id WHERE cgm.composite_group_id = ? ORDER BY cn.code",
                (r["composite_group_id"],),
            )
        ]

    return {
        "id": r["id"],
        "requirement_key": r["requirement_key"],
        "source": r["source"],
        "class_code": r["class_code"],
        "member_class_codes": member_class_codes,
        "subject_code": r["subject_code"],
        "roll_class_code": r["roll_class_code"],
        "periods_per_cycle": r["periods_per_cycle"],
        "assigned_teacher_code": r["assigned_teacher_code"],
        "assigned_room_code": r["assigned_room_code"],
        "matching_lesson_count": r["matching_lesson_count"],
        "total_lesson_count": r["total_lesson_count"],
        "planning_year": r["planning_year"],
        "lock_status": r["lock_status"],
        "allocation_priority": r["allocation_priority"],
        "review_status": r["review_status"],
        "detected_at": r["detected_at"],
        "reviewed_at": r["reviewed_at"],
        "reviewed_by": r["reviewed_by"],
        "review_note": r["review_note"],
    }


@router.get("/teaching-requirements/candidates")
def list_teaching_requirement_candidates(
    review_status: str | None = Query(None, pattern="^(PENDING|APPROVED|REJECTED)$"),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    sql = "SELECT id FROM teaching_requirement WHERE 1=1"
    params: list = []
    if review_status:
        sql += " AND review_status = ?"
        params.append(review_status)
    sql += " ORDER BY requirement_key"

    ids = [r["id"] for r in conn.execute(sql, params)]
    return {"candidates": [_serialize_candidate(conn, i) for i in ids]}


class ReviewRequest(BaseModel):
    reviewed_by: str
    note: str | None = None


def _review(requirement_id: int, status: str, request: ReviewRequest, conn: sqlite3.Connection) -> dict:
    existing = conn.execute("SELECT id FROM teaching_requirement WHERE id = ?", (requirement_id,)).fetchone()
    if existing is None:
        raise HTTPException(status_code=404, detail=f"No teaching-requirement candidate {requirement_id}")

    conn.execute(
        "UPDATE teaching_requirement SET review_status = ?, reviewed_at = ?, reviewed_by = ?, "
        "review_note = ? WHERE id = ?",
        (status, dt.datetime.now(dt.UTC).isoformat(), request.reviewed_by, request.note, requirement_id),
    )
    log_event(
        conn, "teaching_requirement_reviewed", f"Teaching requirement {requirement_id} marked {status}",
        actor=request.reviewed_by, entity_type="teaching_requirement", entity_id=requirement_id,
        detail={"review_status": status, "note": request.note},
    )
    conn.commit()
    conn.close()

    # Re-run the rules engine so teaching_requirement_blocking reflects the review decision immediately.
    run_analysis()

    return {"id": requirement_id, "review_status": status}


@router.post("/teaching-requirements/candidates/{requirement_id}/approve")
def approve_teaching_requirement_candidate(
    requirement_id: int, request: ReviewRequest, conn: sqlite3.Connection = Depends(get_db_writable)
) -> dict:
    return _review(requirement_id, "APPROVED", request, conn)


@router.post("/teaching-requirements/candidates/{requirement_id}/reject")
def reject_teaching_requirement_candidate(
    requirement_id: int, request: ReviewRequest, conn: sqlite3.Connection = Depends(get_db_writable)
) -> dict:
    return _review(requirement_id, "REJECTED", request, conn)
