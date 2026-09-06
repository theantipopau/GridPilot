import datetime as dt
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.analysis.run import run_analysis
from app.api.deps import get_db, get_db_writable
from app.audit import log_event

router = APIRouter()


def _serialize_candidate(conn: sqlite3.Connection, candidate_id: int) -> dict:
    c = conn.execute(
        """
        SELECT crtc.id, crtc.room_type, crtc.review_status, crtc.matching_lesson_count,
               crtc.total_lesson_count, crtc.detected_at, crtc.reviewed_at, crtc.reviewed_by,
               crtc.review_note, cn.code AS class_code
        FROM class_room_type_constraint crtc
        JOIN class_name cn ON cn.id = crtc.class_name_id
        WHERE crtc.id = ?
        """,
        (candidate_id,),
    ).fetchone()
    if c is None:
        raise HTTPException(status_code=404, detail=f"No room-type candidate {candidate_id}")

    return {
        "id": c["id"],
        "class_code": c["class_code"],
        "room_type": c["room_type"],
        "matching_lesson_count": c["matching_lesson_count"],
        "total_lesson_count": c["total_lesson_count"],
        "review_status": c["review_status"],
        "detected_at": c["detected_at"],
        "reviewed_at": c["reviewed_at"],
        "reviewed_by": c["reviewed_by"],
        "review_note": c["review_note"],
    }


@router.get("/room-constraints/candidates")
def list_room_constraint_candidates(
    review_status: str | None = Query(None, pattern="^(PENDING|APPROVED|REJECTED)$"),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    sql = "SELECT id FROM class_room_type_constraint WHERE 1=1"
    params: list = []
    if review_status:
        sql += " AND review_status = ?"
        params.append(review_status)
    sql += " ORDER BY (CAST(matching_lesson_count AS REAL) / total_lesson_count) DESC, id"

    ids = [r["id"] for r in conn.execute(sql, params)]
    return {"candidates": [_serialize_candidate(conn, i) for i in ids]}


class ReviewRequest(BaseModel):
    reviewed_by: str
    note: str | None = None


def _review(candidate_id: int, status: str, request: ReviewRequest, conn: sqlite3.Connection) -> dict:
    existing = conn.execute("SELECT id FROM class_room_type_constraint WHERE id = ?", (candidate_id,)).fetchone()
    if existing is None:
        raise HTTPException(status_code=404, detail=f"No room-type candidate {candidate_id}")

    conn.execute(
        "UPDATE class_room_type_constraint SET review_status = ?, reviewed_at = ?, reviewed_by = ?, "
        "review_note = ? WHERE id = ?",
        (status, dt.datetime.now(dt.UTC).isoformat(), request.reviewed_by, request.note, candidate_id),
    )
    log_event(
        conn, "room_type_constraint_reviewed", f"Room-type constraint {candidate_id} marked {status}",
        actor=request.reviewed_by, entity_type="class_room_type_constraint", entity_id=candidate_id,
        detail={"review_status": status, "note": request.note},
    )
    conn.commit()
    conn.close()

    # Re-run the rules engine so room_feature_mismatch reflects the review decision immediately.
    run_analysis()

    return {"id": candidate_id, "review_status": status}


@router.post("/room-constraints/candidates/{candidate_id}/approve")
def approve_room_constraint_candidate(
    candidate_id: int, request: ReviewRequest, conn: sqlite3.Connection = Depends(get_db_writable)
) -> dict:
    return _review(candidate_id, "APPROVED", request, conn)


@router.post("/room-constraints/candidates/{candidate_id}/reject")
def reject_room_constraint_candidate(
    candidate_id: int, request: ReviewRequest, conn: sqlite3.Connection = Depends(get_db_writable)
) -> dict:
    return _review(candidate_id, "REJECTED", request, conn)


class BulkApproveRequest(BaseModel):
    candidate_ids: list[int]
    reviewed_by: str
    note: str | None = None


@router.post("/room-constraints/candidates/bulk-approve")
def bulk_approve_room_constraint_candidates(
    request: BulkApproveRequest, conn: sqlite3.Connection = Depends(get_db_writable)
) -> dict:
    """docs/roadmap-v3.md 1.3: the only bulk write in this app - every
    other review decision is one record at a time. Deliberately narrow:
    the frontend computes exactly which ids qualify (100%-consistency
    candidates still PENDING, matching the real-data signal
    room_type_constraints.py's own detection heuristic already relies
    on) and sends that explicit list - this endpoint never re-derives
    "which candidates count as high-confidence" itself, so what the user
    confirmed in the UI is exactly what gets written, not a live
    re-evaluation that could drift between preview and commit. A
    candidate id that no longer exists or was already reviewed by
    someone else in the meantime is skipped and reported, never silently
    dropped or force-overwritten."""
    if not request.candidate_ids:
        raise HTTPException(status_code=400, detail="candidate_ids must not be empty")

    placeholders = ",".join("?" for _ in request.candidate_ids)
    rows = conn.execute(
        f"SELECT id, review_status FROM class_room_type_constraint WHERE id IN ({placeholders})",
        request.candidate_ids,
    ).fetchall()
    found = {r["id"]: r["review_status"] for r in rows}
    missing_ids = [cid for cid in request.candidate_ids if cid not in found]
    already_reviewed_ids = [cid for cid, status in found.items() if status != "PENDING"]
    approved_ids = [cid for cid, status in found.items() if status == "PENDING"]

    now = dt.datetime.now(dt.UTC).isoformat()
    for cid in approved_ids:
        conn.execute(
            "UPDATE class_room_type_constraint SET review_status = 'APPROVED', reviewed_at = ?, "
            "reviewed_by = ?, review_note = ? WHERE id = ?",
            (now, request.reviewed_by, request.note, cid),
        )
    # One audit event for the whole batch, not one per record - the point
    # of a bulk action is that it reads back as a single decision.
    log_event(
        conn, "room_type_constraint_bulk_approved",
        f"{len(approved_ids)} room-type candidates bulk-approved (100% consistency)",
        actor=request.reviewed_by,
        detail={
            "candidate_ids": approved_ids, "note": request.note,
            "missing_ids": missing_ids, "already_reviewed_ids": already_reviewed_ids,
        },
    )
    conn.commit()
    conn.close()

    if approved_ids:
        run_analysis()

    return {
        "approved_count": len(approved_ids), "approved_ids": approved_ids,
        "missing_ids": missing_ids, "already_reviewed_ids": already_reviewed_ids,
    }
