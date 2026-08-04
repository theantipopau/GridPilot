import datetime as dt
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.analysis.run import run_analysis
from app.api.deps import get_db, get_db_writable
from app.audit import log_event

router = APIRouter()


def _serialize_group(conn: sqlite3.Connection, group_id: int) -> dict:
    g = conn.execute(
        """
        SELECT cg.id, cg.review_status, cg.slot_count, cg.detected_at, cg.reviewed_at, cg.reviewed_by, cg.review_note,
               t.code AS teacher_code, rm.code AS room_code
        FROM composite_group cg
        JOIN teacher t ON t.id = cg.teacher_id
        JOIN room rm ON rm.id = cg.room_id
        WHERE cg.id = ?
        """,
        (group_id,),
    ).fetchone()
    if g is None:
        raise HTTPException(status_code=404, detail=f"No composite group {group_id}")

    members = [
        r["code"] for r in conn.execute(
            "SELECT cn.code FROM composite_group_member cgm JOIN class_name cn ON cn.id = cgm.class_name_id "
            "WHERE cgm.composite_group_id = ? ORDER BY cn.code",
            (group_id,),
        )
    ]
    return {
        "id": g["id"],
        "teacher_code": g["teacher_code"],
        "room_code": g["room_code"],
        "class_codes": members,
        "review_status": g["review_status"],
        "slot_count": g["slot_count"],
        "detected_at": g["detected_at"],
        "reviewed_at": g["reviewed_at"],
        "reviewed_by": g["reviewed_by"],
        "review_note": g["review_note"],
    }


@router.get("/composites/candidates")
def list_composite_candidates(
    review_status: str | None = Query(None, pattern="^(PENDING|APPROVED|REJECTED)$"),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    sql = "SELECT id FROM composite_group WHERE 1=1"
    params: list = []
    if review_status:
        sql += " AND review_status = ?"
        params.append(review_status)
    sql += " ORDER BY slot_count DESC, id"

    ids = [r["id"] for r in conn.execute(sql, params)]
    return {"candidates": [_serialize_group(conn, i) for i in ids]}


class ReviewRequest(BaseModel):
    reviewed_by: str
    note: str | None = None


def _review(group_id: int, status: str, request: ReviewRequest, conn: sqlite3.Connection) -> dict:
    existing = conn.execute("SELECT id FROM composite_group WHERE id = ?", (group_id,)).fetchone()
    if existing is None:
        raise HTTPException(status_code=404, detail=f"No composite group {group_id}")

    conn.execute(
        "UPDATE composite_group SET review_status = ?, reviewed_at = ?, reviewed_by = ?, review_note = ? WHERE id = ?",
        (status, dt.datetime.now(dt.UTC).isoformat(), request.reviewed_by, request.note, group_id),
    )
    log_event(
        conn, "composite_group_reviewed", f"Composite group {group_id} marked {status}",
        actor=request.reviewed_by, entity_type="composite_group", entity_id=group_id,
        detail={"review_status": status, "note": request.note},
    )
    conn.commit()
    conn.close()

    # Re-run the rules engine so findings reflect the review decision immediately.
    run_analysis()

    return {"id": group_id, "review_status": status}


@router.post("/composites/candidates/{group_id}/approve")
def approve_composite_candidate(group_id: int, request: ReviewRequest, conn: sqlite3.Connection = Depends(get_db_writable)) -> dict:
    return _review(group_id, "APPROVED", request, conn)


@router.post("/composites/candidates/{group_id}/reject")
def reject_composite_candidate(group_id: int, request: ReviewRequest, conn: sqlite3.Connection = Depends(get_db_writable)) -> dict:
    return _review(group_id, "REJECTED", request, conn)
