import json
import sqlite3

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_db

router = APIRouter()


@router.get("/findings")
def list_findings(
    severity: str | None = Query(None, pattern="^(info|warning|critical)$"),
    rule_id: str | None = None,
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
