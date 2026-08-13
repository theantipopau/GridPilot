"""Tests GET /room-constraints/candidates and the approve/reject flow
(app/api/room_constraints.py) through the real FastAPI app - mirrors
test_findings_review_api.py's pattern. No real school data."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

import app.analysis.run as analysis_run
import app.api.deps as deps
from app.api.main import app
from tests.synthetic import add_lesson, build_richer_synthetic_db


@pytest.fixture
def db_path(tmp_path):
    conn = build_richer_synthetic_db()
    conn.execute("UPDATE room SET room_type = 'Science' WHERE id = 1")
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    conn.commit()

    path = tmp_path / "test.sqlite3"
    file_conn = sqlite3.connect(path)
    conn.backup(file_conn)
    file_conn.close()
    conn.close()
    return path


@pytest.fixture
def client(db_path, monkeypatch):
    monkeypatch.setattr(analysis_run, "DB_PATH", db_path)
    monkeypatch.setattr(deps, "DB_PATH", db_path)
    return TestClient(app)


def _run_rules(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    from app.analysis.room_type_review import sync_room_type_candidates
    sync_room_type_candidates(conn)
    conn.close()


def test_lists_pending_candidates_detected_from_real_usage(client, db_path):
    _run_rules(db_path)

    resp = client.get("/api/room-constraints/candidates?review_status=PENDING")
    assert resp.status_code == 200
    candidates = resp.json()["candidates"]
    assert len(candidates) == 1
    c = candidates[0]
    assert c["class_code"] == "CLASSA"
    assert c["room_type"] == "Science"
    assert c["matching_lesson_count"] == 2
    assert c["total_lesson_count"] == 2
    assert c["review_status"] == "PENDING"


def test_approve_sets_review_fields_and_moves_out_of_pending(client, db_path):
    _run_rules(db_path)
    candidate_id = client.get("/api/room-constraints/candidates?review_status=PENDING").json()["candidates"][0]["id"]

    resp = client.post(
        f"/api/room-constraints/candidates/{candidate_id}/approve",
        json={"reviewed_by": "tester", "note": "Yes, this is genuinely a Science-only class"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"id": candidate_id, "review_status": "APPROVED"}

    pending = client.get("/api/room-constraints/candidates?review_status=PENDING").json()["candidates"]
    assert pending == []

    approved = client.get("/api/room-constraints/candidates?review_status=APPROVED").json()["candidates"]
    assert len(approved) == 1
    assert approved[0]["reviewed_by"] == "tester"
    assert approved[0]["review_note"] == "Yes, this is genuinely a Science-only class"


def test_approving_makes_a_mismatched_lesson_produce_a_finding(client, db_path):
    _run_rules(db_path)
    candidate_id = client.get("/api/room-constraints/candidates?review_status=PENDING").json()["candidates"][0]["id"]

    # Add a lesson in a differently-typed room before approving.
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("UPDATE room SET room_type = 'Classroom' WHERE id = 2")
    add_lesson(conn, day_id=1, period_id=4, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=2)
    conn.close()

    client.post(f"/api/room-constraints/candidates/{candidate_id}/approve", json={"reviewed_by": "tester"})

    resp = client.get("/api/findings?status=OPEN")
    findings = resp.json()["findings"]
    mismatches = [f for f in findings if f["rule_id"] == "room_feature_mismatch"]
    assert len(mismatches) == 1
    assert "CLASSA" in mismatches[0]["title"]


def test_reject_moves_out_of_pending_without_producing_findings(client, db_path):
    _run_rules(db_path)
    candidate_id = client.get("/api/room-constraints/candidates?review_status=PENDING").json()["candidates"][0]["id"]

    resp = client.post(f"/api/room-constraints/candidates/{candidate_id}/reject", json={"reviewed_by": "tester"})
    assert resp.status_code == 200
    assert resp.json() == {"id": candidate_id, "review_status": "REJECTED"}

    findings = client.get("/api/findings?status=OPEN").json()["findings"]
    assert all(f["rule_id"] != "room_feature_mismatch" for f in findings)


def test_review_unknown_candidate_is_404(client, db_path):
    resp = client.post("/api/room-constraints/candidates/999/approve", json={"reviewed_by": "tester"})
    assert resp.status_code == 404
