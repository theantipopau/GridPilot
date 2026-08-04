"""Tests for the audit-event helper. No real school data - see
tests/synthetic.py."""

import json

from app.audit import log_event
from tests.synthetic import build_synthetic_db


def test_log_event_records_expected_fields():
    conn = build_synthetic_db()
    log_event(
        conn, "ingest_completed", "Test import finished",
        actor="tester", entity_type="ingest_run", entity_id=1,
        detail={"source_sha256": "abc123"},
    )

    row = conn.execute("SELECT * FROM audit_event").fetchone()
    assert row["event_type"] == "ingest_completed"
    assert row["summary"] == "Test import finished"
    assert row["actor"] == "tester"
    assert row["entity_type"] == "ingest_run"
    assert row["entity_id"] == "1"
    assert json.loads(row["detail_json"]) == {"source_sha256": "abc123"}
    assert row["occurred_at"] is not None


def test_log_event_defaults_actor_to_local_user():
    conn = build_synthetic_db()
    log_event(conn, "rules_run_completed", "Ran the rules engine")

    row = conn.execute("SELECT actor, entity_type, entity_id, detail_json FROM audit_event").fetchone()
    assert row["actor"] == "local-user"
    assert row["entity_type"] is None
    assert row["entity_id"] is None
    assert row["detail_json"] is None


def test_multiple_events_are_never_overwritten():
    conn = build_synthetic_db()
    log_event(conn, "ingest_completed", "First")
    log_event(conn, "rules_run_completed", "Second")
    log_event(conn, "composite_group_reviewed", "Third")

    rows = conn.execute("SELECT event_type FROM audit_event ORDER BY id").fetchall()
    assert [r["event_type"] for r in rows] == ["ingest_completed", "rules_run_completed", "composite_group_reviewed"]


def test_audit_detail_never_contains_a_name_by_convention():
    """Regression guard mirroring the finding-payload privacy test - audit
    detail must stay codes/ids only. This only checks the specific test
    inputs used elsewhere in the suite don't leak a name; real enforcement
    is code review discipline, documented in docs/privacy-threat-model.md."""
    conn = build_synthetic_db()
    log_event(
        conn, "composite_group_reviewed", "Composite group 1 marked APPROVED",
        actor="Matt Hurley", entity_type="composite_group", entity_id=1,
        detail={"review_status": "APPROVED", "note": "confirmed with faculty head"},
    )
    row = conn.execute("SELECT detail_json FROM audit_event").fetchone()
    detail = json.loads(row["detail_json"])
    assert set(detail.keys()) == {"review_status", "note"}
    assert "first_name" not in json.dumps(detail)
    assert "last_name" not in json.dumps(detail)
