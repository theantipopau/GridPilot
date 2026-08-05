"""Tests the browser upload/import flow (app/api/ingest.py) through the
real FastAPI app via TestClient - the first HTTP-layer test in this
codebase, added because multipart file handling (extension checks, safe
filenames, size limits) is genuinely new integration surface that the
existing module-level tests don't exercise. No real school data - tiny
synthetic .tfx/.sfx fixtures built inline (every section is optional per
docs/data-formats.md, so an empty-but-valid file is enough)."""

import json

import pytest
from fastapi.testclient import TestClient

import app.analysis.run as analysis_run
import app.api.deps as deps
import app.api.ingest as ingest_api
import app.ingest.run as ingest_run
from app.api.main import app

MINIMAL_TFX = {
    "File ID": "Timetabling Solutions X TD 10.1.1.86",
    "Days": [], "Periods": [], "YearLevels": [], "Rooms": [], "Teachers": [],
    "Faculties": [], "RollClasses": [], "ClassNames": [], "ClassGroups": [],
    "Timetable": [], "Students": [],
}
MINIMAL_SFX = {"File ID": "Timetabling Solutions X SO 10.1.1.86", "Students": []}


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(ingest_api, "DB_PATH", db_path)
    monkeypatch.setattr(ingest_api, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(ingest_run, "DB_PATH", db_path)
    monkeypatch.setattr(analysis_run, "DB_PATH", db_path)
    monkeypatch.setattr(deps, "DB_PATH", db_path)

    # Point every CSV/eMinerva cross-validation path at a location that
    # doesn't exist, so these tests exercise ingestion of the uploaded
    # .tfx/.sfx in isolation - matching what a real standalone browser
    # upload looks like (see app/ingest/csv_validate.py's "skip, don't
    # fail" behaviour for a missing file) - rather than accidentally
    # cross-validating against whatever real export happens to be sitting
    # under this machine's configured Timetabler Export/ folder.
    missing = tmp_path / "no-such-cross-validation-file"
    for name in ("ROOM_DETAILS_CSV", "PERIOD_DETAILS_CSV", "TEACHER_DETAILS_CSV",
                 "ROLL_CLASS_DETAILS_CSV", "STUDENT_DETAILS_CSV", "MASTER_TIMETABLE_CYCLE_CSV",
                 "EMINERVA_SCOURSE_PATH"):
        monkeypatch.setattr(ingest_run, name, missing)

    return TestClient(app)


def test_status_reports_no_data_before_anything_is_imported(client):
    resp = client.get("/api/ingest/status")
    assert resp.status_code == 200
    assert resp.json() == {"has_data": False, "last_ingest": None}


def test_upload_tfx_alone_ingests_successfully(client):
    resp = client.post(
        "/api/ingest/upload",
        files=[("tfx_file", ("Term 3.tfx", json.dumps(MINIMAL_TFX), "application/json"))],
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["tfx_filename"] == "Term 3.tfx"
    assert body["sfx_filenames"] == []
    assert body["counts"]["day"] == 0  # empty fixture, but ingest completed without error
    assert "findings_total" in body["analysis"]

    status = client.get("/api/ingest/status").json()
    assert status["has_data"] is False  # no Timetable[] rows in this fixture - correctly reported
    assert status["last_ingest"]["tfx_source_path"] is not None


def test_upload_tfx_and_sfx_together(client):
    resp = client.post(
        "/api/ingest/upload",
        files=[
            ("tfx_file", ("Term 3.tfx", json.dumps(MINIMAL_TFX), "application/json")),
            ("sfx_files", ("YR 7.sfx", json.dumps(MINIMAL_SFX), "application/json")),
            ("sfx_files", ("YR 8.sfx", json.dumps(MINIMAL_SFX), "application/json")),
        ],
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert sorted(body["sfx_filenames"]) == ["YR 7.sfx", "YR 8.sfx"]
    assert body["counts"]["sfx_file"] == 2


def test_non_tfx_file_is_rejected_with_a_clear_message(client):
    resp = client.post(
        "/api/ingest/upload",
        files=[("tfx_file", ("notes.txt", "just some text", "text/plain"))],
    )
    assert resp.status_code == 400
    assert ".tfx" in resp.json()["detail"]


def test_sfx_file_uploaded_as_the_tfx_slot_is_rejected_as_an_ingest_error(client):
    resp = client.post(
        "/api/ingest/upload",
        files=[("tfx_file", ("wrong.tfx", json.dumps(MINIMAL_SFX), "application/json"))],
    )
    assert resp.status_code == 400
    assert "Student Options" in resp.json()["detail"]


def test_reference_endpoint_before_any_import_is_a_clean_503_not_a_crash(client):
    """Regression test for a real bug found by manually exercising the
    onboarding flow: sqlite3.connect() silently creates an empty file at
    DB_PATH the moment ANY endpoint runs (including status), so a naive
    DB_PATH.exists() check for 'has data' breaks after the first request,
    and every other endpoint would otherwise 500 with a raw 'no such
    table' instead of a message the frontend can show meaningfully."""
    resp = client.get("/api/reference")
    assert resp.status_code == 503
    assert "Import" in resp.json()["detail"]


def test_status_still_reports_no_data_after_another_endpoint_has_touched_the_db(client):
    # Hitting a get_db()-backed endpoint first is exactly what silently
    # creates the empty sqlite file that broke a naive exists() check.
    client.get("/api/reference")
    resp = client.get("/api/ingest/status")
    assert resp.status_code == 200
    assert resp.json() == {"has_data": False, "last_ingest": None}


def test_status_and_reference_work_normally_after_a_real_import(client):
    upload = client.post(
        "/api/ingest/upload",
        files=[("tfx_file", ("Term 3.tfx", json.dumps(MINIMAL_TFX), "application/json"))],
    )
    assert upload.status_code == 200, upload.text

    assert client.get("/api/ingest/status").json()["has_data"] is False  # correct: fixture has no Timetable[] rows
    ref = client.get("/api/reference")
    assert ref.status_code == 200
    assert ref.json() == {"days": [], "periods": [], "rooms": [], "teachers": [], "roll_classes": [], "year_levels": []}


def test_status_reflects_a_successful_import(client):
    tfx_with_a_day = dict(MINIMAL_TFX, Days=[{"DayID": "d1", "Code": "Mon A"}])
    resp = client.post(
        "/api/ingest/upload",
        files=[("tfx_file", ("Term 3.tfx", json.dumps(tfx_with_a_day), "application/json"))],
    )
    assert resp.status_code == 200, resp.text

    status = client.get("/api/ingest/status").json()
    assert status["last_ingest"]["source_file_id"] == "Timetabling Solutions X TD 10.1.1.86"
