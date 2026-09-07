"""Tests for GET /blocking-demand (app/analysis/blocking_demand.py) -
roadmap-v3 §4.1/§12.4's Phase 1 structural analysis of the .sfx
subject-selection export: subject-pair impossibility, per-line demand
pressure, and under-subscribed classes, all restricted to sfx_class rows
that resolve to a real LESSON entry (see the module docstring for why -
unfiltered, pastoral/house groups like Fratelli/Registration reuse class
codes across roll classes and produce nonsense "over capacity" noise)."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

import app.api.deps as deps
from app.api.main import app
from tests.synthetic import add_lesson, build_synthetic_db


@pytest.fixture
def db_path(tmp_path):
    conn = build_synthetic_db()
    conn.execute("INSERT INTO ingest_run (id, started_at) VALUES (1, 'test')")
    conn.execute(
        "INSERT INTO sfx_file (id, ingest_run_id, file_name) VALUES (1, 1, 'Test.sfx')"
    )

    conn.execute("INSERT INTO sfx_line (id, sfx_file_id, code, name, subgrid) VALUES (1, 1, 'ELE1', 'ELE1', 1)")
    conn.execute("INSERT INTO sfx_line (id, sfx_file_id, code, name, subgrid) VALUES (2, 1, 'ELE2', 'ELE2', 1)")

    for i, (source_code, class_code) in enumerate(
        [("DEMSUBA", "SUBA1"), ("DEMSUBB", "SUBB1"), ("DEMSUBC", "SUBC1"), ("DEMSUBD", "SUBD1")], start=3
    ):
        conn.execute(
            "INSERT INTO subject (id, source_code, name) VALUES (?, ?, ?)", (i, source_code, source_code)
        )
        conn.execute(
            "INSERT INTO class_name (id, code, name, subject_id) VALUES (?, ?, ?, ?)",
            (i, class_code, source_code, i),
        )

    # A second LESSON-linked instance of SUBD on line 2, so the "spans two
    # lines" case is genuinely LESSON-linked on both sides, not excluded
    # from the impossibility matrix merely by falling out of the LESSON filter.
    conn.execute(
        "INSERT INTO class_name (id, code, name, subject_id) VALUES (8, 'SUBD2', 'DEMSUBD', 6)"
    )

    for sid in [*range(101, 103), *range(111, 119), *range(121, 125), *range(131, 137), *range(141, 147), *range(201, 206)]:
        conn.execute(
            "INSERT INTO student (id, code, first_name, last_name, roll_class_id) VALUES (?, ?, 'Test', 'Student', 1)",
            (sid, str(sid)),
        )

    # HOUSEX: a pastoral/house group whose only timetable presence is
    # REGISTRATION, not LESSON - proves the filter excludes it even though
    # it has a max_class_size and enrolment that would otherwise read as
    # wildly over capacity.
    conn.execute("INSERT INTO subject (id, source_code, name) VALUES (7, 'HOUSEX', 'HOUSEX')")
    conn.execute("INSERT INTO class_name (id, code, name, subject_id) VALUES (7, 'HOUSEX1', 'HOUSEX', 7)")
    conn.execute(
        "INSERT INTO timetable_entry (source_ref, day_id, period_id, roll_class_id, class_name_id, entry_type) "
        "VALUES ('test', 1, 1, 1, 7, 'REGISTRATION')"
    )
    for sid in range(201, 206):
        conn.execute("INSERT INTO enrolment (student_id, class_name_id, source) VALUES (?, 7, 'test')", (sid,))

    # SUBA and SUBB both confined to line 1 alone - an impossible pair.
    conn.execute(
        "INSERT INTO sfx_class (sfx_file_id, class_code, subject_code, roll_class_code, max_class_size, sfx_line_id) "
        "VALUES (1, 'SUBA1', 'SUBA', '7A', 10, 1)"
    )
    conn.execute(
        "INSERT INTO sfx_class (sfx_file_id, class_code, subject_code, roll_class_code, max_class_size, sfx_line_id) "
        "VALUES (1, 'SUBB1', 'SUBB', '7B', 10, 1)"
    )
    # SUBC confined to line 2 alone - no partner there, so no pair.
    conn.execute(
        "INSERT INTO sfx_class (sfx_file_id, class_code, subject_code, roll_class_code, max_class_size, sfx_line_id) "
        "VALUES (1, 'SUBC1', 'SUBC', '7A', 4, 2)"
    )
    # SUBD spans both lines - never a singleton, excluded from the matrix.
    conn.execute(
        "INSERT INTO sfx_class (sfx_file_id, class_code, subject_code, roll_class_code, max_class_size, sfx_line_id) "
        "VALUES (1, 'SUBD1', 'SUBD', '7A', 10, 1)"
    )
    conn.execute(
        "INSERT INTO sfx_class (sfx_file_id, class_code, subject_code, roll_class_code, max_class_size, sfx_line_id) "
        "VALUES (1, 'SUBD2', 'SUBD', '7A', 10, 2)"
    )
    # A duplicate class_code on the REGISTRATION side only, to confirm the
    # LESSON filter (not just a class_code lookup) is what excludes HOUSEX.
    conn.execute(
        "INSERT INTO sfx_class (sfx_file_id, class_code, subject_code, roll_class_code, max_class_size, sfx_line_id) "
        "VALUES (1, 'HOUSEX1', 'HOUSEX', '7A', 2, 1)"
    )

    add_lesson(conn, day_id=1, period_id=1, roll_class_id=1, class_name_id=3, teacher_id=1, room_id=1)  # SUBA1
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=4, teacher_id=2, room_id=2)  # SUBB1
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=1, class_name_id=5, teacher_id=1, room_id=1)  # SUBC1
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=1, class_name_id=6, teacher_id=2, room_id=2)  # SUBD1
    add_lesson(conn, day_id=2, period_id=3, roll_class_id=1, class_name_id=8, teacher_id=1, room_id=1)  # SUBD2

    # SUBA1: 2 of 10 enrolled (under half). SUBB1: 8 of 10 (not under half).
    # SUBC1: 4 of 4 (full, never "over"). SUBD1/SUBD2: 6 of 10 each (not
    # under half) - SUBD only exists to prove a multi-line subject is
    # excluded from the impossibility matrix, not to also show up here.
    for sid in [101, 102]:
        conn.execute("INSERT INTO enrolment (student_id, class_name_id, source) VALUES (?, 3, 'test')", (sid,))
    for sid in range(111, 119):
        conn.execute("INSERT INTO enrolment (student_id, class_name_id, source) VALUES (?, 4, 'test')", (sid,))
    for sid in range(121, 125):
        conn.execute("INSERT INTO enrolment (student_id, class_name_id, source) VALUES (?, 5, 'test')", (sid,))
    for sid in range(131, 137):
        conn.execute("INSERT INTO enrolment (student_id, class_name_id, source) VALUES (?, 6, 'test')", (sid,))
    for sid in range(141, 147):
        conn.execute("INSERT INTO enrolment (student_id, class_name_id, source) VALUES (?, 8, 'test')", (sid,))

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


def test_impossible_subject_pairs_from_singleton_lines(client):
    resp = client.get("/api/blocking-demand")
    assert resp.status_code == 200, resp.text
    pairs = resp.json()["impossible_subject_pairs"]
    assert pairs == [
        {"sfx_line_id": 1, "line_code": "ELE1", "line_name": "ELE1", "subjects": ["SUBA", "SUBB"]}
    ]


def test_line_pressure_is_enrolled_over_capacity(client):
    resp = client.get("/api/blocking-demand")
    lines = {l["sfx_line_id"]: l for l in resp.json()["lines"]}
    # Line 1: SUBA1 (max 10, enr 2) + SUBB1 (max 10, enr 8) + SUBD1 (max 10, enr 6) -> 16/30.
    assert lines[1]["total_capacity"] == 30
    assert lines[1]["total_enrolled"] == 16
    assert lines[1]["pressure"] == pytest.approx(16 / 30, abs=1e-3)
    # Line 2: SUBC1 (max 4, enr 4) + SUBD2 (max 10, enr 6) -> 10/14.
    assert lines[2]["total_capacity"] == 14
    assert lines[2]["total_enrolled"] == 10
    assert lines[2]["pressure"] == pytest.approx(10 / 14, abs=1e-3)


def test_under_subscribed_classes_below_half_capacity(client):
    resp = client.get("/api/blocking-demand")
    codes = {c["class_code"] for c in resp.json()["under_subscribed_classes"]}
    assert codes == {"SUBA1"}


def test_registration_only_class_excluded_despite_shared_class_code(client):
    resp = client.get("/api/blocking-demand")
    body = resp.json()
    all_codes = {c["class_code"] for c in body["under_subscribed_classes"]}
    all_codes |= {s for g in body["impossible_subject_pairs"] for s in g["subjects"]}
    assert "HOUSEX1" not in all_codes
    assert "HOUSEX" not in all_codes


def test_no_sfx_data_returns_empty(client, db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM sfx_class")
    conn.commit()
    conn.close()

    resp = client.get("/api/blocking-demand")
    assert resp.status_code == 200
    assert resp.json() == {"impossible_subject_pairs": [], "lines": [], "under_subscribed_classes": []}
