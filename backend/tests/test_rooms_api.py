"""Tests app/api/rooms.py - the read-only Rooms page endpoint
(docs/roadmap-v2.md 3.3a). No real school data - see tests/synthetic.py."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

import app.api.deps as deps
from app.analysis.room_pool_rules import run_room_pool_rules
from app.analysis.run import _persist
from app.api.main import app
from tests.synthetic import add_lesson, build_synthetic_db


@pytest.fixture
def db_path(tmp_path):
    conn = build_synthetic_db()
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


def test_list_rooms_includes_utilisation(client):
    resp = client.get("/api/rooms")
    assert resp.status_code == 200, resp.text
    rooms = {r["code"]: r for r in resp.json()["rooms"]}
    assert "R1" in rooms and "R2" in rooms
    # R1 hosts the one lesson (1 of the fixture's 2 LESSON_SLOT periods).
    assert rooms["R1"]["used_slots"] == 1
    assert rooms["R1"]["total_lesson_slots"] == 2
    assert rooms["R1"]["utilisation_pct"] == 50.0
    assert rooms["R2"]["used_slots"] == 0
    assert rooms["R2"]["utilisation_pct"] == 0.0


def test_room_pool_membership_is_reported(client, db_path):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO room_pool (id, source_guid, code, name, type_is_class) VALUES (1, 'g1', 'RUR 1', 'RUR 1', 1)"
    )
    conn.execute("INSERT INTO room_pool_room (room_pool_id, room_id) VALUES (1, 1)")
    conn.execute("INSERT INTO room_pool_room (room_pool_id, room_id) VALUES (1, 2)")
    conn.execute("INSERT INTO room_pool_class_name (room_pool_id, class_name_id) VALUES (1, 1)")
    conn.commit()
    conn.close()

    resp = client.get("/api/rooms")
    rooms = {r["code"]: r for r in resp.json()["rooms"]}
    assert rooms["R1"]["pool"] == {"pool_code": "RUR 1", "room_codes": ["R1", "R2"]}
    assert rooms["R2"]["pool"] == {"pool_code": "RUR 1", "room_codes": ["R1", "R2"]}


def test_room_with_no_pool_reports_null(client):
    resp = client.get("/api/rooms")
    rooms = {r["code"]: r for r in resp.json()["rooms"]}
    assert rooms["R1"]["pool"] is None


def test_open_finding_count_reflects_a_real_room_pool_violation(client, db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "INSERT INTO room_pool (id, source_guid, code, name, type_is_class) VALUES (1, 'g1', 'RUR 1', 'RUR 1', 1)"
    )
    conn.execute("INSERT INTO room_pool_room (room_pool_id, room_id) VALUES (1, 1)")
    conn.execute("INSERT INTO room_pool_class_name (room_pool_id, class_name_id) VALUES (1, 1)")
    # CLASSA (class_name_id=1) is scheduled in R1, which IS in its pool - no
    # violation there. Add a second lesson for the same class in R2, outside
    # the pool, to produce a real finding to count.
    conn.execute(
        "INSERT INTO timetable_entry (source_ref, day_id, period_id, roll_class_id, class_name_id, room_id, "
        "teacher_id, entry_type) VALUES ('test2', 2, 3, 1, 1, 2, 1, 'LESSON')"
    )
    conn.commit()
    _persist(conn, run_room_pool_rules(conn))
    conn.close()

    resp = client.get("/api/rooms")
    rooms = {r["code"]: r for r in resp.json()["rooms"]}
    assert rooms["R2"]["open_finding_count"] == 1
    assert rooms["R1"]["open_finding_count"] == 0


def test_expected_class_codes_reflect_approved_room_type_constraints(client, db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE room SET room_type = 'Science' WHERE id = 1")
    conn.execute(
        "INSERT INTO class_room_type_constraint (class_name_id, room_type, review_status, "
        "matching_lesson_count, total_lesson_count, detected_at) VALUES (1, 'Science', 'APPROVED', 2, 2, 'test')"
    )
    conn.commit()
    conn.close()

    resp = client.get("/api/rooms")
    rooms = {r["code"]: r for r in resp.json()["rooms"]}
    assert rooms["R1"]["expected_class_codes"] == ["CLASSA"]
    assert rooms["R2"]["expected_class_codes"] == []
