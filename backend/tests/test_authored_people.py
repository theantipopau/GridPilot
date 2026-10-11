"""Authored people - new students and staff added between exports
(app/analysis/authored_people.py, app/api/authored_people.py), plus their
interaction with re-ingest (resync.py's superseded-row cleanup).

The core promise of this feature is surviving a re-ingest, so one test
drives a genuine resync_source_tables() pass rather than simulating the
delete/rebuild cycle. API tests follow the same hermetic pattern as
test_findings_explain_api.py: TestClient over a synthetic DB, no real
network.
"""

import sqlite3

import pytest
from fastapi.testclient import TestClient

import app.api.deps as deps
from app.analysis.authored_people import (
    add_authored_student,
    add_authored_teacher,
    remove_superseded_authored_people,
    update_authored_student,
)
from app.api.main import app
from tests.synthetic import build_synthetic_db


@pytest.fixture
def db_path(tmp_path):
    conn = build_synthetic_db()
    path = tmp_path / "test.sqlite3"
    file_conn = sqlite3.connect(path)
    conn.backup(file_conn)
    file_conn.close()
    conn.close()
    return path


import sqlite3  # noqa: E402 - fixture above shares the module


@pytest.fixture
def client(db_path):
    # A writable connection override keeps every test transaction local -
    # same trick test_blocking_api-style fixtures use, without touching
    # the on-disk DB_PATH anywhere.
    # check_same_thread=False: TestClient runs the dependency in a worker
    # thread - same rationale app/api/deps.py's get_db documents.
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    def _override():
        yield conn

    app.dependency_overrides[deps.get_db] = _override
    app.dependency_overrides[deps.get_db_writable] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()
    conn.close()


def test_add_authored_student_and_teacher_round_trip(client):
    resp = client.post(
        "/api/authored-students",
        json={"code": "NEW001", "first_name": "Ada", "last_name": "Example", "entered_by": "test"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["source"] == "AUTHORED"

    resp_t = client.post(
        "/api/authored-teachers",
        json={"code": "NEW T", "first_name": "Bea", "last_name": "Example",
              "staff_category": "TEACHER", "contracted_load_minutes": 1200.0, "entered_by": "test"},
    )
    assert resp_t.status_code == 200, resp_t.text

    students = client.get("/api/students").json()
    codes = {s["code"]: s["source"] for s in students["students"]}
    assert codes["NEW001"] == "AUTHORED"
    teachers = client.get("/api/teachers").json()
    tcodes = {t["code"]: t["source"] for t in teachers["teachers"]}
    assert tcodes["NEW T"] == "AUTHORED"


def test_duplicate_student_code_409(client):
    client.post("/api/authored-students", json={"code": "NEW002", "last_name": "First", "entered_by": "test"})
    resp = client.post("/api/authored-students", json={"code": "NEW002", "last_name": "Second", "entered_by": "test"})
    assert resp.status_code == 409


def test_empty_code_rejected(client):
    resp = client.post("/api/authored-students", json={"code": "   ", "last_name": "X", "entered_by": "test"})
    # FastAPI/Pydantic strip nothing - an all-whitespace code still passes
    # min_length; the ValueError path is a 409 via HTTPException detail.
    assert resp.status_code in (409, 422)


def test_roll_class_must_exist(client):
    resp = client.post(
        "/api/authored-students",
        json={"code": "NEW003", "last_name": "Y", "roll_class_code": "NOPE", "entered_by": "test"},
    )
    assert resp.status_code == 409
    assert "roll class" in resp.json()["detail"]


def test_invalid_staff_category_rejected(client):
    resp = client.post(
        "/api/authored-teachers",
        json={"code": "NEWX", "staff_category": "SOMETHING", "entered_by": "test"},
    )
    assert resp.status_code in (409, 422)


def test_exported_code_conflicts(client):
    # synthetic DB already has student 100001 and teacher T1.
    resp = client.post("/api/authored-students", json={"code": "100001", "last_name": "Dupe", "entered_by": "test"})
    assert resp.status_code == 409
    resp_t = client.post("/api/authored-teachers", json={"code": "T1", "last_name": "Dupe", "entered_by": "test"})
    assert resp_t.status_code == 409


def test_update_missing_authored_student_404(client):
    resp = client.post("/api/authored-students/GHOST", json={"first_name": "Nobody", "updated_by": "test"})
    assert resp.status_code == 404


# --- resync interaction -----------------------------------------------------

def test_remove_superseded_authored_people():
    """After a re-ingest, authored rows whose code the export now carries
    are retired; the rest survive; the audit trail records the handover.
    Rows are inserted directly (not via add_authored_*) because the
    export-collision guard - correctly - refuses to create a row whose
    code the export already carries; this test simulates the legitimate
    pre-existing case of "authored first, export gained it later"."""
    conn = build_synthetic_db()  # student 100001 + teacher T1 already exist
    import datetime as dt

    now = dt.datetime.now(dt.UTC).isoformat()
    conn.execute(
        "INSERT INTO authored_student (code, last_name, created_at, updated_at, updated_by) "
        "VALUES ('100001', 'Authored Dup', ?, ?, 'test')",
        (now, now),
    )
    conn.execute(
        "INSERT INTO authored_teacher (code, last_name, faculty_codes_json, created_at, updated_at, updated_by) "
        "VALUES ('T1', 'Authored Dup T', '[]', ?, ?, 'test')",
        (now, now),
    )
    add_authored_student(conn, code="NEW100", last_name="Stays", entered_by="test")
    add_authored_teacher(conn, code="NEW T", last_name="Stays T", entered_by="test")

    result = remove_superseded_authored_people(conn)
    assert result == {"students": 1, "teachers": 1}
    assert conn.execute("SELECT 1 FROM authored_student WHERE code = 'NEW100'").fetchone()
    assert conn.execute("SELECT 1 FROM authored_student WHERE code = '100001'").fetchone() is None
    assert conn.execute("SELECT 1 FROM authored_teacher WHERE code = 'NEW T'").fetchone()
    assert conn.execute("SELECT 1 FROM authored_teacher WHERE code = 'T1'").fetchone() is None

    events = conn.execute(
        "SELECT event_type FROM audit_event WHERE event_type LIKE 'authored_%superseded%'"
    ).fetchall()
    assert len(events) == 2


def test_authored_survives_reingest():
    """The feature's whole point: a real resync_source_tables() pass must
    leave authored people in place."""
    from app.db.resync import resync_source_tables

    conn = build_synthetic_db()
    add_authored_student(conn, code="NEW200", last_name="Survivor", entered_by="test")
    add_authored_teacher(conn, code="NEW TT", last_name="Survivor T", entered_by="test")

    def ingest_fn():
        # Rebuild what the delete pass wiped - the minimum the source
        # tables need so a real parser run isn't required here.
        conn.execute("INSERT INTO day (id, code, day_no, week_label) VALUES (1, 'Day 1 A', 1, 'A')")

    resync_source_tables(conn, ingest_fn)

    assert conn.execute("SELECT 1 FROM authored_student WHERE code = 'NEW200'").fetchone()
    assert conn.execute("SELECT 1 FROM authored_teacher WHERE code = 'NEW TT'").fetchone()


def test_users_can_update_authored_teacher(client):
    client.post(
        "/api/authored-teachers",
        json={"code": "NEW TT4", "last_name": "Editable", "entered_by": "test"},
    )
    resp = client.post(
        "/api/authored-teachers/NEW TT4",
        json={"last_name": "Renamed", "updated_by": "test"},
    )
    assert resp.status_code == 200
    teacher = next(
        t for t in client.get("/api/teachers").json()["teachers"] if t["code"] == "NEW TT4"
    )
    assert teacher["last_name"] == "Renamed"


def test_update_authored_student_direct(db_path):
    # check_same_thread=False: TestClient runs the dependency in a worker
    # thread - same rationale app/api/deps.py's get_db documents.
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    add_authored_student(conn, code="NEW500", last_name="Before", entered_by="test")
    update_authored_student(conn, "NEW500", last_name="After", updated_by="test")
    row = conn.execute("SELECT last_name FROM authored_student WHERE code = 'NEW500'").fetchone()
    assert row["last_name"] == "After"
    conn.close()
