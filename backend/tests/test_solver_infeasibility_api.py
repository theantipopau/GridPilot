"""Tests POST /solver/runs/{id}/explain-infeasibility (app/api/solver.py
+ app/analysis/infeasibility.py + app/advisor/explain.py) - roadmap-v3
4.3. Never calls a real Ollama server - explain_infeasibility is
monkeypatched, same hermetic pattern as test_findings_explain_api.py. A
real end-to-end check against actual Ollama was done manually."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

import app.api.deps as deps
import app.api.solver as solver_api
from app.advisor.explain import AdvisorError
from app.api.main import app
from tests.synthetic import add_lesson, build_richer_synthetic_db


@pytest.fixture
def db_path(tmp_path):
    """A real teacher_double_booking: T1 teaches both CLASSA and CLASSD at
    day1/P1 (two different rooms), and is booked solid everywhere else in
    the cycle (real CLASSB lessons at every other LESSON_SLOT period) -
    genuinely nowhere for either to go, so a repair run over the real,
    rules-engine-computed finding ends INFEASIBLE with something real for
    the explain endpoint to diagnose."""
    conn = build_richer_synthetic_db()
    conn.execute("INSERT INTO subject (id, source_code, name) VALUES (3, 'SUBD', 'Subject D')")
    conn.execute("INSERT INTO class_name (id, code, name, subject_id) VALUES (3, 'CLASSD', 'Class D', 3)")

    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=3, teacher_id=1, room_id=2)
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=2, class_name_id=2, teacher_id=1, room_id=2)
    add_lesson(conn, day_id=1, period_id=4, roll_class_id=2, class_name_id=2, teacher_id=1, room_id=2)
    add_lesson(conn, day_id=2, period_id=5, roll_class_id=2, class_name_id=2, teacher_id=1, room_id=2)
    add_lesson(conn, day_id=3, period_id=6, roll_class_id=2, class_name_id=2, teacher_id=1, room_id=2)

    from app.analysis.clash_rules import run_clash_rules
    from app.analysis.run import _persist
    _persist(conn, run_clash_rules(conn))
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


def _infeasible_run_id(client) -> int:
    finding_id = client.get("/api/findings").json()["findings"][0]["id"]
    resp = client.post("/api/solver/repair", json={"finding_ids": [finding_id], "created_by": "tester"})
    body = resp.json()
    assert body["status"] == "INFEASIBLE", body
    return body["solver_run_id"]


def test_explain_infeasibility_returns_the_mocked_advisor_text(client, monkeypatch):
    run_id = _infeasible_run_id(client)

    async def fake_explain(diagnoses: list[dict]) -> str:
        assert {d["class_code"] for d in diagnoses} == {"CLASSA", "CLASSD"}
        # Each is individually fine at its own home slot (checked with the
        # OTHER one excluded from the busy background) - the honest,
        # correct answer here is "true," since this is a genuine two-lesson
        # deadlock (both want the same slot with the same teacher), not a
        # single-lesson structural impossibility.
        assert all(d["has_legal_slot"] is True for d in diagnoses)
        return "T1 has no free slot anywhere in the cycle."

    monkeypatch.setattr(solver_api, "explain_infeasibility", fake_explain)

    resp = client.post(f"/api/solver/runs/{run_id}/explain-infeasibility")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["explanation"] == "T1 has no free slot anywhere in the cycle."
    assert "model" in body
    assert len(body["diagnoses"]) == 2


def test_explain_infeasibility_surfaces_advisor_errors_as_a_clean_503(client, monkeypatch):
    run_id = _infeasible_run_id(client)

    async def fake_explain_failing(diagnoses: list[dict]) -> str:
        raise AdvisorError("Can't reach Ollama at http://localhost:11434 - is it running?")

    monkeypatch.setattr(solver_api, "explain_infeasibility", fake_explain_failing)

    resp = client.post(f"/api/solver/runs/{run_id}/explain-infeasibility")
    assert resp.status_code == 503
    assert "Ollama" in resp.json()["detail"]


def test_explain_infeasibility_unknown_run_is_404(client):
    resp = client.post("/api/solver/runs/999/explain-infeasibility")
    assert resp.status_code == 404


def test_explain_infeasibility_on_a_fully_resolved_run_is_400(client, monkeypatch, db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE finding SET status = 'OPEN'")
    # Free up day1/P4 for T1 (drop the fixed CLASSB lesson sitting there),
    # so CLASSD now has somewhere to move and the clash is solvable.
    conn.execute("DELETE FROM timetable_entry WHERE day_id = 1 AND period_id = 4")
    conn.commit()
    conn.close()

    finding_id = client.get("/api/findings").json()["findings"][0]["id"]
    resp = client.post("/api/solver/repair", json={"finding_ids": [finding_id], "created_by": "tester"})
    assert resp.json()["status"] == "SOLVED", resp.json()
    run_id = resp.json()["solver_run_id"]

    resp = client.post(f"/api/solver/runs/{run_id}/explain-infeasibility")
    assert resp.status_code == 400
