import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from app.analysis.suggestions import suggest_fixes
from app.api.deps import get_db

router = APIRouter()


@router.get("/findings")
def list_findings(
    severity: str | None = Query(None, pattern="^(info|warning|critical)$"),
    rule_id: str | None = None,
    status: str | None = Query("OPEN", pattern="^(OPEN|ACKNOWLEDGED|RESOLVED|ACCEPTED_RISK|ALL)$"),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    sql = "SELECT id, rule_id, severity, title, entity_refs_json, slot_refs_json, evidence_json, status, computed_at FROM finding WHERE 1=1"
    params: list = []
    if severity:
        sql += " AND severity = ?"
        params.append(severity)
    if rule_id:
        sql += " AND rule_id = ?"
        params.append(rule_id)
    if status and status != "ALL":
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY severity, rule_id, id"

    rows = conn.execute(sql, params).fetchall()
    findings = [
        {
            "id": r["id"],
            "rule_id": r["rule_id"],
            "severity": r["severity"],
            "title": r["title"],
            "entity_refs": json.loads(r["entity_refs_json"]),
            "slot_refs": json.loads(r["slot_refs_json"]),
            "evidence": json.loads(r["evidence_json"]),
            "status": r["status"],
            "computed_at": r["computed_at"],
        }
        for r in rows
    ]

    counts_by_severity = {"info": 0, "warning": 0, "critical": 0}
    for f in findings:
        counts_by_severity[f["severity"]] += 1

    return {"findings": findings, "total": len(findings), "counts_by_severity": counts_by_severity}


@router.get("/findings/{finding_id}/suggestions")
def get_suggestions(finding_id: int, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    """Algorithmic candidate fixes (PROJECT_ROADMAP.md Milestone 4) - every
    candidate has already been validated against the same clash rules used
    everywhere else in this API; nothing here is AI-generated. Can take a
    couple of seconds (searches every free slot/room); computed on demand,
    never precomputed for all findings."""
    row = conn.execute("SELECT id FROM finding WHERE id = ?", (finding_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No finding {finding_id}")
    return suggest_fixes(conn, finding_id)
