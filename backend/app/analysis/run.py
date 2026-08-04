"""Orchestrates the deterministic rules engine: sync composite candidates,
run every rule, persist findings. Findings are upserted by a stable
dedupe_key rather than wiped and recreated - a finding keeps its id and
any status a human has set across re-runs, as long as the same underlying
issue still reproduces. A finding that no longer reproduces is marked
RESOLVED, not deleted, so anything referencing its id (a proposed_change,
see Milestone 3) stays valid."""

import datetime as dt
import json
import sqlite3

from app.analysis.clash_rules import run_clash_rules
from app.analysis.composite_review import sync_composite_candidates
from app.analysis.load_rules import run_load_rules
from app.analysis.models import Finding
from app.audit import log_event
from app.config import DB_PATH


def _persist(conn: sqlite3.Connection, findings: list[Finding]) -> dict[str, int]:
    now = dt.datetime.now(dt.UTC).isoformat()
    by_key = {f.dedupe_key(): f for f in findings}

    existing = {r["dedupe_key"]: r["id"] for r in conn.execute("SELECT id, dedupe_key FROM finding")}

    updated = 0
    inserted = 0
    for key, f in by_key.items():
        if key in existing:
            conn.execute(
                "UPDATE finding SET severity = ?, title = ?, entity_refs_json = ?, slot_refs_json = ?, "
                "evidence_json = ?, computed_at = ?, status = CASE WHEN status = 'RESOLVED' THEN 'OPEN' ELSE status END "
                "WHERE dedupe_key = ?",
                (f.severity, f.title, json.dumps([e.to_dict() for e in f.entity_refs]),
                 json.dumps([s.to_dict() for s in f.slot_refs]), json.dumps(f.evidence), now, key),
            )
            updated += 1
        else:
            conn.execute(
                "INSERT INTO finding (dedupe_key, rule_id, severity, title, entity_refs_json, slot_refs_json, "
                "evidence_json, status, first_seen_at, computed_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?)",
                (key, f.rule_id, f.severity, f.title, json.dumps([e.to_dict() for e in f.entity_refs]),
                 json.dumps([s.to_dict() for s in f.slot_refs]), json.dumps(f.evidence), now, now),
            )
            inserted += 1

    stale_keys = set(existing) - set(by_key)
    resolved = 0
    if stale_keys:
        placeholders = ",".join("?" for _ in stale_keys)
        cur = conn.execute(
            f"UPDATE finding SET status = 'RESOLVED', computed_at = ? "
            f"WHERE dedupe_key IN ({placeholders}) AND status != 'RESOLVED'",
            (now, *stale_keys),
        )
        resolved = cur.rowcount

    conn.commit()
    return {"inserted": inserted, "updated": updated, "resolved": resolved}


def run_analysis(db_path=None) -> dict:
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        composite_sync = sync_composite_candidates(conn)
        findings = [*run_clash_rules(conn), *run_load_rules(conn)]
        persist_result = _persist(conn, findings)

        by_rule: dict[str, int] = {}
        for f in findings:
            by_rule[f.rule_id] = by_rule.get(f.rule_id, 0) + 1

        log_event(
            conn, "rules_run_completed", f"Rules engine run: {len(findings)} findings",
            detail={"findings_by_rule": by_rule, "finding_persistence": persist_result,
                    "composite_sync": composite_sync},
        )

        return {
            "composite_sync": composite_sync,
            "findings_total": len(findings),
            "findings_by_rule": by_rule,
            "finding_persistence": persist_result,
        }
    finally:
        conn.close()


if __name__ == "__main__":
    result = run_analysis()
    print(json.dumps(result, indent=2))
