"""POST /timetable-entries/{id}/room-advice (app/advisor/room.py +
app/api/timetable_entries.py). Hermetic like test_findings_explain_api.py:
explain_room_choice is monkeypatched so nothing here touches a real
Ollama server. The deterministic fact-gathering half (which slots/rooms
are legal) is genuinely computed against the synthetic timetable."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

import app.api.deps as deps
import app.api.timetable_entries as entries_api
import app.advisor.room as room_module
from app.api.main import app
from tests.synthetic import add_lesson, build_synthetic_db


@pytest.fixture
def db_path(tmp_path):
    conn = build_synthetic_db()
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, room_id=1, teacher_id=1)
    conn.commit()
    path = tmp_path / "test.sqlite3"
    file_conn = sqlite3.connect(path)
    conn.backup(file_conn)
    file_conn.close()
    conn.close()
    return path


@pytest.fixture
def client(db_path):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    def _override():
        yield conn

    app.dependency_overrides[deps.get_db] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()
    conn.close()


def test_room_advice_returns_facts_and_explanation(client, monkeypatch):
    # Patch the binding the API module uses (from-import at module scope),
    # or the call would reach a real Ollama if one happens to be running.
    async def fake_explain(facts: dict) -> str:
        assert facts["entry_id"] == 1
        assert facts["class_code"] == "CLASSA"
        assert facts["current_room_code"] == "R1"
        assert facts["legal_slots_with_rooms"], "at least one legal slot must be computed"
        return "R1 is the sensible room: it is free at every slot this lesson could legally occupy."

    monkeypatch.setattr(entries_api, "explain_room_choice", fake_explain)

    resp = client.post("/api/timetable-entries/1/room-advice")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "sensible room" in body["explanation"]
    assert body["entry_id"] == 1
    assert body["model"]
    # The class's own room history is fact, computed from timetable_entry.
    assert body["facts"]["class_room_usage_this_cycle"] == [{"room_code": "R1", "lessons": 1}]


def test_room_advice_404_for_unknown_entry(client, monkeypatch):
    async def never_called(facts):  # pragma: no cover
        raise AssertionError("must not be reached")

    monkeypatch.setattr(room_module, "explain_room_choice", never_called)
    resp = client.post("/api/timetable-entries/99999/room-advice")
    assert resp.status_code == 404


def test_room_advice_advisor_error_becomes_503(client, monkeypatch):
    # The API layer imports explain_room_choice at module scope, so patch
    # the binding it actually uses, exactly as test_findings_explain_api.py
    # does for findings.
    async def failing(facts):
        raise room_module.AdvisorError("Can't reach Ollama at http://localhost:11434 - is it running?")

    monkeypatch.setattr(entries_api, "explain_room_choice", failing)
    resp = client.post("/api/timetable-entries/1/room-advice")
    assert resp.status_code == 503
    assert "Ollama" in resp.json()["detail"]
