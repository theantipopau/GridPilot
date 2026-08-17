"""Tests app/api/staffing_policy.py - industrial agreement entry/review
and release reconciliation (docs/roadmap-v2.md 2.1/2.3). No real EA
figures anywhere here - see tests/synthetic.py and schema.sql's
industrial_agreement comment for why GridPilot never seeds real numbers
itself."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

import app.api.deps as deps
from app.api.main import app
from tests.synthetic import build_synthetic_db


@pytest.fixture
def db_path(tmp_path):
    conn = build_synthetic_db()
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


def test_new_agreement_is_unconfirmed_by_default(client):
    resp = client.post(
        "/api/agreements",
        json={"name": "Test EA 2023-2026", "effective_from": "2023-01-01", "created_by": "tester"},
    )
    assert resp.status_code == 200, resp.text
    agreement_id = resp.json()["id"]

    listed = client.get("/api/agreements").json()["agreements"]
    agreement = next(a for a in listed if a["id"] == agreement_id)
    assert agreement["confirmed_by"] is None
    assert agreement["confirmed_at"] is None
    assert agreement["load_rules"] == []
    assert agreement["leadership_bands"] == []


def test_confirming_an_agreement_sets_confirmed_fields(client):
    agreement_id = client.post(
        "/api/agreements",
        json={"name": "Test EA", "effective_from": "2023-01-01", "created_by": "tester"},
    ).json()["id"]

    resp = client.post(f"/api/agreements/{agreement_id}/confirm", json={"confirmed_by": "hr-rep"})
    assert resp.status_code == 200, resp.text

    agreement = client.get("/api/agreements").json()["agreements"][0]
    assert agreement["confirmed_by"] == "hr-rep"
    assert agreement["confirmed_at"] is not None


def test_confirming_unknown_agreement_is_404(client):
    resp = client.post("/api/agreements/999/confirm", json={"confirmed_by": "hr-rep"})
    assert resp.status_code == 404


def test_add_load_rule_and_reject_duplicate_sector(client):
    agreement_id = client.post(
        "/api/agreements", json={"name": "Test EA", "effective_from": "2023-01-01", "created_by": "tester"}
    ).json()["id"]

    add = client.post(
        f"/api/agreements/{agreement_id}/load-rules",
        json={"sector": "SECONDARY", "ordinary_hours_per_week": 30.5, "max_contact_hours_per_week": 21.5},
    )
    assert add.status_code == 200, add.text

    dup = client.post(
        f"/api/agreements/{agreement_id}/load-rules",
        json={"sector": "SECONDARY", "ordinary_hours_per_week": 31, "max_contact_hours_per_week": 21.5},
    )
    assert dup.status_code == 400

    agreement = client.get("/api/agreements").json()["agreements"][0]
    assert len(agreement["load_rules"]) == 1
    assert agreement["load_rules"][0]["max_contact_hours_per_week"] == 21.5


def test_add_leadership_band_rejects_bad_tier(client):
    agreement_id = client.post(
        "/api/agreements", json={"name": "Test EA", "effective_from": "2023-01-01", "created_by": "tester"}
    ).json()["id"]

    bad = client.post(
        f"/api/agreements/{agreement_id}/leadership-bands",
        json={"tier": "JUNIOR", "enrolment_min": 0, "enrolment_max": 100},
    )
    assert bad.status_code == 400

    good = client.post(
        f"/api/agreements/{agreement_id}/leadership-bands",
        json={"tier": "MIDDLE", "enrolment_min": 551, "enrolment_max": 600, "units": 66, "hours_per_year": 652},
    )
    assert good.status_code == 200, good.text


def test_enrolment_declaration_is_upserted_by_year(client):
    first = client.post(
        "/api/enrolment-declarations",
        json={"planning_year": "2026", "official_enrolment": 550, "entered_by": "admin"},
    )
    assert first.status_code == 200, first.text

    client.post(
        "/api/enrolment-declarations",
        json={"planning_year": "2026", "official_enrolment": 560, "entered_by": "admin"},
    )

    declarations = client.get("/api/enrolment-declarations").json()["declarations"]
    assert len(declarations) == 1
    assert declarations[0]["official_enrolment"] == 560


def test_reconciliation_with_no_confirmed_agreement_reports_none(client):
    resp = client.get("/api/staffing-policy/reconciliation")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["middle_pool"]["agreement_name"] is None
    assert body["middle_pool"]["units"] is None
    assert body["total_allocated_minutes_per_cycle"] == 0


def test_reconciliation_resolves_the_matching_band_once_confirmed(client):
    agreement_id = client.post(
        "/api/agreements", json={"name": "Test EA", "effective_from": "2023-01-01", "created_by": "tester"}
    ).json()["id"]
    client.post(f"/api/agreements/{agreement_id}/confirm", json={"confirmed_by": "hr-rep"})
    client.post(
        f"/api/agreements/{agreement_id}/leadership-bands",
        json={"tier": "MIDDLE", "enrolment_min": 551, "enrolment_max": 600, "units": 66, "hours_per_year": 652},
    )
    client.post(
        "/api/enrolment-declarations",
        json={"planning_year": "2026", "official_enrolment": 560, "entered_by": "admin"},
    )

    resp = client.get("/api/staffing-policy/reconciliation?planning_year=2026")
    body = resp.json()
    assert body["middle_pool"]["agreement_name"] == "Test EA"
    assert body["middle_pool"]["enrolment"] == 560
    assert body["middle_pool"]["units"] == 66
    assert body["middle_pool"]["hours_per_year"] == 652


def test_reconciliation_reports_allocated_release_from_role_assignments(client):
    role_id = client.post(
        "/api/roles", json={"name": "Head of Department", "release_minutes_per_cycle": 240}
    ).json()["id"]
    client.post("/api/teachers/T1/role", json={"staff_role_id": role_id, "assigned_by": "tester"})

    resp = client.get("/api/staffing-policy/reconciliation")
    body = resp.json()
    assert body["total_allocated_minutes_per_cycle"] == 240
    assert body["allocated"] == [{"teacher_code": "T1", "role_name": "Head of Department", "release_minutes_per_cycle": 240}]
