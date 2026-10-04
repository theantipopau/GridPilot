"""Tests GET /teaching-requirements/candidates and the approve/reject
flow (app/api/teaching_requirements.py) through the real FastAPI app -
mirrors test_room_constraints_api.py's pattern. No real school data."""

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


def _run_sync(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    from app.analysis.teaching_requirement_review import sync_teaching_requirement_candidates
    sync_teaching_requirement_candidates(conn)
    conn.close()


def test_lists_pending_candidates_detected_from_real_usage(client, db_path):
    _run_sync(db_path)

    resp = client.get("/api/teaching-requirements/candidates?review_status=PENDING")
    assert resp.status_code == 200, resp.text
    candidates = resp.json()["candidates"]
    assert len(candidates) == 1
    c = candidates[0]
    assert c["requirement_key"] == "CLASSA"
    assert c["class_code"] == "CLASSA"
    assert c["member_class_codes"] is None
    assert c["subject_code"] == "SUBA"
    assert c["assigned_teacher_code"] == "T1"
    assert c["assigned_room_code"] == "R1"
    assert c["periods_per_cycle"] == 2
    assert c["review_status"] == "PENDING"


def test_approve_sets_review_fields_and_moves_out_of_pending(client, db_path):
    _run_sync(db_path)
    candidate_id = client.get("/api/teaching-requirements/candidates?review_status=PENDING").json()["candidates"][0]["id"]

    resp = client.post(
        f"/api/teaching-requirements/candidates/{candidate_id}/approve",
        json={"reviewed_by": "tester", "note": "Yes, this reflects what we intend to run"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"id": candidate_id, "review_status": "APPROVED"}

    pending = client.get("/api/teaching-requirements/candidates?review_status=PENDING").json()["candidates"]
    assert pending == []
    approved = client.get("/api/teaching-requirements/candidates?review_status=APPROVED").json()["candidates"]
    assert len(approved) == 1
    assert approved[0]["reviewed_by"] == "tester"


def test_reject_moves_out_of_pending(client, db_path):
    _run_sync(db_path)
    candidate_id = client.get("/api/teaching-requirements/candidates?review_status=PENDING").json()["candidates"][0]["id"]

    resp = client.post(f"/api/teaching-requirements/candidates/{candidate_id}/reject", json={"reviewed_by": "tester"})
    assert resp.status_code == 200
    assert resp.json() == {"id": candidate_id, "review_status": "REJECTED"}


def test_review_unknown_candidate_is_404(client, db_path):
    resp = client.post("/api/teaching-requirements/candidates/999/approve", json={"reviewed_by": "tester"})
    assert resp.status_code == 404


def test_approving_an_unstaffed_requirement_produces_a_blocking_finding(client, db_path):
    _run_sync(db_path)
    candidate_id = client.get("/api/teaching-requirements/candidates?review_status=PENDING").json()["candidates"][0]["id"]

    # No teacher_capability row exists at all for T1/SUBA - nobody is
    # marked eligible to teach it.
    client.post(f"/api/teaching-requirements/candidates/{candidate_id}/approve", json={"reviewed_by": "tester"})

    findings = client.get("/api/findings?status=OPEN").json()["findings"]
    matches = [f for f in findings if f["rule_id"] == "teaching_requirement_blocking"]
    assert len(matches) == 1
    assert matches[0]["severity"] == "critical"
    assert "CLASSA" in matches[0]["title"]


def test_approving_a_staffed_requirement_produces_no_blocking_finding(client, db_path):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO teacher_capability (teacher_code, subject_code, capability_status, source_type, "
        "effective_from, created_at, created_by, updated_at) "
        "VALUES ('T1', 'SUBA', 'ELIGIBLE', 'SCHOOL_CONFIRMED', 'test', 'test', 'tester', 'test')"
    )
    conn.commit()
    conn.close()

    _run_sync(db_path)
    candidate_id = client.get("/api/teaching-requirements/candidates?review_status=PENDING").json()["candidates"][0]["id"]
    client.post(f"/api/teaching-requirements/candidates/{candidate_id}/approve", json={"reviewed_by": "tester"})

    findings = client.get("/api/findings?status=OPEN").json()["findings"]
    assert all(f["rule_id"] != "teaching_requirement_blocking" for f in findings)
