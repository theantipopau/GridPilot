"""Tests app/api/teachers.py - list/detail (read-only, sourced from the
.tfx import) and staff-role assignment (app-owned, the only writable part
of this API). The teacher_code-not-teacher_id design is the point being
tested in test_role_assignment_survives_a_teacher_table_rebuild: it must
keep working even after the teacher table is wiped and rebuilt with new
surrogate ids, exactly what happens on every real re-ingest."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

import app.api.deps as deps
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


def test_list_teachers_includes_load_and_no_role_by_default(client):
    resp = client.get("/api/teachers")
    assert resp.status_code == 200, resp.text
    teachers = {t["code"]: t for t in resp.json()["teachers"]}
    assert "T1" in teachers
    assert teachers["T1"]["scheduled_load_minutes"] == 60  # the one lesson added, 60 load_minutes
    assert teachers["T1"]["role"] is None
    assert teachers["T2"]["scheduled_load_minutes"] is None  # no lessons assigned to T2


def test_get_teacher_detail_by_code(client):
    resp = client.get("/api/teachers/T1")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == "T1"
    assert body["first_name"] == "Test"


def test_get_unknown_teacher_is_404(client):
    resp = client.get("/api/teachers/NOPE")
    assert resp.status_code == 404


def test_create_role_and_assign_to_teacher(client):
    create = client.post(
        "/api/roles", json={"name": "Head of Department", "tier": "Tier 1", "release_minutes_per_cycle": 240}
    )
    assert create.status_code == 200, create.text
    role_id = create.json()["id"]

    assign = client.post("/api/teachers/T1/role", json={"staff_role_id": role_id, "assigned_by": "tester"})
    assert assign.status_code == 200, assign.text

    detail = client.get("/api/teachers/T1").json()
    assert detail["role"]["name"] == "Head of Department"
    assert detail["role"]["tier"] == "Tier 1"
    assert detail["role"]["release_minutes_per_cycle"] == 240


def test_reassigning_a_teacher_replaces_the_previous_role(client):
    r1 = client.post("/api/roles", json={"name": "Role A"}).json()["id"]
    r2 = client.post("/api/roles", json={"name": "Role B"}).json()["id"]
    client.post("/api/teachers/T1/role", json={"staff_role_id": r1, "assigned_by": "tester"})
    client.post("/api/teachers/T1/role", json={"staff_role_id": r2, "assigned_by": "tester"})

    detail = client.get("/api/teachers/T1").json()
    assert detail["role"]["name"] == "Role B"


def test_unassigning_a_role(client):
    role_id = client.post("/api/roles", json={"name": "Role A"}).json()["id"]
    client.post("/api/teachers/T1/role", json={"staff_role_id": role_id, "assigned_by": "tester"})
    client.post("/api/teachers/T1/role", json={"staff_role_id": None, "assigned_by": "tester"})

    detail = client.get("/api/teachers/T1").json()
    assert detail["role"] is None


def test_duplicate_role_name_is_rejected(client):
    client.post("/api/roles", json={"name": "Head of Department"})
    dup = client.post("/api/roles", json={"name": "Head of Department"})
    assert dup.status_code == 400


def test_role_assignment_survives_a_teacher_table_rebuild(client, db_path):
    """The actual point of keying by teacher_code: simulate what a
    re-ingest does to the teacher table (delete + reinsert with new
    surrogate ids, decoy row first so T1's new id differs from its old
    one) and confirm the role assignment still resolves to the right
    teacher afterwards."""
    role_id = client.post("/api/roles", json={"name": "Head of Department"}).json()["id"]
    client.post("/api/teachers/T1/role", json={"staff_role_id": role_id, "assigned_by": "tester"})

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

    detail = client.get("/api/teachers/T1").json()
    assert detail["role"]["name"] == "Head of Department"
