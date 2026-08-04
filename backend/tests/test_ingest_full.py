"""Full-pipeline ingest test: .tfx + CSV cross-validation + eMinerva
enrolment reconciliation, against the real export data. Only asserts on
aggregate counts and discrepancy structure - never on individual names."""

import hashlib
import re
import sqlite3

import pytest

from app.config import TFX_PATH
from app.ingest.run import run_full_ingest, table_counts

pytestmark = pytest.mark.skipif(not TFX_PATH.exists(), reason="real export data not present")

KNOWN_BENIGN_CHECKS = {
    "room_override_unresolved",
    "timetable_unassigned_entries_excluded_from_csv",
}


@pytest.fixture(scope="module")
def counts_and_db(tmp_path_factory) -> tuple[dict, sqlite3.Connection]:
    db_path = tmp_path_factory.mktemp("ingest") / "full.sqlite3"
    counts = run_full_ingest(db_path=db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    yield counts, conn
    conn.close()


def test_table_counts(counts_and_db):
    counts, _ = counts_and_db
    assert counts["student"] == 560
    assert counts["teacher"] == 74
    assert counts["timetable_entry"] == 2181
    assert counts["enrolment"] > 6000


def test_ingest_run_records_source_hash_and_audit_event(counts_and_db):
    """The hash proves exactly which .tfx version everything downstream
    (findings, composite candidates) was analysed against."""
    _, conn = counts_and_db
    row = conn.execute("SELECT tfx_source_sha256 FROM ingest_run").fetchone()
    assert row["tfx_source_sha256"] is not None
    assert re.fullmatch(r"[0-9a-f]{64}", row["tfx_source_sha256"])
    assert row["tfx_source_sha256"] == hashlib.sha256(TFX_PATH.read_bytes()).hexdigest()

    audit_row = conn.execute(
        "SELECT summary FROM audit_event WHERE event_type = 'ingest_completed'"
    ).fetchone()
    assert audit_row is not None


def test_no_unexplained_master_timetable_mismatches(counts_and_db):
    """timetable_row_only_in_csv / timetable_row_only_in_tfx_unexplained
    would mean the .tfx and CSV exports disagree about the grid in a way
    we can't explain - that must not happen against the current export."""
    _, conn = counts_and_db
    bad = conn.execute(
        "SELECT check_name, description FROM ingest_discrepancy "
        "WHERE check_name IN ('timetable_row_only_in_csv', 'timetable_row_only_in_tfx_unexplained')"
    ).fetchall()
    assert bad == [], bad


def test_no_enrolment_mismatches_between_tfx_and_eminerva(counts_and_db):
    _, conn = counts_and_db
    bad = conn.execute(
        "SELECT check_name FROM ingest_discrepancy "
        "WHERE check_name IN ('enrolment_only_in_tfx', 'enrolment_only_in_eminerva')"
    ).fetchall()
    assert bad == [], bad


def test_all_discrepancies_are_known_benign_or_info(counts_and_db):
    """Any discrepancy check_name not already known and accounted for
    should fail the test loudly rather than pass unnoticed - this is the
    'fail loudly on any discrepancy' requirement applied to the test
    suite itself."""
    _, conn = counts_and_db
    rows = conn.execute(
        "SELECT check_name, severity FROM ingest_discrepancy WHERE severity = 'error'"
    ).fetchall()
    assert rows == [], f"Unexpected error-level discrepancies: {rows}"

    unexpected = conn.execute(
        "SELECT DISTINCT check_name FROM ingest_discrepancy "
        "WHERE severity = 'warning' AND check_name NOT IN ({})".format(
            ",".join("?" for _ in KNOWN_BENIGN_CHECKS)
        ),
        tuple(KNOWN_BENIGN_CHECKS),
    ).fetchall()
    assert unexpected == [], f"Unexpected warning-level discrepancy types: {unexpected}"
