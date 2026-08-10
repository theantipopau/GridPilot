"""Tests POST /findings/{id}/explain (app/api/findings.py +
app/advisor/explain.py). Never calls a real Ollama server - explain_finding
is monkeypatched, so these stay hermetic and fast regardless of whether
Ollama happens to be installed/running on the machine running the suite.
A real end-to-end check against actual Ollama was done manually - see
docs/ai-advisor.md."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

import app.api.deps as deps
import app.api.findings as findings_api
from app.advisor.explain import AdvisorError
from app.api.main import app
from tests.synthetic import build_synthetic_db


@pytest.fixture
def db_path(tmp_path):
    conn = build_synthetic_db()
    conn.execute(
        "INSERT INTO finding (dedupe_key, rule_id, severity, title, entity_refs_json, slot_refs_json, "
        "evidence_json, status, first_seen_at, computed_at) VALUES ('k1', 'teacher_double_booking', "
        "'critical', 'Teacher T1 double-booked at Day 1 A P1', "
        "'[{\"type\": \"teacher\", \"code\": \"T1\"}]', '[{\"day_code\": \"Day 1 A\", \"period_code\": \"P1\"}]', "
        "'{}', 'OPEN', 'test', 'test')"
    )
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


def test_explain_returns_the_mocked_advisor_text(client, monkeypatch):
    async def fake_explain(finding: dict) -> str:
        assert finding["rule_id"] == "teacher_double_booking"
        assert finding["entity_refs"] == [{"type": "teacher", "code": "T1"}]
        return "Teacher T1 is booked into two lessons at the same time."

    monkeypatch.setattr(findings_api, "explain_finding", fake_explain)

    finding_id = 1  # first (only) row inserted by the fixture
    resp = client.post(f"/api/findings/{finding_id}/explain")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["explanation"] == "Teacher T1 is booked into two lessons at the same time."
    assert "model" in body


def test_explain_surfaces_advisor_errors_as_a_clean_503(client, monkeypatch):
    async def fake_explain_failing(finding: dict) -> str:
        raise AdvisorError("Can't reach Ollama at http://localhost:11434 - is it running?")

    monkeypatch.setattr(findings_api, "explain_finding", fake_explain_failing)

    resp = client.post("/api/findings/1/explain")
    assert resp.status_code == 503
    assert "Ollama" in resp.json()["detail"]


def test_explain_unknown_finding_is_404(client):
    resp = client.post("/api/findings/999/explain")
    assert resp.status_code == 404
