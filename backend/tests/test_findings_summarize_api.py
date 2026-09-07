"""Tests POST /findings/summarize (app/api/findings.py +
app/analysis/portfolio.py + app/advisor/explain.py) - roadmap-v3 4.5.
Never calls a real Ollama server - explain_portfolio is monkeypatched,
same hermetic pattern as test_findings_explain_api.py."""

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
        "'[{\"type\": \"teacher\", \"code\": \"T1\"}]', '[]', '{}', 'OPEN', 'test', 'test')"
    )
    conn.execute(
        "INSERT INTO finding (dedupe_key, rule_id, severity, title, entity_refs_json, slot_refs_json, "
        "evidence_json, status, first_seen_at, computed_at) VALUES ('k2', 'room_double_booking', "
        "'critical', 'Room R1 double-booked at Day 1 A P1', "
        "'[{\"type\": \"room\", \"code\": \"R1\"}]', '[]', '{}', 'OPEN', 'test', 'test')"
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


def test_summarize_returns_the_mocked_advisor_text_and_computed_summary(client, monkeypatch):
    async def fake_explain(summary: dict, findings: list) -> str:
        assert summary["total_count"] == 2
        assert len(findings) == 2
        return "Two double-bookings share the same slot."

    monkeypatch.setattr(findings_api, "explain_portfolio", fake_explain)

    resp = client.post("/api/findings/summarize", json={"finding_ids": [1, 2]})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["explanation"] == "Two double-bookings share the same slot."
    assert body["summary"]["total_count"] == 2
    assert "model" in body


def test_summarize_surfaces_advisor_errors_as_a_clean_503(client, monkeypatch):
    async def fake_explain_failing(summary: dict, findings: list) -> str:
        raise AdvisorError("Can't reach Ollama at http://localhost:11434 - is it running?")

    monkeypatch.setattr(findings_api, "explain_portfolio", fake_explain_failing)

    resp = client.post("/api/findings/summarize", json={"finding_ids": [1, 2]})
    assert resp.status_code == 503
    assert "Ollama" in resp.json()["detail"]


def test_summarize_empty_selection_is_400(client):
    resp = client.post("/api/findings/summarize", json={"finding_ids": []})
    assert resp.status_code == 400


def test_summarize_unknown_ids_is_404(client):
    resp = client.post("/api/findings/summarize", json={"finding_ids": [999]})
    assert resp.status_code == 404
