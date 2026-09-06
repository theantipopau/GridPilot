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


def _add_second_pending_candidate(db_path) -> None:
    """The shared fixture only produces one candidate (CLASSA) - bulk
    tests need a second one to actually exercise "bulk"."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("UPDATE room SET room_type = 'Classroom' WHERE id = 2")
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=2, room_id=2)
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=2, class_name_id=2, teacher_id=2, room_id=2)
    conn.commit()
    conn.close()


def test_bulk_approve_approves_every_given_id_in_one_action(client, db_path):
    _run_rules(db_path)
    _add_second_pending_candidate(db_path)
    _run_rules(db_path)
    pending = client.get("/api/room-constraints/candidates?review_status=PENDING").json()["candidates"]
    assert len(pending) == 2
    ids = [c["id"] for c in pending]

    resp = client.post(
        "/api/room-constraints/candidates/bulk-approve",
        json={"candidate_ids": ids, "reviewed_by": "tester", "note": "100% consistency, bulk-confirmed"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["approved_count"] == 2
    assert sorted(body["approved_ids"]) == sorted(ids)
    assert body["missing_ids"] == []
    assert body["already_reviewed_ids"] == []

    assert client.get("/api/room-constraints/candidates?review_status=PENDING").json()["candidates"] == []
    approved = client.get("/api/room-constraints/candidates?review_status=APPROVED").json()["candidates"]
    assert len(approved) == 2
    assert all(c["reviewed_by"] == "tester" for c in approved)
    assert all(c["review_note"] == "100% consistency, bulk-confirmed" for c in approved)


def test_bulk_approve_reports_but_does_not_choke_on_an_already_reviewed_id(client, db_path):
    _run_rules(db_path)
    _add_second_pending_candidate(db_path)
    _run_rules(db_path)
    pending = client.get("/api/room-constraints/candidates?review_status=PENDING").json()["candidates"]
    ids = [c["id"] for c in pending]

    # Someone else reviews one of them individually first.
    client.post(f"/api/room-constraints/candidates/{ids[0]}/reject", json={"reviewed_by": "someone-else"})

    resp = client.post(
        "/api/room-constraints/candidates/bulk-approve",
        json={"candidate_ids": ids, "reviewed_by": "tester"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["approved_count"] == 1
    assert body["approved_ids"] == [ids[1]]
    assert body["already_reviewed_ids"] == [ids[0]]

    # The already-rejected one must stay rejected, not get silently flipped.
    rejected = client.get("/api/room-constraints/candidates?review_status=REJECTED").json()["candidates"]
    assert [c["id"] for c in rejected] == [ids[0]]


def test_bulk_approve_reports_a_missing_id_without_failing_the_whole_batch(client, db_path):
    _run_rules(db_path)
    candidate_id = client.get("/api/room-constraints/candidates?review_status=PENDING").json()["candidates"][0]["id"]

    resp = client.post(
        "/api/room-constraints/candidates/bulk-approve",
        json={"candidate_ids": [candidate_id, 999999], "reviewed_by": "tester"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["approved_count"] == 1
    assert body["approved_ids"] == [candidate_id]
    assert body["missing_ids"] == [999999]


def test_bulk_approve_rejects_an_empty_id_list(client, db_path):
    resp = client.post(
        "/api/room-constraints/candidates/bulk-approve",
        json={"candidate_ids": [], "reviewed_by": "tester"},
    )
    assert resp.status_code == 400


def test_bulk_approve_logs_one_audit_event_for_the_whole_batch(client, db_path):
    _run_rules(db_path)
    _add_second_pending_candidate(db_path)
    _run_rules(db_path)
    ids = [c["id"] for c in client.get("/api/room-constraints/candidates?review_status=PENDING").json()["candidates"]]

    client.post("/api/room-constraints/candidates/bulk-approve", json={"candidate_ids": ids, "reviewed_by": "tester"})

    events = client.get("/api/audit?event_type=room_type_constraint_bulk_approved").json()["events"]
    assert len(events) == 1
    assert events[0]["actor"] == "tester"
