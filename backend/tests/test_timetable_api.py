"""Tests GET /timetable (single teacher/room/roll_class) and GET
/timetable/all (every lesson, unfiltered - the master grid)."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

import app.api.deps as deps
from app.api.main import app
from tests.synthetic import add_lesson, build_synthetic_db


@pytest.fixture
def db_path(tmp_path):
    conn = build_synthetic_db()
    # T1 teaches CLASSA to 7A in R1 at Day 1 A P1; T2 teaches CLASSB to 7B in R2 at the same slot.
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=1, teacher_id=1, room_id=1)
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=2, room_id=2)
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


def test_get_timetable_filters_to_one_teacher(client):
    resp = client.get("/api/timetable?view=teacher&code=T1")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["view"] == "teacher"
    assert body["code"] == "T1"
    assert len(body["entries"]) == 1
    assert body["entries"][0]["class_code"] == "CLASSA"


def test_get_timetable_unknown_code_is_404(client):
    resp = client.get("/api/timetable?view=teacher&code=NOPE")
    assert resp.status_code == 404


def test_get_full_timetable_returns_every_entry_unfiltered(client):
    resp = client.get("/api/timetable/all")
    assert resp.status_code == 200, resp.text
    entries = resp.json()["entries"]
    teacher_codes = {e["teacher_code"] for e in entries}
    assert teacher_codes == {"T1", "T2"}
    assert len(entries) == 2
