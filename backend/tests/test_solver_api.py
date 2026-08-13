"""Tests POST /api/solver/repair (app/api/solver.py) through the real
FastAPI app - mirrors test_room_constraints_api.py's pattern. No real
school data."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

import app.api.deps as deps
from app.analysis.clash_rules import run_clash_rules
from app.analysis.run import _persist
from app.api.main import app
from tests.synthetic import add_lesson, build_richer_synthetic_db


@pytest.fixture
def db_path(tmp_path):
    conn = build_richer_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=2, room_id=1)
    _persist(conn, run_clash_rules(conn))

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


def _finding_id(db_path, rule_id):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT id FROM finding WHERE rule_id = ?", (rule_id,)).fetchone()
    conn.close()
    return row["id"]


def test_repair_creates_a_reviewable_change_set(client, db_path):
    finding_id = _finding_id(db_path, "room_double_booking")
    resp = client.post("/api/solver/repair", json={"finding_ids": [finding_id], "created_by": "tester"})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["status"] == "SOLVED"
    assert body["moved_count"] == 1
    assert body["change_set_id"] is not None
    assert [f["id"] for f in body["findings_resolved"]] == [finding_id]
    assert body["findings_unresolved"] == []
    assert body["not_eligible"] == []

    cs = client.get(f"/api/change-sets/{body['change_set_id']}").json()
    assert cs["created_by"] == "tester"
    assert len(cs["changes"]) == 1
    assert cs["validation_status"] == "VALID"
    assert finding_id in cs["changes"][0]["finding_ids"]


def test_default_scope_is_every_open_repair_eligible_finding(client, db_path):
    resp = client.post("/api/solver/repair", json={"created_by": "tester"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "SOLVED"
    assert body["moved_count"] == 1


def test_unsupported_rule_type_reported_not_eligible_via_api(client, db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "INSERT INTO finding (dedupe_key, rule_id, severity, title, entity_refs_json, slot_refs_json, "
        "evidence_json, status, first_seen_at, computed_at) VALUES ('k-consistency', 'class_room_instability', "
        "'info', 'Class CLASSA used 2 rooms', '[{\"type\": \"class\", \"code\": \"CLASSA\"}]', '[]', '{}', "
        "'OPEN', 'test', 'test')"
    )
    conn.commit()
    finding_id = conn.execute("SELECT id FROM finding WHERE dedupe_key = 'k-consistency'").fetchone()["id"]
    conn.close()

    resp = client.post("/api/solver/repair", json={"finding_ids": [finding_id], "created_by": "tester"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "NO_MOVABLE_ENTRIES"
    assert body["change_set_id"] is None
    assert len(body["not_eligible"]) == 1
    assert body["not_eligible"][0]["rule_id"] == "class_room_instability"


def test_no_findings_selected_returns_no_movable_entries(client, db_path):
    resp = client.post("/api/solver/repair", json={"finding_ids": [], "created_by": "tester"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "NO_MOVABLE_ENTRIES"
    assert body["change_set_id"] is None


def test_repair_is_logged_to_the_audit_trail(client, db_path):
    finding_id = _finding_id(db_path, "room_double_booking")
    client.post("/api/solver/repair", json={"finding_ids": [finding_id], "created_by": "tester"})

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    events = conn.execute("SELECT * FROM audit_event WHERE event_type = 'mass_repair_run'").fetchall()
    conn.close()
    assert len(events) == 1
    assert events[0]["actor"] == "tester"
