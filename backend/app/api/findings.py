import datetime as dt
import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.advisor.explain import AdvisorError, OLLAMA_MODEL, explain_finding
from app.analysis.suggestions import suggest_fixes
from app.api.deps import get_db, get_db_writable
from app.audit import log_event

router = APIRouter()


@router.get("/findings")
def list_findings(
    severity: str | None = Query(None, pattern="^(info|warning|critical)$"),
    rule_id: str | None = None,
    status: str | None = Query("OPEN", pattern="^(OPEN|ACKNOWLEDGED|RESOLVED|ACCEPTED_RISK|ALL)$"),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    sql = (
        "SELECT id, rule_id, severity, title, entity_refs_json, slot_refs_json, evidence_json, status, "
        "computed_at, reviewed_at, reviewed_by, review_note FROM finding WHERE 1=1"
    )
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
            "reviewed_at": r["reviewed_at"],
            "reviewed_by": r["reviewed_by"],
            "review_note": r["review_note"],
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


def _related_open_findings(conn: sqlite3.Connection, finding_id: int, entity_refs: list, slot_refs: list) -> list[dict]:
    """Other OPEN findings sharing an entity code or a time slot with this
    one - almost always either the same underlying clash seen from another
    entity's side (a teacher-double-booking and a room-double-booking at
    the same slot are often one scheduling mistake, not two) or a genuinely
    connected problem. Given to the advisor as context so it can say that,
    rather than explaining every finding as if it exists in isolation."""
    entity_keys = {(r["type"], r["code"]) for r in entity_refs}
    slot_keys = {(s["day_code"], s["period_code"]) for s in slot_refs}

    rows = conn.execute(
        "SELECT id, rule_id, title, entity_refs_json, slot_refs_json FROM finding "
        "WHERE status = 'OPEN' AND id != ?",
        (finding_id,),
    ).fetchall()

    related = []
    for row in rows:
        other_entities = {(e["type"], e["code"]) for e in json.loads(row["entity_refs_json"])}
        other_slots = {(s["day_code"], s["period_code"]) for s in json.loads(row["slot_refs_json"])}
        if entity_keys & other_entities or slot_keys & other_slots:
            related.append({"rule_id": row["rule_id"], "title": row["title"]})
    return related[:5]


@router.post("/findings/{finding_id}/explain")
async def explain_finding_endpoint(finding_id: int, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    """AI-generated explanation of an existing finding, via a local Ollama
    model - never a suggestion or a change, see app/advisor/explain.py.
    Computed on demand, not cached or precomputed."""
    row = conn.execute(
        "SELECT rule_id, severity, title, entity_refs_json, slot_refs_json, evidence_json "
        "FROM finding WHERE id = ?",
        (finding_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No finding {finding_id}")

    entity_refs = json.loads(row["entity_refs_json"])
    slot_refs = json.loads(row["slot_refs_json"])
    finding = {
        "rule_id": row["rule_id"],
        "severity": row["severity"],
        "title": row["title"],
        "entity_refs": entity_refs,
        "slot_refs": slot_refs,
        "evidence": json.loads(row["evidence_json"]),
    }
    related = _related_open_findings(conn, finding_id, entity_refs, slot_refs)
    try:
        explanation = await explain_finding(finding, related)
    except AdvisorError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    return {"finding_id": finding_id, "explanation": explanation, "model": OLLAMA_MODEL}


class FindingReviewRequest(BaseModel):
    reviewed_by: str
    note: str | None = None


def _set_finding_status(
    finding_id: int, status: str, request: FindingReviewRequest, conn: sqlite3.Connection
) -> dict:
    """Shared by accept-risk and reopen - a finding's status is otherwise
    only ever written by the rules engine (app/analysis/run.py), so this is
    the one place a human decision overrides that. Never touches RESOLVED:
    a finding the engine says no longer reproduces should only come back
    via the engine re-detecting it, not a manual click."""
    row = conn.execute("SELECT status FROM finding WHERE id = ?", (finding_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No finding {finding_id}")
    if row["status"] == "RESOLVED":
        raise HTTPException(status_code=409, detail="This finding is already resolved - nothing to review.")

    now = dt.datetime.now(dt.UTC).isoformat()
    conn.execute(
        "UPDATE finding SET status = ?, reviewed_at = ?, reviewed_by = ?, review_note = ? WHERE id = ?",
        (status, now, request.reviewed_by, request.note, finding_id),
    )
    log_event(
        conn, "finding_status_changed", f"Finding {finding_id} marked {status}",
        actor=request.reviewed_by, entity_type="finding", entity_id=finding_id,
        detail={"status": status, "note": request.note},
    )
    conn.commit()
    return {"id": finding_id, "status": status}


@router.post("/findings/{finding_id}/accept-risk")
def accept_finding_risk(
    finding_id: int, request: FindingReviewRequest, conn: sqlite3.Connection = Depends(get_db_writable)
) -> dict:
    """Marks a finding as an intentional, known clash - e.g. a deliberate
    supervision overlap - rather than something to fix. It stays out of the
    default OPEN view but is never hidden outright: GET /api/findings?
    status=ACCEPTED_RISK (or ALL) still shows it, with who accepted it and
    why. Survives the rules engine's next run because _persist only ever
    flips a *RESOLVED* finding back to OPEN, never an ACCEPTED_RISK one -
    see app/analysis/run.py."""
    return _set_finding_status(finding_id, "ACCEPTED_RISK", request, conn)


@router.post("/findings/{finding_id}/reopen")
def reopen_finding(
    finding_id: int, request: FindingReviewRequest, conn: sqlite3.Connection = Depends(get_db_writable)
) -> dict:
    """Undoes an accept-risk (or acknowledged) decision, putting the finding
    back in the default OPEN view."""
    return _set_finding_status(finding_id, "OPEN", request, conn)
