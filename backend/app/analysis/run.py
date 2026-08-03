"""Orchestrates the deterministic rules engine: sync composite candidates,
run every rule, persist findings. Recomputed from scratch each run (old
findings are cleared first) - same pattern as ingestion, so a finding
never lingers after the condition that caused it is fixed."""

import datetime as dt
import json
import sqlite3

from app.analysis.clash_rules import run_clash_rules
from app.analysis.composite_review import sync_composite_candidates
from app.analysis.models import Finding
from app.config import DB_PATH


def _persist(conn: sqlite3.Connection, findings: list[Finding]) -> None:
    conn.execute("DELETE FROM finding")
    now = dt.datetime.now(dt.UTC).isoformat()
    conn.executemany(
        "INSERT INTO finding (rule_id, severity, title, entity_refs_json, slot_refs_json, evidence_json, computed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (
                f.rule_id,
                f.severity,
                f.title,
                json.dumps([e.to_dict() for e in f.entity_refs]),
                json.dumps([s.to_dict() for s in f.slot_refs]),
                json.dumps(f.evidence),
                now,
            )
            for f in findings
        ],
    )
    conn.commit()


def run_analysis(db_path=None) -> dict:
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        composite_sync = sync_composite_candidates(conn)
        findings = run_clash_rules(conn)
        _persist(conn, findings)

        by_rule: dict[str, int] = {}
        for f in findings:
            by_rule[f.rule_id] = by_rule.get(f.rule_id, 0) + 1

        return {"composite_sync": composite_sync, "findings_total": len(findings), "findings_by_rule": by_rule}
    finally:
        conn.close()


if __name__ == "__main__":
    result = run_analysis()
    print(json.dumps(result, indent=2))
