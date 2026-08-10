"""Tests POST /findings/{id}/accept-risk and /reopen (app/api/findings.py) -
the one place a human decision overrides a finding's status, which is
otherwise only ever written by the rules engine."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

import app.api.deps as deps
from app.api.main import app
from tests.synthetic import build_synthetic_db


def _insert_finding(conn, dedupe_key="k1", status="OPEN"):
    conn.execute(
        "INSERT INTO finding (dedupe_key, rule_id, severity, title, entity_refs_json, slot_refs_json, "
        "evidence_json, status, first_seen_at, computed_at) VALUES (?, 'teacher_double_booking', "
        "'critical', 'Teacher T1 double-booked at Day 1 A P1', "
        "'[{\"type\": \"teacher\", \"code\": \"T1\"}]', '[{\"day_code\": \"Day 1 A\", \"period_code\": \"P1\"}]', "
        "'{}', ?, 'test', 'test')",
        (dedupe_key, status),
    )


@pytest.fixture
def db_path(tmp_path):
    conn = build_synthetic_db()
    _insert_finding(conn, "k1", "OPEN")
    _insert_finding(conn, "k2", "RESOLVED")
    conn.commit()
    path = tmp_path / "test.sqlite3"
    file_conn = sqlite3.connect(path)
    conn.backup(file_conn)
    file_conn.close()
    conn.close()
    return path


@pytest.fixture
def client(db_path, monkeypatch):
    monkeypatch.setattr(deps, "DB_PATH", db_path)
    return TestClient(app)


def test_accept_risk_sets_status_and_review_fields(client):
    resp = client.post("/api/findings/1/accept-risk", json={"reviewed_by": "tester", "note": "Deliberate overlap"})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"id": 1, "status": "ACCEPTED_RISK"}

    listed = client.get("/api/findings?status=ACCEPTED_RISK").json()["findings"]
    assert len(listed) == 1
    assert listed[0]["reviewed_by"] == "tester"
    assert listed[0]["review_note"] == "Deliberate overlap"
    assert listed[0]["reviewed_at"] is not None


def test_accepted_risk_finding_drops_out_of_default_open_view(client):
    client.post("/api/findings/1/accept-risk", json={"reviewed_by": "tester"})
    open_findings = client.get("/api/findings").json()["findings"]
    assert all(f["id"] != 1 for f in open_findings)


def test_reopen_puts_it_back_in_the_open_view(client):
    client.post("/api/findings/1/accept-risk", json={"reviewed_by": "tester"})
    resp = client.post("/api/findings/1/reopen", json={"reviewed_by": "tester2"})
    assert resp.status_code == 200
    assert resp.json() == {"id": 1, "status": "OPEN"}

    open_findings = client.get("/api/findings").json()["findings"]
    assert any(f["id"] == 1 for f in open_findings)


def test_cannot_review_a_resolved_finding(client):
    resp = client.post("/api/findings/2/accept-risk", json={"reviewed_by": "tester"})
    assert resp.status_code == 409


def test_review_unknown_finding_is_404(client):
    resp = client.post("/api/findings/999/accept-risk", json={"reviewed_by": "tester"})
    assert resp.status_code == 404


def test_accept_risk_is_logged_to_the_audit_trail(client, db_path):
    client.post("/api/findings/1/accept-risk", json={"reviewed_by": "tester", "note": "Deliberate overlap"})
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    events = conn.execute("SELECT * FROM audit_event WHERE event_type = 'finding_status_changed'").fetchall()
    conn.close()
    assert len(events) == 1
    assert events[0]["actor"] == "tester"
    assert events[0]["entity_id"] == "1"
