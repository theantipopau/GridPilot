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


def test_repair_persists_a_first_class_solver_run(client, db_path):
    """docs/roadmap-v3.md 4.2: every solve is a persisted, comparable
    object - not just a response the browser might discard."""
    finding_id = _finding_id(db_path, "room_double_booking")
    resp = client.post("/api/solver/repair", json={"finding_ids": [finding_id], "created_by": "tester"})
    run_id = resp.json()["solver_run_id"]
    assert run_id is not None

    runs = client.get("/api/solver/runs").json()["runs"]
    assert len(runs) == 1
    assert runs[0]["id"] == run_id
    assert runs[0]["status"] == "SOLVED"
    assert runs[0]["created_by"] == "tester"
    assert runs[0]["moved_count"] == 1
    assert runs[0]["change_set_id"] == resp.json()["change_set_id"]

    detail = client.get(f"/api/solver/runs/{run_id}").json()
    assert len(detail["moves"]) == 1
    assert detail["moves"][0]["class_code"] in ("CLASSA", "CLASSB")
    assert [f["id"] for f in detail["findings_resolved"]] == [finding_id]
    assert detail["findings_resolved"][0]["title"]  # a real title, not just an id


def test_a_run_that_resolves_nothing_is_still_persisted(client, db_path):
    """A run isn't only worth remembering when it succeeds - "Run 3
    resolved 0 of 1" is exactly the kind of comparison point solver.md
    section 6 wants a future run to be judged against."""
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
    assert resp.json()["status"] == "NO_MOVABLE_ENTRIES"
    run_id = resp.json()["solver_run_id"]
    assert run_id is not None

    detail = client.get(f"/api/solver/runs/{run_id}").json()
    assert detail["status"] == "NO_MOVABLE_ENTRIES"
    assert detail["moves"] == []
    assert detail["change_set_id"] is None
    assert len(detail["not_eligible"]) == 1


def test_an_empty_scope_is_not_worth_a_solver_run(client, db_path):
    """No findings selected at all never reaches solve_repair() - a
    trivial no-op isn't a run worth remembering or comparing."""
    client.post("/api/solver/repair", json={"finding_ids": [], "created_by": "tester"})
    assert client.get("/api/solver/runs").json()["runs"] == []


def test_unknown_solver_run_is_404(client, db_path):
    resp = client.get("/api/solver/runs/999")
    assert resp.status_code == 404


def test_solver_runs_list_is_most_recent_first(client, db_path):
    finding_id = _finding_id(db_path, "room_double_booking")
    first = client.post("/api/solver/repair", json={"finding_ids": [finding_id], "created_by": "a"}).json()
    # Re-open the finding the first run just resolved so a second run has something real to do.
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE finding SET status = 'OPEN' WHERE id = ?", (finding_id,))
    conn.commit()
    conn.close()
    second = client.post("/api/solver/repair", json={"finding_ids": [finding_id], "created_by": "b"}).json()

    runs = client.get("/api/solver/runs").json()["runs"]
    assert [r["id"] for r in runs] == [second["solver_run_id"], first["solver_run_id"]]
