"""Tests GET /teacher-capabilities/candidates and the approve/reject
flow (app/api/teacher_capability.py) through the real FastAPI app -
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
    from app.analysis.teacher_capability_review import sync_teacher_capability_candidates
    sync_teacher_capability_candidates(conn)
    conn.close()


def test_lists_review_required_candidates_detected_from_real_usage(client, db_path):
    _run_sync(db_path)

    resp = client.get("/api/teacher-capabilities/candidates?capability_status=REVIEW_REQUIRED")
    assert resp.status_code == 200, resp.text
    candidates = resp.json()["candidates"]
    assert len(candidates) == 1
    c = candidates[0]
    assert c["teacher_code"] == "T1"
    assert c["subject_code"] == "SUBA"
    assert c["capability_status"] == "REVIEW_REQUIRED"
    assert c["source_type"] == "CURRENT_TIMETABLE_INFERRED"


def test_approve_sets_eligible_and_moves_out_of_review_required(client, db_path):
    _run_sync(db_path)
    candidate_id = client.get(
        "/api/teacher-capabilities/candidates?capability_status=REVIEW_REQUIRED"
    ).json()["candidates"][0]["id"]

    resp = client.post(
        f"/api/teacher-capabilities/candidates/{candidate_id}/approve",
        json={"reviewed_by": "tester", "note": "Yes, T1 is qualified for SUBA"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"id": candidate_id, "capability_status": "ELIGIBLE"}

    pending = client.get("/api/teacher-capabilities/candidates?capability_status=REVIEW_REQUIRED").json()["candidates"]
    assert pending == []
    eligible = client.get("/api/teacher-capabilities/candidates?capability_status=ELIGIBLE").json()["candidates"]
    assert len(eligible) == 1


def test_reject_produces_a_critical_finding(client, db_path):
    _run_sync(db_path)
    candidate_id = client.get(
        "/api/teacher-capabilities/candidates?capability_status=REVIEW_REQUIRED"
    ).json()["candidates"][0]["id"]

    resp = client.post(f"/api/teacher-capabilities/candidates/{candidate_id}/reject", json={"reviewed_by": "tester"})
    assert resp.status_code == 200
    assert resp.json() == {"id": candidate_id, "capability_status": "NOT_ELIGIBLE"}

    findings = client.get("/api/findings?status=OPEN").json()["findings"]
    matches = [f for f in findings if f["rule_id"] == "teacher_not_qualified_for_class"]
    assert len(matches) == 1
    assert matches[0]["severity"] == "critical"


def test_review_unknown_candidate_is_404(client, db_path):
    resp = client.post("/api/teacher-capabilities/candidates/999/approve", json={"reviewed_by": "tester"})
    assert resp.status_code == 404


def _add_second_review_required_candidate(db_path) -> None:
    """The shared fixture only produces one candidate (T1 x SUBA) - bulk
    tests need a second one to actually exercise "bulk"."""
    conn = sqlite3.connect(db_path)
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=2, class_name_id=2, teacher_id=2, room_id=2)
    conn.close()


def test_bulk_approve_approves_every_given_id_in_one_action(client, db_path):
    _run_sync(db_path)
    _add_second_review_required_candidate(db_path)
    _run_sync(db_path)
    pending = client.get("/api/teacher-capabilities/candidates?capability_status=REVIEW_REQUIRED").json()["candidates"]
    assert len(pending) == 2
    ids = [c["id"] for c in pending]

    resp = client.post(
        "/api/teacher-capabilities/candidates/bulk-approve",
        json={"candidate_ids": ids, "reviewed_by": "tester", "note": "Confirmed against the staffing list"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["approved_count"] == 2
    assert sorted(body["approved_ids"]) == sorted(ids)
    assert body["missing_ids"] == []
    assert body["already_reviewed_ids"] == []

    assert client.get("/api/teacher-capabilities/candidates?capability_status=REVIEW_REQUIRED").json()["candidates"] == []
    eligible = client.get("/api/teacher-capabilities/candidates?capability_status=ELIGIBLE").json()["candidates"]
    assert len(eligible) == 2


def test_bulk_approve_reports_but_does_not_choke_on_an_already_reviewed_id(client, db_path):
    _run_sync(db_path)
    _add_second_review_required_candidate(db_path)
    _run_sync(db_path)
    ids = [c["id"] for c in client.get("/api/teacher-capabilities/candidates?capability_status=REVIEW_REQUIRED").json()["candidates"]]

    client.post(f"/api/teacher-capabilities/candidates/{ids[0]}/reject", json={"reviewed_by": "someone-else"})

    resp = client.post(
        "/api/teacher-capabilities/candidates/bulk-approve",
        json={"candidate_ids": ids, "reviewed_by": "tester"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["approved_count"] == 1
    assert body["approved_ids"] == [ids[1]]
    assert body["already_reviewed_ids"] == [ids[0]]

    rejected = client.get("/api/teacher-capabilities/candidates?capability_status=NOT_ELIGIBLE").json()["candidates"]
    assert [c["id"] for c in rejected] == [ids[0]]


def test_bulk_approve_reports_a_missing_id_without_failing_the_whole_batch(client, db_path):
    _run_sync(db_path)
    candidate_id = client.get("/api/teacher-capabilities/candidates?capability_status=REVIEW_REQUIRED").json()["candidates"][0]["id"]

    resp = client.post(
        "/api/teacher-capabilities/candidates/bulk-approve",
        json={"candidate_ids": [candidate_id, 999999], "reviewed_by": "tester"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["approved_count"] == 1
    assert body["approved_ids"] == [candidate_id]
    assert body["missing_ids"] == [999999]


def test_bulk_approve_rejects_an_empty_id_list(client, db_path):
    resp = client.post(
        "/api/teacher-capabilities/candidates/bulk-approve",
        json={"candidate_ids": [], "reviewed_by": "tester"},
    )
    assert resp.status_code == 400


def test_bulk_approve_logs_one_audit_event_for_the_whole_batch(client, db_path):
    _run_sync(db_path)
    _add_second_review_required_candidate(db_path)
    _run_sync(db_path)
    ids = [c["id"] for c in client.get("/api/teacher-capabilities/candidates?capability_status=REVIEW_REQUIRED").json()["candidates"]]

    client.post("/api/teacher-capabilities/candidates/bulk-approve", json={"candidate_ids": ids, "reviewed_by": "tester"})

    events = client.get("/api/audit?event_type=teacher_capability_bulk_approved").json()["events"]
    assert len(events) == 1
    assert events[0]["actor"] == "tester"


def test_reviewed_capability_survives_a_teacher_table_rebuild(client, db_path):
    """The actual point of keying by teacher_code, not teacher_id: simulate
    what a re-ingest does to the teacher table (delete + reinsert with new
    surrogate ids, decoy row first so T1's new id differs from its old
    one - see test_teachers_api.py's equivalent test for
    teacher_role_assignment) and confirm the review still resolves to the
    right teacher afterwards."""
    _run_sync(db_path)
    candidate_id = client.get(
        "/api/teacher-capabilities/candidates?capability_status=REVIEW_REQUIRED"
    ).json()["candidates"][0]["id"]
    client.post(f"/api/teacher-capabilities/candidates/{candidate_id}/reject", json={"reviewed_by": "tester"})

    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM timetable_entry")
    old_t1_id = conn.execute("SELECT id FROM teacher WHERE code = 'T1'").fetchone()[0]
    conn.execute("DELETE FROM teacher")
    conn.execute("INSERT INTO teacher (code, first_name, last_name) VALUES ('T0', 'Decoy', 'Teacher')")
    conn.execute("INSERT INTO teacher (code, first_name, last_name) VALUES ('T1', 'Test', 'One')")
    new_t1_id = conn.execute("SELECT id FROM teacher WHERE code = 'T1'").fetchone()[0]
    conn.commit()
    conn.close()
    assert new_t1_id != old_t1_id  # the rebuild genuinely changed the surrogate id

    from app.analysis.capability import resolve
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    assert resolve(conn, "T1", "SUBA", None) == "NOT_ELIGIBLE"  # the review, keyed by code, still resolves
