"""Persists every mass-repair solve as a first-class `solver_run` row -
docs/roadmap-v3.md 4.2, docs/solver.md section 6: "a solver run must be
a first-class, persisted, comparable object, not a fire-and-forget
button." Deliberately additive: recording a run changes nothing about
whether a change set gets created (app/api/solver.py's existing
behaviour is untouched) - this only means a run that resolved nothing,
or whose change set a reviewer later rejected, is still a fact the app
remembers, and two runs over the same findings can be compared side by
side."""

import datetime as dt
import json
import sqlite3

from app.analysis.repair_solver import RepairResult


def record_solver_run(
    conn: sqlite3.Connection,
    *,
    created_by: str,
    finding_ids: list[int],
    time_budget_seconds: float,
    result: RepairResult,
    change_set_id: int | None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO solver_run (
            created_at, created_by, mode, finding_ids_json, time_budget_seconds, status,
            moved_count, movable_entry_count, solve_time_seconds,
            findings_resolved_json, findings_unresolved_json, not_eligible_json, moves_json, change_set_id
        ) VALUES (?, ?, 'REPAIR', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            dt.datetime.now(dt.UTC).isoformat(), created_by, json.dumps(finding_ids), time_budget_seconds,
            result.status, result.moved_count, result.movable_entry_count, result.solve_time_seconds,
            json.dumps(result.findings_resolved), json.dumps(result.findings_unresolved),
            json.dumps([{"finding_id": ne.finding_id, "rule_id": ne.rule_id, "reason": ne.reason} for ne in result.not_eligible]),
            json.dumps([
                {"entry_id": m.entry_id, "class_code": m.class_code, "before": m.before, "after": m.after}
                for m in result.moves
            ]),
            change_set_id,
        ),
    )
    return cur.lastrowid


def _finding_titles(conn: sqlite3.Connection, finding_ids: list[int]) -> dict[int, str]:
    if not finding_ids:
        return {}
    placeholders = ",".join("?" for _ in finding_ids)
    return {
        r["id"]: r["title"]
        for r in conn.execute(f"SELECT id, title FROM finding WHERE id IN ({placeholders})", tuple(finding_ids))
    }


def _serialize_summary(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    findings_resolved = json.loads(row["findings_resolved_json"])
    findings_unresolved = json.loads(row["findings_unresolved_json"])
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "created_by": row["created_by"],
        "mode": row["mode"],
        "status": row["status"],
        "scope_count": len(json.loads(row["finding_ids_json"])),
        "findings_resolved_count": len(findings_resolved),
        "findings_unresolved_count": len(findings_unresolved),
        "moved_count": row["moved_count"],
        "movable_entry_count": row["movable_entry_count"],
        "solve_time_seconds": row["solve_time_seconds"],
        "time_budget_seconds": row["time_budget_seconds"],
        "change_set_id": row["change_set_id"],
    }


def list_solver_runs(conn: sqlite3.Connection, limit: int = 50) -> list[dict]:
    rows = conn.execute("SELECT * FROM solver_run ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [_serialize_summary(conn, r) for r in rows]


def get_solver_run(conn: sqlite3.Connection, run_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM solver_run WHERE id = ?", (run_id,)).fetchone()
    if row is None:
        return None

    finding_ids = json.loads(row["finding_ids_json"])
    findings_resolved = json.loads(row["findings_resolved_json"])
    findings_unresolved = json.loads(row["findings_unresolved_json"])
    titles = _finding_titles(conn, finding_ids)

    summary = _serialize_summary(conn, row)
    summary.update({
        "findings_resolved": [{"id": fid, "title": titles.get(fid)} for fid in findings_resolved],
        "findings_unresolved": [{"id": fid, "title": titles.get(fid)} for fid in findings_unresolved],
        "not_eligible": json.loads(row["not_eligible_json"]),
        "moves": json.loads(row["moves_json"]),
    })
    return summary
