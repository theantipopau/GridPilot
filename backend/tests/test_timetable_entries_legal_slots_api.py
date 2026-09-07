"""Tests GET /timetable-entries/{id}/legal-slots (app/api/timetable_entries.py
+ app/analysis/suggestions.py's legal_slots_for_entry) through the real
FastAPI app."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

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
    monkeypatch.setattr(deps, "DB_PATH", db_path)
    return TestClient(app)


def test_legal_slots_for_a_real_entry(client, db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    entry_id = conn.execute("SELECT id FROM timetable_entry WHERE entry_type = 'LESSON'").fetchone()["id"]
    conn.close()

    resp = client.get(f"/api/timetable-entries/{entry_id}/legal-slots")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["entry_id"] == entry_id
    assert body["class_code"] == "CLASSA"
    assert len(body["slots"]) == 5  # richer fixture's LESSON_SLOT count
    home = next(s for s in body["slots"] if s["day_code"] == "Day 1 A" and s["period_code"] == "P1")
    assert home["legal"] is True


def test_legal_slots_for_unknown_entry_is_404(client):
    resp = client.get("/api/timetable-entries/999/legal-slots")
    assert resp.status_code == 404
