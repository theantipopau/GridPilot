import json
import sqlite3

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_db

router = APIRouter()


@router.get("/audit")
def list_audit_events(
    event_type: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    sql = "SELECT id, occurred_at, actor, event_type, entity_type, entity_id, summary, detail_json FROM audit_event WHERE 1=1"
    params: list = []
    if event_type:
        sql += " AND event_type = ?"
        params.append(event_type)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    events = [
        {
            "id": r["id"],
            "occurred_at": r["occurred_at"],
            "actor": r["actor"],
            "event_type": r["event_type"],
            "entity_type": r["entity_type"],
            "entity_id": r["entity_id"],
            "summary": r["summary"],
            "detail": json.loads(r["detail_json"]) if r["detail_json"] else None,
        }
        for r in rows
    ]
    return {"events": events, "total": len(events)}
