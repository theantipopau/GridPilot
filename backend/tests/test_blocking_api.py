"""Tests GET /blocking-lines (app/api/blocking.py) - the read-only
blocking-pattern view built from blocking_line/blocking_line_class_group
(parsed from the .tfx's MRCGs, see app/ingest/tfx_parser.py)."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

import app.api.deps as deps
from app.api.main import app
from tests.synthetic import build_synthetic_db


@pytest.fixture
def db_path(tmp_path):
    conn = build_synthetic_db()

    # Two class groups (7A and 7B) both offering CLASSA - a "locked" line.
    conn.execute(
        "INSERT INTO class_group (id, source_guid, roll_class_id, periods_per_cycle) VALUES (1, 'cg1', 1, 4)"
    )
    conn.execute(
        "INSERT INTO class_group_course (source_guid, class_group_id, class_name_id, teacher_id, room_id) "
        "VALUES ('c1', 1, 1, 1, 1)"
    )
    conn.execute(
        "INSERT INTO class_group (id, source_guid, roll_class_id, periods_per_cycle) VALUES (2, 'cg2', 2, 4)"
    )
    conn.execute(
        "INSERT INTO class_group_course (source_guid, class_group_id, class_name_id, teacher_id, room_id) "
        "VALUES ('c2', 2, 2, 2, 2)"
    )

    conn.execute(
        "INSERT INTO blocking_line (id, source_guid, default_code, code, name) "
        "VALUES (1, 'mrcg1', '7A B', 'ENG', 'English')"
    )
    conn.execute("INSERT INTO blocking_line_class_group (blocking_line_id, class_group_id) VALUES (1, 1)")
    conn.execute("INSERT INTO blocking_line_class_group (blocking_line_id, class_group_id) VALUES (1, 2)")
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


def test_blocking_lines_grouped_by_default_code_prefix(client):
    resp = client.get("/api/blocking-lines")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["groups"] == [
        {
            "group": "7A",
            "lines": [
                {
                    "id": 1,
                    "default_code": "7A B",
                    "line": "B",
                    "code": "ENG",
                    "name": "English",
                    "class_groups": [
                        {
                            "roll_class_code": "7A",
                            "periods_per_cycle": 4,
                            "courses": [
                                {"class_name_code": "CLASSA", "teacher_code": "T1", "room_code": "R1"}
                            ],
                        },
                        {
                            "roll_class_code": "7B",
                            "periods_per_cycle": 4,
                            "courses": [
                                {"class_name_code": "CLASSB", "teacher_code": "T2", "room_code": "R2"}
                            ],
                        },
                    ],
                }
            ],
        }
    ]


def test_no_blocking_lines_returns_empty_groups(client, db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM blocking_line_class_group")
    conn.execute("DELETE FROM blocking_line")
    conn.commit()
    conn.close()

    resp = client.get("/api/blocking-lines")
    assert resp.status_code == 200
    assert resp.json() == {"groups": []}
