"""Tests app/api/dashboard.py against a synthetic fixture via TestClient -
every number it returns must be a real query result, never a placeholder,
so these assert exact expected counts rather than just "some number"."""

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
    add_lesson(conn, day_id=1, period_id=1, roll_class_id=2, class_name_id=2, teacher_id=1, room_id=2)
    conn.commit()

    path = tmp_path / "test.sqlite3"
    # Persist the in-memory synthetic db to a real file the FastAPI
    # dependency can open, matching how the app always connects (a real
    # sqlite3.connect(DB_PATH), not the same in-memory handle).
    file_conn = sqlite3.connect(path)
    conn.backup(file_conn)
    file_conn.close()
    conn.close()
    return path


@pytest.fixture
def client(db_path, monkeypatch):
    monkeypatch.setattr(deps, "DB_PATH", db_path)
    return TestClient(app)


def test_dashboard_counts_are_real_query_results(client):
    resp = client.get("/api/dashboard")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["counts"]["teachers"] == 2
    assert body["counts"]["rooms"] == 3
    assert body["counts"]["roll_classes"] == 2
    assert body["counts"]["students"] == 1
    assert body["counts"]["lessons"] == 2
    assert body["counts"]["days"] == 3

    assert body["findings_by_severity"] == {"critical": 0, "warning": 0, "info": 0}
    assert body["composites_pending"] == 0
    assert body["change_sets_draft"] == 0
    # 2 lessons occupy 2 distinct room-slots - just assert it's a real
    # computed percentage, not None and not an implausible value.
    assert body["room_utilisation_pct"] is not None
    assert 0 < body["room_utilisation_pct"] <= 100


def test_dashboard_reflects_open_findings_pending_composites_and_draft_change_sets(client, db_path):
    # `client` isn't referenced directly below, but requesting it applies
    # the DB_PATH monkeypatch this test's own request also depends on.
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO finding (dedupe_key, rule_id, severity, title, entity_refs_json, slot_refs_json, "
        "evidence_json, status, first_seen_at, computed_at) VALUES "
        "('k1', 'rule', 'critical', 'Test finding', '[]', '[]', '{}', 'OPEN', 'test', 'test')"
    )
    conn.execute(
        "INSERT INTO composite_group (teacher_id, room_id, review_status, slot_count, detected_at) "
        "VALUES (1, 1, 'PENDING', 2, 'test')"
    )
    conn.execute(
        "INSERT INTO change_set (name, validation_status, approval_status, created_at, created_by) "
        "VALUES ('Draft CS', 'NOT_VALIDATED', 'DRAFT', 'test', 'tester')"
    )
    conn.commit()
    conn.close()

    resp = client.get("/api/dashboard")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["findings_by_severity"]["critical"] == 1
    assert body["composites_pending"] == 1
    assert body["change_sets_draft"] == 1
